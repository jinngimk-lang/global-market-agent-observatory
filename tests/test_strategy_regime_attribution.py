from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.models import Candle, TradingMode
from app.innovation.store import SQLiteStrategyEvidenceStore
from app.learning.models import (
    StrategyHealthPolicy,
    StrategyObservation,
    StrategyObservationStatus,
)
from app.learning.service import StrategyLearningService
from app.learning.store import SQLiteStrategyLearningStore
from app.research.market_intelligence import MarketStructureSnapshot
from app.strategy.base import StrategyAction, StrategySignal
from app.trading.autonomous import TradingCycleResult


def build_service(tmp_path, *, min_observations: int = 2) -> StrategyLearningService:
    return StrategyLearningService(
        store=SQLiteStrategyLearningStore(tmp_path / "learning.db"),
        evidence_store=SQLiteStrategyEvidenceStore(tmp_path / "evidence.db"),
        mode=TradingMode.REPLAY,
        evaluation_horizon_seconds=60,
        transaction_cost_bps=Decimal("0"),
        health_policy=StrategyHealthPolicy(
            min_observations=min_observations,
            window_observations=20,
            min_expectancy_after_costs=Decimal("0"),
            max_drawdown=Decimal("0.25"),
        ),
    )


def closed_observation(
    index: int,
    *,
    regime: str,
    net_return: str,
) -> StrategyObservation:
    observed = datetime(2026, 8, 20, 14, 0, tzinfo=UTC) + timedelta(minutes=index)
    return StrategyObservation(
        observation_id=f"regime-{index}",
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
        status=StrategyObservationStatus.CLOSED,
        exit_price=Decimal("100"),
        net_return=Decimal(net_return),
        closed_at=observed + timedelta(minutes=1),
    )


def test_observation_locks_regime_from_strategy_used_structure_before_outcome(tmp_path) -> None:
    service = build_service(tmp_path)
    observed = datetime(2026, 8, 20, 14, 0, tzinfo=UTC)
    candle = Candle(
        symbol="NVDA",
        interval="1m",
        open_time=observed - timedelta(minutes=1),
        close_time=observed,
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1000,
        source="test",
    )
    signal = StrategySignal(
        strategy_id="vwap",
        version="1.0.0",
        symbol="NVDA",
        action=StrategyAction.BUY,
        confidence=Decimal("0.8"),
        entry_price=Decimal("101"),
        generated_at=observed,
    )
    cycle = TradingCycleResult(
        symbol="NVDA",
        observed_at=observed,
        reference_price=Decimal("101"),
        structure=MarketStructureSnapshot(
            symbol="NVDA",
            vwap=Decimal("100"),
            net_gex_1pct=Decimal("250000"),
        ),
        signals=[signal],
    )

    service.observe_cycle(candle, cycle)

    observation = service.store.list_observations("vwap", "1.0.0")[0]
    assert observation.market_regime == "positive-gamma|above-vwap"


def test_regime_attribution_exposes_degradation_without_global_health_side_effect(tmp_path) -> None:
    service = build_service(tmp_path)
    store = service.store
    store.add_observation(
        closed_observation(0, regime="positive-gamma|above-vwap", net_return="0.20")
    )
    store.add_observation(
        closed_observation(1, regime="positive-gamma|above-vwap", net_return="0.20")
    )
    store.add_observation(
        closed_observation(2, regime="negative-gamma|below-vwap", net_return="-0.10")
    )
    store.add_observation(
        closed_observation(3, regime="negative-gamma|below-vwap", net_return="-0.10")
    )

    health = service.refresh_strategy("vwap", "1.0.0")

    by_regime = {item.regime: item for item in health.regime_attribution}
    weak = by_regime["negative-gamma|below-vwap"]
    assert weak.closed_observations == 2
    assert weak.expectancy_after_costs == Decimal("-0.10")
    assert weak.degraded is True
    assert "negative_expectancy" in weak.degradation_reasons
    assert "regime_degraded:negative-gamma|below-vwap" not in health.degradation_reasons
