"""Market structure primitives for research only.

No execution path. Produces analytical zones from price history.
"""

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PriceLevel:
    price: float
    strength: float
    source: str = "swing"


@dataclass(frozen=True)
class PriceZone:
    lower: float
    upper: float
    kind: str
    confidence: float


def cluster_levels(levels: Iterable[PriceLevel], tolerance: float = 0.005) -> list[PriceZone]:
    """Cluster nearby price levels into research zones.

    This is intentionally deterministic. It does not generate trading signals.
    """
    ordered = sorted(levels, key=lambda x: x.price)
    zones: list[PriceZone] = []
    if not ordered:
        return zones

    group = [ordered[0]]
    for level in ordered[1:]:
        center = sum(x.price for x in group) / len(group)
        if abs(level.price - center) / center <= tolerance:
            group.append(level)
        else:
            zones.append(_make_zone(group))
            group = [level]
    zones.append(_make_zone(group))
    return zones


def _make_zone(group: list[PriceLevel]) -> PriceZone:
    values = [x.price for x in group]
    confidence = min(1.0, sum(x.strength for x in group) / max(len(group), 1))
    return PriceZone(min(values), max(values), "structure", confidence)
