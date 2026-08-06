from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


def run_node(source: str) -> dict:
    if NODE is None:
        pytest.skip("node is not available")
    result = subprocess.run(
        [NODE, "-e", source],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_runtime_static_mode_disables_write_capabilities() -> None:
    runtime_path = json.dumps(str(ROOT / "app" / "web" / "runtime.js"))
    payload = run_node(
        f"""
const fs = require('fs');
const vm = require('vm');
const context = vm.createContext({{window: {{}}}});
vm.runInContext(fs.readFileSync({runtime_path}, 'utf8'), context);
const runtime = vm.runInContext(
  "window.ObservatoryRuntime.resolve({{mode: 'static', market: {{symbol: 'ethusdt', interval: '5m'}}}})",
  context,
);
console.log(JSON.stringify(runtime));
"""
    )

    assert payload["mode"] == "static"
    assert payload["observeOnly"] is True
    assert payload["market"] == {"symbol": "ETHUSDT", "interval": "5m"}
    assert payload["capabilities"] == {
        "paperOrders": False,
        "researchRefresh": False,
        "accountRefresh": False,
    }


def test_fallback_history_is_deterministic_and_valid_ohlc() -> None:
    client_path = json.dumps(str(ROOT / "app" / "web" / "market-client.js"))
    payload = run_node(
        f"""
const fs = require('fs');
const vm = require('vm');
const context = vm.createContext({{window: {{}}, console}});
vm.runInContext(fs.readFileSync({client_path}, 'utf8'), context);
vm.runInContext('Date.now = () => 1760000000000', context);
const first = vm.runInContext(
  "window.ObservatoryMarketClient.fallbackHistory('BTCUSDT', '1m', 8)",
  context,
);
const second = vm.runInContext(
  "window.ObservatoryMarketClient.fallbackHistory('BTCUSDT', '1m', 8)",
  context,
);
console.log(JSON.stringify({{first, second}}));
"""
    )

    assert payload["first"] == payload["second"]
    assert len(payload["first"]) == 8
    for candle in payload["first"]:
        assert candle["source"] == "deterministic-replay"
        assert candle["high"] >= max(candle["open"], candle["close"])
        assert candle["low"] <= min(candle["open"], candle["close"])
        assert candle["low"] > 0


def test_fallback_stream_candle_moves_and_preserves_ohlc() -> None:
    client_path = json.dumps(str(ROOT / "app" / "web" / "market-client.js"))
    payload = run_node(
        f"""
const fs = require('fs');
const vm = require('vm');
const context = vm.createContext({{window: {{}}, console}});
vm.runInContext(fs.readFileSync({client_path}, 'utf8'), context);
const previous = {{
  symbol: 'BTCUSDT', interval: '1m', open_time: '2026-08-06T00:00:00.000Z',
  open: 64000, high: 64100, low: 63900, close: 64050, volume: 0, source: 'deterministic-replay'
}};
const first = context.window.ObservatoryMarketClient.nextFallbackCandle(previous, 1, 1760000000000);
const second = context.window.ObservatoryMarketClient.nextFallbackCandle(first, 2, 1760000001000);
console.log(JSON.stringify({{first, second}}));
"""
    )

    assert payload["first"]["open"] == 64050
    assert payload["second"]["open"] == payload["first"]["close"]
    assert payload["first"]["close"] != payload["second"]["close"]
    for candle in payload.values():
        assert candle["high"] >= max(candle["open"], candle["close"])
        assert candle["low"] <= min(candle["open"], candle["close"])
