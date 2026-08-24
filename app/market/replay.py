from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from app.domain.models import Candle


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

    async def stream(self, *, limit: int | None = None) -> AsyncIterator[Candle]:
        rng = random.Random(self.seed)
        price = self.start_price
        count = 0
        open_time = self.start_time or datetime.now(UTC).replace(second=0, microsecond=0)
        while limit is None or count < limit:
            movement = rng.gauss(0, max(price * 0.0015, 1))
            close = max(price + movement, 0.01)
            spread = abs(rng.gauss(0, max(price * 0.0008, 0.5)))
            volume = max(rng.lognormvariate(2.5, 0.5), 0.01)
            yield Candle(
                symbol=self.symbol,
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
            price = close
            open_time += timedelta(minutes=1)
            count += 1
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
