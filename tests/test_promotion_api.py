from fastapi.testclient import TestClient

from app.api.main import create_app
from app.domain.models import TradingMode
from app.settings import Settings


def test_health_distinguishes_requested_auto_trading_from_promoted_execution(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "api.db"),
            trading_mode=TradingMode.PAPER,
            auto_trading_enabled=True,
            market_source="replay",
            replay_delay_seconds=0.01,
        )
    )

    with TestClient(app) as client:
        payload = client.get("/api/health").json()

    assert payload["auto_trading_enabled"] is True
    assert payload["promotion_execution_allowed"] is False
    assert payload["autonomous_execution_enabled"] is False
    assert payload["strategy_promotion_blocked"] == 2


def test_trading_status_exposes_versioned_promotion_blockers(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "api.db"),
            trading_mode=TradingMode.PAPER,
            auto_trading_enabled=True,
            market_source="replay",
            replay_delay_seconds=0.01,
        )
    )

    with TestClient(app) as client:
        payload = client.get("/api/trading/status").json()

    assert payload["promotion_execution_allowed"] is False
    assert payload["autonomous_execution_enabled"] is False
    reports = {item["strategy_id"]: item for item in payload["strategy_promotion"]}
    assert set(reports) == {"vwap", "gamma-levels"}
    assert reports["vwap"]["version"] == "1.0.0"
    assert reports["vwap"]["current_stage"] == "replay"
    assert reports["vwap"]["required_stage"] == "paper"
    assert reports["vwap"]["allowed"] is False
