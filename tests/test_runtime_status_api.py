from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.settings import Settings


def test_trading_status_exposes_runtime_loop_liveness(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "runtime-status.db"),
            replay_delay_seconds=0.01,
            options_structure_enabled=False,
            strategy_learning_enabled=True,
            strategy_improvement_interval_seconds=0.05,
        )
    )

    with TestClient(app) as client:
        payload = client.get("/api/trading/status").json()

    loops = payload["runtime_loops"]
    assert loops["market_feed"] == {
        "running": True,
        "failure_count": 0,
        "last_error": None,
        "retry_seconds": 1.0,
        "retry_max_seconds": 30.0,
    }
    assert loops["continuous_improvement"]["enabled"] is True
    assert loops["continuous_improvement"]["running"] is True
    assert loops["continuous_improvement"]["last_error"] is None
    assert loops["options_structure"] == {
        "enabled": False,
        "configured": False,
        "running": False,
        "failure_count": 0,
        "last_error": None,
        "symbol_errors": {},
        "refresh_seconds": 60.0,
        "max_age_seconds": 120.0,
    }
    assert loops["account_observers"] == {
        "configured": 0,
        "running": False,
        "errors": {},
    }
