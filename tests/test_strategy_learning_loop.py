from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.models import Candle, TradingMode
from app.innovation.models import PromotionEvidence
from app.innovation.store import SQLiteStrategyEvidenceStore
from app.learning.models import StrategyHealthPolicy
from app.learning.service import StrategyLearningService
from app.learning.store import SQLiteStrategyLearningStore
from app.strategy.base import StrategyAction, StrategySignal
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


def signal(at: datetime, *, price: str = "100") -> StrategySignal:
    return StrategySignal(
        strategy_id="vwap",
        version="1.0.0",
        symbol="NVDA",
        action=StrategyAction.BUY,
        confidence=Decimal("0.8"),
        rationale_codes=["vwap_reclaim"],
        entry_price=Decimal(price),
        invalidation_price=Decimal("98"),
        generated_at=at,
    )


def build_service(tmp_path, *, min_observations: int = 2) -> tuple[
    StrategyLearningService,
    SQLiteStrategyLearningStore,
    SQLiteStrategyEvidenceStore,
]:
    database = tmp_path / "learning.db"
    learning_store = SQLiteStrategyLearningStore(database)
    evidence_store = SQLiteStrategyEvidenceStore(database)
    service = StrategyLearningService(
        store=learning_store,
        evidence_store=evidence_store,
        mode=TradingMode.REPLAY,
        evaluation_horizon_seconds=60,
        transaction_cost_bps=Decimal("10"),
        health_policy=StrategyHealthPolicy(
            min_observations=min_observations,
            window_observations=20,
            min_expectancy_after_costs=Decimal("0"),
            max_drawdown=Decimal("0.05"),
        ),
    )
    return service, learning_store, evidence_store


def test_learning_loop_settles_due_signal_and_updates_promotion_evidence(tmp_path) -> None:
    service, _, evidence_store = build_service(tmp_path)
    first = candle(0, "100")
    second = candle(1, "110")

    service.observe_cycle(
        first,
        TradingCycleResult(symbol="NVDA", signals=[signal(first.close_time)]),
    )
    service.observe_cycle(second, TradingCycleResult(symbol="NVDA"))

    health = service.refresh_strategy("vwap", "1.0.0")
    evidence = evidence_store.get("vwap", "1.0.0")

    assert health.closed_observations == 1
    assert health.expectancy_after_costs == Decimal("0.099")
    assert health.win_rate == Decimal("1")
    assert health.degraded is False
    assert evidence is not None
    assert evidence.replay_observations == 1
    assert evidence.expectancy_after_costs == Decimal("0.099")
    assert evidence.transaction_cost_model_documented is True
    assert evidence.degradation_rule_defined is True
    assert any(ref.startswith("runtime-learning:") for ref in evidence.evidence_refs)


def test_learning_loop_flags_degradation_after_sufficient_negative_evidence(tmp_path) -> None:
    service, _, _ = build_service(tmp_path, min_observations=2)

    first = candle(0, "100")
    second = candle(1, "90")
    third = candle(2, "100")
    fourth = candle(3, "90")

    service.observe_cycle(
        first,
        TradingCycleResult(symbol="NVDA", signals=[signal(first.close_time)]),
    )
    service.observe_cycle(second, TradingCycleResult(symbol="NVDA"))
    service.observe_cycle(
        third,
        TradingCycleResult(symbol="NVDA", signals=[signal(third.close_time)]),
    )
    service.observe_cycle(fourth, TradingCycleResult(symbol="NVDA"))

    health = service.refresh_strategy("vwap", "1.0.0")

    assert health.closed_observations == 2
    assert health.expectancy_after_costs < 0
    assert health.degraded is True
    assert "negative_expectancy" in health.degradation_reasons
    assert "drawdown_limit" in health.degradation_reasons


def test_pending_observation_is_idempotent_for_same_strategy_signal(tmp_path) -> None:
    service, learning_store, _ = build_service(tmp_path)
    first = candle(0, "100")
    cycle = TradingCycleResult(symbol="NVDA", signals=[signal(first.close_time)])

    service.observe_cycle(first, cycle)
    service.observe_cycle(first, cycle)

    observations = learning_store.list_observations("vwap", "1.0.0")
    assert len(observations) == 1
    assert observations[0].status.value == "pending"


def test_runtime_learning_never_erases_stronger_existing_evidence(tmp_path) -> None:
    service, _, evidence_store = build_service(tmp_path)
    evidence_store.upsert(
        "vwap",
        "1.0.0",
        PromotionEvidence(
            replay_observations=100,
            expectancy_after_costs=Decimal("0.02"),
            max_drawdown=Decimal("0.03"),
            out_of_sample_verified=True,
            evidence_refs=["walk-forward:2026q2"],
        ),
    )
    first = candle(0, "100")
    second = candle(1, "110")

    service.observe_cycle(
        first,
        TradingCycleResult(symbol="NVDA", signals=[signal(first.close_time)]),
    )
    service.observe_cycle(second, TradingCycleResult(symbol="NVDA"))

    evidence = evidence_store.get("vwap", "1.0.0")

    assert evidence is not None
    assert evidence.replay_observations == 100
    assert evidence.expectancy_after_costs == Decimal("0.02")
    assert evidence.max_drawdown == Decimal("0.03")
    assert evidence.out_of_sample_verified is True
    assert "walk-forward:2026q2" in evidence.evidence_refs
    assert any(ref.startswith("runtime-learning:") for ref in evidence.evidence_refs)
