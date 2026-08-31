from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.domain.models import Candle
from app.market.alpaca_history import HistoricalBarsResult
from app.settings import Settings


class FakeHistoryClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    async def fetch(self, symbol: str, *, timeframe: str, limit: int = 240):
        self.calls.append((symbol, timeframe, limit))
        base = datetime(2026, 1, 1, tzinfo=UTC)
        candles = []
        for index in range(8):
            opened = base + timedelta(days=index)
            close = 100 + index
            candles.append(
                Candle(
                    symbol=symbol,
                    interval="1d",
                    open_time=opened,
                    close_time=opened + timedelta(days=1),
                    open=close - 1,
                    high=close + (4 if index == 3 else 2),
                    low=close - (5 if index == 4 else 2),
                    close=close,
                    volume=1_000_000 + index,
                    source="alpaca:iex:historical",
                )
            )
        return HistoricalBarsResult(
            symbol=symbol,
            timeframe=timeframe,
            feed="iex",
            coverage="single-exchange",
            fetched_at=datetime(2026, 8, 31, tzinfo=UTC),
            candles=candles,
        )


def test_market_history_api_returns_verified_bars_and_derived_levels(tmp_path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "history-api.db"),
        trading_universe={"NVDA", "KLAC", "SPCX"},
        allowed_symbols={"NVDA", "KLAC", "SPCX", "BTCUSDT"},
    )
    app = create_app(settings)
    fake = FakeHistoryClient()
    app.state.runtime.historical_bars = fake

    with TestClient(app) as client:
        response = client.get("/api/market/history/nvda?timeframe=1Day&limit=120")

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "NVDA"
    assert body["timeframe"] == "1Day"
    assert body["source"] == "alpaca:iex:historical"
    assert body["coverage"] == "single-exchange"
    assert len(body["candles"]) == 8
    assert body["levels"]["methodology"] == "confirmed-price-pivots"
    assert body["levels"]["support"] is not None
    assert body["levels"]["resistance"] is not None
    assert fake.calls == [("NVDA", "1Day", 120)]


def test_market_history_api_rejects_symbol_outside_allowed_universe(tmp_path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "history-symbol.db"),
        trading_universe={"NVDA"},
        allowed_symbols={"NVDA", "BTCUSDT"},
    )
    app = create_app(settings)
    fake = FakeHistoryClient()
    app.state.runtime.historical_bars = fake

    with TestClient(app) as client:
        response = client.get("/api/market/history/TSLA?timeframe=1Day")

    assert response.status_code == 404
    assert fake.calls == []


def test_market_history_api_fails_explicitly_when_provider_is_unavailable(tmp_path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "history-unavailable.db"),
        trading_universe={"NVDA"},
        allowed_symbols={"NVDA", "BTCUSDT"},
    )
    app = create_app(settings)
    app.state.runtime.historical_bars = None

    with TestClient(app) as client:
        response = client.get("/api/market/history/NVDA?timeframe=1Month")

    assert response.status_code == 503
    assert "historical" in response.json()["detail"].lower()


def test_market_history_api_rejects_intraday_alias_instead_of_faking_history(tmp_path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "history-timeframe.db"),
        trading_universe={"NVDA"},
        allowed_symbols={"NVDA", "BTCUSDT"},
    )
    app = create_app(settings)
    app.state.runtime.historical_bars = FakeHistoryClient()

    with TestClient(app) as client:
        response = client.get("/api/market/history/NVDA?timeframe=1Min")

    assert response.status_code == 422
