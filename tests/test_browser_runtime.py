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


def test_backend_actions_load_market_structure_read_only() -> None:
    actions_path = json.dumps(str(ROOT / "app" / "web" / "backend-actions.js"))
    payload = run_node(
        f"""
const fs = require('fs');
const vm = require('vm');
const requests = [];
const fetch = async (url, options) => {{
  requests.push({{url, method: options.method}});
  return {{ok: true, json: async () => ({{generated_at: '2026-08-24T05:00:00Z', symbols: {{}}}})}};
}};
const context = vm.createContext({{window: {{}}, fetch, console}});
vm.runInContext(fs.readFileSync({actions_path}, 'utf8'), context);
const actions = context.window.ObservatoryBackendActions.create({{apiBase: '/backend'}});
(async () => {{
  const result = await actions.loadMarketStructure();
  console.log(JSON.stringify({{requests, result}}));
}})();
"""
    )
    assert payload["requests"] == [
        {"url": "/backend/api/market/structure", "method": "GET"}
    ]
    assert payload["result"]["symbols"] == {}


def test_backend_actions_load_market_coverage_read_only() -> None:
    actions_path = json.dumps(str(ROOT / "app" / "web" / "backend-actions.js"))
    payload = run_node(
        f"""
const fs = require('fs');
const vm = require('vm');
const requests = [];
const fetch = async (url, options) => {{
  requests.push({{url, method: options.method}});
  return {{ok: true, json: async () => ({{fresh_coverage_ratio: 0.5, symbols: {{}}}})}};
}};
const context = vm.createContext({{window: {{}}, fetch, console}});
vm.runInContext(fs.readFileSync({actions_path}, 'utf8'), context);
const actions = context.window.ObservatoryBackendActions.create({{apiBase: '/backend'}});
(async () => {{
  const result = await actions.loadMarketCoverage();
  console.log(JSON.stringify({{requests, result}}));
}})();
"""
    )
    assert payload["requests"] == [
        {"url": "/backend/api/market/coverage", "method": "GET"}
    ]
    assert payload["result"]["fresh_coverage_ratio"] == 0.5


def test_fallback_history_is_deterministic_and_valid_ohlc() -> None:
    client_path = json.dumps(str(ROOT / "app" / "web" / "market-client.js"))
    payload = run_node(
        f"""
const fs = require('fs'); const vm = require('vm');
const context = vm.createContext({{window: {{}}, console}});
vm.runInContext(fs.readFileSync({client_path}, 'utf8'), context);
vm.runInContext('Date.now = () => 1760000000000', context);
const first = vm.runInContext("window.ObservatoryMarketClient.fallbackHistory('BTCUSDT', '1m', 8)", context);
const second = vm.runInContext("window.ObservatoryMarketClient.fallbackHistory('BTCUSDT', '1m', 8)", context);
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
const fs = require('fs'); const vm = require('vm');
const context = vm.createContext({{window: {{}}, console}});
vm.runInContext(fs.readFileSync({client_path}, 'utf8'), context);
const previous = {{symbol:'BTCUSDT', interval:'1m', open_time:'2026-08-06T00:00:00.000Z', open:64000, high:64100, low:63900, close:64050, volume:0, source:'deterministic-replay'}};
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


def test_backend_stream_does_not_mislabel_render_failure_as_invalid_data() -> None:
    client_path = json.dumps(str(ROOT / "app" / "web" / "market-client.js"))
    payload = run_node(
        f"""
const fs = require('fs'); const vm = require('vm'); let socket = null;
class FakeWebSocket {{ constructor() {{ this.listeners={{}}; socket=this; }} addEventListener(n,c) {{this.listeners[n]=c;}} emit(n,e={{}}) {{if(this.listeners[n]) this.listeners[n](e);}} close() {{}} get readyState() {{return 1;}} }}
const window={{location:{{protocol:'http:',host:'127.0.0.1:8000',href:'http://127.0.0.1:8000/'}},setTimeout,clearTimeout,setInterval,clearInterval}};
const context=vm.createContext({{window,WebSocket:FakeWebSocket,URL,console,setTimeout,clearTimeout,setInterval,clearInterval}});
vm.runInContext(fs.readFileSync({client_path},'utf8'),context);
const statuses=[]; const client=context.window.ObservatoryMarketClient.create({{mode:'backend',apiBase:'',market:{{symbol:'BTCUSDT',interval:'1m'}}}});
client.connect(()=>{{throw new Error('chart rejected stale point');}},s=>statuses.push(s.label)); socket.emit('open');
socket.emit('message',{{data:JSON.stringify({{type:'candle',data:{{symbol:'BTCUSDT',interval:'1m',open_time:'2026-08-24T06:31:00Z',open:59050,high:59100,low:59000,close:59080,volume:10,source:'replay'}}}})}});
socket.emit('message',{{data:'{{'}}); console.log(JSON.stringify({{statuses}}));
"""
    )
    assert "RENDER ERROR" in payload["statuses"]
    assert payload["statuses"].count("INVALID STREAM DATA") == 1


def test_market_client_identifies_out_of_order_candles() -> None:
    client_path = json.dumps(str(ROOT / "app" / "web" / "market-client.js"))
    payload = run_node(
        f"""
const fs=require('fs'); const vm=require('vm'); const context=vm.createContext({{window:{{}},console}});
vm.runInContext(fs.readFileSync({client_path},'utf8'),context);
const check=context.window.ObservatoryMarketClient.isOutOfOrderCandle;
console.log(JSON.stringify({{
  older: check({{open_time:'2026-08-24T06:30:00Z'}}, Date.parse('2026-08-24T06:31:00Z')),
  equal: check({{open_time:'2026-08-24T06:31:00Z'}}, Date.parse('2026-08-24T06:31:00Z')),
  newer: check({{open_time:'2026-08-24T06:32:00Z'}}, Date.parse('2026-08-24T06:31:00Z')),
}}));
"""
    )
    assert payload == {"older": True, "equal": False, "newer": False}
