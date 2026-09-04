from __future__ import annotations

import time
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.settings import Settings


def test_market_structure_status_separates_observed_and_missing_symbols(tmp_path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "structure-status.db"),
        market_source="replay",
        market_symbol="BTCUSDT",
        trading_universe={"BTCUSDT", "NVDA"},
        allowed_symbols={"BTCUSDT", "NVDA"},
        replay_delay_seconds=0.01,
        replay_seed=19,
        starting_cash=Decimal("10000"),
    )
    app = create_app(settings)

    with TestClient(app) as client:
        payload = None
        for _ in range(80):
            response = client.get("/api/market/structure")
            assert response.status_code == 200
            payload = response.json()
            if payload["symbols"]["BTCUSDT"]["status"] == "observed":
                break
            time.sleep(0.02)

    assert payload is not None
    assert set(payload["symbols"]) == {"BTCUSDT", "NVDA"}

    observed = payload["symbols"]["BTCUSDT"]
    assert observed["status"] == "observed"
    assert observed["market_source"] == "replay"
    assert observed["latest_price"] is not None
    assert observed["observed_at"] is not None
    assert observed["structure"]["vwap"] is not None
    assert observed["availability"] == {
        "vwap": True,
        "order_flow_imbalance": False,
        "options_structure": False,
    }
    assert observed["provenance"]["market_source"] == "replay"
    assert observed["provenance"]["vwap"] == "typical-price-volume:last-200-candles"

    missing = payload["symbols"]["NVDA"]
    assert missing["status"] == "missing"
    assert missing["market_source"] is None
    assert missing["latest_price"] is None
    assert missing["observed_at"] is None
    assert missing["structure"] is None
    assert missing["market_data_stale"] is True
    assert missing["availability"] == {
        "vwap": False,
        "order_flow_imbalance": False,
        "options_structure": False,
    }
    assert missing["provenance"] == {}
