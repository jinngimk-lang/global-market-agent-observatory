from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from app.broker.alpaca import AlpacaObserver
from app.broker.ibkr import IBKRObserver


@pytest.mark.asyncio
async def test_alpaca_snapshot_maps_prior_equity_daily_pnl_and_block_flags() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/account":
            return httpx.Response(
                200,
                json={
                    "id": "acct-1",
                    "status": "ACTIVE",
                    "currency": "USD",
                    "equity": "9500",
                    "last_equity": "10000",
                    "cash": "5000",
                    "buying_power": "8000",
                    "trading_blocked": False,
                    "account_blocked": False,
                    "trade_suspended_by_user": False,
                },
            )
        if request.url.path == "/v2/positions":
            return httpx.Response(200, json=[])
        if request.url.path == "/v2/orders":
            return httpx.Response(200, json=[])
        raise AssertionError(request.url.path)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://paper-api.alpaca.markets"
    ) as client:
        observed = await AlpacaObserver(api_key="key", api_secret="secret", client=client).snapshot()

    assert observed.prior_equity == Decimal("10000")
    assert observed.daily_pnl == Decimal("-500")
    assert observed.trading_blocked is False
    assert observed.account_blocked is False
    assert observed.trade_suspended_by_user is False


@pytest.mark.asyncio
async def test_ibkr_snapshot_maps_daily_pnl_when_gateway_provides_it() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/api/iserver/accounts":
            return httpx.Response(200, json={"selectedAccount": "U123", "accounts": ["U123"]})
        if request.url.path == "/v1/api/portfolio/U123/summary":
            return httpx.Response(
                200,
                json={
                    "netliquidation": {"amount": 9500, "currency": "USD"},
                    "totalcashvalue": {"amount": 5000, "currency": "USD"},
                    "availablefunds": {"amount": 8000, "currency": "USD"},
                    "dailypnl": {"amount": -300, "currency": "USD"},
                },
            )
        if request.url.path == "/v1/api/portfolio/U123/positions/0":
            return httpx.Response(200, json=[])
        if request.url.path == "/v1/api/iserver/account/orders":
            return httpx.Response(200, json={"orders": []})
        raise AssertionError(request.url.path)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://localhost:5000/v1/api"
    ) as client:
        observed = await IBKRObserver(account_id="U123", client=client).snapshot()

    assert observed.daily_pnl == Decimal("-300")
