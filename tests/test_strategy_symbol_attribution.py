from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.models import TradingMode
from app.innovation.store import SQLiteStrategyEvidenceStore
from app.learning.models import StrategyObservation, StrategyObservationStatus
from app.learning.service import StrategyLearningService
from app.learning.store import SQLiteStrategyLearningStore
from app.strategy.base import StrategyAction


def closed_observation(index: int, symbol: str, net_return: str) -> StrategyObservation:
    observed = datetime(2026, 8, 20, 14, 0, tzinfo=UTC) + timedelta(minutes=index)
    return StrategyObservation(
        observation_id=f"{symbol}-{index}",
        strategy_id="vwap",
        version="1.0.0",
        symbol=symbol,
        mode=TradingMode.REPLAY,
        action=StrategyAction.BUY,
        entry_price=Decimal("100"),
        observed_at=observed,
        due_at=observed + timedelta(minutes=1),
        transaction_cost_bps=Decimal("0"),
        status=StrategyObservationStatus.CLOSED,
        exit_price=Decimal("100"),
        net_return=Decimal(net_return),
        closed_at=observed + timedelta(minutes=1),
    )


def test_symbol_degradation_cannot_hide_inside_aggregate_expectancy(tmp_path) -> None:
    learning_store = SQLiteStrategyLearningStore(tmp_path / "learning.db")
    service = StrategyLearningService(
        store=learning_store,
        evidence_store=SQLiteStrategyEvidenceStore(tmp_path / "evidence.db"),
        mode=TradingMode.REPLAY,
        evaluation_horizon_seconds=60,
        transaction_cost_bps=Decimal("0"),
        health_policy={
            "min_observations": 2,
            "window_observations": 20,
            "min_expectancy_after_costs": Decimal("0"),
            "max_drawdown": Decimal("0.25"),
        },
    )

    # Aggregate expectancy is strongly positive because NVDA wins dominate.
    for index, value in enumerate(["0.30", "0.30", "0.30", "0.30"]):
        learning_store.add_observation(closed_observation(index, "NVDA", value))
    learning_store.add_observation(closed_observation(10, "KLAC", "-0.10"))
    learning_store.add_observation(closed_observation(11, "KLAC", "-0.10"))

    health = service.refresh_strategy("vwap", "1.0.0")

    assert health.expectancy_after_costs > 0
    by_symbol = {item.symbol: item for item in health.symbol_attribution}
    assert by_symbol["NVDA"].degraded is False
    assert by_symbol["KLAC"].closed_observations == 2
    assert by_symbol["KLAC"].expectancy_after_costs == Decimal("-0.10")
    assert by_symbol["KLAC"].degraded is True
    assert "negative_expectancy" in by_symbol["KLAC"].degradation_reasons
    assert health.degraded is True
    assert "symbol_degraded:KLAC" in health.degradation_reasons


def test_symbol_attribution_respects_minimum_sample_size(tmp_path) -> None:
    learning_store = SQLiteStrategyLearningStore(tmp_path / "learning.db")
    service = StrategyLearningService(
        store=learning_store,
        evidence_store=SQLiteStrategyEvidenceStore(tmp_path / "evidence.db"),
        mode=TradingMode.REPLAY,
        evaluation_horizon_seconds=60,
        transaction_cost_bps=Decimal("0"),
        health_policy={
            "min_observations": 3,
            "window_observations": 20,
            "min_expectancy_after_costs": Decimal("0"),
            "max_drawdown": Decimal("0.25"),
        },
    )
    learning_store.add_observation(closed_observation(0, "KLAC", "-0.50"))

    health = service.refresh_strategy("vwap", "1.0.0")
    klac = health.symbol_attribution[0]

    assert klac.symbol == "KLAC"
    assert klac.closed_observations == 1
    assert klac.degraded is False
    assert health.degraded is False
