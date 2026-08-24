from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.models import TradingMode
from app.strategy.base import StrategyAction


class StrategyObservationStatus(StrEnum):
    PENDING = "pending"
    CLOSED = "closed"


class StrategyEvaluationPartition(StrEnum):
    UNASSIGNED = "unassigned"
    CALIBRATION = "calibration"
    HOLDOUT = "holdout"


class StrategyHealthPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    min_observations: int = 30
    window_observations: int = 50
    min_expectancy_after_costs: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0.10")

    @field_validator("min_observations", "window_observations")
    @classmethod
    def positive_counts(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("strategy health observation counts must be positive")
        return value

    @field_validator("max_drawdown")
    @classmethod
    def valid_drawdown(cls, value: Decimal) -> Decimal:
        if value <= 0 or value > 1:
            raise ValueError("max_drawdown must be in (0, 1]")
        return value


class StrategyObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    observation_id: str
    strategy_id: str
    version: str
    symbol: str
    mode: TradingMode
    action: StrategyAction
    entry_price: Decimal
    observed_at: datetime
    due_at: datetime
    transaction_cost_bps: Decimal
    evaluation_partition: StrategyEvaluationPartition = StrategyEvaluationPartition.UNASSIGNED
    walk_forward_fold: int | None = None
    status: StrategyObservationStatus = StrategyObservationStatus.PENDING
    exit_price: Decimal | None = None
    net_return: Decimal | None = None
    closed_at: datetime | None = None


class StrategyHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_id: str
    version: str
    closed_observations: int = 0
    expectancy_after_costs: Decimal | None = None
    max_drawdown: Decimal | None = None
    win_rate: Decimal | None = None
    degraded: bool = False
    degradation_reasons: list[str] = Field(default_factory=list)
    updated_at: datetime
