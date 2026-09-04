from __future__ import annotations

from datetime import UTC, datetime

from app.intelligence.models import ContextItem, FreshnessClass

_NEAR_REALTIME_NEWS_SECONDS = 15 * 60


def classify_freshness(item: ContextItem, now: datetime) -> FreshnessClass:
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    now = now.astimezone(UTC)

    latency_class = item.source.latency_class.strip().lower()
    if latency_class == "delayed":
        return FreshnessClass.DELAYED

    age_seconds = max((now - item.event_time).total_seconds(), 0.0)
    if latency_class == "official-current":
        return (
            FreshnessClass.OFFICIAL_CURRENT
            if age_seconds <= item.freshness_sla_seconds
            else FreshnessClass.STALE
        )
    if latency_class == "near-realtime":
        return (
            FreshnessClass.NEAR_REALTIME
            if age_seconds <= item.freshness_sla_seconds
            else FreshnessClass.STALE
        )

    if age_seconds <= item.freshness_sla_seconds:
        return FreshnessClass.REALTIME
    if item.source.source_type.strip().lower() == "news" and age_seconds <= max(
        item.freshness_sla_seconds,
        _NEAR_REALTIME_NEWS_SECONDS,
    ):
        return FreshnessClass.NEAR_REALTIME
    return FreshnessClass.STALE
