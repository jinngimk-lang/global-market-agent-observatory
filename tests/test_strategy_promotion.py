from decimal import Decimal

from app.domain.models import TradingMode
from app.innovation.gate import PromotionPolicy, StrategyPromotionGate
from app.innovation.models import (
    PromotionEvidence,
    StrategyHypothesis,
    StrategyStage,
)
from app.strategy.manifests import strategy_hypotheses


def hypothesis(stage: StrategyStage = StrategyStage.RESEARCH) -> StrategyHypothesis:
    return StrategyHypothesis(
        strategy_id="example",
        version="1.0.0",
        problem="Find selective state transitions with asymmetric invalidation.",
        category_default="Every indicator observation should predict direction.",
        deleted_constraint="Every observation requires a directional forecast.",
        new_axis="Abstain unless an observable state transition creates asymmetric risk.",
        expected_mechanism="State transition plus explicit invalidation filters weak observations.",
        observable_inputs=["price", "volume", "vwap"],
        provenance_requirements=["timestamped bars", "documented vwap method"],
        falsification_conditions=["out-of-sample expectancy <= 0 after costs"],
        known_failure_regimes=["illiquid market", "stale data"],
        safety_constraints=["stale data blocks new risk"],
        stage=stage,
    )


def test_research_requires_explicit_reframe_and_falsification() -> None:
    gate = StrategyPromotionGate()
    incomplete = hypothesis().model_copy(
        update={"deleted_constraint": "", "falsification_conditions": []}
    )

    decision = gate.evaluate(
        incomplete,
        PromotionEvidence(),
        target=StrategyStage.RESEARCH,
    )

    assert decision.allowed is False
    assert "missing_deleted_constraint" in decision.blockers
    assert "missing_falsification_conditions" in decision.blockers


def test_replay_promotion_requires_replayable_provenance() -> None:
    gate = StrategyPromotionGate()

    blocked = gate.evaluate(
        hypothesis(),
        PromotionEvidence(
            deterministic_implementation=True,
            data_provenance_complete=False,
            replayable_data=False,
            transaction_cost_model_documented=True,
        ),
        target=StrategyStage.REPLAY,
    )

    assert blocked.allowed is False
    assert "data_provenance_incomplete" in blocked.blockers
    assert "replay_data_unavailable" in blocked.blockers


def test_paper_promotion_requires_out_of_sample_positive_expectancy_and_drawdown_bound() -> None:
    gate = StrategyPromotionGate(
        PromotionPolicy(min_replay_observations=100, max_replay_drawdown=Decimal("0.15"))
    )

    allowed = gate.evaluate(
        hypothesis(stage=StrategyStage.REPLAY),
        PromotionEvidence(
            deterministic_implementation=True,
            data_provenance_complete=True,
            replayable_data=True,
            transaction_cost_model_documented=True,
            out_of_sample_verified=True,
            oos_holdout_observations=40,
            walk_forward_folds=4,
            replay_observations=250,
            expectancy_after_costs=Decimal("0.003"),
            max_drawdown=Decimal("0.08"),
        ),
        target=StrategyStage.PAPER,
    )

    assert allowed.allowed is True
    assert allowed.code == "promotion_allowed"


def test_paper_promotion_rejects_oos_boolean_without_holdout_depth() -> None:
    gate = StrategyPromotionGate(
        PromotionPolicy(min_replay_observations=100, max_replay_drawdown=Decimal("0.15"))
    )

    decision = gate.evaluate(
        hypothesis(stage=StrategyStage.REPLAY),
        PromotionEvidence(
            deterministic_implementation=True,
            data_provenance_complete=True,
            replayable_data=True,
            transaction_cost_model_documented=True,
            out_of_sample_verified=True,
            replay_observations=250,
            expectancy_after_costs=Decimal("0.003"),
            max_drawdown=Decimal("0.08"),
        ),
        target=StrategyStage.PAPER,
    )

    assert decision.allowed is False
    assert "insufficient_oos_holdout_observations" in decision.blockers
    assert "insufficient_walk_forward_folds" in decision.blockers


