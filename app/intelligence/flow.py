from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.intelligence.models import ContextItem, ContextSource, EvidenceKind
from app.market.coverage import MarketCoverageSnapshot
from app.research.market_intelligence import MarketStructureSnapshot


def build_flow_context(
    symbol: str,
    structure: MarketStructureSnapshot,
    coverage: MarketCoverageSnapshot,
    *,
    freshness_sla_seconds: int,
    now: datetime | None = None,
) -> list[ContextItem]:
    normalized_symbol = symbol.strip().upper()
    symbol_coverage = coverage.symbols.get(normalized_symbol)
    if symbol_coverage is None or symbol_coverage.status == "missing":
        return []
    if symbol_coverage.close_time is None or symbol_coverage.source is None:
        return []

    observed_at = _utc(symbol_coverage.close_time)
    ingested_at = _utc(now or coverage.generated_at)
    provider = symbol_coverage.source
    source = ContextSource(
        provider=provider,
        source_type="market-structure",
        official=False,
        coverage=_coverage_description(
            provider,
            symbol_coverage.status,
            symbol_coverage.cycle_status,
        ),
        latency_class="realtime",
    )
    base_metadata = {
        "feed_status": symbol_coverage.status,
        "cycle_status": symbol_coverage.cycle_status,
        "market_interval": coverage.interval,
    }
    if symbol_coverage.latest_price is not None:
        base_metadata["latest_price"] = str(symbol_coverage.latest_price)

    metrics: list[tuple[str, Decimal | None, str, str]] = [
        ("VWAP", structure.vwap, "vwap", "vwap"),
        (
            "Order Flow Imbalance",
            structure.order_flow_imbalance,
            "order_flow",
            "order-flow-imbalance",
        ),
        ("Net GEX Proxy", structure.net_gex_1pct, "gex", "net-gex-1pct"),
        ("Put Wall Estimate", structure.put_wall, "gex", "put-wall"),
        ("Call Wall Estimate", structure.call_wall, "gex", "call-wall"),
    ]

    items: list[ContextItem] = []
    for label, value, methodology_key, metric_id in metrics:
        if value is None:
            continue
        metadata = dict(base_metadata)
        methodology = structure.methodology.get(methodology_key)
        if methodology:
            metadata["methodology"] = methodology
        items.append(
            ContextItem(
                item_id=(
                    f"flow:{normalized_symbol}:{metric_id}:"
                    f"{observed_at.isoformat()}"
                ),
                symbols=[normalized_symbol],
                category="flow",
                label=label,
                summary=f"{normalized_symbol} {label} = {value}",
                event_time=observed_at,
                published_at=observed_at,
                ingested_at=ingested_at,
                freshness_sla_seconds=freshness_sla_seconds,
                evidence_kind=EvidenceKind.DERIVED,
                confidence=_metric_confidence(label, structure.confidence),
                tags=[f"metric:{metric_id}", f"feed:{provider}"],
                metadata=metadata,
                source=source,
            )
        )
    return items


def _coverage_description(provider: str, feed_status: str, cycle_status: str) -> str:
    normalized = provider.strip().lower()
    if normalized.startswith("alpaca:iex"):
        feed = "Alpaca IEX single-exchange market feed"
    elif normalized.startswith("alpaca:sip"):
        feed = "Alpaca SIP consolidated US market feed"
    else:
        feed = f"market feed {provider}"
    return f"{feed}; feed {feed_status}; cycle {cycle_status}"


def _metric_confidence(label: str, structure_confidence: Decimal) -> Decimal:
    if label in {"Net GEX Proxy", "Put Wall Estimate", "Call Wall Estimate"}:
        return min(max(structure_confidence, Decimal("0")), Decimal("1"))
    return Decimal("1")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
