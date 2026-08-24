from __future__ import annotations

from collections.abc import Mapping, Set
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.store.sqlite import SQLiteStore


class MarketSymbolCoverage(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    source: str | None = None
    latest_price: Decimal | None = None
    open_time: datetime | None = None
    close_time: datetime | None = None
    age_seconds: float | None = None
    cycle_status: str
    cycle_error: str | None = None


class MarketCoverageSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    market_source: str
    interval: str
    fresh_symbols: list[str] = Field(default_factory=list)
    stale_symbols: list[str] = Field(default_factory=list)
    missing_symbols: list[str] = Field(default_factory=list)
    fresh_coverage_ratio: float
    symbols: dict[str, MarketSymbolCoverage]


def build_market_coverage(
    *,
    store: SQLiteStore,
    symbols: Set[str],
    interval: str,
    market_source: str,
    max_age_seconds: float,
    last_cycle_results: Mapping[str, object],
    last_cycle_errors: Mapping[str, str],
    now: datetime | None = None,
) -> MarketCoverageSnapshot:
    generated_at = now or datetime.now(UTC)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)
    generated_at = generated_at.astimezone(UTC)

    normalized_symbols = sorted({symbol.strip().upper() for symbol in symbols if symbol.strip()})
    coverage: dict[str, MarketSymbolCoverage] = {}
    fresh_symbols: list[str] = []
    stale_symbols: list[str] = []
    missing_symbols: list[str] = []

    for symbol in normalized_symbols:
        cycle_error = last_cycle_errors.get(symbol)
        cycle_status = (
            "error"
            if cycle_error is not None
            else "observed"
            if symbol in last_cycle_results
            else "waiting"
        )
        latest = store.latest_candle(symbol, interval=interval)
        if latest is None:
            missing_symbols.append(symbol)
            coverage[symbol] = MarketSymbolCoverage(
                status="missing",
                cycle_status=cycle_status,
                cycle_error=cycle_error,
            )
            continue

        close_time = latest.close_time
        if close_time.tzinfo is None:
            close_time = close_time.replace(tzinfo=UTC)
        close_time = close_time.astimezone(UTC)
        age_seconds = max((generated_at - close_time).total_seconds(), 0.0)
        status = "fresh" if age_seconds <= max_age_seconds else "stale"
        if status == "fresh":
            fresh_symbols.append(symbol)
        else:
            stale_symbols.append(symbol)

        coverage[symbol] = MarketSymbolCoverage(
            status=status,
            source=latest.source,
            latest_price=Decimal(str(latest.close)),
            open_time=latest.open_time,
            close_time=latest.close_time,
            age_seconds=age_seconds,
            cycle_status=cycle_status,
            cycle_error=cycle_error,
        )

    denominator = len(normalized_symbols)
    ratio = len(fresh_symbols) / denominator if denominator else 0.0
    return MarketCoverageSnapshot(
        generated_at=generated_at,
        market_source=market_source,
        interval=interval,
        fresh_symbols=fresh_symbols,
        stale_symbols=stale_symbols,
        missing_symbols=missing_symbols,
        fresh_coverage_ratio=ratio,
        symbols=coverage,
    )
