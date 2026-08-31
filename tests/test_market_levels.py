from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.models import Candle


def candle(index: int, *, high: float, low: float, close: float) -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index)
    return Candle(
        symbol="NVDA",
        interval="1d",
        open_time=opened,
        close_time=opened + timedelta(days=1),
        open=close,
        high=high,
        low=low,
        close=close,
        volume=1_000_000,
        source="alpaca:iex:historical",
    )


def test_levels_choose_nearest_confirmed_pivots_around_latest_close() -> None:
    from app.market.levels import derive_support_resistance

    candles = [
        candle(0, high=110, low=100, close=105),
        candle(1, high=112, low=101, close=108),
        candle(2, high=115, low=99, close=110),
        candle(3, high=121, low=104, close=118),  # confirmed swing high
        candle(4, high=117, low=102, close=107),
        candle(5, high=114, low=96, close=101),   # confirmed swing low
        candle(6, high=116, low=100, close=112),
        candle(7, high=124, low=107, close=122),  # confirmed swing high
        candle(8, high=119, low=105, close=111),
        candle(9, high=118, low=98, close=103),   # confirmed swing low
        candle(10, high=120, low=104, close=115),
    ]

    levels = derive_support_resistance(candles, pivot_width=1, lookback=50)

    assert levels.latest_close == 115
    assert levels.support == 98
    assert levels.resistance == 121
    assert levels.support_method == "confirmed-pivot"
    assert levels.resistance_method == "confirmed-pivot"
    assert levels.methodology == "confirmed-price-pivots"
    assert levels.observation_count == len(candles)


def test_levels_fall_back_to_lookback_extrema_when_no_pivot_qualifies() -> None:
    from app.market.levels import derive_support_resistance

    candles = [
        candle(0, high=101, low=99, close=100),
        candle(1, high=102, low=100, close=101),
        candle(2, high=103, low=101, close=102),
        candle(3, high=104, low=102, close=103),
    ]

    levels = derive_support_resistance(candles, pivot_width=1, lookback=20)

    assert levels.support == 99
    assert levels.resistance == 104
    assert levels.support_method == "lookback-extreme"
    assert levels.resistance_method == "lookback-extreme"


def test_levels_do_not_invent_values_with_insufficient_history() -> None:
    from app.market.levels import derive_support_resistance

    levels = derive_support_resistance(
        [candle(0, high=101, low=99, close=100)],
        pivot_width=2,
        lookback=60,
    )

    assert levels.support is None
    assert levels.resistance is None
    assert levels.support_method == "insufficient-history"
    assert levels.resistance_method == "insufficient-history"
