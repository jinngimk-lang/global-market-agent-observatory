from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.models import TradingMode
from app.innovation.store import SQLiteStrategyEvidenceStore
from app.learning.models import (
    StrategyEntryPriceSource,
    StrategyObservation,
    StrategyObservationStatus,
)
from app.learning.service import StrategyLearningService
from app.learning.store import SQLiteStrategyLearningStore
from app.strategy.base import StrategyAction


def observation(
    index: int,
    *,
    source: StrategyEntryPriceSource,
    slippage_bps: Decimal | None = None,
    latency_seconds: Decimal | None = None,
) -> StrategyObservation:
    observed = datetime(2026, 8, 25, 14, 0, tzinfo=UTC) + timedelta(minutes=index)
    return StrategyObservation(
        observation_id=f"friction-{index}",
        strategy_id="vwap",
        version="1.0.0",
        symbol="NVDA",
        mode=TradingMode.REPLAY,
        action=StrategyAction.BUY,
        signal_entry_price=Decimal("100"),
        entry_price=Decimal("100"),
        entry_price_source=source,
        modeled_entry_slippage_bps=Decimal("5"),
        modeled_exit_slippage_bps=Decimal("7"),
        observed_entry_slippage_bps=slippage_bps,
        execution_latency_seconds=latency_seconds,
        execution_client_order_id=(
            f"order-{index}" if source is StrategyEntryPriceSource.OBSERVED_FILL else None
        ),
        observed_at=observed,
        due_at=observed + timedelta(minutes=1),
        transaction_cost_bps=Decimal("10"),
        status=StrategyObservationStatus.CLOSED,
        exit_price=Decimal("101"),
        net_return=Decimal("0.01"),
        closed_at=observed + timedelta(minutes=1),
    )


def test_health_separates_observed_execution_from_modeled_friction(tmp_path) -> None:
    database = tmp_path / "friction-attribution.db"
    store = SQLiteStrategyLearningStore(database)
    service = StrategyLearningService(
        store=store,
        evidence_store=SQLiteStrategyEvidenceStore(database),
        mode=TradingMode.REPLAY,
        evaluation_horizon_seconds=60,
        transaction_cost_bps=Decimal("10"),
        modeled_entry_slippage_bps=Decimal("5"),
        modeled_exit_slippage_bps=Decimal("7"),
    )
    store.add_observation(
        observation(0, source=StrategyEntryPriceSource.MODELED)
    )
    store.add_observation(
        observation(
            1,
            source=StrategyEntryPriceSource.OBSERVED_FILL,
            slippage_bps=Decimal("20"),
            latency_seconds=Decimal("2"),
        )
    )
    store.add_observation(
        observation(
            2,
            source=StrategyEntryPriceSource.OBSERVED_FILL,
            slippage_bps=Decimal("-10"),
            latency_seconds=Decimal("4"),
        )
    )

    health = service.refresh_strategy("vwap", "1.0.0")
    friction = health.execution_friction

    assert friction.closed_observations == 3
    assert friction.modeled_entry_observations == 1
    assert friction.observed_fill_observations == 2
    assert friction.observed_fill_rate == Decimal("0.6666666666666666666666666667")
    assert friction.mean_observed_entry_slippage_bps == Decimal("5")
    assert friction.mean_execution_latency_seconds == Decimal("3")
    assert friction.current_transaction_cost_bps == Decimal("10")
    assert friction.current_modeled_entry_slippage_bps == Decimal("5")
    assert friction.current_modeled_exit_slippage_bps == Decimal("7")
