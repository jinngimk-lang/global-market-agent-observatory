from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "web" / "index.html"
APP_JS = ROOT / "app" / "web" / "app.js"
MARKET_CLIENT = ROOT / "app" / "web" / "market-client.js"


def test_dashboard_exposes_explicit_symbol_switcher() -> None:
    html = INDEX.read_text(encoding="utf-8")
    source = APP_JS.read_text(encoding="utf-8")

    assert 'id="symbol-switcher"' in html
    assert 'id="market-context-label"' in html
    assert "renderSymbolSwitcher" in source
    assert "switchSymbol" in source
    assert "trading_universe" in source
    assert "market_symbol" in source


def test_backend_market_client_supports_dynamic_symbol_history_and_multi_symbol_stream() -> None:
    source = MARKET_CLIENT.read_text(encoding="utf-8")

    assert "async function loadHistory(requestedSymbol = symbol" in source
    assert "requestedInterval = interval" in source
    assert "encodeURIComponent(requestedSymbol)" in source
    assert "if (runtime.mode === 'backend') onCandle(candle);" in source
