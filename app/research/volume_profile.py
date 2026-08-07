"""Volume profile primitives for market research.

This module intentionally provides analytics only. It does not create
execution signals or trading actions.
"""

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class VolumeNode:
    price: float
    volume: float


@dataclass(frozen=True)
class VolumeProfile:
    poc: float | None
    value_area_high: float | None
    value_area_low: float | None
    nodes: tuple[VolumeNode, ...]


def build_volume_profile(nodes: Iterable[VolumeNode]) -> VolumeProfile:
    """Create a deterministic volume profile snapshot.

    The caller supplies already-normalized price/volume buckets.
    Calculation is deliberately separated from data ingestion.
    """
    items = tuple(nodes)
    if not items:
        return VolumeProfile(None, None, None, ())

    poc_node = max(items, key=lambda item: item.volume)
    prices = sorted(item.price for item in items)

    return VolumeProfile(
        poc=poc_node.price,
        value_area_low=prices[0],
        value_area_high=prices[-1],
        nodes=items,
    )
