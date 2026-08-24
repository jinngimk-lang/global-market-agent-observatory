from __future__ import annotations

from pydantic import SecretStr
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.domain.models import TradingState
from app.settings import Settings


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_operator_controls_fail_closed_when_token_not_configured(tmp_path) -> None:
    app = create_app(Settings(database_path=str(tmp_path / "operator.db")))

    with TestClient(app) as client:
        response = client.post("/api/operator/halt", json={"reason": "test"})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "operator_auth_not_configured"
    assert app.state.runtime.trading_state is TradingState.ACTIVE


def test_operator_controls_reject_missing_or_wrong_bearer_token(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "operator.db"),
            operator_api_token=SecretStr("correct-token"),
        )
    )

    with TestClient(app) as client:
        missing = client.post("/api/operator/halt", json={"reason": "missing"})
        wrong = client.post(
            "/api/operator/halt",
            headers=auth("wrong-token"),
            json={"reason": "wrong"},
        )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert app.state.runtime.trading_state is TradingState.ACTIVE


def test_authenticated_halt_persists_and_is_audited(tmp_path) -> None:
    database = tmp_path / "operator.db"
    app = create_app(
        Settings(
            database_path=str(database),
            operator_api_token=SecretStr("operator-token"),
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/operator/halt",
            headers=auth("operator-token"),
            json={"reason": "manual risk review"},
        )
        audit = client.get("/api/audit?limit=10").json()

    assert response.status_code == 200
    assert response.json()["trading_state"] == "halted"
    assert app.state.runtime.trading_state is TradingState.HALTED
    assert app.state.runtime.trading_state_store.get() is TradingState.HALTED
    assert any(
        item["event_type"] == "kill_switch"
        and item["payload"].get("reason") == "operator:manual risk review"
        for item in audit
    )


def test_authenticated_activation_never_bypasses_strategy_gates(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "operator.db"),
            operator_api_token=SecretStr("operator-token"),
            auto_trading_enabled=True,
        )
    )
    app.state.runtime.orchestrator.halt("test setup")

    with TestClient(app) as client:
        response = client.post(
            "/api/operator/activate",
            headers=auth("operator-token"),
            json={"reason": "review complete"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["trading_state"] == "active"
    assert payload["promotion_execution_allowed"] is False
    assert payload["autonomous_execution_enabled"] is False
    assert app.state.runtime.trading_state_store.get() is TradingState.ACTIVE


def test_activation_is_blocked_while_strategy_health_is_degraded(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "operator.db"),
            operator_api_token=SecretStr("operator-token"),
        )
    )
    app.state.runtime.orchestrator.reduce_only("strategy_degradation:test")
    app.state.runtime.strategy_health_execution_allowed = False

    with TestClient(app) as client:
        response = client.post(
            "/api/operator/activate",
            headers=auth("operator-token"),
            json={"reason": "unsafe request"},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "strategy_health_blocked"
    assert app.state.runtime.trading_state is TradingState.REDUCING
