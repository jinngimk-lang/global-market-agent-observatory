from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from app.domain.models import Candle

# Replay is explicitly simulated data. These are seed anchors for local UI and
# strategy verification only; they are not market quotes and must never be
# presented as live provider prices.
_REPLAY_DASHBOARD_SYMBOLS = {"BTCUSDT", "NVDA", "KLAC", "SPCX"}
_REPLAY_START_PRICES = {
    "BTCUSDT": 60000.0,
    "NVDA": 120.0,
    "KLAC": 800.0,
    "SPCX": 100.0,
}


class ReplayFeed:
    def __init__(
        self,
        *,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        seed: int = 42,
        delay_seconds: float = 0.4,
        start_price: float = 60000.0,
        start_time: datetime | None = None,
    ) -> None:
        self.symbol = symbol.strip().upper()
        self.symbols = set(_REPLAY_DASHBOARD_SYMBOLS) | {self.symbol}
        self.interval = interval
        self.seed = seed
        self.delay_seconds = delay_seconds
        self.start_price = start_price
        if start_time is None:
            self.start_time = None
        elif start_time.tzinfo is None:
            self.start_time = start_time.replace(tzinfo=UTC)
        else:
            self.start_time = start_time.astimezone(UTC)

    def _initial_price(self, symbol: str) -> float:
        if symbol == self.symbol:
            # ApplicationState passes 60000 when no persisted primary candle
            # exists. For an equity primary, use a clearly synthetic equity
            # anchor instead of making it look like a $60k stock quote.
            if self.start_price != 60000.0 or symbol == "BTCUSDT":
                return self.start_price
        return _REPLAY_START_PRICES.get(symbol, 100.0)

    async def stream(self, *, limit: int | None = None) -> AsyncIterator[Candle]:
        symbols = sorted(self.symbols)
        rngs = {
            symbol: random.Random(f"{self.seed}:{symbol}")
            for symbol in symbols
        }
        prices = {symbol: self._initial_price(symbol) for symbol in symbols}
        base_time = self.start_time or datetime.now(UTC).replace(second=0, microsecond=0)
        open_times = {symbol: base_time for symbol in symbols}
        count = 0

        while limit is None or count < limit:
            for symbol in symbols:
                if limit is not None and count >= limit:
                    return
                rng = rngs[symbol]
                price = prices[symbol]
                open_time = open_times[symbol]
                movement = rng.gauss(0, max(price * 0.0015, 0.05))
                close = max(price + movement, 0.01)
                spread = abs(rng.gauss(0, max(price * 0.0008, 0.02)))
                volume = max(rng.lognormvariate(2.5, 0.5), 0.01)
                yield Candle(
                    symbol=symbol,
                    interval=self.interval,
                    open_time=open_time,
                    close_time=open_time + timedelta(minutes=1),
                    open=round(price, 8),
                    high=round(max(price, close) + spread, 8),
                    low=round(max(min(price, close) - spread, 0.01), 8),
                    close=round(close, 8),
                    volume=round(volume, 8),
                    source="replay",
                    closed=True,
                )
                prices[symbol] = close
                open_times[symbol] = open_time + timedelta(minutes=1)
                count += 1

            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
