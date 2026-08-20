from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.models import Candle


class AlpacaStockBarFeed:
    """Normalize Alpaca real-time stock minute bars into repository Candles."""

    def __init__(
        self,
        *,
        symbols: set[str],
        api_key: str,
        api_secret: str,
        feed: str = "iex",
        connect: Callable[[str], Any] | None = None,
    ) -> None:
        normalized = {item.strip().upper() for item in symbols if item.strip()}
        if not normalized:
            raise ValueError("At least one stock symbol is required")
        if not api_key or not api_secret:
            raise ValueError("Alpaca market-data credentials are required")
        self.symbols = normalized
        self.api_key = api_key
        self.api_secret = api_secret
        self.feed = feed.strip().lower()
        self.url = f"wss://stream.data.alpaca.markets/v2/{self.feed}"
        self._connect = connect or self._default_connect

    @staticmethod
    def _default_connect(url: str):
        import websockets

        return websockets.connect(url)

    async def stream(self, *, limit: int | None = None) -> AsyncIterator[Candle]:
        emitted = 0
        async with self._connect(self.url) as websocket:
            connected = self._decode(await websocket.recv())
            if not self._is_success(connected, "connected"):
                raise RuntimeError("Alpaca market-data connection failed")

            await websocket.send(
                json.dumps(
                    {"action": "auth", "key": self.api_key, "secret": self.api_secret},
                    separators=(",", ":"),
                )
            )
            authenticated = self._decode(await websocket.recv())
            if not self._is_success(authenticated, "authenticated"):
                message = self._first_message(authenticated)
                raise RuntimeError(f"Alpaca authentication failed: {message}")

            symbols = sorted(self.symbols)
            await websocket.send(
                json.dumps(
                    {"action": "subscribe", "bars": symbols},
                    separators=(",", ":"),
                )
            )
            subscription = self._decode(await websocket.recv())
            if not any(item.get("T") == "subscription" for item in subscription):
                message = self._first_message(subscription)
                raise RuntimeError(f"Alpaca subscription failed: {message}")

            while limit is None or emitted < limit:
                messages = self._decode(await websocket.recv())
                for item in messages:
                    if item.get("T") not in {"b", "u"}:
                        continue
                    candle = self._bar_to_candle(item)
                    if candle.symbol not in self.symbols:
                        continue
                    yield candle
                    emitted += 1
                    if limit is not None and emitted >= limit:
                        return

    def _bar_to_candle(self, item: dict[str, Any]) -> Candle:
        opened = self._parse_timestamp(str(item["t"]))
        source = f"alpaca:{self.feed}"
        if item.get("T") == "u":
            source = f"{source}:updated"
        return Candle(
            symbol=str(item["S"]),
            interval="1m",
            open_time=opened,
            close_time=opened + timedelta(minutes=1),
            open=float(item["o"]),
            high=float(item["h"]),
            low=float(item["l"]),
            close=float(item["c"]),
            volume=float(item["v"]),
            source=source,
            closed=True,
        )

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _decode(payload: str | bytes) -> list[dict[str, Any]]:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        data = json.loads(payload)
        if isinstance(data, dict):
            return [data]
        if not isinstance(data, list):
            raise RuntimeError("Unexpected Alpaca websocket payload")
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
