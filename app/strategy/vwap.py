from __future__ import annotations

from decimal import Decimal

from app.strategy.base import StrategyAction, StrategyInput, StrategySignal, hold_signal


class VWAPStrategy:
    strategy_id = "vwap"
    version = "1.0.0"

    def evaluate(self, market: StrategyInput) -> StrategySignal:
        level = market.structure.vwap
        previous = market.previous_price
        if level is None or previous is None:
            return hold_signal(
                strategy_id=self.strategy_id,
                version=self.version,
                market=market,
                rationale_code="insufficient_vwap_context",
            )

        if previous <= level and market.current_price > level:
            return StrategySignal(
                strategy_id=self.strategy_id,
                version=self.version,
                symbol=market.symbol,
                action=StrategyAction.BUY,
                confidence=Decimal("0.65"),
                rationale_codes=["vwap_reclaim"],
                entry_price=market.current_price,
                invalidation_price=level,
            )

        if previous >= level and market.current_price < level:
            return StrategySignal(
                strategy_id=self.strategy_id,
                version=self.version,
                symbol=market.symbol,
                action=StrategyAction.REDUCE,
                confidence=Decimal("0.60"),
                rationale_codes=["vwap_rejection"],
                entry_price=market.current_price,
                invalidation_price=level,
            )

        return hold_signal(
            strategy_id=self.strategy_id,
            version=self.version,
            market=market,
            rationale_code="no_vwap_trigger",
        )
