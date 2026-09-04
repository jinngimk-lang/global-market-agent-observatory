from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PriceZone(BaseModel):
    model_config = ConfigDict(frozen=True)

    lower: Decimal
    upper: Decimal
    label: str
    source: str


class MarketStructureSnapshot(BaseModel):
    """Derived market structure state; never an executable order by itself."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    supports: list[PriceZone] = Field(default_factory=list)
    resistances: list[PriceZone] = Field(default_factory=list)
    vwap: Decimal | None = None
    anchored_vwap: Decimal | None = None
    volume_profile_poc: Decimal | None = None
    volume_profile_hvn: list[Decimal] = Field(default_factory=list)
    volume_profile_lvn: list[Decimal] = Field(default_factory=list)
    order_flow_imbalance: Decimal | None = None
    net_gex_1pct: Decimal | None = None
    gamma_flip: Decimal | None = None
    call_wall: Decimal | None = None
    put_wall: Decimal | None = None
    confidence: Decimal = Decimal("0")
    methodology: dict[str, str] = Field(default_factory=dict)

    @property
    def execution_allowed(self) -> bool:
        return False
