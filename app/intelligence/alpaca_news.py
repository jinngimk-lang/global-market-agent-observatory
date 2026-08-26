from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from app.intelligence.models import ContextItem, ContextSource, EvidenceKind


class AlpacaNewsStream:
    """Normalize Alpaca's real-time news stream into typed context evidence."""

    url = "wss://stream.data.alpaca.markets/v1beta1/news"

    def __init__(
        self,
        *,
        symbols: set[str],
        api_key: str,
        api_secret: str,
        connect: Callable[[str], Any] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        normalized = {item.strip().upper() for item in symbols if item.strip()}
        if not normalized:
            raise ValueError("At least one news symbol is required")
        if not api_key or not api_secret:
            raise ValueError("Alpaca news credentials are required")
        self.symbols = normalized
        self.api_key = api_key
        self.api_secret = api_secret
        self._connect = connect or self._default_connect
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _default_connect(url: str):
        import websockets

        return websockets.connect(url)

    async def stream(self, *, limit: int | None = None) -> AsyncIterator[ContextItem]:
        emitted = 0
        async with self._connect(self.url) as websocket:
            connected = self._decode(await websocket.recv())
            if not self._is_success(connected, "connected"):
                raise RuntimeError("Alpaca news connection failed")

            await websocket.send(
                json.dumps(
                    {"action": "auth", "key": self.api_key, "secret": self.api_secret},
                    separators=(",", ":"),
                )
            )
            authenticated = self._decode(await websocket.recv())
            if not self._is_success(authenticated, "authenticated"):
                raise RuntimeError(
                    f"Alpaca news authentication failed: {self._first_message(authenticated)}"
                )

            await websocket.send(
                json.dumps(
                    {"action": "subscribe", "news": ["*"]},
                    separators=(",", ":"),
                )
            )
            subscription = self._decode(await websocket.recv())
            if not any(
                item.get("T") == "subscription" and "*" in item.get("news", [])
                for item in subscription
            ):
                raise RuntimeError(
                    f"Alpaca news subscription failed: {self._first_message(subscription)}"
                )

            while limit is None or emitted < limit:
                messages = self._decode(await websocket.recv())
                for message in messages:
                    if message.get("T") != "n":
                        continue
                    item = self._news_to_context(message)
                    if item is None:
                        continue
                    yield item
                    emitted += 1
                    if limit is not None and emitted >= limit:
                        return

    def _news_to_context(self, message: dict[str, Any]) -> ContextItem | None:
        provider_symbols = {
            str(symbol).strip().upper()
            for symbol in message.get("symbols", [])
            if str(symbol).strip()
        }
        relevant_symbols = sorted(provider_symbols & self.symbols)
        if not relevant_symbols:
            return None

        created_at = self._parse_timestamp(str(message["created_at"]))
        updated_at = self._parse_timestamp(
            str(message.get("updated_at") or message["created_at"])
        )
        ingested_at = self._normalize_timestamp(self._clock())
        headline = str(message.get("headline") or "").strip()
        if not headline:
            raise RuntimeError("Alpaca news item missing headline")
        summary = str(message.get("summary") or "").strip() or headline
        publisher = str(message.get("source") or "unknown").strip() or "unknown"
        author = str(message.get("author") or "").strip()
        tags = [f"publisher:{publisher}"]
        if author:
            tags.append(f"author:{author}")

        return ContextItem(
            item_id=f"alpaca-news:{message['id']}",
            symbols=relevant_symbols,
            category="news",
            label=headline,
            summary=summary,
            event_time=updated_at,
            published_at=created_at,
            source_updated_at=updated_at,
            ingested_at=ingested_at,
            freshness_sla_seconds=120,
            evidence_kind=EvidenceKind.FACT,
            confidence="1",
            tags=tags,
            source=ContextSource(
                provider="alpaca-news",
                source_type="news",
                official=False,
                coverage="provider news tagged to configured symbols",
                latency_class="realtime",
                source_url=str(message.get("url") or "").strip() or None,
            ),
        )

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return AlpacaNewsStream._normalize_timestamp(parsed)

    @staticmethod
    def _normalize_timestamp(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _decode(payload: str | bytes) -> list[dict[str, Any]]:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        data = json.loads(payload)
        if isinstance(data, dict):
            return [data]
        if not isinstance(data, list):
            raise RuntimeError("Unexpected Alpaca news websocket payload")
        return [item for item in data if isinstance(item, dict)]

    @staticmethod
    def _is_success(messages: list[dict[str, Any]], expected: str) -> bool:
        return any(
            item.get("T") == "success" and item.get("msg") == expected
            for item in messages
        )

    @staticmethod
    def _first_message(messages: list[dict[str, Any]]) -> str:
        if not messages:
            return "empty response"
        return str(messages[0].get("msg") or messages[0])
