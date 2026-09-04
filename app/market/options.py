from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator


class OptionRight(StrEnum):
    CALL = "call"
    PUT = "put"


class GEXAssumptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    call_sign: int
    put_sign: int

    @field_validator("call_sign", "put_sign")
    @classmethod
    def validate_sign(cls, value: int) -> int:
        if value not in {-1, 1}:
            raise ValueError("GEX sign must be -1 or 1")
        return value


class OptionOpenInterestPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    strike: Decimal
    right: OptionRight
    open_interest: Decimal
    gamma: Decimal
    contract_multiplier: Decimal = Decimal("100")


class GammaStrikeExposure(BaseModel):
    model_config = ConfigDict(frozen=True)

    strike: Decimal
    right: OptionRight
    gex_1pct: Decimal


class GammaStructureEstimate(BaseModel):
    model_config = ConfigDict(frozen=True)

    spot: Decimal
    net_gex_1pct: Decimal
    call_wall: Decimal | None = None
    put_wall: Decimal | None = None
    gamma_flip: Decimal | None = None
    exposures: list[GammaStrikeExposure]
    methodology: str
    caveat: str


def estimate_gamma_structure(
    *,
    spot: Decimal,
    options: list[OptionOpenInterestPoint],
    assumptions: GEXAssumptions,
) -> GammaStructureEstimate:
    """Estimate OI-based gamma exposure under explicit inventory assumptions.

    gex_1pct = gamma * open_interest * multiplier * spot^2 * 1% * sign

    This intentionally does not infer true dealer inventory. The signs are an
    input that must be named by the caller. Gamma flip is left unset because a
    current-point gamma snapshot cannot establish the zero-gamma spot without
    repricing the option set across spot scenarios.
    """

    if spot <= 0:
        raise ValueError("spot must be positive")

    exposures: list[GammaStrikeExposure] = []
    for item in options:
        sign = assumptions.call_sign if item.right is OptionRight.CALL else assumptions.put_sign
        raw = (
            item.gamma
            * item.open_interest
            * item.contract_multiplier
            * spot
            * spot
            * Decimal("0.01")
        )
        exposures.append(
            GammaStrikeExposure(
                strike=item.strike,
                right=item.right,
                gex_1pct=raw * sign,
            )
        )

    net = sum((item.gex_1pct for item in exposures), Decimal("0"))
    calls = [item for item in exposures if item.right is OptionRight.CALL]
    puts = [item for item in exposures if item.right is OptionRight.PUT]
    call_wall = (
        max(calls, key=lambda item: (abs(item.gex_1pct), item.strike)).strike
        if calls
        else None
    )
    put_wall = (
        max(puts, key=lambda item: (abs(item.gex_1pct), -item.strike)).strike
        if puts
        else None
    )

    return GammaStructureEstimate(
        spot=spot,
        net_gex_1pct=net,
        call_wall=call_wall,
        put_wall=put_wall,
        gamma_flip=None,
        exposures=exposures,
        methodology=assumptions.label,
        caveat=(
            "Open-interest gamma exposure proxy under explicit sign assumptions; "
            "this is not observed dealer inventory. Gamma flip requires repricing "
            "the option set across spot scenarios."
        ),
    )
