from datetime import UTC, datetime, timedelta

from app.domain.models import Candle, EvidenceGrade, EvidenceItem
from app.store.sqlite import SQLiteStore


def test_persists_and_reads_candles(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "observatory.db", starting_cash="1000")
    start = datetime(2026, 8, 6, 0, 0, tzinfo=UTC)
    candle = Candle(
        symbol="btcusdt",
        interval="1m",
        open_time=start,
        close_time=start + timedelta(minutes=1),
        open=100,
        high=110,
        low=95,
        close=105,
        volume=12.5,
        source="test",
    )

    store.upsert_candle(candle)
    loaded = store.list_candles("BTCUSDT", limit=10)

    assert loaded == [candle]


def test_persists_evidence_with_grade_and_hash(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "observatory.db", starting_cash="1000")
    item = EvidenceItem(
        evidence_id="ev-1",
        title="Verified filing",
        source_type="regulator_filing",
        source_url="https://example.test/filing",
        grade=EvidenceGrade.B,
        observed_at=datetime(2026, 8, 6, tzinfo=UTC),
        summary="Issuer disclosed a material agreement.",
        content_hash="abc123",
        tags=["partnership"],
    )

    store.add_evidence(item)
    loaded = store.list_evidence(limit=10)

    assert loaded == [item]


def test_persists_verified_crisis_winners(tmp_path) -> None:
    from decimal import Decimal

    from app.research.crisis import CrisisWindow, CrisisWinner, TradeCase

    store = SQLiteStore(tmp_path / "observatory.db", starting_cash="1000")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    winner = CrisisWinner(
        case=TradeCase(
            case_id="case-1",
            actor_name="Verified Fund",
            actor_type="institution",
            instrument="INDEX FUTURE",
            opened_at=start,
            closed_at=start + timedelta(days=2),
            gross_pnl=Decimal("1000"),
            costs=Decimal("100"),
            evidence_grade=EvidenceGrade.A,
            evidence_urls=["https://example.test/audit"],
        ),
        window=CrisisWindow(
            name="selloff",
            start=start,
            end=start + timedelta(days=3),
            market="GLOBAL",
            max_drawdown=Decimal("-0.12"),
        ),
        net_pnl=Decimal("900"),
    )

    store.add_crisis_winner(winner)
    loaded = store.list_crisis_winners(limit=10)

    assert loaded == [winner]
