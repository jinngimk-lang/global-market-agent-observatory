from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from app.market.alpaca_options import OptionChainObservation
from app.market.options import GEXAssumptions, estimate_gamma_structure
from app.research.market_intelligence import MarketStructureSnapshot


class OptionsChainSource(Protocol):
    async def fetch_chain(
        self,
        underlying_symbol: str,
        *,
        expiration_date_gte: date,
        expiration_date_lte: date,
        fetched_at: datetime | None = None,
    ) -> OptionChainObservation: ...


class OptionsStructureService:
    """Build fresh, provenance-carrying option structure snapshots.

    The service caches only a bounded-lifetime structure. Expired or explicitly
    invalidated data returns ``None`` so callers fail closed rather than trade on
    stale walls.
    """

    def __init__(
        self,
        *,
        source: OptionsChainSource,
        expiration_horizon_days: int = 45,
        max_age_seconds: float = 120.0,
        assumptions: GEXAssumptions | None = None,
    ) -> None:
        if expiration_horizon_days <= 0:
            raise ValueError("expiration_horizon_days must be positive")
        if max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")
        self.source = source
        self.expiration_horizon_days = expiration_horizon_days
        self.max_age_seconds = max_age_seconds
        self.assumptions = assumptions or GEXAssumptions(
            label="oi-gamma-proxy: calls +1, puts -1",
            call_sign=1,
            put_sign=-1,
        )
        self._structures: dict[str, tuple[datetime, MarketStructureSnapshot]] = {}

    async def refresh(
        self,
        symbol: str,
        spot: Decimal,
        *,
        observed_at: datetime | None = None,
    ) -> MarketStructureSnapshot:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        if spot <= 0:
            raise ValueError("spot must be positive")

        observed = observed_at or datetime.now(UTC)
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=UTC)
        observed = observed.astimezone(UTC)
        expiry_end = observed.date() + timedelta(days=self.expiration_horizon_days)
        chain = await self.source.fetch_chain(
            normalized,
            expiration_date_gte=observed.date(),
            expiration_date_lte=expiry_end,
            fetched_at=observed,
        )
        estimate = estimate_gamma_structure(
            spot=spot,
            options=chain.gex_inputs(),
            assumptions=self.assumptions,
        )

        oi_sources = sorted({item.open_interest_source for item in chain.contracts})
        greek_sources = sorted({item.greeks_source for item in chain.contracts})
        oi_dates = sorted({item.open_interest_date.isoformat() for item in chain.contracts})
        structure = MarketStructureSnapshot(
            symbol=normalized,
            net_gex_1pct=estimate.net_gex_1pct,
            gamma_flip=estimate.gamma_flip,
            call_wall=estimate.call_wall,
            put_wall=estimate.put_wall,
            confidence=Decimal("0.5") if chain.contracts else Decimal("0"),
            methodology={
                "gamma": estimate.methodology,
                "gamma_caveat": estimate.caveat,
                "options_provider": chain.provider,
                "options_feed": chain.feed,
                "open_interest_source": ",".join(oi_sources),
                "greeks_source": ",".join(greek_sources),
                "open_interest_dates": ",".join(oi_dates),
                "options_fetched_at": chain.fetched_at.astimezone(UTC).isoformat(),
            },
        )
        self._structures[normalized] = (observed, structure)
        return structure

    def structure_for(
        self,
        symbol: str,
        observed_at: datetime,
    ) -> MarketStructureSnapshot | None:
        normalized = symbol.strip().upper()
        cached = self._structures.get(normalized)
        if cached is None:
            return None
        refreshed_at, structure = cached
        current = observed_at
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        age = max(
            (current.astimezone(UTC) - refreshed_at.astimezone(UTC)).total_seconds(),
            0.0,
        )
        if age > self.max_age_seconds:
            return None
        return structure

    def invalidate(self, symbol: str) -> None:
        self._structures.pop(symbol.strip().upper(), None)

    def refreshed_at(self, symbol: str) -> datetime | None:
        cached = self._structures.get(symbol.strip().upper())
        return cached[0] if cached is not None else None
