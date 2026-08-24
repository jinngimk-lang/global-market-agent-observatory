from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.models import Candle, TradingMode
from app.innovation.store import SQLiteStrategyEvidenceStore
from app.learning.service import StrategyLearningService
from app.learning.store import SQLiteStrategyLearningStore
from app.strategy.base import StrategyAction, StrategySignal
from app.trading.autonomous import TradingCycleResult


BASE = datetime(2026, 8, 24, 13, 0, tzinfo=UTC)


def candle(index: int) -> Candle:
    opened = BASE + timedelta(minutes=index)
    price = 100 + index
    return Candle(
        symbol="NVDA",
        interval="1m",
        open_time=opened,
        close_time=opened + timedelta(minutes=1),
        open=float(price),
        high=float(price),
        low=float(price),
        close=float(price),
        volume=1000,
        source="test",
    )


def signal(index: int) -> StrategySignal:
    observed = candle(index).close_time
    return StrategySignal(
        strategy_id="vwap",
        version="1.0.0",
        symbol="NVDA",
        action=StrategyAction.BUY,
        confidence=Decimal("0.8"),
        rationale_codes=["prospective_partition_test"],
        entry_price=Decimal(str(100 + index)),
        invalidation_price=Decimal(str(98 + index)),
        generated_at=observed,
    )


def service(tmp_path) -> StrategyLearningService:
    database = tmp_path / "walk-forward.db"
    return StrategyLearningService(
        store=SQLiteStrategyLearningStore(database),
        evidence_store=SQLiteStrategyEvidenceStore(database),
        mode=TradingMode.REPLAY,
        evaluation_horizon_seconds=3600,
        transaction_cost_bps=Decimal("0"),
    )


def test_new_observations_lock_walk_forward_partition_before_outcome(tmp_path) -> None:
    learning = service(tmp_path)

    for index in range(31):
        learning.observe_cycle(
            candle(index),
            TradingCycleResult(symbol="NVDA", signals=[signal(index)]),
        )

    observations = learning.store.list_observations("vwap", "1.0.0")
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
