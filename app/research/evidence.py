from __future__ import annotations

import hashlib
import json
from typing import Any

from app.domain.models import EvidenceGrade

_GRADE_A_SOURCES = {"broker_export", "signed_onchain_transaction", "audited_record"}
_GRADE_B_SOURCES = {"regulator_filing", "regulator_holdings", "exchange_notice"}
_GRADE_C_SOURCES = {"company_release", "official_project_release", "verified_interview"}


def grade_evidence(source_type: str) -> EvidenceGrade:
    normalized = source_type.strip().lower()
    if normalized in _GRADE_A_SOURCES:
        return EvidenceGrade.A
    if normalized in _GRADE_B_SOURCES:
        return EvidenceGrade.B
    if normalized in _GRADE_C_SOURCES:
        return EvidenceGrade.C
    return EvidenceGrade.D


def content_hash(payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
