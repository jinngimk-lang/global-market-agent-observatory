from __future__ import annotations

from decimal import Decimal
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.models import OrderIntent, PortfolioSnapshot, Side
from app.strategy.base import StrategyAction, StrategySignal


class PortfolioPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    risk_fraction_per_trade: Decimal = Decimal("0.01")
    max_order_notional: Decimal = Decimal("5000")
    max_group_exposure: Decimal = Decimal("25000")
    reduce_fraction: Decimal = Decimal("0.5")
    symbol_groups: dict[str, str] = Field(default_factory=dict)

    @field_validator("risk_fraction_per_trade", "reduce_fraction")
    @classmethod
    def validate_fraction(cls, value: Decimal) -> Decimal:
        if value <= 0 or value > 1:
            raise ValueError("fraction must be in (0, 1]")
        return value

    @field_validator("max_order_notional", "max_group_exposure")
    @classmethod
    def validate_positive_limit(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("exposure limits must be positive")
        return value

    @field_validator("symbol_groups")
    @classmethod
    def normalize_groups(cls, values: dict[str, str]) -> dict[str, str]:
        return {symbol.strip().upper(): group.strip() for symbol, group in values.items()}


class AllocationDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    signal: StrategySignal
    intent: OrderIntent | None = None
    code: str
    message: str
    risk_budget: Decimal = Decimal("0")
    requested_notional: Decimal = Decimal("0")


class PortfolioAllocator:
    def __init__(self, policy: PortfolioPolicy) -> None:
        self._policy = policy

    @property
    def policy(self) -> PortfolioPolicy:
        return self._policy

    def allocate(
        self,
        signals: list[StrategySignal],
        portfolio: PortfolioSnapshot,
    ) -> list[AllocationDecision]:
        selected: dict[str, StrategySignal] = {}
        for item in signals:
            current = selected.get(item.symbol)
            if current is None or self._selection_key(item) > self._selection_key(current):
                selected[item.symbol] = item
        return [self.allocate_signal(selected[symbol], portfolio) for symbol in sorted(selected)]

    def allocate_signal(
        self,
        signal: StrategySignal,
        portfolio: PortfolioSnapshot,
    ) -> AllocationDecision:
        if signal.action is StrategyAction.HOLD:
            return self._no_intent(signal, "hold", "Strategy requested no portfolio change.")

        if signal.action in {StrategyAction.REDUCE, StrategyAction.EXIT}:
            return self._allocate_reduction(signal, portfolio)

        if signal.action is StrategyAction.BUY:
            return self._allocate_long_entry(signal, portfolio)

        return self._no_intent(
            signal,
            "unsupported_action",
            f"Action {signal.action.value} is not enabled by the long-only allocator.",
        )

    def _allocate_long_entry(
        self,
        signal: StrategySignal,
        portfolio: PortfolioSnapshot,
    ) -> AllocationDecision:
        entry = signal.entry_price
        invalidation = signal.invalidation_price
        if entry is None or entry <= 0:
            return self._no_intent(signal, "missing_entry_price", "A positive entry price is required.")
        if invalidation is None:
            return self._no_intent(
                signal,
                "missing_invalidation",
                "A long entry requires an explicit invalidation price.",
            )
        if invalidation <= 0 or invalidation >= entry:
            return self._no_intent(
                signal,
                "invalid_invalidation",
                "Long invalidation must be positive and below the entry price.",
            )

        risk_budget = max(portfolio.equity, Decimal("0")) * self._policy.risk_fraction_per_trade
        risk_per_share = entry - invalidation
        if risk_budget <= 0 or risk_per_share <= 0:
            return self._no_intent(signal, "no_risk_budget", "No positive risk budget is available.")

        risk_quantity = risk_budget / risk_per_share
        notional_cap = min(self._policy.max_order_notional, max(portfolio.cash, Decimal("0")))
        quantity_cap = notional_cap / entry
        quantity = min(risk_quantity, quantity_cap)
        code = "allocated"

        group = self._policy.symbol_groups.get(signal.symbol)
        if group is not None:
            group_exposure = self._group_exposure(portfolio, group)
            remaining = self._policy.max_group_exposure - group_exposure
            if remaining <= 0:
                return AllocationDecision(
                    signal=signal,
                    code="group_exposure_limit",
                    message=f"No remaining exposure capacity in group {group}.",
                    risk_budget=risk_budget,
                )
            group_quantity_cap = remaining / entry
            if group_quantity_cap < quantity:
                quantity = group_quantity_cap
                code = "resized_group_exposure"

        if quantity <= 0:
            return AllocationDecision(
                signal=signal,
                code="no_allocatable_quantity",
                message="Risk and exposure limits leave no allocatable quantity.",
                risk_budget=risk_budget,
            )

        requested_notional = quantity * entry
        intent = OrderIntent(
            client_order_id=self._client_order_id(signal),
            symbol=signal.symbol,
            side=Side.BUY,
            quantity=quantity,
            reference_price=entry,
        )
        return AllocationDecision(
            signal=signal,
            intent=intent,
            code=code,
            message="Signal converted to a risk-budgeted long order intent.",
            risk_budget=risk_budget,
            requested_notional=requested_notional,
        )

    def _allocate_reduction(
        self,
        signal: StrategySignal,
        portfolio: PortfolioSnapshot,
    ) -> AllocationDecision:
        position = next((p for p in portfolio.positions if p.symbol == signal.symbol), None)
        if position is None or position.quantity <= 0:
            return self._no_intent(
                signal,
                "no_long_position",
                "There is no long position to reduce or exit.",
            )
        quantity = (
            position.quantity
            if signal.action is StrategyAction.EXIT
            else position.quantity * self._policy.reduce_fraction
        )
        reference_price = signal.entry_price or position.market_price
        intent = OrderIntent(
            client_order_id=self._client_order_id(signal),
            symbol=signal.symbol,
            side=Side.SELL,
            quantity=quantity,
            reference_price=reference_price,
        )
        return AllocationDecision(
            signal=signal,
            intent=intent,
            code="allocated_exit" if signal.action is StrategyAction.EXIT else "allocated_reduce",
            message="Risk-reducing signal converted to a sell order intent.",
            requested_notional=quantity * reference_price,
        )

    def _group_exposure(self, portfolio: PortfolioSnapshot, group: str) -> Decimal:
        total = Decimal("0")
        for position in portfolio.positions:
            if self._policy.symbol_groups.get(position.symbol) == group:
                total += position.gross_value
        return total

    @staticmethod
    def _selection_key(signal: StrategySignal) -> tuple[int, Decimal, str]:
        priority = {
            StrategyAction.EXIT: 5,
            StrategyAction.REDUCE: 4,
            StrategyAction.SELL: 3,
            StrategyAction.BUY: 2,
            StrategyAction.HOLD: 1,
        }[signal.action]
        return priority, signal.confidence, signal.strategy_id

    @staticmethod
    def _client_order_id(signal: StrategySignal) -> str:
        material = "|".join(
            [
                signal.strategy_id,
                signal.version,
                signal.symbol,
                signal.action.value,
                signal.generated_at.isoformat(),
            ]
        )
        digest = sha256(material.encode("utf-8")).hexdigest()[:20]
        return f"auto-{signal.symbol.lower()}-{digest}"

    @staticmethod
    def _no_intent(signal: StrategySignal, code: str, message: str) -> AllocationDecision:
        return AllocationDecision(signal=signal, code=code, message=message)
