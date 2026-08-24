from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "web" / "index.html"
APP_JS = ROOT / "app" / "web" / "app.js"
BACKEND_JS = ROOT / "app" / "web" / "backend-actions.js"


def test_dashboard_focuses_on_autonomous_trading_decisions() -> None:
    html = INDEX.read_text(encoding="utf-8")

    required_ids = [
        "system-summary",
        "decision-cards",
        "decision-chain",
        "portfolio-summary",
        "positions-body",
        "executions-body",
        "strategy-health-body",
        "runtime-loops",
        "chart",
    ]
    for element_id in required_ids:
        assert f'id="{element_id}"' in html

    for removed in [
        "order-form",
        "crisis-winners-body",
        "partnerships-body",
        "evidence-body",
        "research-button",
        "external-accounts-body",
    ]:
        assert f'id="{removed}"' not in html


def test_dashboard_reads_only_trading_decision_and_audit_data() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    backend = BACKEND_JS.read_text(encoding="utf-8")

    assert "ObservatoryBackendActions?.create(runtime)" in source
    assert "renderDecisionCards" in source
    assert "renderDecisionChain" in source
    assert "renderStrategyHealth" in source
    assert "renderRuntimeLoops" in source

    for endpoint in [
        "/api/trading/status",
        "/api/portfolio",
        "/api/orders",
        "/api/audit",
    ]:
        assert endpoint in backend

    assert "method: 'POST'" not in backend
    for removed_endpoint in [
        "/api/research/crisis-winners",
        "/api/research/partnerships",
        "/api/evidence",
        "/api/research/refresh",
    ]:
        assert removed_endpoint not in source
        assert removed_endpoint not in backend
