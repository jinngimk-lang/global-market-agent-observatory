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


def test_application_state_wires_modeled_execution_friction_from_settings(tmp_path) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "friction.db"),
            strategy_modeled_entry_slippage_bps=Decimal("7"),
            strategy_modeled_exit_slippage_bps=Decimal("9"),
        )
    )

    observation = state.learning._observation_from_signal(signal(0), Decimal("100"))

    assert observation.entry_price == Decimal("100.0700")
    assert observation.modeled_entry_slippage_bps == Decimal("7")
    assert observation.modeled_exit_slippage_bps == Decimal("9")


def test_execution_friction_settings_load_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("STRATEGY_MODELED_ENTRY_SLIPPAGE_BPS", "3.5")
    monkeypatch.setenv("STRATEGY_MODELED_EXIT_SLIPPAGE_BPS", "4.5")

    settings = Settings.from_env()

    assert settings.strategy_modeled_entry_slippage_bps == Decimal("3.5")
    assert settings.strategy_modeled_exit_slippage_bps == Decimal("4.5")
