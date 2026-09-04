from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.intelligence.models import ContextItem, SymbolContextSnapshot
from app.intelligence.store import SQLiteContextStore


class ContextSourceHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    configured: bool
    running: bool
    failure_count: int = 0
    last_success_at: datetime | None = None
    last_event_at: datetime | None = None
    last_error: str | None = None
    retry_seconds: float | None = None


@dataclass
class _MutableSourceHealth:
    configured: bool
    failure_count: int = 0
    last_success_at: datetime | None = None
    last_event_at: datetime | None = None
    last_error: str | None = None
    retry_seconds: float | None = None


class ContextIntelligenceService:
    """Own isolated context-source loops and assemble read-only symbol snapshots."""

    def __init__(
        self,
        *,
        store: SQLiteContextStore,
        symbols: set[str],
        news_stream: Any | None = None,
        sec_client: Any | None = None,
        government_client: Any | None = None,
        sec_poll_seconds: float = 60.0,
        government_poll_seconds: float = 300.0,
        retry_seconds: float = 1.0,
        retry_max_seconds: float = 30.0,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        normalized_symbols = {
            symbol.strip().upper() for symbol in symbols if symbol.strip()
        }
        if not normalized_symbols:
            raise ValueError("Context intelligence requires at least one symbol")
        if sec_poll_seconds <= 0 or government_poll_seconds <= 0:
            raise ValueError("Context polling intervals must be positive")
        if retry_seconds <= 0 or retry_max_seconds <= 0:
            raise ValueError("Context retry intervals must be positive")
        if retry_seconds > retry_max_seconds:
            raise ValueError("Context retry_seconds must be <= retry_max_seconds")

        self.store = store
        self.symbols = normalized_symbols
        self.news_stream = news_stream
        self.sec_client = sec_client
        self.government_client = government_client
        self.sec_poll_seconds = sec_poll_seconds
        self.government_poll_seconds = government_poll_seconds
        self.retry_seconds = retry_seconds
        self.retry_max_seconds = retry_max_seconds
        self._clock = clock or (lambda: datetime.now(UTC))

        self._source_state = {
            "alpaca-news": _MutableSourceHealth(configured=news_stream is not None),
            "sec-edgar": _MutableSourceHealth(configured=sec_client is not None),
            "federal-register": _MutableSourceHealth(
                configured=government_client is not None
            ),
        }
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self) -> None:
        if self.news_stream is not None and "alpaca-news" not in self._tasks:
            self._tasks["alpaca-news"] = asyncio.create_task(
                self._run_news(),
                name="context-alpaca-news",
            )
        if self.sec_client is not None and "sec-edgar" not in self._tasks:
            self._tasks["sec-edgar"] = asyncio.create_task(
                self._run_sec(),
                name="context-sec-edgar",
            )
        if (
            self.government_client is not None
            and "federal-register" not in self._tasks
        ):
            self._tasks["federal-register"] = asyncio.create_task(
                self._run_government(),
                name="context-federal-register",
            )

    async def stop(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

        closed: set[int] = set()
        for client in (self.news_stream, self.sec_client, self.government_client):
            if client is None or id(client) in closed:
                continue
            closed.add(id(client))
            close = getattr(client, "close", None)
            if close is None:
                continue
            result = close()
            if result is not None and hasattr(result, "__await__"):
                await result

    def snapshot(
        self,
        symbol: str,
        *,
        flow_items: list[ContextItem] | None = None,
        limit_per_category: int = 20,
    ) -> SymbolContextSnapshot:
        normalized = symbol.strip().upper()
        if normalized not in self.symbols:
            raise LookupError(f"{normalized} is outside the configured context universe")
        if limit_per_category <= 0:
            raise ValueError("limit_per_category must be positive")

        flow = [
            item
            for item in (flow_items or [])
            if normalized in item.symbols and item.category == "flow"
        ]
        flow.sort(key=lambda item: (item.event_time, item.item_id), reverse=True)
        return SymbolContextSnapshot(
            symbol=normalized,
            generated_at=self._now(),
            news=self.store.recent(
                normalized,
                category="news",
                limit=limit_per_category,
            ),
            filings=self.store.recent(
                normalized,
                category="filing",
                limit=limit_per_category,
            ),
            government=self.store.recent(
                normalized,
                category="government",
                limit=limit_per_category,
            ),
            flow=flow[:limit_per_category],
        )

    def source_health(self) -> dict[str, ContextSourceHealth]:
        result: dict[str, ContextSourceHealth] = {}
        for source, state in self._source_state.items():
            task = self._tasks.get(source)
            result[source] = ContextSourceHealth(
                source=source,
                configured=state.configured,
                running=task is not None and not task.done(),
                failure_count=state.failure_count,
                last_success_at=state.last_success_at,
                last_event_at=state.last_event_at,
                last_error=state.last_error,
                retry_seconds=state.retry_seconds,
            )
        return result

    async def refresh_sec_once(self) -> None:
        if self.sec_client is None:
            return
        source = "sec-edgar"
        successful_symbols = 0
        errors: list[str] = []
        for symbol in sorted(self.symbols):
            since_accession = self._latest_accession(symbol)
            try:
                items = await self.sec_client.fetch_recent(
                    symbol,
                    since_accession=since_accession,
                )
            except asyncio.CancelledError:
                raise
            except LookupError:
                continue
            except Exception as exc:
                errors.append(f"{symbol}: {type(exc).__name__}: {exc}")
                continue
            successful_symbols += 1
            for item in items:
                self._record(source, item)

        state = self._source_state[source]
        if successful_symbols:
            state.last_success_at = self._now()
            state.last_error = None if not errors else "; ".join(errors)
        elif errors:
            raise RuntimeError("; ".join(errors))

    async def refresh_government_once(self) -> None:
        if self.government_client is None:
            return
        source = "federal-register"
        successful_symbols = 0
        errors: list[str] = []
        for symbol in sorted(self.symbols):
            try:
                items = await self.government_client.fetch_recent(symbol)
            except asyncio.CancelledError:
                raise
            except LookupError:
                continue
            except Exception as exc:
                errors.append(f"{symbol}: {type(exc).__name__}: {exc}")
                continue
            successful_symbols += 1
            for item in items:
                self._record(source, item)

        state = self._source_state[source]
        if successful_symbols:
            state.last_success_at = self._now()
            state.last_error = None if not errors else "; ".join(errors)
        elif errors:
            raise RuntimeError("; ".join(errors))

    async def _run_news(self) -> None:
        source = "alpaca-news"
        retry = self.retry_seconds
        while True:
            try:
                async for item in self.news_stream.stream():
                    self._record(source, item)
                    retry = self.retry_seconds
                raise RuntimeError("Alpaca news stream ended")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                state = self._source_state[source]
                state.failure_count += 1
                state.last_error = f"{type(exc).__name__}: {exc}"
                state.retry_seconds = retry
                await asyncio.sleep(retry)
                retry = min(self.retry_max_seconds, retry * 2)

    async def _run_sec(self) -> None:
        await self._run_polling_source(
            source="sec-edgar",
            refresh=self.refresh_sec_once,
            interval=self.sec_poll_seconds,
        )

    async def _run_government(self) -> None:
        await self._run_polling_source(
            source="federal-register",
            refresh=self.refresh_government_once,
            interval=self.government_poll_seconds,
        )

    async def _run_polling_source(
        self,
        *,
        source: str,
        refresh: Callable[[], Any],
        interval: float,
    ) -> None:
        retry = self.retry_seconds
        while True:
            try:
                await refresh()
                state = self._source_state[source]
                state.last_success_at = self._now()
                state.last_error = None
                state.retry_seconds = None
                retry = self.retry_seconds
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                state = self._source_state[source]
                state.failure_count += 1
                state.last_error = f"{type(exc).__name__}: {exc}"
                state.retry_seconds = retry
                await asyncio.sleep(retry)
                retry = min(self.retry_max_seconds, retry * 2)

    def _record(self, source: str, item: ContextItem) -> None:
        self.store.upsert(item)
        state = self._source_state[source]
        now = self._now()
        state.last_event_at = item.event_time
        state.last_success_at = now
        state.last_error = None
        state.retry_seconds = None

    def _latest_accession(self, symbol: str) -> str | None:
        for item in self.store.recent(symbol, category="filing", limit=1):
            for tag in item.tags:
                if tag.startswith("accession:"):
                    accession = tag.removeprefix("accession:").strip()
                    return accession or None
        return None

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
