from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.api.state import ApplicationState
from app.domain.models import Candle, TradingState
from app.settings import Settings


class FlakyMarketFeed:
    def __init__(self) -> None:
        self.attempts = 0

    async def stream(self):
        self.attempts += 1
        if self.attempts == 1:
            raise RuntimeError("market websocket disconnected")
        observed = datetime(2026, 8, 21, 14, 0, tzinfo=UTC)
        yield Candle(
            symbol="NVDA",
            interval="1m",
            open_time=observed - timedelta(minutes=1),
            close_time=observed,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000,
            source="test-reconnected",
        )


@pytest.mark.asyncio
async def test_market_feed_reconnects_after_stream_exception(tmp_path) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "market-feed-resilience.db"),
            strategy_learning_enabled=False,
            options_structure_enabled=False,
            market_feed_retry_seconds=0.01,
        )
    )
    feed = FlakyMarketFeed()
    state.feed = feed

    await state._run_feed()

    assert feed.attempts == 2
    assert state.market_feed_failure_count == 1
    assert state.last_market_feed_error == "RuntimeError: market websocket disconnected"
    assert state.last_cycle_results["NVDA"].symbol == "NVDA"


@pytest.mark.asyncio
async def test_market_feed_disconnect_halts_autonomous_risk_but_keeps_reconnecting(
    tmp_path,
) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "market-feed-fail-closed.db"),
            strategy_learning_enabled=False,
            options_structure_enabled=False,
            market_feed_retry_seconds=0.01,
        )
    )
    state.autonomous._execution_enabled = True
    feed = FlakyMarketFeed()
    state.feed = feed

    await state._run_feed()

    assert feed.attempts == 2
    assert state.trading_state is TradingState.HALTED
    assert state.market_feed_failure_count == 1
    assert state.last_cycle_results["NVDA"].symbol == "NVDA"
