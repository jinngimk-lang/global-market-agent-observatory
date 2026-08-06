from __future__ import annotations

from typing import Protocol

from app.domain.models import ExternalAccountSnapshot, PortfolioSnapshot


class AccountAdapter(Protocol):
    def snapshot(self) -> PortfolioSnapshot: ...


class AccountObserver(Protocol):
    name: str

    async def snapshot(self) -> ExternalAccountSnapshot: ...
