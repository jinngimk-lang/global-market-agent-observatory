from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.models import Candle, OrderIntent, OrderStatus, Side, TradingMode
from app.execution.models import ExecutionResult
from app.innovation.store import SQLiteStrategyEvidenceStore
from app.learning.service import StrategyLearningService
from app.learning.store import SQLiteStrategyLearningStore
from app.portfolio.engine import AllocationDecision
from app.strategy.base import StrategyAction, StrategySignal
from app.trading.autonomous import TradingCycleResult


def candle(minute: int, close: str) -> Candle:
    opened = datetime(2026, 8, 25, 14, minute, tzinfo=UTC)
    return Candle(
        symbol="NVDA",
        interval="1m",
        open_time=opened,
        close_time=opened + timedelta(minutes=1),
        open=float(close),
        high=float(close),
        low=float(close),
        close=float(close),
        volume=1000,
        source="test",
    )


def signal(at: datetime) -> StrategySignal:
    return StrategySignal(
        strategy_id="vwap",
        version="1.0.0",
        symbol="NVDA",
        action=StrategyAction.BUY,
        confidence=Decimal("0.8"),
        rationale_codes=["vwap_reclaim"],
        entry_price=Decimal("100"),
        invalidation_price=Decimal("98"),
        generated_at=at,
    )


def service(tmp_path) -> tuple[StrategyLearningService, SQLiteStrategyLearningStore]:
    database = tmp_path / "friction.db"
    store = SQLiteStrategyLearningStore(database)
    return (
        StrategyLearningService(
            store=store,
            evidence_store=SQLiteStrategyEvidenceStore(database),
            mode=TradingMode.REPLAY,
            evaluation_horizon_seconds=60,
            transaction_cost_bps=Decimal("10"),
            modeled_entry_slippage_bps=Decimal("5"),
            modeled_exit_slippage_bps=Decimal("5"),
        ),
        store,
    )


def allocation_for(strategy_signal: StrategySignal, client_order_id: str) -> AllocationDecision:
    return AllocationDecision(
        signal=strategy_signal,
        intent=OrderIntent(
            client_order_id=client_order_id,
            symbol="NVDA",
            side=Side.BUY,
            quantity=Decimal("10"),
            reference_price=Decimal("100"),
            requested_at=strategy_signal.generated_at,
        ),
        code="allocated",
        message="test",
        requested_notional=Decimal("1000"),
    )


def test_modeled_slippage_is_explicit_and_applied_adversely(tmp_path) -> None:
    learning, store = service(tmp_path)
    first = candle(0, "100")
    second = candle(1, "110")
    strategy_signal = signal(first.close_time)

    learning.observe_cycle(
        first,
        TradingCycleResult(symbol="NVDA", signals=[strategy_signal]),
    )
    observation = store.list_observations("vwap", "1.0.0")[0]

    assert observation.signal_entry_price == Decimal("100")
    assert observation.entry_price == Decimal("100.0500")
    assert observation.entry_price_source.value == "modeled"
    assert observation.modeled_entry_slippage_bps == Decimal("5")
    assert observation.modeled_exit_slippage_bps == Decimal("5")
    assert observation.observed_entry_slippage_bps is None
    assert observation.execution_latency_seconds is None
    assert observation.execution_client_order_id is None

    learning.observe_cycle(second, TradingCycleResult(symbol="NVDA"))
    closed = store.list_observations("vwap", "1.0.0", closed_only=True)[0]

    assert closed.exit_price == Decimal("109.9450")
    assert closed.net_return == Decimal("0.09790054972513743128435782109")


