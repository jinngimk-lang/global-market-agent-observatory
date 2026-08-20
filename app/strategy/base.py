from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.research.market_intelligence import MarketStructureSnapshot


class StrategyAction(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    REDUCE = "reduce"
    EXIT = "exit"


class StrategyInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    current_price: Decimal
    previous_price: Decimal | None = None
    structure: MarketStructureSnapshot
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StrategySignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_id: str
    version: str
    symbol: str
    action: StrategyAction
    confidence: Decimal
    rationale_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    entry_price: Decimal | None = None
    invalidation_price: Decimal | None = None
    target_price: Decimal | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: Decimal) -> Decimal:
        if value < 0 or value > 1:
            raise ValueError("confidence must be between 0 and 1")
        return value


class Strategy(Protocol):
    strategy_id: str
    version: str

    def evaluate(self, market: StrategyInput) -> StrategySignal: ...


def hold_signal(
    *,
    strategy_id: str,
    version: str,
    market: StrategyInput,
    rationale_code: str,
) -> StrategySignal:
    return StrategySignal(
        strategy_id=strategy_id,
        version=version,
        symbol=market.symbol,
        action=StrategyAction.HOLD,
        confidence=Decimal("0"),
        rationale_codes=[rationale_code],
        entry_price=market.current_price,
    )
