from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.domain.models import Candle
from app.settings import Settings


def stale_candle(symbol: str) -> Candle:
    opened = datetime.now(UTC) - timedelta(minutes=10)
    return Candle(
        symbol=symbol,
        interval="1m",
        open_time=opened,
        close_time=opened + timedelta(minutes=1),
        open=100,
        high=101,
        low=99,
        close=100,
        volume=10,
        source="manual-fixture",
        closed=True,
    )


def test_market_coverage_distinguishes_fresh_stale_and_missing_symbols(tmp_path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "coverage.db"),
        market_source="replay",
        market_symbol="BTCUSDT",
        trading_universe={"BTCUSDT", "NVDA", "KLAC"},
        allowed_symbols={"BTCUSDT", "NVDA", "KLAC"},
        replay_delay_seconds=0.01,
        market_data_max_age_seconds=5,
    )
    app = create_app(settings)
    app.state.runtime.store.upsert_candle(stale_candle("NVDA"))

    with TestClient(app) as client:
        payload = None
        for _ in range(80):
            response = client.get("/api/market/coverage")
            assert response.status_code == 200
            payload = response.json()
            if payload["symbols"]["BTCUSDT"]["status"] == "fresh":
                break
            time.sleep(0.02)

    assert payload is not None
    assert payload["market_source"] == "replay"
    assert payload["interval"] == "1m"
    assert payload["fresh_symbols"] == ["BTCUSDT"]
    assert payload["stale_symbols"] == ["NVDA"]
    assert payload["missing_symbols"] == ["KLAC"]
    assert payload["fresh_coverage_ratio"] == 1 / 3

    fresh = payload["symbols"]["BTCUSDT"]
    assert fresh["status"] == "fresh"
    assert fresh["source"] == "replay"
    assert fresh["latest_price"] is not None
    assert fresh["close_time"] is not None
    assert fresh["age_seconds"] <= 5
    assert fresh["cycle_status"] == "observed"
    assert fresh["cycle_error"] is None

    stale = payload["symbols"]["NVDA"]
    assert stale["status"] == "stale"
    assert stale["source"] == "manual-fixture"
    assert stale["age_seconds"] > 5
    assert stale["cycle_status"] == "waiting"
    assert stale["cycle_error"] is None

    missing = payload["symbols"]["KLAC"]
    assert missing == {
        "status": "missing",
        "source": None,
        "latest_price": None,
        "open_time": None,
        "close_time": None,
        "age_seconds": None,
        "cycle_status": "waiting",
        "cycle_error": None,
    }
