from decimal import Decimal

from app.research.market_intelligence import MarketStructureSnapshot, PriceZone


def test_market_structure_snapshot_is_not_execution_capable():
    snapshot = MarketStructureSnapshot(
        symbol="BTCUSDT",
        supports=[
            PriceZone(
                lower=Decimal("62000"),
                upper=Decimal("62500"),
                label="support",
                source="derived",
            )
        ],
        put_wall=Decimal("62000"),
        call_wall=Decimal("70000"),
    )

    assert snapshot.execution_allowed is False
    assert snapshot.put_wall == Decimal("62000")
    assert snapshot.call_wall == Decimal("70000")
