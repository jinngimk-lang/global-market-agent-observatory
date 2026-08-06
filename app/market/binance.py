from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import websockets

from app.domain.models import Candle


class BinanceKlineFeed:
    def __init__(
        self,
        *,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        endpoint: str = "wss://stream.binance.com:9443/ws",
    ) -> None:
        self.symbol = symbol.strip().upper()
        self.interval = interval
        self.endpoint = endpoint.rstrip("/")

    @property
    def url(self) -> str:
        return f"{self.endpoint}/{self.symbol.lower()}@kline_{self.interval}"

    async def stream(self, *, limit: int | None = None) -> AsyncIterator[Candle]:
        emitted = 0
        backoff = 1.0
        while limit is None or emitted < limit:
            try:
                async with websockets.connect(
                    self.url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=10,
                    max_queue=32,
                ) as socket:
                    backoff = 1.0
                    async for raw in socket:
                        payload = json.loads(raw)
                        if payload.get("e") != "kline":
                            continue
                        yield self.normalize(payload)
                        emitted += 1
                        if limit is not None and emitted >= limit:
                            return
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    @staticmethod
    def normalize(payload: dict[str, Any]) -> Candle:
        kline = payload["k"]
        return Candle(
            symbol=kline.get("s") or payload["s"],
            interval=kline["i"],
            open_time=datetime.fromtimestamp(kline["t"] / 1000, tz=UTC),
            close_time=datetime.fromtimestamp(kline["T"] / 1000, tz=UTC),
            open=float(kline["o"]),
            high=float(kline["h"]),
            low=float(kline["l"]),
            close=float(kline["c"]),
            volume=float(kline["v"]),
            source="binance",
            closed=bool(kline["x"]),
        )
