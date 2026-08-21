from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app.market.options_structure import OptionsStructureService

from app.api.state import ApplicationState
from app.domain.models import Candle, TradingMode
from app.market.alpaca_options import OptionChainObservation, OptionContractObservation
from app.market.options import OptionRight
from app.settings import Settings
from app.strategy.base import StrategyAction, StrategyInput, StrategySignal, hold_signal


class FakeOptionsChainSource:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, date, date, datetime | None]] = []

    async def fetch_chain(
        self,
        underlying_symbol: str,
        *,
        expiration_date_gte: date,
        expiration_date_lte: date,
        fetched_at: datetime | None = None,
    ) -> OptionChainObservation:
        self.calls.append(
            (
                underlying_symbol,
                expiration_date_gte,
                expiration_date_lte,
                fetched_at,
            )
        )
        if self.fail:
            raise RuntimeError("options unavailable")
        observed = fetched_at or datetime.now(UTC)
        expiry = expiration_date_lte
        return OptionChainObservation(
            feed="indicative",
            underlying_symbol=underlying_symbol,
            fetched_at=observed,
            contracts=[
                OptionContractObservation(
                    feed="indicative",
                    underlying_symbol=underlying_symbol,
                    contract_symbol=f"{underlying_symbol}-CALL",
                    right=OptionRight.CALL,
                    expiration_date=expiry,
                    strike=Decimal("105"),
                    open_interest=Decimal("1200"),
                    open_interest_date=observed.date() - timedelta(days=1),
                    gamma=Decimal("0.02"),
                    market_data_updated_at=observed,
                    fetched_at=observed,
                    open_interest_source="https://paper-api.alpaca.markets/v2/options/contracts",
                    greeks_source=(
                        "https://data.alpaca.markets/v1beta1/options/snapshots/"
                        f"{underlying_symbol}"
                    ),
                ),
                OptionContractObservation(
                    feed="indicative",
                    underlying_symbol=underlying_symbol,
                    contract_symbol=f"{underlying_symbol}-PUT",
                    right=OptionRight.PUT,
                    expiration_date=expiry,
                    strike=Decimal("95"),
                    open_interest=Decimal("1400"),
                    open_interest_date=observed.date() - timedelta(days=1),
                    gamma=Decimal("0.03"),
                    market_data_updated_at=observed,
                    fetched_at=observed,
                    open_interest_source="https://paper-api.alpaca.markets/v2/options/contracts",
                    greeks_source=(
                        "https://data.alpaca.markets/v1beta1/options/snapshots/"
                        f"{underlying_symbol}"
                    ),
                ),
            ],
        )


class WallAwareStrategy:
    strategy_id = "wall-aware"
    version = "1.0.0"

    def evaluate(self, market: StrategyInput) -> StrategySignal:
        if market.structure.put_wall is not None:
            return StrategySignal(
                strategy_id=self.strategy_id,
                version=self.version,
                symbol=market.symbol,
                action=StrategyAction.BUY,
                confidence=Decimal("0.7"),
                rationale_codes=["fresh_put_wall"],
                entry_price=market.current_price,
                generated_at=market.observed_at,
            )
        return hold_signal(
            strategy_id=self.strategy_id,
            version=self.version,
            market=market,
            rationale_code="no_fresh_wall",
        )


def candle(at: datetime, close: str = "100") -> Candle:
    return Candle(
        symbol="NVDA",
        interval="1m",
        open_time=at - timedelta(minutes=1),
        close_time=at,
        open=float(close),
        high=float(close),
        low=float(close),
        close=float(close),
        volume=1000,
        source="test",
    )


@pytest.mark.asyncio
async def test_options_structure_service_builds_gex_walls_with_provenance() -> None:
    source = FakeOptionsChainSource()
    service = OptionsStructureService(
        source=source,
        expiration_horizon_days=28,
        max_age_seconds=120,
    )
    observed = datetime(2026, 8, 21, 14, 0, tzinfo=UTC)

    structure = await service.refresh("NVDA", Decimal("100"), observed_at=observed)

    assert structure.symbol == "NVDA"
    assert structure.call_wall == Decimal("105")
    assert structure.put_wall == Decimal("95")
    assert structure.net_gex_1pct is not None
    assert structure.methodology["options_provider"] == "alpaca"
    assert structure.methodology["options_feed"] == "indicative"
    assert structure.methodology["open_interest_source"].endswith("/v2/options/contracts")
    assert structure.methodology["greeks_source"].endswith("/NVDA")
    assert service.structure_for("NVDA", observed + timedelta(seconds=119)) is not None
    assert service.structure_for("NVDA", observed + timedelta(seconds=121)) is None


@pytest.mark.asyncio
async def test_application_state_runs_options_structure_task_when_source_is_configured(
    tmp_path,
) -> None:
    source = FakeOptionsChainSource()
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "options-loop.db"),
            strategy_learning_enabled=False,
            options_structure_enabled=True,
            options_structure_refresh_seconds=0.01,
        ),
        options_chain_source=source,
    )

    await state.start()
    try:
        assert state._options_structure_task is not None
        assert state._options_structure_task.get_name() == "options-structure"
    finally:
        await state.stop()


@pytest.mark.asyncio
async def test_process_candle_only_uses_fresh_options_structure(tmp_path) -> None:
    source = FakeOptionsChainSource()
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "options-freshness.db"),
            trading_mode=TradingMode.REPLAY,
            strategy_learning_enabled=False,
            options_structure_enabled=True,
            options_structure_max_age_seconds=60,
        ),
        options_chain_source=source,
    )
    strategy = WallAwareStrategy()
    state.strategies = [strategy]
    state.autonomous._strategies = [strategy]
    observed = datetime(2026, 8, 21, 14, 0, tzinfo=UTC)
    state.store.upsert_candle(candle(observed))

    await state.refresh_options_structure_once(observed_at=observed)
    fresh_cycle = await state.process_candle(candle(observed + timedelta(seconds=30)))
    stale_cycle = await state.process_candle(candle(observed + timedelta(seconds=90)))

    assert fresh_cycle.signals[0].action is StrategyAction.BUY
    assert fresh_cycle.signals[0].rationale_codes == ["fresh_put_wall"]
    assert stale_cycle.signals[0].action is StrategyAction.HOLD
    assert stale_cycle.signals[0].rationale_codes == ["no_fresh_wall"]


@pytest.mark.asyncio
async def test_options_refresh_failure_invalidates_previous_structure(tmp_path) -> None:
    source = FakeOptionsChainSource()
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "options-failure.db"),
            strategy_learning_enabled=False,
            options_structure_enabled=True,
            options_structure_max_age_seconds=300,
        ),
        options_chain_source=source,
    )
    observed = datetime(2026, 8, 21, 14, 0, tzinfo=UTC)
    state.store.upsert_candle(candle(observed))
    await state.refresh_options_structure_once(observed_at=observed)
    assert state.options_structure.structure_for("NVDA", observed) is not None

    source.fail = True
    await state.refresh_options_structure_once(observed_at=observed + timedelta(seconds=10))

    assert state.options_structure.structure_for(
        "NVDA", observed + timedelta(seconds=10)
    ) is None
    assert "RuntimeError: options unavailable" in state.options_structure_errors["NVDA"]
