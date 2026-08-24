from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import TradingMode
from app.innovation.gate import PromotionPolicy, StrategyPromotionGate
from app.innovation.models import PromotionEvidence, StrategyHypothesis, StrategyStage
from app.innovation.store import SQLiteStrategyEvidenceStore


class RuntimeStrategyPromotion(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_id: str
    version: str
    current_stage: StrategyStage
    required_stage: StrategyStage
    allowed: bool
    code: str
    blockers: list[str] = Field(default_factory=list)


class StrategyPromotionRegistry:
    def __init__(
        self,
        *,
        manifests: dict[str, StrategyHypothesis],
        evidence_store: SQLiteStrategyEvidenceStore,
        gate: StrategyPromotionGate | None = None,
        promotion_policy: PromotionPolicy | None = None,
    ) -> None:
        if gate is not None and promotion_policy is not None:
            raise ValueError("provide gate or promotion_policy, not both")
        self._manifests = dict(manifests)
        self._evidence_store = evidence_store
        self._gate = gate or StrategyPromotionGate(promotion_policy)

    @property
    def manifests(self) -> dict[str, StrategyHypothesis]:
        return dict(self._manifests)

    @property
    def promotion_policy(self) -> PromotionPolicy:
        return self._gate.policy

    def evidence_for(self, strategy_id: str, version: str) -> PromotionEvidence:
        return self._evidence_store.get(strategy_id, version) or PromotionEvidence()

    def decision_for(self, strategy_id: str, mode: TradingMode) -> RuntimeStrategyPromotion:
        normalized = strategy_id.strip().lower()
        manifest = self._manifests.get(normalized)
        if manifest is None:
            required = self._gate.required_stage_for_mode(mode)
            return RuntimeStrategyPromotion(
                strategy_id=normalized,
                version="unknown",
                current_stage=StrategyStage.IDEA,
                required_stage=required,
                allowed=False,
                code="strategy_manifest_missing",
                blockers=["strategy_manifest_missing"],
            )

        evidence = self.evidence_for(manifest.strategy_id, manifest.version)
        decision = self._gate.eligible_for_mode(manifest, evidence, mode)
        return RuntimeStrategyPromotion(
            strategy_id=manifest.strategy_id,
            version=manifest.version,
            current_stage=manifest.stage,
            required_stage=decision.target,
            allowed=decision.allowed,
            code=decision.code,
            blockers=decision.blockers,
        )

    def evaluate_runtime(
        self,
        strategies: list[object],
        mode: TradingMode,
    ) -> list[RuntimeStrategyPromotion]:
        reports: list[RuntimeStrategyPromotion] = []
        for strategy in strategies:
            strategy_id = str(getattr(strategy, "strategy_id", "")).strip().lower()
            version = str(getattr(strategy, "version", "")).strip()
            report = self.decision_for(strategy_id, mode)
            manifest = self._manifests.get(strategy_id)
            if manifest is not None and manifest.version != version:
                report = report.model_copy(
                    update={
                        "allowed": False,
                        "code": "strategy_version_manifest_mismatch",
                        "blockers": [
                            f"runtime_version:{version or 'missing'}",
                            f"manifest_version:{manifest.version}",
                        ],
                    }
                )
            reports.append(report)
        return reports

    def runtime_allowed(self, strategies: list[object], mode: TradingMode) -> bool:
        reports = self.evaluate_runtime(strategies, mode)
        return bool(reports) and all(report.allowed for report in reports)
