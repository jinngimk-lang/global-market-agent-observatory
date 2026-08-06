from fastapi.testclient import TestClient

from app.api.main import create_app
from app.settings import Settings


def test_dashboard_assets_expose_required_observability_panels(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "dashboard.db"),
            replay_delay_seconds=0.05,
        )
    )

    with TestClient(app) as client:
        index = client.get("/")
        javascript = client.get("/static/app.js")
        runtime = client.get("/static/runtime.js")
        market_client = client.get("/static/market-client.js")
        backend_actions = client.get("/static/backend-actions.js")
        config = client.get("/static/config.js")
        stylesheet = client.get("/static/styles.css")

    assert index.status_code == 200
    assert javascript.status_code == 200
    assert runtime.status_code == 200
    assert market_client.status_code == 200
    assert backend_actions.status_code == 200
    assert config.status_code == 200
    assert stylesheet.status_code == 200
    assert 'id="chart"' in index.text
    assert 'id="mode-badge"' in index.text
    assert 'id="capability-badge"' in index.text
    assert 'id="positions-body"' in index.text
    assert 'id="orders-body"' in index.text
    assert 'id="evidence-body"' in index.text
    assert 'id="external-accounts-body"' in index.text
    assert 'id="crisis-winners-body"' in index.text
    assert 'id="partnerships-body"' in index.text
    assert 'id="order-form"' in index.text
    assert 'src="/static/config.js"' in index.text
    assert 'src="/static/runtime.js"' in index.text
    assert 'src="/static/market-client.js"' in index.text
    assert 'src="/static/backend-actions.js"' in index.text
    assert "global.ObservatoryRuntime" in runtime.text
    assert "function resolve" in runtime.text
    assert "mode: 'backend'" in config.text
    assert "https://api.binance.com/api/v3/klines" in market_client.text
    assert "wss://stream.binance.com:9443/ws/" in market_client.text
    assert "fallbackHistory" in market_client.text
    assert "Math.min(30000" in market_client.text
    assert "Authorization" not in market_client.text
    assert "/api/orders" in backend_actions.text
    assert "/api/research/refresh" in backend_actions.text
    assert "ObservatoryMarketClient.create(runtime)" in javascript.text
    assert "gradeCell.innerHTML" not in javascript.text
    assert "runtime.capabilities.paperOrders" in javascript.text
    assert "LightweightCharts.createChart" in javascript.text
    assert "new WebSocket" in market_client.text
    assert "/api/portfolio" in javascript.text
    assert "/api/evidence" in javascript.text
    assert "/api/accounts" in javascript.text
    assert "/api/research/crisis-winners" in javascript.text
    assert "/api/research/partnerships" in javascript.text
    assert "LIVE DISABLED" in index.text
    assert "grid-template-columns" in stylesheet.text
