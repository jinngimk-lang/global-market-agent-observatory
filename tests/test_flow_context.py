from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.intelligence.freshness import classify_freshness
from app.intelligence.models import EvidenceKind, FreshnessClass
from app.market.coverage import MarketCoverageSnapshot, MarketSymbolCoverage
from app.research.market_intelligence import MarketStructureSnapshot


def _coverage(*, when: datetime, status: str = "fresh") -> MarketCoverageSnapshot:
    return MarketCoverageSnapshot(
        generated_at=when + timedelta(seconds=2),
        market_source="alpaca",
        interval="1m",
        fresh_symbols=["NVDA"] if status == "fresh" else [],
        stale_symbols=["NVDA"] if status == "stale" else [],
        missing_symbols=[],
        fresh_coverage_ratio=1.0 if status == "fresh" else 0.0,
        symbols={
            "NVDA": MarketSymbolCoverage(
                status=status,
                source="alpaca:iex",
                latest_price=Decimal("201"),
                open_time=when - timedelta(minutes=1),
                close_time=when,
                age_seconds=2.0 if status == "fresh" else 30.0,
                cycle_status="observed",
            )
        },
    )


def test_flow_context_preserves_market_structure_methodology_and_coverage() -> None:
    from app.intelligence.flow import build_flow_context

    observed_at = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
    structure = MarketStructureSnapshot(
        symbol="NVDA",
        vwap=Decimal("200"),
        order_flow_imbalance=Decimal("0.25"),
        net_gex_1pct=Decimal("1500000"),
        put_wall=Decimal("195"),
        call_wall=Decimal("210"),
        methodology={
            "vwap": "typical-price-volume:last-200-candles",
            "order_flow": "signed-volume-proxy",
            "gex": "OI*gamma*spot^2*1% proxy; dealer inventory inferred",
        },
    )

    items = build_flow_context(
        "NVDA",
        structure,
        _coverage(when=observed_at),
        freshness_sla_seconds=5,
        now=observed_at + timedelta(seconds=2),
    )

    by_label = {item.label: item for item in items}
    assert set(by_label) == {
        "VWAP",
        "Order Flow Imbalance",
        "Net GEX Proxy",
        "Put Wall Estimate",
        "Call Wall Estimate",
    }
    assert all(item.evidence_kind is EvidenceKind.DERIVED for item in items)
    assert all(item.category == "flow" for item in items)
    assert all(item.source.provider == "alpaca:iex" for item in items)
    assert all("IEX single-exchange" in item.source.coverage for item in items)
    assert by_label["VWAP"].metadata["methodology"] == (
        "typical-price-volume:last-200-candles"
    )
    assert by_label["Order Flow Imbalance"].metadata["methodology"] == (
        "signed-volume-proxy"
    )
    assert "dealer inventory inferred" in by_label["Net GEX Proxy"].metadata[
        "methodology"
    ]
    assert by_label["VWAP"].metadata["latest_price"] == "201"
    assert classify_freshness(
        by_label["VWAP"], observed_at + timedelta(seconds=2)
    ) is FreshnessClass.REALTIME


def test_flow_context_omits_missing_metrics_instead_of_zero_filling() -> None:
    from app.intelligence.flow import build_flow_context

    observed_at = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
    structure = MarketStructureSnapshot(
        symbol="NVDA",
        vwap=Decimal("200"),
        methodology={"vwap": "verified-vwap"},
    )

    items = build_flow_context(
        "NVDA",
        structure,
        _coverage(when=observed_at),
        freshness_sla_seconds=5,
        now=observed_at + timedelta(seconds=2),
    )

    assert [item.label for item in items] == ["VWAP"]
    assert "0" not in items[0].metadata.values()


def test_stale_market_coverage_cannot_be_presented_as_realtime_flow() -> None:
    from app.intelligence.flow import build_flow_context

    observed_at = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
    now = observed_at + timedelta(seconds=30)
    items = build_flow_context(
        "NVDA",
        MarketStructureSnapshot(
            symbol="NVDA",
            vwap=Decimal("200"),
            methodology={"vwap": "verified-vwap"},
        ),
        _coverage(when=observed_at, status="stale"),
        freshness_sla_seconds=5,
        now=now,
    )

    assert len(items) == 1
    assert classify_freshness(items[0], now) is FreshnessClass.STALE
    assert items[0].metadata["feed_status"] == "stale"


def test_flow_context_returns_no_verified_data_when_symbol_coverage_is_missing() -> None:
    from app.intelligence.flow import build_flow_context

    now = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
    coverage = MarketCoverageSnapshot(
        generated_at=now,
        market_source="alpaca",
        interval="1m",
        fresh_symbols=[],
        stale_symbols=[],
        missing_symbols=["NVDA"],
        fresh_coverage_ratio=0.0,
        symbols={
            "NVDA": MarketSymbolCoverage(status="missing", cycle_status="waiting")
        },
    )

    items = build_flow_context(
        "NVDA",
        MarketStructureSnapshot(symbol="NVDA", vwap=Decimal("200")),
        coverage,
        freshness_sla_seconds=5,
        now=now,
    )

    assert items == []
