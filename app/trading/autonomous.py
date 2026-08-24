from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.audit.service import AuditService
from app.domain.models import AuditEventType, Candle, OrderStatus
from app.execution.models import ExecutionResult
from app.market.features import vwap
from app.portfolio.engine import AllocationDecision, PortfolioAllocator
from app.research.market_intelligence import MarketStructureSnapshot
from app.store.sqlite import SQLiteStore
from app.strategy.base import Strategy, StrategyAction, StrategyInput, StrategySignal
from app.trading.cycle_store import SQLiteCycleCheckpointStore
from app.trading.orchestrator import TradingOrchestrator
from app.trading.portfolio_source import PortfolioSource


class TradingCycleResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    observed_at: datetime | None = None
    market_source: str | None = None
    reference_price: Decimal | None = None
    structure: MarketStructureSnapshot | None = None
    signals: list[StrategySignal] = Field(default_factory=list)
    allocations: list[AllocationDecision] = Field(default_factory=list)
    executions: list[ExecutionResult] = Field(default_factory=list)
    skipped_reason: str | None = None


class AutonomousTradingEngine:
    def __init__(
        self,
        *,
        store: SQLiteStore,
        strategies: list[Strategy],
        allocator: PortfolioAllocator,
        portfolio_source: PortfolioSource,
        orchestrator: TradingOrchestrator,
        audit: AuditService,
        execution_enabled: bool,
    ) -> None:
        self._store = store
        self._cycle_store = SQLiteCycleCheckpointStore(store.path)
        self._strategies = strategies
        self._allocator = allocator
        self._portfolio_source = portfolio_source
        self._orchestrator = orchestrator
        self._audit = audit
        self._execution_enabled = execution_enabled
        self._latest_structure_results: dict[str, TradingCycleResult] = {}

    @property
    def execution_enabled(self) -> bool:
        return self._execution_enabled

    @property
    def latest_structure_results(self) -> dict[str, TradingCycleResult]:
        return dict(self._latest_structure_results)

    def _record_structure_result(self, result: TradingCycleResult) -> TradingCycleResult:
        if result.structure is not None:
            self._latest_structure_results[result.symbol] = result
        return result

    async def on_candle(
        self,
        candle: Candle,
        *,
        now: datetime | None = None,
        structure: MarketStructureSnapshot | None = None,
    ) -> TradingCycleResult:
        # Provider-declared revisions update market history but are never a second
        # trading decision for an already observed minute.
        if candle.source.endswith(":updated"):
            self._store.upsert_candle(candle)
            return TradingCycleResult(
                symbol=candle.symbol,
                observed_at=candle.close_time,
                market_source=candle.source,
                reference_price=Decimal(str(candle.close)),
                skipped_reason="market_revision",
            )

        if self._cycle_store.is_completed(candle):
            return TradingCycleResult(
                symbol=candle.symbol,
                observed_at=candle.close_time,
                market_source=candle.source,
                reference_price=Decimal(str(candle.close)),
                skipped_reason="cycle_already_completed",
            )

        self._store.upsert_candle(candle)
        candles = self._store.list_candles(
            candle.symbol,
            interval=candle.interval,
            limit=200,
        )
        level = vwap(candles)
        if structure is None:
            structure = MarketStructureSnapshot(
                symbol=candle.symbol,
                vwap=level,
                methodology={"vwap": "typical-price-volume:last-200-candles"},
            )
        else:
            methodology = dict(structure.methodology)
            methodology["vwap"] = "typical-price-volume:last-200-candles"
            structure = structure.model_copy(
                update={
                    "vwap": level,
                    "methodology": methodology,
                }
            )

        previous = Decimal(str(candles[-2].close)) if len(candles) >= 2 else None
        market = StrategyInput(
            symbol=candle.symbol,
            current_price=Decimal(str(candle.close)),
            previous_price=previous,
            structure=structure,
            observed_at=candle.close_time,
        )
        signals = [strategy.evaluate(market) for strategy in self._strategies]

        for signal in signals:
            self._audit.record(
                AuditEventType.STRATEGY_SIGNAL,
                subject=signal.symbol,
                payload={
                    "strategy_id": signal.strategy_id,
                    "version": signal.version,
                    "action": signal.action.value,
                    "confidence": str(signal.confidence),
                    "rationale_codes": signal.rationale_codes,
                    "generated_at": signal.generated_at.isoformat(),
                },
            )

        actionable = [
            signal for signal in signals if signal.action is not StrategyAction.HOLD
        ]
        if not actionable:
            self._cycle_store.mark_completed(candle)
            return self._record_structure_result(
                TradingCycleResult(
                    symbol=candle.symbol,
                    observed_at=candle.close_time,
                    market_source=candle.source,
                    reference_price=Decimal(str(candle.close)),
                    structure=structure,
                    signals=signals,
                )
            )

        state = await self._portfolio_source.snapshot()
        allocations = self._allocator.allocate(signals, state.portfolio)
        for decision in allocations:
            self._audit.record(
                AuditEventType.SYSTEM,
                subject=decision.signal.symbol,
                payload={
                    "kind": "portfolio_decision",
                    "code": decision.code,
                    "message": decision.message,
                    "requested_notional": str(decision.requested_notional),
                    "client_order_id": (
                        decision.intent.client_order_id if decision.intent else None
                    ),
                },
            )

        executions: list[ExecutionResult] = []
        if self._execution_enabled:
            current = now or datetime.now(UTC)
            if current.tzinfo is None:
                current = current.replace(tzinfo=UTC)
            close_time = candle.close_time
            if close_time.tzinfo is None:
                close_time = close_time.replace(tzinfo=UTC)
            market_age = max(
                (
                    current.astimezone(UTC) - close_time.astimezone(UTC)
                ).total_seconds(),
                0.0,
            )
            context = state.risk_context.model_copy(
                update={"market_data_age_seconds": market_age}
            )
            for decision in allocations:
                if decision.intent is None:
                    continue
                executions.append(
                    await self._orchestrator.execute_intent(
                        decision.intent,
                        state.portfolio,
                        context,
                    )
                )

        # A monitoring-only cycle, a known risk rejection, or a known broker
        # state is terminal for this exact market observation. UNKNOWN must not
        # be checkpointed because restart/recovery still needs reconciliation.
        if not any(result.status is OrderStatus.UNKNOWN for result in executions):
            self._cycle_store.mark_completed(candle)

        return self._record_structure_result(
            TradingCycleResult(
                symbol=candle.symbol,
                observed_at=candle.close_time,
                market_source=candle.source,
                reference_price=Decimal(str(candle.close)),
                structure=structure,
                signals=signals,
                allocations=allocations,
                executions=executions,
            )
        )
