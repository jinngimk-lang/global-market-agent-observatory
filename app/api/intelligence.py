from __future__ import annotations

from datetime import UTC, datetime
from math import ceil
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.intelligence.flow import build_flow_context
from app.intelligence.freshness import classify_freshness
from app.intelligence.models import ContextItem, SymbolContextSnapshot
from app.market.coverage import build_market_coverage
from app.settings import Settings


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _serialize_item(item: ContextItem, *, now: datetime) -> dict[str, Any]:
    payload = item.model_dump(mode="json")
    payload["freshness"] = classify_freshness(item, now).value
    payload["age_seconds"] = max((now - _utc(item.event_time)).total_seconds(), 0.0)
    payload["provider_latency_seconds"] = float(item.provider_latency_seconds)
    payload["clock_anomaly"] = item.clock_anomaly
    return payload


def _flow_snapshot(settings: Settings, runtime: object, symbol: str, now: datetime):
    latest = getattr(runtime.autonomous, "latest_structure_results", {})
    cycle = latest.get(symbol)
    if cycle is None or cycle.structure is None:
        return []
    coverage = build_market_coverage(
        store=runtime.store,
        symbols=settings.trading_universe,
        interval=settings.market_interval,
        market_source=settings.market_source,
        max_age_seconds=settings.market_data_max_age_seconds,
        last_cycle_results=runtime.last_cycle_results,
        last_cycle_errors=runtime.last_cycle_errors,
        generated_at=now,
    )
    return build_flow_context(
        symbol,
        cycle.structure,
        coverage,
        freshness_sla_seconds=max(1, ceil(settings.market_data_max_age_seconds)),
        now=now,
    )


def _metric_value(items: list[ContextItem], metric: str) -> float | None:
    for item in items:
        if item.metadata.get("metric") != metric:
            continue
        raw = item.metadata.get("value")
        if raw is None:
            continue
        try:
            return float(raw)
        except ValueError:
            continue
    return None


def _synthesize(snapshot: SymbolContextSnapshot) -> tuple[str, list[str]]:
    flags: list[str] = []
    latest_price = None
    for item in snapshot.flow:
        raw = item.metadata.get("latest_price")
        if raw is None:
            continue
        try:
            latest_price = float(raw)
            break
        except ValueError:
            continue
    vwap = _metric_value(snapshot.flow, "vwap")
    ofi = _metric_value(snapshot.flow, "order-flow-imbalance")

    flow_text = "资金行为暂无可验证实时结构"
    if latest_price is not None and vwap is not None and ofi is not None:
        if latest_price > vwap and ofi > 0:
            flow_text = "资金行为偏多：价格位于 VWAP 上方且 OFI 为正"
            flags.append("flow-bullish")
        elif latest_price < vwap and ofi < 0:
            flow_text = "资金行为偏空：价格位于 VWAP 下方且 OFI 为负"
            flags.append("flow-bearish")
        else:
            flow_text = "资金行为分化：价格/VWAP 与 OFI 尚未形成同向确认"
            flags.append("flow-mixed")

    counts = (
        f"新闻 {len(snapshot.news)} 条 · SEC {len(snapshot.filings)} 条 · "
        f"政府/监管 {len(snapshot.government)} 条 · 资金结构 {len(snapshot.flow)} 项"
    )
    if not any((snapshot.news, snapshot.filings, snapshot.government, snapshot.flow)):
        return "NO VERIFIED DATA", ["no-verified-data"]
    return (
        f"{flow_text}。当前可验证上下文：{counts}。"
        "新闻、披露和监管事件仅作为上下文事实，不自动解释为买入或卖出许可。",
        flags,
    )


def _snapshot_payload(
    snapshot: SymbolContextSnapshot,
    *,
    enabled: bool,
    now: datetime,
) -> dict[str, Any]:
    synthesis, flags = _synthesize(snapshot)
    return {
        "symbol": snapshot.symbol,
        "generated_at": now.isoformat(),
        "enabled": enabled,
        "execution_authority": "none",
        "synthesis": synthesis,
        "synthesis_confidence": None,
        "aggregate_flags": flags,
        "news": [_serialize_item(item, now=now) for item in snapshot.news],
        "filings": [_serialize_item(item, now=now) for item in snapshot.filings],
        "government": [
            _serialize_item(item, now=now) for item in snapshot.government
        ],
        "flow": [_serialize_item(item, now=now) for item in snapshot.flow],
    }


def build_intelligence_router(*, settings: Settings, runtime: object) -> APIRouter:
    router = APIRouter(prefix="/api/intelligence", tags=["context-intelligence"])

    @router.get("/status")
    async def intelligence_status() -> dict[str, Any]:
        return {
            "enabled": settings.context_intelligence_enabled,
            "generated_at": datetime.now(UTC).isoformat(),
            "refresh_hint_seconds": 5,
            "sources": {
                name: health.model_dump(mode="json")
                for name, health in runtime.context_intelligence.source_health().items()
            },
            "execution_authority": "none",
        }

    @router.get("/{symbol}")
    async def intelligence_for_symbol(symbol: str) -> dict[str, Any]:
        normalized = symbol.strip().upper()
        if normalized not in settings.trading_universe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "context_symbol_not_configured",
                    "message": "Symbol is outside the configured context universe.",
                },
            )
        now = datetime.now(UTC)
        flow_items = _flow_snapshot(settings, runtime, normalized, now)
        snapshot = runtime.context_intelligence.snapshot(
            normalized,
            flow_items=flow_items,
            limit_per_category=settings.context_recent_limit,
        )
        return _snapshot_payload(
            snapshot,
            enabled=settings.context_intelligence_enabled,
            now=now,
        )

    return router
