from fastapi.testclient import TestClient

from app.api.main import create_app
from app.settings import Settings


def test_dashboard_exposes_chinese_context_intelligence_panel(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "context-dashboard.db"),
            replay_delay_seconds=0.05,
        )
    )

    with TestClient(app) as client:
        index = client.get("/")
        script = client.get("/static/context-intelligence.js")
        actions = client.get("/static/backend-actions.js")

    assert index.status_code == 200
    assert script.status_code == 200
    assert actions.status_code == 200

    html = index.text
    assert 'id="context-intelligence-panel"' in html
    assert 'id="context-freshness-strip"' in html
    assert 'id="context-synthesis"' in html
    assert 'id="context-news"' in html
    assert 'id="context-filings"' in html
    assert 'id="context-government"' in html
    assert 'id="context-flow"' in html
    assert "综合情报" in html
    assert "实时新闻" in html
    assert "SEC / 公司披露" in html
    assert "政府 / 监管" in html
    assert "资金行为" in html
    assert "仅作上下文证据，不代表交易许可" in html
    assert 'src="/static/context-intelligence.js"' in html

    source = script.text
    assert "loadIntelligence" in source
    assert "loadIntelligenceStatus" in source
    assert "REALTIME" in source
    assert "NEAR-REALTIME" in source
    assert "OFFICIAL-CURRENT" in source
    assert "DELAYED" in source
    assert "STALE" in source
    assert "接收延迟" in source
    assert "官方源" in source
    assert "NO VERIFIED DATA" in source
    assert "5000" in source

    action_source = actions.text
    assert "loadIntelligence(symbol)" in action_source
    assert "loadIntelligenceStatus()" in action_source
    assert "/api/intelligence/" in action_source