def test_matching_fill_uses_observed_entry_without_double_counting_modeled_slippage(
    tmp_path,
) -> None:
    learning, store = service(tmp_path)
    first = candle(0, "100")
    second = candle(1, "110")
    strategy_signal = signal(first.close_time)
    client_order_id = "auto-nvda-test"
    allocation = allocation_for(strategy_signal, client_order_id)
    execution = ExecutionResult(
        client_order_id=client_order_id,
        broker_order_id="broker-1",
        status=OrderStatus.FILLED,
        filled_quantity=Decimal("10"),
        filled_price=Decimal("100.20"),
        observed_at=strategy_signal.generated_at + timedelta(seconds=2),
    )

    learning.observe_cycle(
        first,
        TradingCycleResult(
            symbol="NVDA",
            signals=[strategy_signal],
            allocations=[allocation],
            executions=[execution],
        ),
    )
    observation = store.list_observations("vwap", "1.0.0")[0]

    assert observation.signal_entry_price == Decimal("100")
    assert observation.entry_price == Decimal("100.20")
    assert observation.entry_price_source.value == "observed-fill"
    assert observation.observed_entry_slippage_bps == Decimal("20.000")
    assert observation.execution_latency_seconds == Decimal("2.0")
    assert observation.execution_client_order_id == client_order_id

    learning.observe_cycle(second, TradingCycleResult(symbol="NVDA"))
    closed = store.list_observations("vwap", "1.0.0", closed_only=True)[0]

    assert closed.exit_price == Decimal("109.9450")
    assert closed.net_return == Decimal("0.09625548902195608782435129741")


def test_unmatched_fill_cannot_contaminate_strategy_execution_provenance(tmp_path) -> None:
    learning, store = service(tmp_path)
    first = candle(0, "100")
    strategy_signal = signal(first.close_time)
    allocation = allocation_for(strategy_signal, "intended-order")
    unrelated_fill = ExecutionResult(
        client_order_id="different-order",
        broker_order_id="broker-other",
        status=OrderStatus.FILLED,
        filled_quantity=Decimal("10"),
        filled_price=Decimal("120"),
        observed_at=strategy_signal.generated_at + timedelta(seconds=1),
    )

    learning.observe_cycle(
        first,
        TradingCycleResult(
            symbol="NVDA",
            signals=[strategy_signal],
            allocations=[allocation],
            executions=[unrelated_fill],
        ),
    )
    observation = store.list_observations("vwap", "1.0.0")[0]

    assert observation.entry_price == Decimal("100.0500")
    assert observation.entry_price_source.value == "modeled"
    assert observation.observed_entry_slippage_bps is None
    assert observation.execution_latency_seconds is None
    assert observation.execution_client_order_id is None


def test_broker_paper_evidence_counts_only_exact_verified_fills(tmp_path) -> None:
    database = tmp_path / "broker-paper-friction.db"
    store = SQLiteStrategyLearningStore(database)
    evidence_store = SQLiteStrategyEvidenceStore(database)
    learning = StrategyLearningService(
        store=store,
        evidence_store=evidence_store,
        mode=TradingMode.BROKER_PAPER,
        evaluation_horizon_seconds=60,
        transaction_cost_bps=Decimal("10"),
    )

    first = candle(0, "100")
    first_signal = signal(first.close_time)
    learning.observe_cycle(
        first,
        TradingCycleResult(symbol="NVDA", signals=[first_signal]),
    )
    learning.observe_cycle(candle(1, "101"), TradingCycleResult(symbol="NVDA"))

    third = candle(2, "100")
    third_signal = signal(third.close_time)
    client_order_id = "broker-paper-verified-fill"
    allocation = allocation_for(third_signal, client_order_id)
    execution = ExecutionResult(
        client_order_id=client_order_id,
        broker_order_id="broker-paper-1",
        status=OrderStatus.FILLED,
        filled_quantity=Decimal("10"),
        filled_price=Decimal("100.10"),
        observed_at=third_signal.generated_at + timedelta(seconds=1),
    )
    learning.observe_cycle(
        third,
        TradingCycleResult(
            symbol="NVDA",
            signals=[third_signal],
            allocations=[allocation],
            executions=[execution],
        ),
    )
    learning.observe_cycle(candle(3, "101"), TradingCycleResult(symbol="NVDA"))

    evidence = evidence_store.get("vwap", "1.0.0")

    assert evidence is not None
    assert evidence.broker_paper_observations == 2
    assert evidence.verified_broker_paper_fill_observations == 1
