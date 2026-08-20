from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.models import ExternalAccountSnapshot, ObservedPosition
from app.reconciliation.service import ReconciliationError, reconcile_external_account


def snapshot(**updates) -> ExternalAccountSnapshot:
    values = {
        "provider": "alpaca",
        "account_id": "acct-1",
        "mode": "live",
        "status": "active",
        "base_currency": "USD",
        "equity": Decimal("9500"),
        "prior_equity": Decimal("10000"),
        "daily_pnl": Decimal("-500"),
        "cash": Decimal("5000"),
        "buying_power": Decimal("8000"),
        "trading_blocked": False,
        "account_blocked": False,
        "trade_suspended_by_user": False,
        "positions": [
            ObservedPosition(
                symbol="NVDA",
                quantity=Decimal("5"),
                average_price=Decimal("195"),
                market_price=Decimal("200"),
                unrealized_pnl=Decimal("25"),
            )
        ],
        "observed_at": datetime(2026, 8, 20, 14, 0, tzinfo=UTC),
    }
    values.update(updates)
    return ExternalAccountSnapshot(**values)


def test_reconciliation_converts_broker_snapshot_to_portfolio_and_risk_context() -> None:
    observed = snapshot()

    result = reconcile_external_account(
        observed,
        now=datetime(2026, 8, 20, 14, 0, 5, tzinfo=UTC),
    )

    assert result.provider == "alpaca"
    assert result.portfolio.cash == Decimal("5000")
    assert result.portfolio.positions[0].symbol == "NVDA"
    assert result.portfolio.positions[0].average_price == Decimal("195")
    assert result.portfolio.positions[0].market_price == Decimal("200")
    assert result.risk_context.account_state_age_seconds == 5
    assert result.risk_context.portfolio_drawdown == Decimal("500")
    assert result.daily_pnl == Decimal("-500")


def test_reconciliation_rejects_blocked_account() -> None:
    with pytest.raises(ReconciliationError, match="blocked"):
        reconcile_external_account(snapshot(trading_blocked=True))


def test_reconciliation_rejects_missing_cash_or_equity() -> None:
    with pytest.raises(ReconciliationError, match="cash"):
        reconcile_external_account(snapshot(cash=None))

    with pytest.raises(ReconciliationError, match="equity"):
        reconcile_external_account(snapshot(equity=None))


def test_reconciliation_rejects_position_without_market_price() -> None:
    with pytest.raises(ReconciliationError, match="market price"):
        reconcile_external_account(
            snapshot(
                positions=[
                    ObservedPosition(
                        symbol="NVDA",
                        quantity=Decimal("5"),
                        average_price=Decimal("195"),
                        market_price=None,
                    )
                ]
            )
        )


def test_reconciliation_requires_daily_pnl_for_live_risk() -> None:
    with pytest.raises(ReconciliationError, match="daily pnl"):
        reconcile_external_account(snapshot(daily_pnl=None), require_daily_pnl=True)


def test_reconciliation_can_allow_missing_daily_pnl_for_non_live_observation() -> None:
    result = reconcile_external_account(snapshot(daily_pnl=None), require_daily_pnl=False)

    assert result.daily_pnl is None
    assert result.risk_context.portfolio_drawdown == Decimal("0")


def test_reconciliation_preserves_stale_age_for_risk_engine_to_reject() -> None:
    result = reconcile_external_account(
        snapshot(),
        now=datetime(2026, 8, 20, 14, 1, tzinfo=UTC),
    )

    assert result.risk_context.account_state_age_seconds == 60
