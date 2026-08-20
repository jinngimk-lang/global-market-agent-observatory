from decimal import Decimal

import pytest

from app.audit.service import AuditService
from app.domain.models import (
    AuditEventType,
    OrderIntent,
    OrderStatus,
    PortfolioSnapshot,
    RiskContext,
    RiskLimits,
    Side,
    TradingState,
)
from app.execution.controller import ExecutionController
from app.execution.models import ExecutionResult
from app.risk.engine import RiskEngine
from app.store.sqlite import SQLiteStore
from app.trading.orchestrator import TradingOrchestrator


class FakeExecutionAdapter:
    name = "fake"

    def __init__(self, *, submit_status: OrderStatus = OrderStatus.ACCEPTED) -> None:
        self.submit_status = submit_status
        self.submit_calls = 0
        self.lookup_calls = 0
        self.existing: dict[str, ExecutionResult] = {}

    async def get_order_by_client_id(self, client_order_id: str) -> ExecutionResult | None:
        self.lookup_calls += 1
        return self.existing.get(client_order_id)

    async def submit(self, intent: OrderIntent) -> ExecutionResult:
        self.submit_calls += 1
        result = ExecutionResult(
            client_order_id=intent.client_order_id,
            broker_order_id=(None if self.submit_status is OrderStatus.UNKNOWN else "broker-1"),
            status=self.submit_status,
            code=("unknown_execution" if self.submit_status is OrderStatus.UNKNOWN else "broker_result"),
            message="submit result",
        )
        if self.submit_status is not OrderStatus.UNKNOWN:
            self.existing[intent.client_order_id] = result
        return result

    async def cancel(self, broker_order_id: str) -> ExecutionResult:
        return ExecutionResult(
            client_order_id="cancelled",
            broker_order_id=broker_order_id,
            status=OrderStatus.REJECTED,
            message="cancelled",
        )


def make_intent() -> OrderIntent:
    return OrderIntent(
        client_order_id="nvda-1",
        symbol="NVDA",
        side=Side.BUY,
        quantity=Decimal("1"),
        reference_price=Decimal("200"),
    )


def make_orchestrator(tmp_path, adapter: FakeExecutionAdapter) -> tuple[TradingOrchestrator, AuditService]:
    risk = RiskEngine(
        RiskLimits(
            allowed_symbols={"NVDA"},
            max_order_notional=Decimal("10000"),
            max_symbol_exposure=Decimal("10000"),
            max_gross_exposure=Decimal("20000"),
        )
    )
    controller = ExecutionController(adapter=adapter, risk_engine=risk)
    audit = AuditService(SQLiteStore(tmp_path / "trading.db"))
    return TradingOrchestrator(execution=controller, audit=audit), audit


@pytest.mark.asyncio
async def test_approved_intent_executes_and_audits_risk_and_execution(tmp_path) -> None:
    adapter = FakeExecutionAdapter()
    orchestrator, audit = make_orchestrator(tmp_path, adapter)

    result = await orchestrator.execute_intent(
        make_intent(),
        PortfolioSnapshot(cash=Decimal("10000")),
        RiskContext(),
    )

    assert result.status is OrderStatus.ACCEPTED
    assert adapter.submit_calls == 1
    assert [event.event_type for event in audit.list_events()] == [
        AuditEventType.RISK_DECISION,
        AuditEventType.EXECUTION,
    ]


@pytest.mark.asyncio
async def test_kill_switch_halts_new_exposure_and_is_audited(tmp_path) -> None:
    adapter = FakeExecutionAdapter()
    orchestrator, audit = make_orchestrator(tmp_path, adapter)

    orchestrator.halt("manual emergency stop")
    result = await orchestrator.execute_intent(
        make_intent(),
        PortfolioSnapshot(cash=Decimal("10000")),
        RiskContext(),
    )

    assert orchestrator.trading_state is TradingState.HALTED
    assert result.status is OrderStatus.REJECTED
    assert result.code == "trading_halted"
    assert adapter.submit_calls == 0
    assert audit.list_events()[0].event_type is AuditEventType.KILL_SWITCH


@pytest.mark.asyncio
async def test_stale_market_data_fails_closed_before_broker_submit(tmp_path) -> None:
    adapter = FakeExecutionAdapter()
    orchestrator, _ = make_orchestrator(tmp_path, adapter)

    result = await orchestrator.execute_intent(
        make_intent(),
        PortfolioSnapshot(cash=Decimal("10000")),
        RiskContext(market_data_age_seconds=60.0),
    )

    assert result.status is OrderStatus.REJECTED
    assert result.code == "stale_market_data"
    assert adapter.submit_calls == 0


@pytest.mark.asyncio
async def test_unknown_submit_is_reconciled_then_halts_if_still_unresolved(tmp_path) -> None:
    adapter = FakeExecutionAdapter(submit_status=OrderStatus.UNKNOWN)
    orchestrator, _ = make_orchestrator(tmp_path, adapter)

    result = await orchestrator.execute_intent(
        make_intent(),
        PortfolioSnapshot(cash=Decimal("10000")),
        RiskContext(),
    )

    assert result.status is OrderStatus.UNKNOWN
    assert adapter.submit_calls == 1
    assert adapter.lookup_calls == 2
    assert orchestrator.trading_state is TradingState.HALTED

    second = await orchestrator.execute_intent(
        make_intent(),
        PortfolioSnapshot(cash=Decimal("10000")),
        RiskContext(),
    )
    assert second.status is OrderStatus.REJECTED
    assert second.code == "trading_halted"
    assert adapter.submit_calls == 1
