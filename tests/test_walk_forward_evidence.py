from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.models import Candle, TradingMode
from app.innovation.store import SQLiteStrategyEvidenceStore
from app.learning.models import StrategyEvaluationPartition, StrategyObservationStatus
from app.learning.service import StrategyLearningService
from app.learning.store import SQLiteStrategyLearningStore
from app.strategy.base import StrategyAction, StrategySignal
from app.trading.autonomous import TradingCycleResult


def candle(minute: int, close: str) -> Candle:
    opened = datetime(2026, 8, 20, 14, 0, tzinfo=UTC) + timedelta(minutes=minute)
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
        source="walk-forward-test",
    )


def signal(at: datetime, *, strategy_id: str = "wf", price: str = "100") -> StrategySignal:
    return StrategySignal(
        strategy_id=strategy_id,
        version="1.0.0",
        symbol="NVDA",
        action=StrategyAction.BUY,
        confidence=Decimal("0.8"),
        rationale_codes=["walk_forward_test"],
        entry_price=Decimal(price),
        invalidation_price=Decimal("95"),
        generated_at=at,
    )


def service(tmp_path) -> StrategyLearningService:
    return StrategyLearningService(
        store=SQLiteStrategyLearningStore(tmp_path / "learning.db"),
        evidence_store=SQLiteStrategyEvidenceStore(tmp_path / "evidence.db"),
        mode=TradingMode.REPLAY,
        evaluation_horizon_seconds=60,
        transaction_cost_bps=Decimal("0"),
        walk_forward_calibration_observations=2,
        walk_forward_holdout_observations=1,
        oos_min_holdout_observations=2,
        oos_min_completed_folds=2,
    )


def add_and_close(svc: StrategyLearningService, index: int, entry: str, exit_: str) -> None:
    first = candle(index * 2, entry)
    second = candle(index * 2 + 1, exit_)
    svc.observe_cycle(
        first,
        TradingCycleResult(symbol="NVDA", signals=[signal(first.close_time, price=entry)]),
    )
    svc.observe_cycle(second, TradingCycleResult(symbol="NVDA"))


def test_walk_forward_partition_and_fold_are_locked_before_outcome(tmp_path) -> None:
    svc = service(tmp_path)
    first = candle(0, "100")
    svc.observe_cycle(
        first,
        TradingCycleResult(symbol="NVDA", signals=[signal(first.close_time)]),
    )

    pending = svc.store.list_observations("wf", "1.0.0")
    assert len(pending) == 1
    assert pending[0].evaluation_partition is StrategyEvaluationPartition.CALIBRATION
    assert pending[0].walk_forward_fold == 0
    assert pending[0].net_return is None

    svc.observe_cycle(candle(1, "120"), TradingCycleResult(symbol="NVDA"))
    closed = svc.store.list_observations("wf", "1.0.0")[0]
    assert closed.evaluation_partition is StrategyEvaluationPartition.CALIBRATION
    assert closed.walk_forward_fold == 0


def test_only_precommitted_holdout_can_verify_oos_and_drive_promotion_metrics(tmp_path) -> None:
    svc = service(tmp_path)

    add_and_close(svc, 0, "100", "120")
    add_and_close(svc, 1, "100", "120")
    add_and_close(svc, 2, "100", "90")

    evidence = svc._evidence_store.get("wf", "1.0.0")
    assert evidence is not None
    assert evidence.out_of_sample_verified is False

    add_and_close(svc, 3, "100", "130")
    add_and_close(svc, 4, "100", "130")
    add_and_close(svc, 5, "100", "80")

    observations = svc.store.list_observations("wf", "1.0.0", closed_only=True)
    partitions = [(item.evaluation_partition, item.walk_forward_fold) for item in observations]
    assert partitions == [
        (StrategyEvaluationPartition.CALIBRATION, 0),
        (StrategyEvaluationPartition.CALIBRATION, 0),
        (StrategyEvaluationPartition.HOLDOUT, 0),
        (StrategyEvaluationPartition.CALIBRATION, 1),
        (StrategyEvaluationPartition.CALIBRATION, 1),
        (StrategyEvaluationPartition.HOLDOUT, 1),
    ]

    evidence = svc._evidence_store.get("wf", "1.0.0")
    assert evidence is not None
    assert evidence.out_of_sample_verified is True
    assert evidence.oos_holdout_observations == 2
    assert evidence.walk_forward_folds == 2
    assert evidence.expectancy_after_costs == Decimal("-0.15")
    assert evidence.max_drawdown == Decimal("0.3")
    assert any(ref.startswith("walk-forward-oos:wf@1.0.0:") for ref in evidence.evidence_refs)


def test_old_unassigned_observations_never_become_oos_by_relabeling(tmp_path) -> None:
    svc = service(tmp_path)
    generated = svc._observation_from_signal(
        signal(candle(0, "100").close_time),
        Decimal("100"),
    )
    legacy = generated.model_copy(
        update={
            "evaluation_partition": StrategyEvaluationPartition.UNASSIGNED,
            "walk_forward_fold": None,
        }
    )
    svc.store.add_observation(legacy)
    svc.store.update_observation(
        legacy.model_copy(
            update={
                "status": StrategyObservationStatus.CLOSED,
                "exit_price": Decimal("200"),
                "net_return": Decimal("1"),
                "closed_at": legacy.due_at,
            }
        )
    )

    svc.refresh_strategy("wf", "1.0.0")
    evidence = svc._evidence_store.get("wf", "1.0.0")
    assert evidence is not None
    assert evidence.out_of_sample_verified is False
    assert evidence.oos_holdout_observations == 0