def test_live_promotion_requires_broker_paper_and_execution_safety_evidence() -> None:
    gate = StrategyPromotionGate(
        PromotionPolicy(min_broker_paper_observations=30, max_live_drawdown=Decimal("0.12"))
    )
    base = PromotionEvidence(
        deterministic_implementation=True,
        data_provenance_complete=True,
        replayable_data=True,
        transaction_cost_model_documented=True,
        out_of_sample_verified=True,
        oos_holdout_observations=60,
        walk_forward_folds=6,
        replay_observations=500,
        paper_observations=100,
        broker_paper_observations=50,
        verified_broker_paper_fill_observations=50,
        expectancy_after_costs=Decimal("0.002"),
        max_drawdown=Decimal("0.09"),
        idempotency_verified=True,
        failure_injection_verified=True,
        reconciliation_verified=False,
        degradation_rule_defined=True,
    )

    blocked = gate.evaluate(
        hypothesis(stage=StrategyStage.BROKER_PAPER),
        base,
        target=StrategyStage.LIVE,
    )
    allowed = gate.evaluate(
        hypothesis(stage=StrategyStage.BROKER_PAPER),
        base.model_copy(update={"reconciliation_verified": True}),
        target=StrategyStage.LIVE,
    )

    assert blocked.allowed is False
    assert "reconciliation_unverified" in blocked.blockers
    assert allowed.allowed is True


def test_live_promotion_rejects_broker_paper_counts_without_verified_fills() -> None:
    gate = StrategyPromotionGate(PromotionPolicy(min_broker_paper_observations=30))
    evidence = PromotionEvidence(
        deterministic_implementation=True,
        data_provenance_complete=True,
        replayable_data=True,
        transaction_cost_model_documented=True,
        out_of_sample_verified=True,
        oos_holdout_observations=60,
        walk_forward_folds=6,
        replay_observations=500,
        paper_observations=100,
        broker_paper_observations=50,
        expectancy_after_costs=Decimal("0.002"),
        max_drawdown=Decimal("0.09"),
        idempotency_verified=True,
        failure_injection_verified=True,
        reconciliation_verified=True,
        degradation_rule_defined=True,
    )

    decision = gate.evaluate(
        hypothesis(stage=StrategyStage.BROKER_PAPER),
        evidence,
        target=StrategyStage.LIVE,
    )

    assert decision.allowed is False
    assert "insufficient_verified_broker_paper_fills" in decision.blockers


def test_strategy_version_cannot_skip_promotion_stages() -> None:
    gate = StrategyPromotionGate()

    decision = gate.evaluate(
        hypothesis(stage=StrategyStage.RESEARCH),
        PromotionEvidence(),
        target=StrategyStage.LIVE,
    )

    assert decision.allowed is False
    assert decision.code == "stage_skip_forbidden"


def test_runtime_mode_maps_to_minimum_strategy_stage() -> None:
    gate = StrategyPromotionGate()

    assert gate.required_stage_for_mode(TradingMode.REPLAY) is StrategyStage.REPLAY
    assert gate.required_stage_for_mode(TradingMode.PAPER) is StrategyStage.PAPER
    assert gate.required_stage_for_mode(TradingMode.BROKER_PAPER) is StrategyStage.BROKER_PAPER
    assert gate.required_stage_for_mode(TradingMode.LIVE) is StrategyStage.LIVE


def test_current_vwap_and_gamma_hypotheses_encode_constraint_deletion() -> None:
    manifests = strategy_hypotheses()

    assert set(manifests) == {"vwap", "gamma-levels"}
    assert "direction" in manifests["vwap"].deleted_constraint.lower()
    assert "wall" in manifests["gamma-levels"].category_default.lower()
    assert manifests["vwap"].stage is StrategyStage.REPLAY
    assert manifests["gamma-levels"].stage is StrategyStage.REPLAY
