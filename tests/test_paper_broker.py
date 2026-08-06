from decimal import Decimal

from app.broker.paper import PaperBroker
from app.domain.models import OrderIntent, OrderStatus, Side
from app.store.sqlite import SQLiteStore


def intent(order_id: str, side: Side, quantity: str, price: str) -> OrderIntent:
    return OrderIntent(
        client_order_id=order_id,
        symbol="BTCUSDT",
        side=side,
        quantity=Decimal(quantity),
        reference_price=Decimal(price),
    )


def test_paper_broker_tracks_average_cost_and_realized_pnl(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "observatory.db", starting_cash="1000")
    broker = PaperBroker(store)

    first = broker.submit(intent("buy-1", Side.BUY, "2", "100"), Decimal("100"))
    second = broker.submit(intent("buy-2", Side.BUY, "1", "130"), Decimal("130"))
    third = broker.submit(intent("sell-1", Side.SELL, "1", "140"), Decimal("140"))
    snapshot = broker.snapshot()

    assert first.status is OrderStatus.FILLED
    assert second.status is OrderStatus.FILLED
    assert third.status is OrderStatus.FILLED
    assert snapshot.cash == Decimal("810")
    assert snapshot.realized_pnl_today == Decimal("30")
    assert len(snapshot.positions) == 1
    assert snapshot.positions[0].quantity == Decimal("2")
    assert snapshot.positions[0].average_price == Decimal("110")
    assert snapshot.positions[0].market_price == Decimal("140")


def test_duplicate_client_order_id_is_idempotent(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "observatory.db", starting_cash="1000")
    broker = PaperBroker(store)
    order = intent("duplicate", Side.BUY, "1", "100")

    first = broker.submit(order, Decimal("100"))
    second = broker.submit(order, Decimal("100"))
    snapshot = broker.snapshot()

    assert second.order_id == first.order_id
    assert snapshot.cash == Decimal("900")
    assert snapshot.positions[0].quantity == Decimal("1")


def test_flipping_from_long_to_short_resets_average_price(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "observatory.db", starting_cash="1000")
    broker = PaperBroker(store)

    broker.submit(intent("buy", Side.BUY, "1", "100"), Decimal("100"))
    broker.submit(intent("sell", Side.SELL, "2", "90"), Decimal("90"))
    snapshot = broker.snapshot()

    assert snapshot.realized_pnl_today == Decimal("-10")
    assert snapshot.positions[0].quantity == Decimal("-1")
    assert snapshot.positions[0].average_price == Decimal("90")


def test_paper_broker_preserves_decimal_realized_pnl_precision(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "observatory.db", starting_cash="10")
    broker = PaperBroker(store)

    broker.submit(intent("base-buy", Side.BUY, "1", "1"), Decimal("1"))
    broker.submit(intent("base-sell", Side.SELL, "1", "2"), Decimal("2"))
    broker.submit(intent("tiny-buy", Side.BUY, "1", "0.1"), Decimal("0.1"))
    broker.submit(
        intent("tiny-sell", Side.SELL, "1", "0.100000000000000001"),
        Decimal("0.100000000000000001"),
    )

    assert broker.snapshot().realized_pnl_today == Decimal("1.000000000000000001")
