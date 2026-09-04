from __future__ import annotations

import importlib
import importlib.util
from datetime import UTC, datetime, timedelta

from app.intelligence.models import ContextItem, ContextSource, EvidenceKind


def _store_class():
    spec = importlib.util.find_spec("app.intelligence.store")
    assert spec is not None, "context intelligence store module is missing"
    return importlib.import_module("app.intelligence.store").SQLiteContextStore


def _item(
    item_id: str,
    *,
    symbol: str,
    category: str,
    provider: str,
    when: datetime,
    summary: str,
) -> ContextItem:
    return ContextItem(
        item_id=item_id,
        symbols=[symbol],
        category=category,
        label=f"{category}:{item_id}",
        summary=summary,
        event_time=when,
        published_at=when,
        ingested_at=when + timedelta(seconds=1),
        freshness_sla_seconds=120,
        evidence_kind=EvidenceKind.FACT,
        confidence="1",
        source=ContextSource(
            provider=provider,
            source_type=category,
            official=provider == "sec-edgar",
            coverage="test coverage",
        ),
    )


def test_store_upserts_stable_provider_id_without_duplicate(tmp_path) -> None:
    Store = _store_class()
    path = tmp_path / "context.db"
    store = Store(path)
    when = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)

    store.upsert(
        _item(
            "alpaca-news:42",
            symbol="NVDA",
            category="news",
            provider="alpaca-news",
            when=when,
            summary="first version",
        )
    )
    store.upsert(
        _item(
            "alpaca-news:42",
            symbol="NVDA",
            category="news",
            provider="alpaca-news",
            when=when + timedelta(seconds=5),
            summary="updated version",
        )
    )

    recent = store.recent("NVDA", category="news", limit=10)
    assert len(recent) == 1
    assert recent[0].summary == "updated version"


def test_store_persists_context_across_restart(tmp_path) -> None:
    Store = _store_class()
    path = tmp_path / "context.db"
    when = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
    Store(path).upsert(
        _item(
            "sec:000123",
            symbol="KLAC",
            category="filing",
            provider="sec-edgar",
            when=when,
            summary="8-K filed",
        )
    )

    reopened = Store(path)
    recent = reopened.recent("KLAC", category="filing", limit=10)
    assert [item.item_id for item in recent] == ["sec:000123"]


def test_store_filters_by_symbol_and_category_and_orders_newest_first(tmp_path) -> None:
    Store = _store_class()
    store = Store(tmp_path / "context.db")
    base = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
    store.upsert(
        _item(
            "n1",
            symbol="NVDA",
            category="news",
            provider="alpaca-news",
            when=base,
            summary="older NVDA news",
        )
    )
    store.upsert(
        _item(
            "n2",
            symbol="NVDA",
            category="news",
            provider="alpaca-news",
            when=base + timedelta(minutes=1),
            summary="newer NVDA news",
        )
    )
    store.upsert(
        _item(
            "f1",
            symbol="NVDA",
            category="filing",
            provider="sec-edgar",
            when=base + timedelta(minutes=2),
            summary="NVDA filing",
        )
    )
    store.upsert(
        _item(
            "k1",
            symbol="KLAC",
            category="news",
            provider="alpaca-news",
            when=base + timedelta(minutes=3),
            summary="KLAC news",
        )
    )

    recent = store.recent("NVDA", category="news", limit=10)
    assert [item.item_id for item in recent] == ["n2", "n1"]


def test_store_tracks_latest_event_time_per_provider(tmp_path) -> None:
    Store = _store_class()
    store = Store(tmp_path / "context.db")
    base = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
    store.upsert(
        _item(
            "a1",
            symbol="NVDA",
            category="news",
            provider="alpaca-news",
            when=base,
            summary="first",
        )
    )
    store.upsert(
        _item(
            "a2",
            symbol="KLAC",
            category="news",
            provider="alpaca-news",
            when=base + timedelta(seconds=30),
            summary="second",
        )
    )

    assert store.latest_provider_event("alpaca-news") == base + timedelta(seconds=30)
    assert store.latest_provider_event("sec-edgar") is None
