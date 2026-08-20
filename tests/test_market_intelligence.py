from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.models import Candle, Side
from app.market.features import TradePrint, anchored_vwap, order_flow_imbalance, volume_profile, vwap
from app.market.options import (
    GEXAssumptions,
    OptionOpenInterestPoint,
    OptionRight,
    estimate_gamma_structure,
)
from app.research.market_intelligence import MarketStructureSnapshot


def candle(
    minute: int,
    *,
    high: float,
    low: float,
    close: float,
    volume: float,
) -> Candle:
    opened = datetime(2026, 8, 20, 13, minute, tzinfo=UTC)
    return Candle(
        symbol="NVDA",
        interval="1m",
        open_time=opened,
        close_time=opened + timedelta(minutes=1),
        open=close,
        high=high,
        low=low,
        close=close,
        volume=volume,
        source="test",
    )


def test_vwap_uses_volume_weighted_typical_price() -> None:
    candles = [
        candle(0, high=11, low=9, close=10, volume=100),
        candle(1, high=22, low=18, close=20, volume=300),
    ]

    result = vwap(candles)

    assert result == Decimal("17.5")


def test_anchored_vwap_excludes_observations_before_anchor() -> None:
    candles = [
        candle(0, high=11, low=9, close=10, volume=100),
        candle(1, high=22, low=18, close=20, volume=300),
    ]

    result = anchored_vwap(candles, anchor=candles[1].open_time)

    assert result == Decimal("20")


def test_volume_profile_reports_poc_hvn_and_lvn_from_explicit_bins() -> None:
    candles = [
        candle(0, high=101, low=99, close=100, volume=10),
        candle(1, high=102, low=100, close=101, volume=90),
        candle(2, high=111, low=109, close=110, volume=30),
        candle(3, high=121, low=119, close=120, volume=5),
    ]

    profile = volume_profile(candles, bin_size=Decimal("10"))

    assert profile.poc == Decimal("100")
    assert profile.hvn[0] == Decimal("100")
    assert profile.lvn[0] == Decimal("120")
    assert profile.methodology == "close-price-volume-bin-proxy"


def test_order_flow_imbalance_uses_aggressor_classified_trade_volume() -> None:
    prints = [
        TradePrint(price=Decimal("100"), size=Decimal("30"), aggressor=Side.BUY),
        TradePrint(price=Decimal("100.1"), size=Decimal("10"), aggressor=Side.SELL),
    ]

    result = order_flow_imbalance(prints)

    assert result == Decimal("0.5")


def test_gex_proxy_requires_explicit_sign_assumptions_and_preserves_methodology() -> None:
    assumptions = GEXAssumptions(
        label="calls-positive-puts-negative-open-interest-proxy",
        call_sign=1,
        put_sign=-1,
    )
    options = [
        OptionOpenInterestPoint(
            strike=Decimal("105"),
            right=OptionRight.CALL,
            open_interest=Decimal("100"),
            gamma=Decimal("0.02"),
        ),
        OptionOpenInterestPoint(
            strike=Decimal("95"),
            right=OptionRight.PUT,
            open_interest=Decimal("200"),
            gamma=Decimal("0.015"),
        ),
    ]

    structure = estimate_gamma_structure(
        spot=Decimal("100"),
        options=options,
        assumptions=assumptions,
    )

    assert structure.net_gex_1pct == Decimal("-10000.00000")
    assert structure.call_wall == Decimal("105")
    assert structure.put_wall == Decimal("95")
    assert structure.gamma_flip is None
    assert structure.methodology == assumptions.label
    assert "not observed dealer inventory" in structure.caveat.lower()


def test_gex_signs_must_be_explicit_directional_signs() -> None:
    with pytest.raises(ValueError, match="-1 or 1"):
        GEXAssumptions(label="bad", call_sign=0, put_sign=-1)


def test_market_structure_snapshot_is_analysis_not_direct_execution() -> None:
    snapshot = MarketStructureSnapshot(
        symbol="NVDA",
        vwap=Decimal("200"),
        call_wall=Decimal("220"),
        put_wall=Decimal("190"),
    )

    assert snapshot.execution_allowed is False
