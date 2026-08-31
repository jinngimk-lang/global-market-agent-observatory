from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import Candle

_TIMEFRAME_INTERVALS = {
    "1Day": "1d",
    "1Week": "1w",
    "1Month": "1mo",
}


class HistoricalBarsResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: str
    feed: str
    coverage: str
    fetched_at: datetime
    candles: list[Candle] = Field(default_factory=list)


class AlpacaHistoricalBarsClient:
    """Read verified US-equity historical bars from Alpaca's data API.

    Credentials stay on the server. Only explicitly reviewed dashboard
    timeframes are accepted so UI labels cannot silently drift from provider
    semantics.
    """

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        feed: str = "iex",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError("Alpaca historical market-data credentials are required")
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
        }
        self.feed = feed.strip().lower()
        if not self.feed:
            raise ValueError("feed is required")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url="https://data.alpaca.markets",
            timeout=20.0,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch(
        self,
        symbol: str,
        *,
        timeframe: str,
        limit: int = 240,
        fetched_at: datetime | None = None,
    ) -> HistoricalBarsResult:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol is required")
        if timeframe not in _TIMEFRAME_INTERVALS:
            raise ValueError(
                "timeframe must be one of: " + ", ".join(_TIMEFRAME_INTERVALS)
            )
        if limit <= 0 or limit > 10_000:
            raise ValueError("limit must be in [1, 10000]")

        response = await self._client.get(
            f"/v2/stocks/{normalized_symbol}/bars",
            params={
                "timeframe": timeframe,
                "limit": limit,
                "feed": self.feed,
                "adjustment": "raw",
                "sort": "asc",
            },
            headers=self._headers,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected Alpaca historical bars payload")
        raw_bars = payload.get("bars")
        if not isinstance(raw_bars, list):
            raise RuntimeError("Unexpected Alpaca historical bars payload: bars payload is not a list")

        observed = fetched_at or datetime.now(UTC)
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=UTC)
        observed = observed.astimezone(UTC)
        interval = _TIMEFRAME_INTERVALS[timeframe]
        source = f"alpaca:{self.feed}:historical"
        candles = [
            self._normalize_bar(
                normalized_symbol,
                timeframe=timeframe,
                interval=interval,
                source=source,
                item=item,
            )
            for item in raw_bars
            if isinstance(item, dict)
        ]

        return HistoricalBarsResult(
            symbol=normalized_symbol,
            timeframe=timeframe,
            feed=self.feed,
            coverage=self._coverage(self.feed),
            fetched_at=observed,
            candles=candles,
        )

    @classmethod
    def _normalize_bar(
        cls,
        symbol: str,
        *,
        timeframe: str,
        interval: str,
        source: str,
        item: dict[str, Any],
    ) -> Candle:
        required = ("t", "o", "h", "l", "c", "v")
        if any(key not in item for key in required):
            raise RuntimeError("Malformed Alpaca historical bar")
        opened = cls._parse_timestamp(str(item["t"]))
        return Candle(
            symbol=symbol,
            interval=interval,
            open_time=opened,
            close_time=cls._close_time(opened, timeframe),
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
    def _close_time(opened: datetime, timeframe: str) -> datetime:
        if timeframe == "1Day":
            return opened + timedelta(days=1)
        if timeframe == "1Week":
            return opened + timedelta(days=7)
        year = opened.year + (1 if opened.month == 12 else 0)
        month = 1 if opened.month == 12 else opened.month + 1
        return opened.replace(year=year, month=month)

    @staticmethod
    def _coverage(feed: str) -> str:
        if feed == "sip":
            return "consolidated-us-market"
        if feed == "iex":
            return "single-exchange"
        if feed == "delayed_sip":
            return "consolidated-us-market-delayed"
        return f"provider-feed:{feed}"
