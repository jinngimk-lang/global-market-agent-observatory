from app.api.state import ApplicationState
from app.settings import Settings


def test_application_state_shares_walk_forward_settings_across_learning_and_gate(tmp_path) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "shared-walk-forward.db"),
            strategy_walk_forward_calibration_observations=2,
            strategy_walk_forward_holdout_observations=1,
            strategy_oos_min_holdout_observations=2,
            strategy_oos_min_completed_folds=2,
        )
    )

    assert state.learning._walk_forward_calibration_observations == 2
    assert state.learning._walk_forward_holdout_observations == 1
    assert state.learning._oos_min_holdout_observations == 2
    assert state.learning._oos_min_completed_folds == 2
    assert state.strategy_promotion.promotion_policy.min_oos_holdout_observations == 2
    assert state.strategy_promotion.promotion_policy.min_walk_forward_folds == 2
