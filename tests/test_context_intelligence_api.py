from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.intelligence.models import ContextItem, ContextSource, EvidenceKind
from app.settings import Settings


def _news(symbol: str, *, now: datetime) -> ContextItem:
    published = now - timedelta(seconds=20)
    return ContextItem(
        item_id="alpaca-news:123",
        symbols=[symbol],
        category="news",
        label="Verified provider headline",
        summary="Provider supplied summary.",
        event_time=published,
        published_at=published,
        source_updated_at=published,
        ingested_at=published + timedelta(seconds=2),
        freshness_sla_seconds=120,
        evidence_kind=EvidenceKind.FACT,
        source=ContextSource(
            provider="alpaca-news",
            source_type="news",
            official=False,
            coverage="provider-tagged US equities news",
            latency_class="realtime",
            source_url="https://example.test/news/123",
        ),
    )


def test_intelligence_api_enriches_items_with_freshness_and_latency(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "context-api.db"),
            context_intelligence_enabled=False,
            trading_universe={"NVDA"},
            allowed_symbols={"NVDA"},
            replay_delay_seconds=0.05,
        )
    )
    now = datetime.now(UTC)
    app.state.runtime.context_store.upsert(_news("NVDA", now=now))

    with TestClient(app) as client:
        response = client.get("/api/intelligence/NVDA")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "NVDA"
    assert payload["enabled"] is False
    assert payload["news"][0]["freshness"] == "realtime"
    assert payload["news"][0]["provider_latency_seconds"] == 2.0
    assert payload["news"][0]["source"]["provider"] == "alpaca-news"
    assert payload["news"][0]["source"]["source_url"].endswith("/123")
    assert "age_seconds" in payload["news"][0]
    assert payload["execution_authority"] == "none"


def test_intelligence_api_rejects_symbol_outside_context_universe(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "context-unknown.db"),
            trading_universe={"NVDA"},
            allowed_symbols={"NVDA", "AAPL"},
            replay_delay_seconds=0.05,
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/intelligence/AAPL")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "context_symbol_not_configured"


def test_intelligence_status_does_not_expose_credentials(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "context-status.db"),
            trading_universe={"NVDA"},
            allowed_symbols={"NVDA"},
            replay_delay_seconds=0.05,
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/intelligence/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert set(payload["sources"]) == {"alpaca-news", "sec-edgar", "federal-register"}
    lowered = response.text.lower()
    assert "api_secret" not in lowered
    assert "api_key" not in lowered
