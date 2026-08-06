from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import EvidenceGrade, EvidenceItem


class PartnershipAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    entity: str | None
    maturity: str
    confidence: str
    validation_metrics: list[str] = Field(default_factory=list)
    upside_conditions: list[str] = Field(default_factory=list)
    downside_conditions: list[str] = Field(default_factory=list)
    price_target: Decimal | None = None


def assess_partnership(item: EvidenceItem) -> PartnershipAssessment:
    form = str(item.metadata.get("form") or "").upper()
    filing_items = str(item.metadata.get("items") or "")
    is_binding_filing = (
        item.grade in {EvidenceGrade.A, EvidenceGrade.B}
        and form in {"8-K", "8-K/A", "6-K", "6-K/A"}
        and ("1.01" in filing_items or "material-agreement" in item.tags)
    )

    if is_binding_filing:
        maturity = "binding-regulatory-filed"
        confidence = "high"
    elif item.grade in {EvidenceGrade.B, EvidenceGrade.C}:
        maturity = "announced-awaiting-execution"
        confidence = "medium"
    else:
        maturity = "unverified-lead"
        confidence = "low"

    return PartnershipAssessment(
        evidence_id=item.evidence_id,
        entity=item.entity,
        maturity=maturity,
        confidence=confidence,
        validation_metrics=[
            "revenue contribution",
            "contract backlog or committed volume",
            "cash conversion",
            "delivery and regulatory milestones",
        ],
        upside_conditions=[
            "counterparties meet delivery milestones",
            "commercial terms convert into recurring revenue",
            "follow-on disclosures confirm scaling",
        ],
        downside_conditions=[
            "agreement is terminated or materially amended",
            "minimum purchase or delivery commitments are missed",
            "economics do not improve reported cash flow",
        ],
        price_target=None,
    )
