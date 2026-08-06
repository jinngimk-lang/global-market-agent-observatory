from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.models import EvidenceGrade, EvidenceItem
from app.research.crisis import (
    CrisisWindow,
    DailyClose,
    TradeCase,
    detect_crisis_windows,
    find_verified_crisis_winners,
)
from app.research.partnerships import assess_partnership


def day(offset: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=offset)


def test_detects_drawdown_crisis_from_peak_to_recovery() -> None:
    prices = [
        DailyClose(at=day(0), close=Decimal("100")),
        DailyClose(at=day(1), close=Decimal("98")),
        DailyClose(at=day(2), close=Decimal("88")),
        DailyClose(at=day(3), close=Decimal("85")),
        DailyClose(at=day(4), close=Decimal("92")),
        DailyClose(at=day(5), close=Decimal("100")),
    ]

    windows = detect_crisis_windows(prices, drawdown_threshold=Decimal("0.10"))

    assert len(windows) == 1
    assert windows[0].start == day(0)
    assert windows[0].end == day(5)
    assert windows[0].max_drawdown == Decimal("-0.15")


def test_crisis_winners_require_positive_net_pnl_and_strong_evidence() -> None:
    window = CrisisWindow(
        name="global selloff",
        start=day(0),
        end=day(5),
        market="GLOBAL",
        max_drawdown=Decimal("-0.15"),
    )
    verified = TradeCase(
        case_id="verified",
        actor_name="Verified Fund",
        actor_type="institution",
        instrument="INDEX FUTURE",
        opened_at=day(1),
        closed_at=day(4),
        gross_pnl=Decimal("1200"),
        costs=Decimal("200"),
        evidence_grade=EvidenceGrade.A,
        evidence_urls=["https://example.test/audit"],
        strategy_tags=["hedge"],
    )
    screenshot_only = verified.model_copy(
        update={"case_id": "weak", "evidence_grade": EvidenceGrade.D}
    )
    losing = verified.model_copy(
        update={"case_id": "loss", "gross_pnl": Decimal("100"), "costs": Decimal("200")}
    )

    winners = find_verified_crisis_winners([verified, screenshot_only, losing], [window])

    assert [winner.case.case_id for winner in winners] == ["verified"]
    assert winners[0].net_pnl == Decimal("1000")
    assert winners[0].window.name == "global selloff"


def test_partnership_assessment_uses_filing_strength_without_predicting_returns() -> None:
    evidence = EvidenceItem(
        evidence_id="sec-1",
        title="Material agreement",
        source_type="regulator_filing",
        source_url="https://sec.example/filing",
        grade=EvidenceGrade.B,
        observed_at=day(10),
        event_date=day(9),
        entity="Example Corp",
        summary="Entry into a material definitive agreement",
        content_hash="a" * 64,
        tags=["partnership", "material-agreement"],
        metadata={"form": "8-K", "items": "1.01"},
    )

    assessment = assess_partnership(evidence)

    assert assessment.maturity == "binding-regulatory-filed"
    assert assessment.confidence == "high"
    assert "revenue contribution" in assessment.validation_metrics
    assert assessment.price_target is None


def test_import_payload_only_returns_verified_winners() -> None:
    from app.research.import_cases import parse_import_payload

    payload = {
        "windows": [
            {
                "name": "selloff",
                "start": day(0).isoformat(),
                "end": day(5).isoformat(),
                "market": "GLOBAL",
                "max_drawdown": "-0.15",
            }
        ],
        "cases": [
            {
                "case_id": "case-a",
                "actor_name": "Audited Fund",
                "actor_type": "institution",
                "instrument": "INDEX FUTURE",
                "opened_at": day(1).isoformat(),
                "closed_at": day(4).isoformat(),
                "gross_pnl": "1000",
                "costs": "100",
                "evidence_grade": "A",
                "evidence_urls": ["https://example.test/audit"],
                "strategy_tags": ["hedge"],
            }
        ],
    }

    winners = parse_import_payload(payload)

    assert len(winners) == 1
    assert winners[0].case.case_id == "case-a"
