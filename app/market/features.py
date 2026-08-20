from __future__ import annotations

from datetime import datetime
from decimal import ROUND_FLOOR, Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import Candle, Side


class TradePrint(BaseModel):
    model_config = ConfigDict(frozen=True)

    price: Decimal
    size: Decimal
    aggressor: Side


class VolumeProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    poc: Decimal | None = None
    hvn: list[Decimal] = Field(default_factory=list)
    lvn: list[Decimal] = Field(default_factory=list)
    bins: dict[str, Decimal] = Field(default_factory=dict)
    methodology: str = "close-price-volume-bin-proxy"


def _decimal(value: float | int | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def vwap(candles: list[Candle]) -> Decimal | None:
    total_volume = Decimal("0")
    weighted = Decimal("0")
    for item in candles:
        volume = _decimal(item.volume)
        if volume <= 0:
            continue
        typical = (
            _decimal(item.high) + _decimal(item.low) + _decimal(item.close)
        ) / Decimal("3")
        weighted += typical * volume
        total_volume += volume
    return weighted / total_volume if total_volume else None


def anchored_vwap(candles: list[Candle], *, anchor: datetime) -> Decimal | None:
    return vwap([item for item in candles if item.open_time >= anchor])


def volume_profile(
    candles: list[Candle],
    *,
    bin_size: Decimal,
    node_count: int = 3,
) -> VolumeProfile:
    """Approximate profile using each candle's close and full candle volume.

    This is intentionally labeled a proxy; true volume-at-price requires trade
    or lower-level distribution data rather than OHLCV candles alone.
    """

    if bin_size <= 0:
        raise ValueError("bin_size must be positive")
    if node_count <= 0:
        raise ValueError("node_count must be positive")

    totals: dict[Decimal, Decimal] = {}
    for item in candles:
        volume = _decimal(item.volume)
        if volume <= 0:
            continue
        close = _decimal(item.close)
        bucket = (close / bin_size).to_integral_value(rounding=ROUND_FLOOR) * bin_size
        totals[bucket] = totals.get(bucket, Decimal("0")) + volume

    if not totals:
        return VolumeProfile()

    ranked_high = sorted(totals, key=lambda price: (-totals[price], price))
    ranked_low = sorted(totals, key=lambda price: (totals[price], price))
    return VolumeProfile(
        poc=ranked_high[0],
        hvn=ranked_high[:node_count],
        lvn=ranked_low[:node_count],
        bins={str(price): totals[price] for price in sorted(totals)},
    )


def order_flow_imbalance(prints: list[TradePrint]) -> Decimal | None:
    """Return aggressor-volume imbalance in [-1, 1]."""

    buy = sum(
        (item.size for item in prints if item.aggressor is Side.BUY),
        Decimal("0"),
    )
    sell = sum(
        (item.size for item in prints if item.aggressor is Side.SELL),
        Decimal("0"),
    )
    total = buy + sell
    return (buy - sell) / total if total > 0 else None
