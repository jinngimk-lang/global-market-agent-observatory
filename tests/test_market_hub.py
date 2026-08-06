from datetime import UTC, datetime, timedelta

import pytest

from app.domain.models import Candle
from app.market.binance import BinanceKlineFeed
from app.market.hub import MarketHub
from app.market.replay import ReplayFeed


def candle_at(minute: int, close: float) -> Candle:
    start = datetime(2026, 8, 6, 0, minute, tzinfo=UTC)
    return Candle(
        symbol="BTCUSDT",
        interval="1m",
        open_time=start,
        close_time=start + timedelta(minutes=1),
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        volume=10,
        source="test",
    )


@pytest.mark.asyncio
async def test_market_hub_fans_out_to_multiple_subscribers() -> None:
    hub = MarketHub(queue_size=2)
    item = candle_at(0, 100)

    async with hub.subscribe() as first, hub.subscribe() as second:
        await hub.publish(item)

        assert await first.get() == item
        assert await second.get() == item


@pytest.mark.asyncio
async def test_market_hub_drops_oldest_when_subscriber_is_slow() -> None:
    hub = MarketHub(queue_size=1)

    async with hub.subscribe() as queue:
        await hub.publish(candle_at(0, 100))
        await hub.publish(candle_at(1, 101))

        assert (await queue.get()).close == 101


def test_binance_kline_payload_is_normalized() -> None:
    payload = {
        "e": "kline",
        "E": 1785974460000,
        "s": "BTCUSDT",
        "k": {
            "t": 1785974400000,
            "T": 1785974459999,
            "s": "BTCUSDT",
            "i": "1m",
            "o": "100.0",
            "c": "105.0",
            "h": "110.0",
            "l": "95.0",
            "v": "12.5",
            "x": True,
        },
    }

    candle = BinanceKlineFeed.normalize(payload)

    assert candle.symbol == "BTCUSDT"
    assert candle.open == 100.0
    assert candle.close == 105.0
    assert candle.closed is True
    assert candle.source == "binance"


@pytest.mark.asyncio
async def test_replay_feed_is_deterministic() -> None:
    first = ReplayFeed(symbol="BTCUSDT", seed=7, delay_seconds=0)
    second = ReplayFeed(symbol="BTCUSDT", seed=7, delay_seconds=0)

    first_values = [item.close async for item in first.stream(limit=3)]
    second_values = [item.close async for item in second.stream(limit=3)]

    assert first_values == second_values
    assert len(first_values) == 3
