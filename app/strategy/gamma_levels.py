from __future__ import annotations

from decimal import Decimal

from app.strategy.base import StrategyAction, StrategyInput, StrategySignal, hold_signal


class GammaLevelsStrategy:
    strategy_id = "gamma-levels"
    version = "1.0.0"

    def __init__(
        self,
        *,
        wall_proximity: Decimal = Decimal("0.01"),
        breakout_fraction: Decimal = Decimal("0.01"),
        flow_threshold: Decimal = Decimal("0.15"),
    ) -> None:
        if wall_proximity < 0 or breakout_fraction < 0 or flow_threshold < 0:
            raise ValueError("strategy thresholds must be non-negative")
        self._wall_proximity = wall_proximity
        self._breakout_fraction = breakout_fraction
        self._flow_threshold = flow_threshold

    def evaluate(self, market: StrategyInput) -> StrategySignal:
        put_wall = market.structure.put_wall
        call_wall = market.structure.call_wall
        flow = market.structure.order_flow_imbalance

        if put_wall is None and call_wall is None:
            return hold_signal(
                strategy_id=self.strategy_id,
                version=self.version,
                market=market,
                rationale_code="insufficient_structure",
            )
        if flow is None:
            return hold_signal(
                strategy_id=self.strategy_id,
                version=self.version,
                market=market,
                rationale_code="missing_order_flow",
            )

        positive_flow = flow >= self._flow_threshold
        negative_flow = flow <= -self._flow_threshold

        if (
            call_wall is not None
            and market.current_price > call_wall * (Decimal("1") + self._breakout_fraction)
            and positive_flow
        ):
            return StrategySignal(
                strategy_id=self.strategy_id,
                version=self.version,
                symbol=market.symbol,
                action=StrategyAction.BUY,
                confidence=Decimal("0.72"),
                rationale_codes=["call_wall_breakout", "positive_order_flow"],
                entry_price=market.current_price,
                invalidation_price=call_wall,
                generated_at=market.observed_at,
            )

        if (
            put_wall is not None
            and market.current_price < put_wall * (Decimal("1") - self._breakout_fraction)
            and negative_flow
        ):
            return StrategySignal(
                strategy_id=self.strategy_id,
                version=self.version,
                symbol=market.symbol,
                action=StrategyAction.EXIT,
                confidence=Decimal("0.78"),
                rationale_codes=["put_wall_breakdown", "negative_order_flow"],
                entry_price=market.current_price,
                invalidation_price=put_wall,
                generated_at=market.observed_at,
            )

        if (
            put_wall is not None
            and self._near(market.current_price, put_wall)
            and market.current_price >= put_wall
            and positive_flow
        ):
            return StrategySignal(
                strategy_id=self.strategy_id,
                version=self.version,
                symbol=market.symbol,
                action=StrategyAction.BUY,
                confidence=Decimal("0.68"),
                rationale_codes=["put_wall_support", "positive_order_flow"],
                entry_price=market.current_price,
                invalidation_price=put_wall * (Decimal("1") - self._breakout_fraction),
                generated_at=market.observed_at,
            )

        if (
            call_wall is not None
            and self._near(market.current_price, call_wall)
            and market.current_price <= call_wall
            and negative_flow
        ):
            return StrategySignal(
                strategy_id=self.strategy_id,
                version=self.version,
                symbol=market.symbol,
                action=StrategyAction.REDUCE,
                confidence=Decimal("0.66"),
                rationale_codes=["call_wall_rejection", "negative_order_flow"],
                entry_price=market.current_price,
                invalidation_price=call_wall,
                generated_at=market.observed_at,
            )

        return hold_signal(
            strategy_id=self.strategy_id,
            version=self.version,
            market=market,
            rationale_code="no_gamma_level_trigger",
        )

    def _near(self, price: Decimal, level: Decimal) -> bool:
        if level <= 0:
            return False
        return abs(price - level) / level <= self._wall_proximity
