from __future__ import annotations

import importlib
import importlib.util
from datetime import UTC, datetime, timedelta


def _models_module():
    spec = importlib.util.find_spec("app.intelligence.models")
    assert spec is not None, "context intelligence models module is missing"
    return importlib.import_module("app.intelligence.models")


def _freshness_module():
    spec = importlib.util.find_spec("app.intelligence.freshness")
    assert spec is not None, "context intelligence freshness module is missing"
    return importlib.import_module("app.intelligence.freshness")


def test_context_item_classifies_realtime_news_by_source_specific_sla() -> None:
    models = _models_module()
    freshness = _freshness_module()
    now = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
    source = models.ContextSource(
        provider="alpaca-news",
        source_type="news",
        official=False,
        coverage="symbol-tagged provider news",
    )
    item = models.ContextItem(
        item_id="alpaca-news:123",
        symbols=["NVDA"],
        category="news",
        label="NVDA supplier update",
        summary="Provider-normalized news item.",
        event_time=now - timedelta(seconds=30),
        published_at=now - timedelta(seconds=30),
        ingested_at=now - timedelta(seconds=2),
        freshness_sla_seconds=120,
        evidence_kind=models.EvidenceKind.FACT,
        confidence="1",
        source=source,
    )

    assert freshness.classify_freshness(item, now) is models.FreshnessClass.REALTIME


def test_delayed_structural_source_never_becomes_realtime_even_when_recent() -> None:
    models = _models_module()
    freshness = _freshness_module()
    now = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
    item = models.ContextItem(
        item_id="finra-short:NVDA:20260825",
        symbols=["NVDA"],
        category="flow",
        label="FINRA daily short-sale volume",
        summary="Daily structural evidence.",
        event_time=now - timedelta(minutes=1),
        published_at=now - timedelta(minutes=1),
        ingested_at=now,
        freshness_sla_seconds=86400,
        evidence_kind=models.EvidenceKind.DERIVED,
        confidence="1",
        source=models.ContextSource(
            provider="finra-daily-short-volume",
            source_type="regulatory-market-data",
            official=True,
            coverage="daily off-exchange reported short-sale volume",
            latency_class="delayed",
        ),
    )

    assert freshness.classify_freshness(item, now) is models.FreshnessClass.DELAYED


def test_old_realtime_item_expires_to_stale() -> None:
    models = _models_module()
    freshness = _freshness_module()
    now = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
    item = models.ContextItem(
        item_id="news:old",
        symbols=["KLAC"],
        category="news",
        label="Old item",
        summary="Expired realtime evidence.",
        event_time=now - timedelta(minutes=20),
        published_at=now - timedelta(minutes=20),
        ingested_at=now - timedelta(minutes=20),
        freshness_sla_seconds=120,
        evidence_kind=models.EvidenceKind.FACT,
        confidence="1",
        source=models.ContextSource(
            provider="alpaca-news",
            source_type="news",
            official=False,
            coverage="symbol-tagged provider news",
        ),
    )

    assert freshness.classify_freshness(item, now) is models.FreshnessClass.STALE


def test_negative_provider_latency_is_clamped_and_flagged() -> None:
    models = _models_module()
    now = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
    item = models.ContextItem(
        item_id="clock-skew",
        symbols=["SPCX"],
        category="filing",
        label="Clock skew",
        summary="Provider timestamp arrived after ingestion timestamp.",
        event_time=now + timedelta(seconds=5),
        published_at=now + timedelta(seconds=5),
        ingested_at=now,
        freshness_sla_seconds=120,
        evidence_kind=models.EvidenceKind.FACT,
        confidence="1",
        source=models.ContextSource(
            provider="sec-edgar",
            source_type="filing",
            official=True,
            coverage="company submissions",
        ),
    )

    assert item.provider_latency_seconds == 0
    assert item.clock_anomaly is True
