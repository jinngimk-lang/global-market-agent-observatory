from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "web" / "index.html"
BACKEND = ROOT / "app" / "web" / "backend-actions.js"
ADVANCED = ROOT / "app" / "web" / "advanced-market-chart.js"
STATIC_BUILDER = ROOT / "scripts" / "build_static_site.py"


def test_dashboard_exposes_real_period_controls_and_chart_truth_labels() -> None:
    html = INDEX.read_text(encoding="utf-8")

    for label in ["分时", "日K", "周K", "月K"]:
        assert label in html
    for element_id in [
        "advanced-market-chart",
        "market-period-switcher",
        "market-chart-legend",
        "market-chart-empty",
        "market-chart-source",
    ]:
        assert f'id="{element_id}"' in html

    for truth_label in ["MA20", "MA60", "算法支撑", "算法压力", "成交量"]:
        assert truth_label in html

    assert "/static/advanced-market-chart.js" in html
    assert "/static/advanced-market-chart.css" in html


def test_backend_adapter_requests_real_higher_timeframe_history_read_only() -> None:
    source = BACKEND.read_text(encoding="utf-8")

    assert "loadMarketHistory" in source
    assert "/api/market/history/" in source
    assert "timeframe" in source
    assert "method: 'POST'" not in source


def test_advanced_chart_uses_candles_volume_ma_and_provider_levels() -> None:
    source = ADVANCED.read_text(encoding="utf-8")

    for behavior in [
        "addCandlestickSeries",
        "addHistogramSeries",
        "MA20",
        "MA60",
        "createPriceLine",
        "算法支撑",
        "算法压力",
        "loadMarketHistory",
        "1Day",
        "1Week",
        "1Month",
        "single-exchange",
        "无可验证历史数据",
    ]:
        assert behavior in source

    # A one-minute WebSocket event must not mutate a daily/weekly/monthly chart.
    assert "activePeriod !== '1m'" in source
    assert "candle.symbol !== currentSymbol" in source


def test_static_build_carries_advanced_chart_assets_without_backend_credentials() -> None:
    source = STATIC_BUILDER.read_text(encoding="utf-8")

    assert '"advanced-market-chart.js"' in source
    assert '"advanced-market-chart.css"' in source
