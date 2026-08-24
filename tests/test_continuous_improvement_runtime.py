from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.api.state import ApplicationState
from app.domain.models import Candle, TradingMode
from app.learning.service import StrategyLearningService
from app.settings import Settings
from app.strategy.base import StrategyAction, StrategyInput, StrategySignal, hold_signal
from app.trading.autonomous import TradingCycleResult


def candle(minute: int, close: str) -> Candle:
    opened = datetime(2026, 8, 20, 14, minute, tzinfo=UTC)
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


def buy_signal(at: datetime, price: str = "100") -> StrategySignal:
    return StrategySignal(
        strategy_id="vwap",
        version="1.0.0",
        symbol="NVDA",
        action=StrategyAction.BUY,
        confidence=Decimal("0.8"),
        rationale_codes=["test_buy"],
        entry_price=Decimal(price),
        invalidation_price=Decimal("98"),
        generated_at=at,
    )


class OneShotStrategy:
    strategy_id = "one-shot"
    version = "1.0.0"

    def evaluate(self, market: StrategyInput) -> StrategySignal:
        if market.previous_price is None:
            return StrategySignal(
                strategy_id=self.strategy_id,
                version=self.version,
                symbol=market.symbol,
                action=StrategyAction.BUY,
                confidence=Decimal("0.8"),
                rationale_codes=["first_observation"],
                entry_price=market.current_price,
                invalidation_price=market.current_price * Decimal("0.98"),
                generated_at=market.observed_at,
            )
        return hold_signal(
            strategy_id=self.strategy_id,
            version=self.version,
            market=market,
            rationale_code="already_observed",
        )


def test_application_state_builds_strategy_learning_service(tmp_path) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "app.db"),
            strategy_learning_enabled=True,
        )
    )

    assert isinstance(state.learning, StrategyLearningService)
    assert state.strategy_health_execution_allowed is True
    assert state.strategy_health_reports == []


@pytest.mark.asyncio
async def test_application_start_runs_continuous_improvement_task(tmp_path) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "app.db"),
            strategy_learning_enabled=True,
            strategy_improvement_interval_seconds=0.01,
        )
    )

    await state.start()
    try:
        assert state._improvement_task is not None
        assert state._improvement_task.get_name() == "continuous-improvement"
    finally:
        await state.stop()


@pytest.mark.asyncio
async def test_process_candle_feeds_market_cycle_into_learning_loop(tmp_path) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "app.db"),
            trading_mode=TradingMode.REPLAY,
            strategy_learning_enabled=True,
            strategy_evaluation_horizon_seconds=60,
            strategy_transaction_cost_bps=Decimal("0"),
        )
    )
    one_shot = OneShotStrategy()
    state.strategies = [one_shot]
    state.autonomous._strategies = [one_shot]

    first = candle(0, "100")
    second = candle(1, "110")
    await state.process_candle(first)
    await state.process_candle(second)

    observations = state.strategy_learning_store.list_observations("one-shot", "1.0.0")
    assert len(observations) == 1
    assert observations[0].status.value == "closed"
    assert observations[0].net_return == Decimal("0.1")


def test_degraded_strategy_moves_autonomous_runtime_to_reducing(tmp_path) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "app.db"),
            trading_mode=TradingMode.REPLAY,
            auto_trading_enabled=True,
            strategy_learning_enabled=True,
            strategy_evaluation_horizon_seconds=60,
            strategy_transaction_cost_bps=Decimal("0"),
            strategy_degradation_min_observations=1,
            strategy_degradation_max_drawdown=Decimal("0.01"),
        )
    )
    first = candle(0, "100")
    second = candle(1, "90")
    state.learning.observe_cycle(
        first,
        TradingCycleResult(symbol="NVDA", signals=[buy_signal(first.close_time)]),
    )
    state.learning.observe_cycle(second, TradingCycleResult(symbol="NVDA"))

    state.refresh_continuous_improvement()

    assert state.strategy_health_execution_allowed is False
    assert state.trading_state.value == "reducing"
    assert any(report.degraded for report in state.strategy_health_reports)


def test_continuous_improvement_never_auto_reactivates_reducing_runtime(tmp_path) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "app.db"),
            strategy_learning_enabled=True,
        )
    )
    state.orchestrator.reduce_only("operator_test")

    state.refresh_continuous_improvement()

    assert state.strategy_health_execution_allowed is True
    assert state.trading_state.value == "reducing"


def test_learning_locks_walk_forward_partition_before_outcome(tmp_path) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "walk-forward.db"),
            trading_mode=TradingMode.REPLAY,
            strategy_learning_enabled=True,
            strategy_evaluation_horizon_seconds=3600,
            strategy_transaction_cost_bps=Decimal("0"),
        )
    )

    for index in range(31):
        current = candle(index, str(100 + index))
        state.learning.observe_cycle(
            current,
            TradingCycleResult(
                symbol="NVDA",
                signals=[buy_signal(current.close_time, str(100 + index))],
            ),
        )

    observations = state.strategy_learning_store.list_observations("vwap", "1.0.0")
    payloads = [item.model_dump(mode="json") for item in observations]

    assert [item.get("evaluation_partition") for item in payloads[:20]] == [
        "calibration"
    ] * 20
    assert [item.get("evaluation_partition") for item in payloads[20:30]] == [
        "holdout"
    ] * 10
    assert [item.get("walk_forward_fold") for item in payloads[:30]] == [0] * 30
    assert payloads[30].get("evaluation_partition") == "calibration"
    assert payloads[30].get("walk_forward_fold") == 1
