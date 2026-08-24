from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrategyStage(StrEnum):
    IDEA = "idea"
    RESEARCH = "research"
    REPLAY = "replay"
    PAPER = "paper"
    BROKER_PAPER = "broker-paper"
    LIVE = "live"


class StrategyHypothesis(BaseModel):
    """Version-specific strategy thesis and its current evidence stage."""

    model_config = ConfigDict(frozen=True)

    strategy_id: str
    version: str
    problem: str
    category_default: str
    deleted_constraint: str
    new_axis: str
    expected_mechanism: str
    observable_inputs: list[str] = Field(default_factory=list)
    provenance_requirements: list[str] = Field(default_factory=list)
    falsification_conditions: list[str] = Field(default_factory=list)
    known_failure_regimes: list[str] = Field(default_factory=list)
    safety_constraints: list[str] = Field(default_factory=list)
    stage: StrategyStage = StrategyStage.IDEA

    @field_validator("strategy_id")
    @classmethod
    def normalize_strategy_id(cls, value: str) -> str:
        return value.strip().lower()


class PromotionEvidence(BaseModel):
    """Evidence accumulated by one exact strategy version."""

    model_config = ConfigDict(frozen=True)

    deterministic_implementation: bool = False
    data_provenance_complete: bool = False
    replayable_data: bool = False
    transaction_cost_model_documented: bool = False
    out_of_sample_verified: bool = False
    oos_holdout_observations: int = 0
    walk_forward_folds: int = 0
    replay_observations: int = 0
    paper_observations: int = 0
    broker_paper_observations: int = 0
    expectancy_after_costs: Decimal | None = None
    max_drawdown: Decimal | None = None
    idempotency_verified: bool = False
    failure_injection_verified: bool = False
    reconciliation_verified: bool = False
    degradation_rule_defined: bool = False
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator(
        "oos_holdout_observations",
        "walk_forward_folds",
        "replay_observations",
        "paper_observations",
        "broker_paper_observations",
    )
    @classmethod
    def non_negative_counts(cls, value: int) -> int:
        if value < 0:
            raise ValueError("observation counts must be non-negative")
        return value

    @field_validator("max_drawdown")
    @classmethod
    def normalize_drawdown(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if value < 0:
            value = -value
        return value


class PromotionDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    code: str
    target: StrategyStage
    blockers: list[str] = Field(default_factory=list)
    message: str = ""
