from __future__ import annotations

from decimal import Decimal

from app.broker.paper import PaperBroker
from app.domain.models import OrderIntent, OrderStatus
from app.execution.models import ExecutionResult
from app.store.sqlite import SQLiteStore


class PaperExecutionAdapter:
    """Expose the deterministic local paper broker through ExecutionAdapter."""

    name = "paper"

    def __init__(self, store: SQLiteStore) -> None:
        self._store = store
        self._broker = PaperBroker(store)

    @classmethod
    def from_store(cls, store: SQLiteStore) -> PaperExecutionAdapter:
        return cls(store)

    async def get_order_by_client_id(self, client_order_id: str) -> ExecutionResult | None:
        record = self._store.get_order_by_client_id(client_order_id)
        return self._map_record(record) if record is not None else None

    async def submit(self, intent: OrderIntent) -> ExecutionResult:
        if intent.reference_price is None or intent.reference_price <= 0:
            return ExecutionResult(
                client_order_id=intent.client_order_id,
                status=OrderStatus.REJECTED,
                code="missing_reference_price",
                message="Paper execution requires a positive reference price.",
            )
        record = self._broker.submit(intent, intent.reference_price)
        return self._map_record(record)

    async def cancel(self, broker_order_id: str) -> ExecutionResult:
        return ExecutionResult(
            broker_order_id=broker_order_id,
            status=OrderStatus.REJECTED,
            code="paper_order_terminal",
            message="Local paper orders fill immediately and cannot be cancelled.",
        )

    @staticmethod
    def _map_record(record) -> ExecutionResult:
        return ExecutionResult(
            client_order_id=record.intent.client_order_id,
            broker_order_id=record.order_id,
            status=record.status,
            code="paper_fill",
            message=record.message,
            filled_quantity=(
                record.intent.quantity if record.status is OrderStatus.FILLED else Decimal("0")
            ),
            filled_price=record.filled_price,
            raw_status=record.status.value,
            observed_at=record.filled_at or record.intent.requested_at,
        )
