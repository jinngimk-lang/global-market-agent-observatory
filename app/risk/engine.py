from __future__ import annotations

from decimal import Decimal

from app.domain.models import (
    OrderIntent,
    PortfolioSnapshot,
    RiskContext,
    RiskDecision,
    RiskLimits,
    Side,
    TradingState,
)


class RiskEngine:
    def __init__(self, limits: RiskLimits) -> None:
        self._limits = limits

    @property
    def limits(self) -> RiskLimits:
        return self._limits

    def evaluate(
        self,
        intent: OrderIntent,
        portfolio: PortfolioSnapshot,
        context: RiskContext | None = None,
    ) -> RiskDecision:
        context = context or RiskContext()

        if context.trading_state is TradingState.HALTED:
            return self._reject("trading_halted", "Trading is halted.")

        if context.market_data_age_seconds > self._limits.market_data_max_age_seconds:
            return self._reject("stale_market_data", "Market data is too stale for new risk.")

        if context.account_state_age_seconds > self._limits.account_state_max_age_seconds:
            return self._reject("stale_account_state", "Account state is too stale for new risk.")

        if context.portfolio_drawdown >= self._limits.max_portfolio_drawdown:
            return self._reject(
                "portfolio_drawdown_lockout",
                "Portfolio drawdown limit has been reached.",
            )

        if intent.symbol not in self._limits.allowed_symbols:
            return self._reject("symbol_not_allowed", "Symbol is outside the configured allowlist.")

        if intent.quantity <= 0:
            return self._reject("invalid_quantity", "Quantity must be positive.")

        reference_price = intent.reference_price
        if reference_price is None or reference_price <= 0:
            return self._reject(
                "missing_reference_price",
                "A positive market reference price is required.",
            )

        if context.trading_state is TradingState.REDUCING and self._increases_exposure(
            intent, portfolio
        ):
            return self._reject(
                "reducing_only",
                "Trading state permits exposure reductions only.",
            )

        if portfolio.realized_pnl_today <= -self._limits.daily_loss_limit:
            return self._reject(
                "daily_loss_lockout",
                "Daily realized loss limit has been reached; trading is locked.",
            )

        order_notional = intent.quantity * reference_price
        if order_notional > self._limits.max_order_notional:
            return self._reject(
                "order_notional_limit",
                "Order notional exceeds the configured maximum.",
                order_notional=order_notional,
            )

        current_quantity = Decimal("0")
        other_exposure = Decimal("0")
        for position in portfolio.positions:
            if position.symbol == intent.symbol:
                current_quantity = position.quantity
            else:
                other_exposure += position.gross_value

        signed_quantity = intent.quantity if intent.side is Side.BUY else -intent.quantity
        projected_quantity = current_quantity + signed_quantity
        projected_symbol_exposure = abs(projected_quantity * reference_price)
        if projected_symbol_exposure > self._limits.max_symbol_exposure:
            return self._reject(
                "symbol_exposure_limit",
                "Projected symbol exposure exceeds the configured maximum.",
                order_notional=order_notional,
                projected_gross_exposure=other_exposure + projected_symbol_exposure,
            )

        projected_gross = other_exposure + projected_symbol_exposure
        if projected_gross > self._limits.max_gross_exposure:
            return self._reject(
                "gross_exposure_limit",
                "Projected gross exposure exceeds the configured maximum.",
                order_notional=order_notional,
                projected_gross_exposure=projected_gross,
            )

        if intent.side is Side.BUY and order_notional > portfolio.cash:
            return self._reject(
                "insufficient_cash",
                "Paper account cash is insufficient for the order.",
                order_notional=order_notional,
                projected_gross_exposure=projected_gross,
            )

        return RiskDecision(
            allowed=True,
            code="approved",
            message="Order passed deterministic risk checks.",
            order_notional=order_notional,
            projected_gross_exposure=projected_gross,
        )

    @staticmethod
    def _increases_exposure(intent: OrderIntent, portfolio: PortfolioSnapshot) -> bool:
        current_quantity = Decimal("0")
        for position in portfolio.positions:
            if position.symbol == intent.symbol:
                current_quantity = position.quantity
                break

        signed_quantity = intent.quantity if intent.side is Side.BUY else -intent.quantity
        projected_quantity = current_quantity + signed_quantity
        if current_quantity == 0:
            return projected_quantity != 0
        if projected_quantity == 0:
            return False
        if current_quantity * projected_quantity < 0:
            return True
        return abs(projected_quantity) >= abs(current_quantity)

    @staticmethod
    def _reject(
        code: str,
        message: str,
        *,
        order_notional: Decimal = Decimal("0"),
        projected_gross_exposure: Decimal = Decimal("0"),
    ) -> RiskDecision:
        return RiskDecision(
            allowed=False,
            code=code,
            message=message,
            order_notional=order_notional,
            projected_gross_exposure=projected_gross_exposure,
        )
