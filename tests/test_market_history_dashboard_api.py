from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.main import create_app
from app.domain.models import Candle
from app.market.alpaca_history import AlpacaHistoricalBarsClient, HistoricalBarsResult
from app.settings import Settings


def _candle(symbol: str, interval: str, opened: datetime, close: float) -> Candle:
    return Candle(
        symbol=symbol,
        interval=interval,
        open_time=opened,
        close_time=opened + timedelta(minutes=1),
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        volume=1000,
        source="alpaca:iex:historical",
        closed=True,
    )


def test_alpaca_history_supports_latest_minute_bars_in_chronological_order() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "bars": [
                    {"t": "2026-09-01T14:31:00Z", "o": 101, "h": 103, "l": 100, "c": 102, "v": 1200},
                    {"t": "2026-09-01T14:30:00Z", "o": 100, "h": 102, "l": 99, "c": 101, "v": 1000},
                ]
            },
        )

    async def run() -> HistoricalBarsResult:
        client = httpx.AsyncClient(
            base_url="https://data.alpaca.markets",
            transport=httpx.MockTransport(handler),
        )
        adapter = AlpacaHistoricalBarsClient(
            api_key="key",
            api_secret="secret",
            feed="iex",
            client=client,
        )
        try:
            return await adapter.fetch("NVDA", timeframe="1Min", limit=300)
        finally:
            await client.aclose()

    result = asyncio.run(run())

    assert [item.interval for item in result.candles] == ["1m", "1m"]
    assert [item.open_time.isoformat() for item in result.candles] == [
        "2026-09-01T14:30:00+00:00",
        "2026-09-01T14:31:00+00:00",
    ]
    assert requests
    assert requests[0].url.params["timeframe"] == "1Min"
    assert requests[0].url.params["sort"] == "desc"


def test_market_history_api_uses_runtime_alpaca_history_even_in_replay_mode(tmp_path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "history.db"),
        market_source="replay",
        alpaca_api_key=SecretStr("key"),
        alpaca_api_secret=SecretStr("secret"),
        replay_delay_seconds=0.05,
    )
    app = create_app(settings)
    runtime = app.state.runtime
    observed = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)

    class FakeHistory:
        async def fetch(self, symbol: str, *, timeframe: str, limit: int = 240):
            assert symbol == "NVDA"
            assert timeframe == "1Day"
            assert limit == 260
            return HistoricalBarsResult(
                symbol="NVDA",
                timeframe="1Day",
                feed="iex",
                coverage="single-exchange",
                fetched_at=observed,
                candles=[_candle("NVDA", "1d", observed - timedelta(days=1), 220.5)],
            )

        async def close(self) -> None:
            return None

    runtime.historical_bars = FakeHistory()

    with TestClient(app) as client:
        response = client.get("/api/market/history/NVDA?timeframe=1Day&limit=260")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "NVDA"
    assert payload["timeframe"] == "1Day"
    assert payload["feed"] == "iex"
    assert payload["coverage"] == "single-exchange"
    assert payload["source"] == "alpaca:iex:historical"
    assert payload["candles"][0]["close"] == 220.5


def test_market_history_api_fails_closed_for_unconfigured_higher_timeframe(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "history.db"),
            replay_delay_seconds=0.05,
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/market/history/NVDA?timeframe=1Month&limit=120")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "historical_market_data_unconfigured"


def test_market_history_api_can_fall_back_to_verified_local_minute_store(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "history.db"),
            replay_delay_seconds=0.05,
        )
    )
    runtime = app.state.runtime
    opened = datetime(2026, 9, 1, 14, 30, tzinfo=UTC)
    runtime.store.upsert_candle(_candle("NVDA", "1m", opened, 219.25))

    with TestClient(app) as client:
        response = client.get("/api/market/history/NVDA?timeframe=1Min&limit=300")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "runtime-store"
    assert payload["coverage"] == "runtime-feed"
    assert payload["candles"][0]["close"] == 219.25


def test_market_history_api_rejects_symbols_outside_configured_universe(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "history.db"),
            replay_delay_seconds=0.05,
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/market/history/AAPL?timeframe=1Day&limit=20")

    assert response.status_code == 404
