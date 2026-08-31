from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.domain.models import Candle


class SupportResistanceLevels(BaseModel):
    model_config = ConfigDict(frozen=True)

    support: float | None = None
    resistance: float | None = None
    latest_close: float | None = None
    support_method: str
    resistance_method: str
    methodology: str = "confirmed-price-pivots"
    lookback: int
    pivot_width: int
    observation_count: int


def derive_support_resistance(
    candles: list[Candle],
    *,
    pivot_width: int = 2,
    lookback: int = 120,
) -> SupportResistanceLevels:
    if pivot_width <= 0:
        raise ValueError("pivot_width must be positive")
    if lookback <= 0:
        raise ValueError("lookback must be positive")

    window = candles[-lookback:]
    required = pivot_width * 2 + 1
    if len(window) < required:
        return SupportResistanceLevels(
            latest_close=float(window[-1].close) if window else None,
            support_method="insufficient-history",
            resistance_method="insufficient-history",
            lookback=lookback,
            pivot_width=pivot_width,
            observation_count=len(window),
        )

    lows: list[float] = []
    highs: list[float] = []
    for index in range(pivot_width, len(window) - pivot_width):
        current = window[index]
        neighbors = (
            window[index - pivot_width : index]
            + window[index + 1 : index + pivot_width + 1]
        )
        if all(float(current.low) < float(item.low) for item in neighbors):
            lows.append(float(current.low))
        if all(float(current.high) > float(item.high) for item in neighbors):
            highs.append(float(current.high))

    latest_close = float(window[-1].close)
    support_candidates = [value for value in lows if value <= latest_close]
    resistance_candidates = [value for value in highs if value >= latest_close]

    if support_candidates:
        support = max(support_candidates)
        support_method = "confirmed-pivot"
    else:
        support = min(float(item.low) for item in window)
        support_method = "lookback-extreme"

    if resistance_candidates:
        resistance = min(resistance_candidates)
        resistance_method = "confirmed-pivot"
    else:
        resistance = max(float(item.high) for item in window)
        resistance_method = "lookback-extreme"

    return SupportResistanceLevels(
        support=support,
        resistance=resistance,
        latest_close=latest_close,
        support_method=support_method,
        resistance_method=resistance_method,
        lookback=lookback,
        pivot_width=pivot_width,
        observation_count=len(window),
    )
