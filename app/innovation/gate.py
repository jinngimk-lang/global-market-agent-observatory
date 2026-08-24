from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.models import TradingMode
from app.innovation.models import (
    PromotionDecision,
    PromotionEvidence,
    StrategyHypothesis,
    StrategyStage,
)


class PromotionPolicy(BaseModel):
    """Configurable evidence thresholds; these are policy, not universal truths."""

    model_config = ConfigDict(frozen=True)

    min_replay_observations: int = 100
    min_oos_holdout_observations: int = 20
    min_walk_forward_folds: int = 2
    min_paper_observations: int = 50
    min_broker_paper_observations: int = 30
    min_expectancy_after_costs: Decimal = Decimal("0")
    max_replay_drawdown: Decimal = Decimal("0.20")
    max_live_drawdown: Decimal = Decimal("0.15")


class StrategyPromotionGate:
    _STAGES = (
        StrategyStage.IDEA,
        StrategyStage.RESEARCH,
        StrategyStage.REPLAY,
        StrategyStage.PAPER,
        StrategyStage.BROKER_PAPER,
        StrategyStage.LIVE,
    )

    def __init__(self, policy: PromotionPolicy | None = None) -> None:
        self.policy = policy or PromotionPolicy()

    def required_stage_for_mode(self, mode: TradingMode) -> StrategyStage:
        return {
            TradingMode.REPLAY: StrategyStage.REPLAY,
            TradingMode.PAPER: StrategyStage.PAPER,
            TradingMode.BROKER_PAPER: StrategyStage.BROKER_PAPER,
            TradingMode.LIVE: StrategyStage.LIVE,
        }[mode]

    def evaluate(
        self,
        hypothesis: StrategyHypothesis,
        evidence: PromotionEvidence,
        *,
        target: StrategyStage,
    ) -> PromotionDecision:
        current_index = self._STAGES.index(hypothesis.stage)
        target_index = self._STAGES.index(target)

        if target_index > current_index + 1:
            return PromotionDecision(
                allowed=False,
                code="stage_skip_forbidden",
                target=target,
                blockers=["promotion_must_be_sequential"],
                message=(
                    f"Strategy {hypothesis.strategy_id}@{hypothesis.version} cannot skip "
                    f"from {hypothesis.stage.value} to {target.value}."
                ),
            )

        blockers: list[str] = []
        if target_index >= self._STAGES.index(StrategyStage.RESEARCH):
            blockers.extend(self._research_blockers(hypothesis))
        if target_index >= self._STAGES.index(StrategyStage.REPLAY):
            blockers.extend(self._replay_blockers(evidence))
        if target_index >= self._STAGES.index(StrategyStage.PAPER):
            blockers.extend(self._paper_blockers(evidence))
        if target_index >= self._STAGES.index(StrategyStage.BROKER_PAPER):
            blockers.extend(self._broker_paper_blockers(evidence))
        if target_index >= self._STAGES.index(StrategyStage.LIVE):
            blockers.extend(self._live_blockers(evidence))

        blockers = list(dict.fromkeys(blockers))
        if blockers:
            return PromotionDecision(
                allowed=False,
                code="promotion_blocked",
                target=target,
                blockers=blockers,
                message=(
                    f"Strategy {hypothesis.strategy_id}@{hypothesis.version} lacks evidence "
                    f"for {target.value}."
                ),
            )

        return PromotionDecision(
            allowed=True,
            code="promotion_allowed",
            target=target,
            message=(
                f"Strategy {hypothesis.strategy_id}@{hypothesis.version} satisfies the "
                f"configured evidence gate for {target.value}."
            ),
        )

    def eligible_for_mode(
        self,
        hypothesis: StrategyHypothesis,
        evidence: PromotionEvidence,
        mode: TradingMode,
    ) -> PromotionDecision:
        required = self.required_stage_for_mode(mode)
        stage_index = self._STAGES.index(hypothesis.stage)
        required_index = self._STAGES.index(required)
        if stage_index < required_index:
            return PromotionDecision(
                allowed=False,
                code="strategy_not_promoted_for_mode",
                target=required,
                blockers=[f"current_stage:{hypothesis.stage.value}"],
                message=(
                    f"Strategy {hypothesis.strategy_id}@{hypothesis.version} is at "
                    f"{hypothesis.stage.value}, below required {required.value}."
                ),
            )
        # A manifest that already records the required/higher stage is still checked
        # against the evidence contract so stage metadata cannot become a bypass.
        return self._evaluate_existing_stage(hypothesis, evidence, required)

    def _evaluate_existing_stage(
        self,
        hypothesis: StrategyHypothesis,
        evidence: PromotionEvidence,
        target: StrategyStage,
    ) -> PromotionDecision:
        blockers: list[str] = []
        target_index = self._STAGES.index(target)
        if target_index >= self._STAGES.index(StrategyStage.RESEARCH):
            blockers.extend(self._research_blockers(hypothesis))
        if target_index >= self._STAGES.index(StrategyStage.REPLAY):
            blockers.extend(self._replay_blockers(evidence))
        if target_index >= self._STAGES.index(StrategyStage.PAPER):
            blockers.extend(self._paper_blockers(evidence))
        if target_index >= self._STAGES.index(StrategyStage.BROKER_PAPER):
            blockers.extend(self._broker_paper_blockers(evidence))
        if target_index >= self._STAGES.index(StrategyStage.LIVE):
            blockers.extend(self._live_blockers(evidence))
        blockers = list(dict.fromkeys(blockers))
        return PromotionDecision(
            allowed=not blockers,
            code="promotion_allowed" if not blockers else "promotion_blocked",
            target=target,
            blockers=blockers,
            message=(
                "Strategy evidence satisfies runtime promotion gate."
                if not blockers
                else "Strategy evidence does not satisfy runtime promotion gate."
            ),
        )

    @staticmethod
    def _research_blockers(hypothesis: StrategyHypothesis) -> list[str]:
        blockers: list[str] = []
        required_text = {
            "problem": hypothesis.problem,
            "category_default": hypothesis.category_default,
            "deleted_constraint": hypothesis.deleted_constraint,
            "new_axis": hypothesis.new_axis,
            "expected_mechanism": hypothesis.expected_mechanism,
        }
        for name, value in required_text.items():
            if not value.strip():
                blockers.append(f"missing_{name}")
        if not hypothesis.observable_inputs:
            blockers.append("missing_observable_inputs")
        if not hypothesis.falsification_conditions:
            blockers.append("missing_falsification_conditions")
        return blockers

    @staticmethod
    def _replay_blockers(evidence: PromotionEvidence) -> list[str]:
        blockers: list[str] = []
        if not evidence.deterministic_implementation:
            blockers.append("deterministic_implementation_unverified")
        if not evidence.data_provenance_complete:
            blockers.append("data_provenance_incomplete")
        if not evidence.replayable_data:
            blockers.append("replay_data_unavailable")
        if not evidence.transaction_cost_model_documented:
            blockers.append("transaction_cost_model_missing")
        return blockers

    def _paper_blockers(self, evidence: PromotionEvidence) -> list[str]:
        blockers: list[str] = []
        if not evidence.out_of_sample_verified:
            blockers.append("out_of_sample_unverified")
        if evidence.oos_holdout_observations < self.policy.min_oos_holdout_observations:
            blockers.append("insufficient_oos_holdout_observations")
        if evidence.walk_forward_folds < self.policy.min_walk_forward_folds:
            blockers.append("insufficient_walk_forward_folds")
        if evidence.replay_observations < self.policy.min_replay_observations:
            blockers.append("insufficient_replay_observations")
        if evidence.expectancy_after_costs is None:
            blockers.append("expectancy_after_costs_missing")
        elif evidence.expectancy_after_costs <= self.policy.min_expectancy_after_costs:
            blockers.append("expectancy_after_costs_not_positive")
        if evidence.max_drawdown is None:
            blockers.append("max_drawdown_missing")
        elif evidence.max_drawdown > self.policy.max_replay_drawdown:
            blockers.append("replay_drawdown_exceeds_policy")
        return blockers

    def _broker_paper_blockers(self, evidence: PromotionEvidence) -> list[str]:
        blockers: list[str] = []
        if evidence.paper_observations < self.policy.min_paper_observations:
            blockers.append("insufficient_paper_observations")
        if not evidence.idempotency_verified:
            blockers.append("idempotency_unverified")
        if not evidence.failure_injection_verified:
            blockers.append("failure_injection_unverified")
        return blockers

    def _live_blockers(self, evidence: PromotionEvidence) -> list[str]:
        blockers: list[str] = []
        if evidence.broker_paper_observations < self.policy.min_broker_paper_observations:
            blockers.append("insufficient_broker_paper_observations")
        if not evidence.reconciliation_verified:
            blockers.append("reconciliation_unverified")
        if not evidence.degradation_rule_defined:
            blockers.append("degradation_rule_missing")
        if evidence.max_drawdown is None:
            blockers.append("max_drawdown_missing")
        elif evidence.max_drawdown > self.policy.max_live_drawdown:
            blockers.append("live_drawdown_exceeds_policy")
        if not evidence.idempotency_verified:
            blockers.append("idempotency_unverified")
        if not evidence.failure_injection_verified:
            blockers.append("failure_injection_unverified")
        return blockers
