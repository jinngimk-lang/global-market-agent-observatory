from fastapi.testclient import TestClient

from app.api.main import create_app
from app.settings import Settings


def test_dashboard_assets_expose_autonomous_trading_console(tmp_path) -> None:
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

    required_ids = {
        "chart",
        "mode-badge",
        "capability-badge",
        "trading-state-badge",
        "execution-badge",
        "system-summary",
        "decision-cards",
        "decision-chain",
        "portfolio-summary",
        "positions-body",
        "executions-body",
        "strategy-health-body",
        "runtime-loops",
    }
    for element_id in required_ids:
        assert f'id="{element_id}"' in index.text

    removed_ids = {
        "order-form",
        "orders-body",
        "evidence-body",
        "external-accounts-body",
        "crisis-winners-body",
        "partnerships-body",
        "research-button",
    }
    for element_id in removed_ids:
        assert f'id="{element_id}"' not in index.text

    assert 'src="/static/config.js"' in index.text
    assert 'src="/static/runtime.js"' in index.text
    assert 'src="/static/market-client.js"' in index.text
    assert 'src="/static/backend-actions.js"' in index.text
    assert 'src="/static/app.js"' in index.text

    assert "global.ObservatoryRuntime" in runtime.text
    assert "function resolve" in runtime.text
    assert "mode: 'backend'" in config.text
    assert "https://api.binance.com/api/v3/klines" in market_client.text
    assert "wss://stream.binance.com:9443/ws/" in market_client.text
    assert "fallbackHistory" in market_client.text
    assert "Math.min(30000" in market_client.text
    assert "Authorization" not in market_client.text

    # The browser backend adapter is now read-only. It can retrieve decision
    # state and execution history, but contains no POST/write path.
    assert "/api/trading/status" in backend_actions.text
    assert "/api/portfolio" in backend_actions.text
    assert "/api/orders" in backend_actions.text
    assert "/api/audit" in backend_actions.text
    assert "method: 'POST'" not in backend_actions.text
    assert "/api/research/refresh" not in backend_actions.text

    assert "ObservatoryMarketClient.create(runtime)" in javascript.text
    assert "ObservatoryBackendActions?.create(runtime)" in javascript.text
    assert "renderDecisionCards" in javascript.text
    assert "renderDecisionChain" in javascript.text
    assert "renderStrategyHealth" in javascript.text
    assert "renderRuntimeLoops" in javascript.text
    assert "LightweightCharts.createChart" in javascript.text
    assert "new WebSocket" in market_client.text
    assert "/api/research/crisis-winners" not in javascript.text
    assert "/api/research/partnerships" not in javascript.text
    assert "/api/evidence" not in javascript.text
    assert "grid-template-columns" in stylesheet.text
