from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "web" / "index.html"
SWITCHER = ROOT / "app" / "web" / "symbol-switcher.js"
MARKET_CLIENT = ROOT / "app" / "web" / "market-client.js"


def test_dashboard_exposes_explicit_symbol_switcher() -> None:
    html = INDEX.read_text(encoding="utf-8")
    source = SWITCHER.read_text(encoding="utf-8")

    assert 'id="symbol-switcher"' in html
    assert 'id="market-context-label"' in html
    assert 'src="/static/symbol-switcher.js"' in html
    assert "renderSymbolSwitcher" in source
    assert "navigateToSymbol" in source
    assert "trading_universe" in source
    assert "market_symbol" in source
    assert "美股自动交易" in source


def test_symbol_selection_is_applied_before_runtime_initialization() -> None:
    html = INDEX.read_text(encoding="utf-8")
    source = SWITCHER.read_text(encoding="utf-8")

    config_index = html.index('src="/static/config.js"')
    switcher_index = html.index('src="/static/symbol-switcher.js"')
    runtime_index = html.index('src="/static/runtime.js"')
    app_index = html.index('src="/static/app.js"')

    assert config_index < switcher_index < runtime_index < app_index
    assert "applyRequestedSymbolToConfig();" in source
    assert "global.OBSERVATORY_CONFIG = Object.freeze" in source
    assert "url.searchParams.set('symbol', normalized);" in source
    assert "global.location.assign(url.toString());" in source


def test_backend_market_client_supports_dynamic_symbol_history_and_multi_symbol_stream() -> None:
    source = MARKET_CLIENT.read_text(encoding="utf-8")

    assert "async function loadHistory(requestedSymbol = symbol" in source
    assert "requestedInterval = interval" in source
    assert "encodeURIComponent(targetSymbol)" in source
    assert "if (runtime.mode === 'backend') onCandle(candle);" in source
