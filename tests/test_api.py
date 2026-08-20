from __future__ import annotations

import time
from decimal import Decimal

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.main import create_app
from app.domain.models import ExecutionProvider, TradingMode
from app.settings import Settings


def make_settings(tmp_path) -> Settings:
    return Settings(
        database_path=str(tmp_path / "api.db"),
        market_source="replay",
        market_symbol="BTCUSDT",
        replay_delay_seconds=0.01,
        replay_seed=11,
        starting_cash=Decimal("10000"),
        allowed_symbols={"BTCUSDT"},
        max_order_notional=Decimal("1000"),
        max_gross_exposure=Decimal("2000"),
        daily_loss_limit=Decimal("500"),
    )


def wait_for_candle(client: TestClient) -> list[dict]:
    for _ in range(50):
        response = client.get("/api/candles/BTCUSDT?limit=5")
        if response.json():
            return response.json()
        time.sleep(0.02)
    raise AssertionError("replay feed did not produce a candle")


def test_health_history_order_and_portfolio_flow(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))

    with TestClient(app) as client:
        health = client.get("/api/health")
        candles = wait_for_candle(client)
        order = client.post(
            "/api/orders",
            json={
                "client_order_id": "api-buy-1",
                "symbol": "BTCUSDT",
                "side": "buy",
                "quantity": "0.01",
            },
        )
        portfolio = client.get("/api/portfolio")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["trading_mode"] == "paper"
    assert health.json()["execution_provider"] == "paper"
    assert health.json()["auto_trading_enabled"] is False
    assert health.json()["live_execution_permitted"] is False
    assert health.json()["trading_state"] == "active"
    assert candles[-1]["symbol"] == "BTCUSDT"
    assert order.status_code == 201
    assert order.json()["status"] == "filled"
    assert portfolio.status_code == 200
    assert portfolio.json()["positions"][0]["quantity"] == "0.01"
    assert "equity" in portfolio.json()
    assert "gross_exposure" in portfolio.json()


def test_risk_rejection_is_structured_and_fail_closed(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))

    with TestClient(app) as client:
        wait_for_candle(client)
        response = client.post(
            "/api/orders",
            json={
                "client_order_id": "too-large",
                "symbol": "BTCUSDT",
                "side": "buy",
                "quantity": "10",
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "order_notional_limit"


def test_legacy_order_api_is_disabled_for_live_execution_provider(tmp_path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "live-api.db"),
        market_source="replay",
        market_symbol="BTCUSDT",
        trading_mode=TradingMode.LIVE,
        execution_provider=ExecutionProvider.ALPACA,
        live_trading_enabled=True,
        live_trading_confirmation="I_UNDERSTAND_LIVE_TRADING",
        alpaca_api_key=SecretStr("key"),
        alpaca_api_secret=SecretStr("secret"),
        alpaca_base_url="https://api.alpaca.markets",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/orders",
            json={
                "client_order_id": "must-not-route-live",
                "symbol": "BTCUSDT",
                "side": "buy",
                "quantity": "1",
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "legacy_order_api_disabled"


def test_trading_status_is_read_only_and_exposes_no_credentials(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))

    with TestClient(app) as client:
        payload = client.get("/api/trading/status").json()

    assert payload["trading_mode"] == "paper"
    assert payload["execution_provider"] == "paper"
    assert payload["trading_state"] == "active"
    assert payload["auto_trading_enabled"] is False
    assert payload["trading_universe"] == ["KLAC", "NVDA", "SPCX"]
    assert "alpaca_api_key" not in payload
    assert "ibkr_account_id" not in payload


def test_market_websocket_streams_normalized_candles(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))

    with TestClient(app) as client:
        with client.websocket_connect("/ws/market") as websocket:
            message = websocket.receive_json()

    assert message["type"] == "candle"
    assert message["data"]["symbol"] == "BTCUSDT"
    assert message["data"]["source"] == "replay"


class FakeObserver:
    name = "fake-broker"

    async def snapshot(self):
        from app.domain.models import ExternalAccountSnapshot, ObservedOrder

        return ExternalAccountSnapshot(
            provider="fake-broker",
            account_id="acct-1",
            mode="read-only",
            equity=Decimal("12345"),
            orders=[
                ObservedOrder(
                    order_id="external-1",
                    symbol="AAPL",
                    side="buy",
                    quantity=Decimal("1"),
                    status="filled",
                )
            ],
        )


def test_external_account_observers_are_exposed_read_only(tmp_path) -> None:
    settings = make_settings(tmp_path).model_copy(update={"account_poll_seconds": 0.01})
    app = create_app(settings, observers=[FakeObserver()])

    with TestClient(app) as client:
        payload = None
        for _ in range(50):
            payload = client.get("/api/accounts").json()
            if payload["accounts"] and payload["accounts"][0]["snapshot"]:
                break
            time.sleep(0.02)

    assert payload is not None
    assert payload["live_execution_permitted"] is False
    assert payload["accounts"][0]["name"] == "fake-broker"
    assert payload["accounts"][0]["snapshot"]["equity"] == "12345"
    assert payload["accounts"][0]["snapshot"]["orders"][0]["order_id"] == "external-1"


def test_crisis_winners_and_partnership_assessments_are_exposed(tmp_path) -> None:
    from datetime import UTC, datetime, timedelta

    from app.domain.models import EvidenceGrade, EvidenceItem
    from app.research.crisis import CrisisWindow, CrisisWinner, TradeCase

    app = create_app(make_settings(tmp_path))
    start = datetime(2026, 1, 1, tzinfo=UTC)
    app.state.runtime.store.add_crisis_winner(
        CrisisWinner(
            case=TradeCase(
                case_id="winner-1",
                actor_name="Verified Fund",
                actor_type="institution",
                instrument="INDEX FUTURE",
                opened_at=start,
                closed_at=start + timedelta(days=2),
                gross_pnl=Decimal("1000"),
                costs=Decimal("100"),
                evidence_grade=EvidenceGrade.A,
                evidence_urls=["https://example.test/audit"],
            ),
            window=CrisisWindow(
                name="selloff",
                start=start,
                end=start + timedelta(days=3),
                market="GLOBAL",
                max_drawdown=Decimal("-0.12"),
            ),
            net_pnl=Decimal("900"),
        )
    )
    app.state.runtime.store.add_evidence(
        EvidenceItem(
            evidence_id="partnership-1",
            title="Material agreement",
            source_type="regulator_filing",
            source_url="https://example.test/filing",
            grade=EvidenceGrade.B,
            observed_at=start,
            event_date=start,
            entity="Example Corp",
            summary="Entry into a material definitive agreement",
            content_hash="b" * 64,
            tags=["partnership", "material-agreement"],
            metadata={"form": "8-K", "items": "1.01"},
        )
    )

    with TestClient(app) as client:
        winners = client.get("/api/research/crisis-winners").json()
        partnerships = client.get("/api/research/partnerships").json()

    assert winners[0]["case"]["case_id"] == "winner-1"
    assert winners[0]["net_pnl"] == "900"
    assert partnerships[0]["maturity"] == "binding-regulatory-filed"
    assert partnerships[0]["price_target"] is None


def test_http_responses_include_browser_security_headers(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    policy = response.headers["content-security-policy"]
    assert "default-src 'self'" in policy
    assert "connect-src 'self' ws: wss:" in policy
    assert "https://unpkg.com" in policy
