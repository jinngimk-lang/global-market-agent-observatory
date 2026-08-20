from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import OrderStatus, RiskDecision


class ExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_order_id: str | None = None
    broker_order_id: str | None = None
    status: OrderStatus
    code: str = "broker_result"
    message: str = ""
    filled_quantity: Decimal = Decimal("0")
    filled_price: Decimal | None = None
    raw_status: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExecutionAttempt(BaseModel):
    model_config = ConfigDict(frozen=True)

    result: ExecutionResult
    risk_decision: RiskDecision | None = None
    reused_existing: bool = False
