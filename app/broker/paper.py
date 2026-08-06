from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from threading import RLock
from uuid import uuid4

from app.domain.models import (
    OrderIntent,
    OrderRecord,
    OrderStatus,
    PortfolioSnapshot,
    Position,
    Side,
)
from app.store.sqlite import SQLiteStore


class PaperBroker:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store
        self._lock = RLock()

    def submit(self, intent: OrderIntent, market_price: Decimal) -> OrderRecord:
        if market_price <= 0:
            raise ValueError("market_price must be positive")
        with self._lock:
            existing_order = self._store.get_order_by_client_id(intent.client_order_id)
            if existing_order is not None:
                return existing_order

            cash, _ = self._store.get_account_state()
            existing = self._store.get_position(intent.symbol)
            existing_quantity = existing.quantity if existing else Decimal("0")
            existing_average = existing.average_price if existing else Decimal("0")
            signed_quantity = intent.quantity if intent.side is Side.BUY else -intent.quantity
            new_quantity = existing_quantity + signed_quantity

            realized_delta, new_average = self._calculate_position_change(
                existing_quantity=existing_quantity,
                existing_average=existing_average,
                signed_quantity=signed_quantity,
                fill_price=market_price,
                new_quantity=new_quantity,
            )
            new_cash = cash - (signed_quantity * market_price)
            position = None
            if new_quantity != 0:
                position = Position(
                    symbol=intent.symbol,
                    quantity=new_quantity,
                    average_price=new_average,
                    market_price=market_price,
                )

            filled_at = datetime.now(UTC)
            record = OrderRecord(
                order_id=str(uuid4()),
                intent=intent,
                status=OrderStatus.FILLED,
                message="Filled by deterministic paper broker.",
                filled_price=market_price,
                filled_at=filled_at,
            )
            self._store.apply_paper_fill(
                record=record,
                cash=new_cash,
                realized_pnl_delta=realized_delta,
                position=position,
            )
            return record

    def snapshot(self) -> PortfolioSnapshot:
        cash, realized = self._store.get_account_state()
        return PortfolioSnapshot(
            cash=cash,
            positions=self._store.list_positions(),
            realized_pnl_today=realized,
            mode="paper",
        )

    @staticmethod
    def _calculate_position_change(
        *,
        existing_quantity: Decimal,
        existing_average: Decimal,
        signed_quantity: Decimal,
        fill_price: Decimal,
        new_quantity: Decimal,
    ) -> tuple[Decimal, Decimal]:
        if existing_quantity == 0 or existing_quantity * signed_quantity > 0:
            total_cost = (
                abs(existing_quantity) * existing_average + abs(signed_quantity) * fill_price
            )
            total_quantity = abs(existing_quantity) + abs(signed_quantity)
            return Decimal("0"), total_cost / total_quantity

        closed_quantity = min(abs(existing_quantity), abs(signed_quantity))
        if existing_quantity > 0:
            realized = (fill_price - existing_average) * closed_quantity
        else:
            realized = (existing_average - fill_price) * closed_quantity

        if new_quantity == 0:
            new_average = Decimal("0")
        elif existing_quantity * new_quantity > 0:
            new_average = existing_average
        else:
            new_average = fill_price
        return realized, new_average
