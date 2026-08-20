from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.audit.service import AuditService
from app.broker.paper_execution import PaperExecutionAdapter
from app.domain.models import AuditEventType, Candle, OrderStatus, RiskLimits
from app.execution.controller import ExecutionController
from app.portfolio.engine import PortfolioAllocator, PortfolioPolicy
from app.risk.engine import RiskEngine
from app.store.sqlite import SQLiteStore
from app.strategy.gamma_levels import GammaLevelsStrategy
from app.strategy.vwap import VWAPStrategy
from app.trading.autonomous import AutonomousTradingEngine
from app.trading.orchestrator import TradingOrchestrator
from app.trading.portfolio_source import LocalPaperPortfolioSource


def bar(minute: int, close: float, *, source: str = "alpaca:iex") -> Candle:
    opened = datetime(2026, 8, 20, 14, minute, tzinfo=UTC)
    return Candle(
        symbol="NVDA",
        interval="1m",
        open_time=opened,
        close_time=opened + timedelta(minutes=1),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=100,
        source=source,
        closed=True,
    )


def build_engine(tmp_path, *, execution_enabled: bool = True) -> tuple[AutonomousTradingEngine, SQLiteStore]:
    store = SQLiteStore(tmp_path / "auto.db", starting_cash="10000")
    risk = RiskEngine(
        RiskLimits(
            allowed_symbols={"NVDA"},
            max_order_notional=Decimal("5000"),
            max_symbol_exposure=Decimal("5000"),
            max_gross_exposure=Decimal("5000"),
            market_data_max_age_seconds=5,
            account_state_max_age_seconds=30,
        )
    )
    execution = ExecutionController(
        adapter=PaperExecutionAdapter.from_store(store),
        risk_engine=risk,
    )
    audit = AuditService(store)
    orchestrator = TradingOrchestrator(execution=execution, audit=audit)
    allocator = PortfolioAllocator(
        PortfolioPolicy(
            risk_fraction_per_trade=Decimal("0.01"),
            max_order_notional=Decimal("5000"),
            max_group_exposure=Decimal("5000"),
            symbol_groups={"NVDA": "semiconductor-ai"},
        )
    )
    engine = AutonomousTradingEngine(
        store=store,
        strategies=[VWAPStrategy(), GammaLevelsStrategy()],
        allocator=allocator,
        portfolio_source=LocalPaperPortfolioSource.from_store(store),
        orchestrator=orchestrator,
        audit=audit,
        execution_enabled=execution_enabled,
    )
    return engine, store


@pytest.mark.asyncio
async def test_new_bar_runs_signal_allocation_risk_and_paper_execution(tmp_path) -> None:
    engine, store = build_engine(tmp_path)
    await engine.on_candle(bar(0, 199), now=bar(0, 199).close_time)

    result = await engine.on_candle(bar(1, 201), now=bar(1, 201).close_time)

    buy_signals = [item for item in result.signals if item.action.value == "buy"]
    assert len(buy_signals) == 1
    assert len(result.allocations) == 1
    assert len(result.executions) == 1
    assert result.executions[0].status is OrderStatus.FILLED
    assert store.get_position("NVDA") is not None
    event_types = [event.event_type for event in store.list_audit_events(limit=50)]
    assert AuditEventType.STRATEGY_SIGNAL in event_types
    assert AuditEventType.RISK_DECISION in event_types
    assert AuditEventType.EXECUTION in event_types


@pytest.mark.asyncio
async def test_monitoring_mode_generates_signal_without_submitting_order(tmp_path) -> None:
    engine, store = build_engine(tmp_path, execution_enabled=False)
    await engine.on_candle(bar(0, 199), now=bar(0, 199).close_time)

    result = await engine.on_candle(bar(1, 201), now=bar(1, 201).close_time)

    assert any(item.action.value == "buy" for item in result.signals)
    assert result.executions == []
    assert store.get_position("NVDA") is None


@pytest.mark.asyncio
async def test_stale_market_bar_is_rejected_by_deterministic_risk(tmp_path) -> None:
    engine, _ = build_engine(tmp_path)
    first = bar(0, 199)
    second = bar(1, 201)
    await engine.on_candle(first, now=first.close_time)

    result = await engine.on_candle(second, now=second.close_time + timedelta(seconds=30))

    assert len(result.executions) == 1
    assert result.executions[0].status is OrderStatus.REJECTED
    assert result.executions[0].code == "stale_market_data"


@pytest.mark.asyncio
async def test_updated_bar_is_stored_but_never_creates_new_execution(tmp_path) -> None:
    engine, store = build_engine(tmp_path)
    first = bar(0, 199)
    updated = bar(0, 200, source="alpaca:iex:updated")
    await engine.on_candle(first, now=first.close_time)

    result = await engine.on_candle(updated, now=updated.close_time)

    assert result.skipped_reason == "market_revision"
    assert result.executions == []
    assert store.latest_candle("NVDA").close == 200


@pytest.mark.asyncio
async def test_replaying_same_actionable_bar_reuses_same_order_id(tmp_path) -> None:
    engine, store = build_engine(tmp_path)
    first = bar(0, 199)
    second = bar(1, 201)
    await engine.on_candle(first, now=first.close_time)
    original = await engine.on_candle(second, now=second.close_time)

    replay = await engine.on_candle(second, now=second.close_time)

    assert original.executions[0].broker_order_id == replay.executions[0].broker_order_id
    assert len(store.list_orders()) == 1
