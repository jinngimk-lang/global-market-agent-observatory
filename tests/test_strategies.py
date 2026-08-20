from __future__ import annotations

from decimal import Decimal

from app.research.market_intelligence import MarketStructureSnapshot
from app.strategy.base import StrategyAction, StrategyInput
from app.strategy.gamma_levels import GammaLevelsStrategy
from app.strategy.vwap import VWAPStrategy


def market_input(
    *,
    current: str,
    previous: str | None = None,
    vwap: str | None = None,
    put_wall: str | None = None,
    call_wall: str | None = None,
    imbalance: str | None = None,
) -> StrategyInput:
    return StrategyInput(
        symbol="NVDA",
        current_price=Decimal(current),
        previous_price=(Decimal(previous) if previous is not None else None),
        structure=MarketStructureSnapshot(
            symbol="NVDA",
            vwap=(Decimal(vwap) if vwap is not None else None),
            put_wall=(Decimal(put_wall) if put_wall is not None else None),
            call_wall=(Decimal(call_wall) if call_wall is not None else None),
            order_flow_imbalance=(Decimal(imbalance) if imbalance is not None else None),
        ),
    )


def test_vwap_reclaim_emits_buy_signal_with_invalidation() -> None:
    signal = VWAPStrategy().evaluate(
        market_input(current="201", previous="199", vwap="200")
    )

    assert signal.action is StrategyAction.BUY
    assert "vwap_reclaim" in signal.rationale_codes
    assert signal.invalidation_price == Decimal("200")
    assert signal.strategy_id == "vwap"
    assert signal.version == "1.0.0"


def test_vwap_rejection_emits_reduce_signal() -> None:
    signal = VWAPStrategy().evaluate(
        market_input(current="199", previous="201", vwap="200")
    )

    assert signal.action is StrategyAction.REDUCE
    assert "vwap_rejection" in signal.rationale_codes


def test_put_wall_support_requires_positive_order_flow() -> None:
    strategy = GammaLevelsStrategy(wall_proximity=Decimal("0.01"))

    signal = strategy.evaluate(
        market_input(current="191", put_wall="190", call_wall="220", imbalance="0.30")
    )

    assert signal.action is StrategyAction.BUY
    assert "put_wall_support" in signal.rationale_codes
    assert signal.invalidation_price < Decimal("190")


def test_put_wall_breakdown_with_negative_flow_emits_exit() -> None:
    strategy = GammaLevelsStrategy(
        wall_proximity=Decimal("0.01"),
        breakout_fraction=Decimal("0.01"),
    )

    signal = strategy.evaluate(
        market_input(current="187", put_wall="190", call_wall="220", imbalance="-0.40")
    )

    assert signal.action is StrategyAction.EXIT
    assert "put_wall_breakdown" in signal.rationale_codes


def test_call_wall_rejection_with_negative_flow_emits_reduce() -> None:
    strategy = GammaLevelsStrategy(wall_proximity=Decimal("0.01"))

    signal = strategy.evaluate(
        market_input(current="219", put_wall="190", call_wall="220", imbalance="-0.25")
    )

    assert signal.action is StrategyAction.REDUCE
    assert "call_wall_rejection" in signal.rationale_codes


def test_call_wall_breakout_with_positive_flow_emits_buy() -> None:
    strategy = GammaLevelsStrategy(
        wall_proximity=Decimal("0.01"),
        breakout_fraction=Decimal("0.01"),
    )

    signal = strategy.evaluate(
        market_input(current="223", put_wall="190", call_wall="220", imbalance="0.35")
    )

    assert signal.action is StrategyAction.BUY
    assert "call_wall_breakout" in signal.rationale_codes
    assert signal.invalidation_price == Decimal("220")


def test_missing_structure_returns_hold_not_guess() -> None:
    signal = GammaLevelsStrategy().evaluate(market_input(current="200"))

    assert signal.action is StrategyAction.HOLD
    assert "insufficient_structure" in signal.rationale_codes
