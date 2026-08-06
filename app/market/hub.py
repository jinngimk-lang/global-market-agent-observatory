from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.domain.models import Candle


class MarketHub:
    def __init__(self, *, queue_size: int = 100) -> None:
        if queue_size < 1:
            raise ValueError("queue_size must be at least 1")
        self._queue_size = queue_size
        self._subscribers: set[asyncio.Queue[Candle]] = set()
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[Candle]]:
        queue: asyncio.Queue[Candle] = asyncio.Queue(maxsize=self._queue_size)
        async with self._lock:
            self._subscribers.add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                self._subscribers.discard(queue)

    async def publish(self, candle: Candle) -> None:
        async with self._lock:
            subscribers = tuple(self._subscribers)
        for queue in subscribers:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(candle)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
