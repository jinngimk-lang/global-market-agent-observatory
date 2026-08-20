from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class TradingMode(StrEnum):
    REPLAY = "replay"
    PAPER = "paper"
    BROKER_PAPER = "broker-paper"
    LIVE = "live"


class TradingState(StrEnum):
    ACTIVE = "active"
    REDUCING = "reducing"
    HALTED = "halted"


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(StrEnum):
    ACCEPTED = "accepted"
    FILLED = "filled"
    REJECTED = "rejected"


class EvidenceGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class Candle(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    interval: str = "1m"
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str
    closed: bool = True

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class OrderIntent(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_order_id: str
    symbol: str
    side: Side
    quantity: Decimal
    reference_price: Decimal | None = None
    order_type: OrderType = OrderType.MARKET
    limit_price: Decimal | None = None
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class Position(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    quantity: Decimal
    average_price: Decimal
    market_price: Decimal

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @property
    def gross_value(self) -> Decimal:
        return abs(self.quantity * self.market_price)

    @property
    def unrealized_pnl(self) -> Decimal:
        return self.quantity * (self.market_price - self.average_price)


class PortfolioSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    cash: Decimal
    positions: list[Position] = Field(default_factory=list)
    realized_pnl_today: Decimal = Decimal("0")
    mode: str = "paper"
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @computed_field
    @property
    def gross_exposure(self) -> Decimal:
        return sum((position.gross_value for position in self.positions), Decimal("0"))

    @computed_field
    @property
    def equity(self) -> Decimal:
        market_value = sum(
            (position.quantity * position.market_price for position in self.positions),
            Decimal("0"),
        )
        return self.cash + market_value


class RiskLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed_symbols: set[str] = Field(default_factory=lambda: {"BTCUSDT", "ETHUSDT"})
    max_order_notional: Decimal = Decimal("10000")
    max_gross_exposure: Decimal = Decimal("50000")
    daily_loss_limit: Decimal = Decimal("2000")

    @field_validator("allowed_symbols")
    @classmethod
    def normalize_symbols(cls, values: set[str]) -> set[str]:
        return {value.strip().upper() for value in values}


class RiskDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    code: str
    message: str
    order_notional: Decimal = Decimal("0")
    projected_gross_exposure: Decimal = Decimal("0")


class OrderRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: str
    intent: OrderIntent
    status: OrderStatus
    message: str = ""
    filled_price: Decimal | None = None
    filled_at: datetime | None = None


class EvidenceItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    title: str
    source_type: str
    source_url: str
    grade: EvidenceGrade
    observed_at: datetime
    event_date: datetime | None = None
    entity: str | None = None
    summary: str
    content_hash: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ObservedBalance(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: str
    total: Decimal
    available: Decimal | None = None


class ObservedPosition(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    quantity: Decimal
    average_price: Decimal | None = None
    market_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None


class ObservedOrder(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: str
    symbol: str
    side: str
    quantity: Decimal
    filled_quantity: Decimal = Decimal("0")
    status: str
    submitted_at: datetime | None = None
    filled_price: Decimal | None = None


class ExternalAccountSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    account_id: str
    mode: str
    status: str = "connected"
    base_currency: str | None = None
    equity: Decimal | None = None
    cash: Decimal | None = None
    buying_power: Decimal | None = None
    balances: list[ObservedBalance] = Field(default_factory=list)
    positions: list[ObservedPosition] = Field(default_factory=list)
    orders: list[ObservedOrder] = Field(default_factory=list)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
