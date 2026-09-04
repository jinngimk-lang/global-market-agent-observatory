from __future__ import annotations

from typing import Protocol

from app.domain.models import ExternalAccountSnapshot, OrderIntent, PortfolioSnapshot
from app.execution.models import ExecutionResult


class AccountAdapter(Protocol):
    def snapshot(self) -> PortfolioSnapshot: ...


class AccountObserver(Protocol):
    name: str

    async def snapshot(self) -> ExternalAccountSnapshot: ...


class ExecutionAdapter(Protocol):
    name: str

    async def get_order_by_client_id(self, client_order_id: str) -> ExecutionResult | None: ...

    async def submit(self, intent: OrderIntent) -> ExecutionResult: ...

    async def cancel(self, broker_order_id: str) -> ExecutionResult: ...
