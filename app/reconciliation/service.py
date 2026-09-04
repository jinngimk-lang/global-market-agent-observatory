from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.models import ExternalAccountSnapshot, PortfolioSnapshot, Position, RiskContext


class ReconciliationError(RuntimeError):
    pass


class ReconciledPortfolio(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    account_id: str
    portfolio: PortfolioSnapshot
    risk_context: RiskContext
    daily_pnl: Decimal | None = None
    equity: Decimal
    buying_power: Decimal | None = None


def reconcile_external_account(
    snapshot: ExternalAccountSnapshot,
    *,
    now: datetime | None = None,
    require_daily_pnl: bool = True,
) -> ReconciledPortfolio:
    status = snapshot.status.strip().lower()
    if status not in {"active", "connected"}:
        raise ReconciliationError(
            f"Broker account is not active/connected: {snapshot.status}"
        )
    if snapshot.trading_blocked or snapshot.account_blocked or snapshot.trade_suspended_by_user:
        raise ReconciliationError("Broker account is blocked or trading is suspended")
    if snapshot.cash is None:
        raise ReconciliationError("Broker cash is unavailable")
    if snapshot.equity is None:
        raise ReconciliationError("Broker equity is unavailable")
    if require_daily_pnl and snapshot.daily_pnl is None:
        raise ReconciliationError("Broker daily pnl is unavailable for live risk")

    positions: list[Position] = []
    for observed in snapshot.positions:
        if observed.market_price is None:
            raise ReconciliationError(
                f"Broker market price is unavailable for {observed.symbol}"
            )
        if observed.average_price is None:
            raise ReconciliationError(
                f"Broker average price is unavailable for {observed.symbol}"
            )
        positions.append(
            Position(
                symbol=observed.symbol,
                quantity=observed.quantity,
                average_price=observed.average_price,
                market_price=observed.market_price,
            )
        )

    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    observed_at = snapshot.observed_at
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    age = max(
        (current.astimezone(UTC) - observed_at.astimezone(UTC)).total_seconds(),
        0.0,
    )
    drawdown = max(-(snapshot.daily_pnl or Decimal("0")), Decimal("0"))

    portfolio = PortfolioSnapshot(
        cash=snapshot.cash,
        positions=positions,
        realized_pnl_today=Decimal("0"),
        mode=snapshot.mode,
        observed_at=snapshot.observed_at,
    )
    return ReconciledPortfolio(
        provider=snapshot.provider,
        account_id=snapshot.account_id,
        portfolio=portfolio,
        risk_context=RiskContext(
            account_state_age_seconds=age,
            portfolio_drawdown=drawdown,
        ),
        daily_pnl=snapshot.daily_pnl,
        equity=snapshot.equity,
        buying_power=snapshot.buying_power,
    )
