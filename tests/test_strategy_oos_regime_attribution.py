from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.models import TradingMode
from app.innovation.store import SQLiteStrategyEvidenceStore
from app.learning.models import (
    StrategyEvaluationPartition,
    StrategyHealthPolicy,
    StrategyObservation,
    StrategyObservationStatus,
)
from app.learning.service import StrategyLearningService
from app.learning.store import SQLiteStrategyLearningStore
from app.strategy.base import StrategyAction


def service(tmp_path) -> StrategyLearningService:
    return StrategyLearningService(
        store=SQLiteStrategyLearningStore(tmp_path / "learning.db"),
        evidence_store=SQLiteStrategyEvidenceStore(tmp_path / "evidence.db"),
        mode=TradingMode.REPLAY,
        evaluation_horizon_seconds=60,
        transaction_cost_bps=Decimal("0"),
        health_policy=StrategyHealthPolicy(
            min_observations=2,
            window_observations=50,
            min_expectancy_after_costs=Decimal("0"),
            max_drawdown=Decimal("0.25"),
        ),
        walk_forward_calibration_observations=1,
        walk_forward_holdout_observations=1,
        oos_min_holdout_observations=2,
        oos_min_completed_folds=2,
    )


def observation(
    index: int,
    *,
    partition: StrategyEvaluationPartition,
    fold: int | None,
    regime: str | None,
    net_return: str,
) -> StrategyObservation:
    observed = datetime(2026, 8, 20, 14, 0, tzinfo=UTC) + timedelta(minutes=index)
    return StrategyObservation(
        observation_id=f"oos-regime-{index}",
        strategy_id="vwap",
        version="1.0.0",
        symbol="NVDA",
        mode=TradingMode.REPLAY,
        action=StrategyAction.BUY,
        entry_price=Decimal("100"),
        observed_at=observed,
        due_at=observed + timedelta(minutes=1),
        transaction_cost_bps=Decimal("0"),
        market_regime=regime,
        evaluation_partition=partition,
        walk_forward_fold=fold,
        status=StrategyObservationStatus.CLOSED,
        exit_price=Decimal("100"),
        net_return=Decimal(net_return),
        closed_at=observed + timedelta(minutes=1),
    )


def test_oos_regime_attribution_uses_only_holdout_from_completed_folds(tmp_path) -> None:
    learning = service(tmp_path)
    store = learning.store

    # Two complete folds. Calibration returns are deliberately extreme and must
    # never contaminate the OOS regime expectancy.
    store.add_observation(
        observation(
            0,
            partition=StrategyEvaluationPartition.CALIBRATION,
            fold=0,
            regime="negative-gamma|below-vwap",
            net_return="0.90",
        )
    )
    store.add_observation(
        observation(
            1,
            partition=StrategyEvaluationPartition.HOLDOUT,
            fold=0,
            regime="negative-gamma|below-vwap",
            net_return="-0.10",
        )
    )
    store.add_observation(
        observation(
            2,
            partition=StrategyEvaluationPartition.CALIBRATION,
            fold=1,
            regime="negative-gamma|below-vwap",
            net_return="0.80",
        )
    )
    store.add_observation(
        observation(
            3,
            partition=StrategyEvaluationPartition.HOLDOUT,
            fold=1,
            regime="negative-gamma|below-vwap",
            net_return="-0.20",
        )
    )

    # Historical/unassigned evidence must not be relabeled into OOS.
    store.add_observation(
        observation(
            4,
            partition=StrategyEvaluationPartition.UNASSIGNED,
            fold=None,
            regime="negative-gamma|below-vwap",
            net_return="1.00",
        )
    )
    # Fold 2 is incomplete: holdout alone is not a completed walk-forward fold.
    store.add_observation(
        observation(
            5,
            partition=StrategyEvaluationPartition.HOLDOUT,
            fold=2,
            regime="negative-gamma|below-vwap",
            net_return="1.00",
        )
    )

    health = learning.refresh_strategy("vwap", "1.0.0")

    by_regime = {item.regime: item for item in health.oos_regime_attribution}
    weak = by_regime["negative-gamma|below-vwap"]
    assert weak.holdout_observations == 2
    assert weak.completed_folds == 2
    assert weak.expectancy_after_costs == Decimal("-0.15")
    assert weak.win_rate == Decimal("0")
    assert weak.verified is True


def test_oos_regime_attribution_reports_insufficient_regime_without_promoting_it(tmp_path) -> None:
    learning = service(tmp_path)
    store = learning.store

    # Both global folds are complete, but this regime appears in only one held-out
    # observation, below the configured per-regime evidence threshold.
    store.add_observation(
        observation(
            0,
            partition=StrategyEvaluationPartition.CALIBRATION,
            fold=0,
            regime="positive-gamma|above-vwap",
            net_return="0.01",
        )
    )
    store.add_observation(
        observation(
            1,
            partition=StrategyEvaluationPartition.HOLDOUT,
            fold=0,
            regime="positive-gamma|above-vwap",
            net_return="0.02",
        )
    )
    store.add_observation(
        observation(
            2,
            partition=StrategyEvaluationPartition.CALIBRATION,
            fold=1,
            regime="negative-gamma|below-vwap",
            net_return="0.01",
        )
    )
    store.add_observation(
        observation(
            3,
            partition=StrategyEvaluationPartition.HOLDOUT,
            fold=1,
            regime="negative-gamma|below-vwap",
            net_return="0.03",
        )
    )

    health = learning.refresh_strategy("vwap", "1.0.0")

    by_regime = {item.regime: item for item in health.oos_regime_attribution}
    positive = by_regime["positive-gamma|above-vwap"]
    assert positive.holdout_observations == 1
    assert positive.completed_folds == 1
    assert positive.verified is False
