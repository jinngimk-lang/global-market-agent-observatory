from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.api.state import ApplicationState
from app.learning.models import StrategyEvaluationPartition
from app.settings import Settings
from app.strategy.base import StrategyAction, StrategySignal


def signal(minute: int) -> StrategySignal:
    return StrategySignal(
        strategy_id="vwap",
        version="1.0.0",
        symbol="NVDA",
        action=StrategyAction.BUY,
        confidence=Decimal("0.8"),
        rationale_codes=["runtime_settings_test"],
        entry_price=Decimal("100"),
        invalidation_price=Decimal("98"),
        generated_at=datetime(2026, 8, 20, 14, minute, tzinfo=UTC),
    )


def test_application_state_wires_walk_forward_policy_from_settings(tmp_path) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "app.db"),
            strategy_walk_forward_calibration_observations=1,
            strategy_walk_forward_holdout_observations=1,
            strategy_oos_min_holdout_observations=1,
            strategy_oos_min_completed_folds=1,
        )
    )

    first = state.learning._observation_from_signal(signal(0), Decimal("100"))
    state.strategy_learning_store.add_observation(first)
    second = state.learning._observation_from_signal(signal(1), Decimal("100"))

    assert first.evaluation_partition is StrategyEvaluationPartition.CALIBRATION
    assert first.walk_forward_fold == 0
    assert second.evaluation_partition is StrategyEvaluationPartition.HOLDOUT
    assert second.walk_forward_fold == 0
