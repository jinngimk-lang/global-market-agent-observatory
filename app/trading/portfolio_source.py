from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.broker.base import AccountObserver
from app.broker.paper import PaperBroker
from app.domain.models import PortfolioSnapshot, RiskContext
from app.reconciliation.service import reconcile_external_account
from app.store.sqlite import SQLiteStore


class PortfolioRiskSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio: PortfolioSnapshot
    risk_context: RiskContext


class PortfolioSource(Protocol):
    async def snapshot(self) -> PortfolioRiskSnapshot: ...


class LocalPaperPortfolioSource:
    def __init__(self, store: SQLiteStore) -> None:
        self._broker = PaperBroker(store)

    @classmethod
    def from_store(cls, store: SQLiteStore) -> LocalPaperPortfolioSource:
        return cls(store)

    async def snapshot(self) -> PortfolioRiskSnapshot:
        return PortfolioRiskSnapshot(
            portfolio=self._broker.snapshot(),
            risk_context=RiskContext(),
        )


class BrokerPortfolioSource:
    def __init__(
        self,
        observer: AccountObserver,
        *,
        require_daily_pnl: bool = True,
    ) -> None:
        self._observer = observer
        self._require_daily_pnl = require_daily_pnl

    async def snapshot(self) -> PortfolioRiskSnapshot:
        observed = await self._observer.snapshot()
        reconciled = reconcile_external_account(
            observed,
            require_daily_pnl=self._require_daily_pnl,
        )
        return PortfolioRiskSnapshot(
            portfolio=reconciled.portfolio,
            risk_context=reconciled.risk_context,
        )
