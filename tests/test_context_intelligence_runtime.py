from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.intelligence.service import ContextIntelligenceService

from app.intelligence.models import ContextItem, ContextSource, EvidenceKind
from app.intelligence.store import SQLiteContextStore


def _item(
    *,
    item_id: str,
    symbol: str = "NVDA",
    category: str = "news",
    provider: str = "test-provider",
    event_time: datetime | None = None,
) -> ContextItem:
    observed = event_time or datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    return ContextItem(
        item_id=item_id,
        symbols=[symbol],
        category=category,
        label=f"{category} headline",
        summary=f"{category} summary",
        event_time=observed,
        published_at=observed,
        ingested_at=observed + timedelta(seconds=1),
        freshness_sla_seconds=120,
        evidence_kind=EvidenceKind.FACT,
        confidence=Decimal("1"),
        source=ContextSource(
            provider=provider,
            source_type=category,
            official=category in {"filing", "government"},
            coverage="test coverage",
            latency_class="near-realtime" if category == "filing" else "realtime",
        ),
    )


def test_snapshot_groups_persisted_evidence_and_ephemeral_flow(tmp_path) -> None:
    store = SQLiteContextStore(tmp_path / "context.db")
    store.upsert(_item(item_id="news-1", category="news"))
    store.upsert(_item(item_id="filing-1", category="filing", provider="sec-edgar"))
    store.upsert(
        _item(item_id="government-1", category="government", provider="federal-register")
    )
    flow = _item(item_id="flow-1", category="flow", provider="alpaca:iex")

    service = ContextIntelligenceService(
        store=store,
        symbols={"NVDA", "KLAC"},
        clock=lambda: datetime(2026, 9, 1, 8, 1, tzinfo=UTC),
    )

    snapshot = service.snapshot("nvda", flow_items=[flow])

    assert snapshot.symbol == "NVDA"
    assert [item.item_id for item in snapshot.news] == ["news-1"]
    assert [item.item_id for item in snapshot.filings] == ["filing-1"]
    assert [item.item_id for item in snapshot.government] == ["government-1"]
    assert [item.item_id for item in snapshot.flow] == ["flow-1"]
    assert snapshot.generated_at == datetime(2026, 9, 1, 8, 1, tzinfo=UTC)


def test_snapshot_rejects_symbol_outside_configured_universe(tmp_path) -> None:
    service = ContextIntelligenceService(
        store=SQLiteContextStore(tmp_path / "context.db"),
        symbols={"NVDA"},
    )

    with pytest.raises(LookupError, match="configured context universe"):
        service.snapshot("AAPL")


class _FailingNewsIterator:
    def __aiter__(self):
        return self

    async def __anext__(self) -> ContextItem:
        raise RuntimeError("news disconnected")


class _FailingNewsStream:
    def stream(self) -> _FailingNewsIterator:
        return _FailingNewsIterator()


@pytest.mark.asyncio
async def test_news_loop_failure_isolated_and_source_health_reports_degraded(tmp_path) -> None:
    service = ContextIntelligenceService(
        store=SQLiteContextStore(tmp_path / "context.db"),
        symbols={"NVDA"},
        news_stream=_FailingNewsStream(),
        retry_seconds=0.01,
        retry_max_seconds=0.02,
    )

    await service.start()
    await asyncio.sleep(0.035)
    health = service.source_health()["alpaca-news"]
    await service.stop()

    assert health.configured is True
    assert health.failure_count >= 1
    assert health.last_error == "RuntimeError: news disconnected"
    assert health.running is True


class _FakeSecClient:
    def __init__(self, items: list[ContextItem]) -> None:
        self.items = items
        self.calls: list[tuple[str, str | None]] = []

    async def fetch_recent(
        self,
        symbol: str,
        *,
        since_accession: str | None = None,
    ) -> list[ContextItem]:
        self.calls.append((symbol, since_accession))
        return [item for item in self.items if symbol in item.symbols]


@pytest.mark.asyncio
async def test_sec_refresh_persists_verified_filings_across_service_restart(tmp_path) -> None:
    path = tmp_path / "context.db"
    filing = _item(
        item_id="sec:0001045810-26-000123",
        category="filing",
        provider="sec-edgar",
    ).model_copy(update={"tags": ["accession:0001045810-26-000123"]})
    sec = _FakeSecClient([filing])
    first = ContextIntelligenceService(
        store=SQLiteContextStore(path),
        symbols={"NVDA"},
        sec_client=sec,
    )

    await first.refresh_sec_once()
    assert first.source_health()["sec-edgar"].last_success_at is not None

    restarted = ContextIntelligenceService(
        store=SQLiteContextStore(path),
        symbols={"NVDA"},
    )
    snapshot = restarted.snapshot("NVDA")
    assert [item.item_id for item in snapshot.filings] == [
        "sec:0001045810-26-000123"
    ]


def test_unconfigured_sources_are_explicit_in_health(tmp_path) -> None:
    service = ContextIntelligenceService(
        store=SQLiteContextStore(tmp_path / "context.db"),
        symbols={"NVDA"},
    )

    health = service.source_health()

    assert health["alpaca-news"].configured is False
    assert health["sec-edgar"].configured is False
    assert health["federal-register"].configured is False
    assert all(item.running is False for item in health.values())
