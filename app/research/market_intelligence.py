"""Research primitives for market structure analysis.

Read-only analytical layer. No execution capability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class PriceZone:
    """A price area detected from market structure."""

    lower: Decimal
    upper: Decimal
    label: str
    source: str


@dataclass(frozen=True)
class MarketStructureSnapshot:
    """Derived research state, not a trading instruction."""

    symbol: str
    supports: list[PriceZone] = field(default_factory=list)
    resistances: list[PriceZone] = field(default_factory=list)
    vwap: Decimal | None = None
    volume_profile_poc: Decimal | None = None
    gamma_flip: Decimal | None = None
    call_wall: Decimal | None = None
    put_wall: Decimal | None = None
    confidence: Decimal = Decimal("0")

    @property
    def execution_allowed(self) -> bool:
        return False
