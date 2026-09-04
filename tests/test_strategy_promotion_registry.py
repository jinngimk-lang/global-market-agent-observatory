from decimal import Decimal

from app.domain.models import TradingMode
from app.innovation.models import PromotionEvidence, StrategyStage
from app.innovation.registry import StrategyPromotionRegistry
from app.innovation.store import SQLiteStrategyEvidenceStore
from app.strategy.manifests import strategy_hypotheses
from app.strategy.vwap import VWAPStrategy


def paper_evidence() -> PromotionEvidence:
    return PromotionEvidence(
        deterministic_implementation=True,
        data_provenance_complete=True,
        replayable_data=True,
        transaction_cost_model_documented=True,
        out_of_sample_verified=True,
        replay_observations=250,
        expectancy_after_costs=Decimal("0.002"),
        max_drawdown=Decimal("0.08"),
    )


def test_promotion_evidence_persists_by_exact_strategy_version(tmp_path) -> None:
    store = SQLiteStrategyEvidenceStore(tmp_path / "runtime.db")
    evidence = paper_evidence()

    store.upsert("vwap", "1.0.0", evidence)

    assert store.get("VWAP", "1.0.0") == evidence
    assert store.get("vwap", "2.0.0") is None
    assert list(store.list_all()) == [("vwap", "1.0.0")]


def test_registry_fails_closed_when_current_manifest_stage_is_below_runtime_mode(tmp_path) -> None:
    store = SQLiteStrategyEvidenceStore(tmp_path / "runtime.db")
    store.upsert("vwap", "1.0.0", paper_evidence())
    registry = StrategyPromotionRegistry(
        manifests=strategy_hypotheses(),
        evidence_store=store,
    )

    report = registry.decision_for("vwap", TradingMode.PAPER)

    assert report.allowed is False
    assert report.current_stage is StrategyStage.REPLAY
    assert report.required_stage is StrategyStage.PAPER
    assert report.code == "strategy_not_promoted_for_mode"


def test_registry_rejects_runtime_strategy_version_not_matching_manifest(tmp_path) -> None:
    class NewVWAP:
        strategy_id = "vwap"
        version = "2.0.0"

    registry = StrategyPromotionRegistry(
        manifests=strategy_hypotheses(),
        evidence_store=SQLiteStrategyEvidenceStore(tmp_path / "runtime.db"),
    )

    report = registry.evaluate_runtime([NewVWAP()], TradingMode.REPLAY)[0]

    assert report.allowed is False
    assert report.code == "strategy_version_manifest_mismatch"


def test_unregistered_strategy_is_never_runtime_eligible(tmp_path) -> None:
    class Mystery:
        strategy_id = "mystery"
        version = "1.0.0"

    registry = StrategyPromotionRegistry(
        manifests=strategy_hypotheses(),
        evidence_store=SQLiteStrategyEvidenceStore(tmp_path / "runtime.db"),
    )

    report = registry.evaluate_runtime([Mystery()], TradingMode.REPLAY)[0]

    assert report.allowed is False
    assert report.code == "strategy_manifest_missing"


def test_current_vwap_is_not_eligible_for_paper_just_because_code_exists(tmp_path) -> None:
    registry = StrategyPromotionRegistry(
        manifests=strategy_hypotheses(),
        evidence_store=SQLiteStrategyEvidenceStore(tmp_path / "runtime.db"),
    )

    assert registry.runtime_allowed([VWAPStrategy()], TradingMode.PAPER) is False
