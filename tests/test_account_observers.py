from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from app.broker.alpaca import AlpacaObserver
from app.broker.ccxt_observer import CCXTObserver


@pytest.mark.asyncio
async def test_alpaca_observer_maps_account_positions_and_orders() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/account":
            assert request.headers["APCA-API-KEY-ID"] == "key"
            return httpx.Response(
                200,
                json={
                    "id": "acct-1",
                    "currency": "USD",
                    "equity": "12000.50",
                    "cash": "5000.25",
                    "buying_power": "10000.50",
                    "status": "ACTIVE",
                },
            )
        if request.url.path == "/v2/positions":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "AAPL",
                        "qty": "2",
                        "avg_entry_price": "100",
                        "current_price": "110",
                        "unrealized_pl": "20",
                    }
                ],
            )
        if request.url.path == "/v2/orders":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "order-1",
                        "symbol": "AAPL",
                        "side": "buy",
                        "qty": "2",
                        "filled_qty": "2",
                        "status": "filled",
                        "submitted_at": "2026-08-01T00:00:00Z",
                        "filled_avg_price": "100",
                    }
                ],
            )
        raise AssertionError(f"Unexpected path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://paper-api.alpaca.markets"
    ) as client:
        observer = AlpacaObserver(api_key="key", api_secret="secret", client=client)
        snapshot = await observer.snapshot()

    assert snapshot.provider == "alpaca"
    assert snapshot.account_id == "acct-1"
    assert snapshot.mode == "paper-read-only"
    assert str(snapshot.equity) == "12000.50"
    assert snapshot.positions[0].symbol == "AAPL"
    assert snapshot.positions[0].quantity == 2
    assert snapshot.orders[0].order_id == "order-1"
    assert snapshot.orders[0].submitted_at == datetime.fromisoformat("2026-08-01T00:00:00+00:00")


class FakeExchange:
    id = "kraken"

    def fetch_balance(self):
        return {
            "total": {"USD": 1000, "BTC": 0.1},
            "free": {"USD": 800, "BTC": 0.05},
        }

    def fetch_positions(self):
        return [
            {
                "symbol": "BTC/USD:USD",
                "contracts": 1,
                "entryPrice": 60000,
                "markPrice": 61000,
                "unrealizedPnl": 1000,
            }
        ]

    def fetch_open_orders(self):
        return [
            {
                "id": "ccxt-order-1",
                "symbol": "BTC/USD",
                "side": "sell",
                "amount": 0.1,
                "filled": 0,
                "status": "open",
                "timestamp": 1785542400000,
                "average": None,
            }
        ]


@pytest.mark.asyncio
async def test_ccxt_observer_maps_balances_positions_and_orders() -> None:
    snapshot = await CCXTObserver(exchange=FakeExchange(), mode="sandbox-read-only").snapshot()

    assert snapshot.provider == "ccxt:kraken"
    assert snapshot.mode == "sandbox-read-only"
    assert {balance.asset for balance in snapshot.balances} == {"USD", "BTC"}
    assert snapshot.positions[0].market_price == 61000
    assert snapshot.orders[0].side == "sell"


@pytest.mark.asyncio
async def test_ibkr_observer_maps_gateway_account_data() -> None:
    from app.broker.ibkr import IBKRObserver

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/api/iserver/accounts":
            return httpx.Response(200, json={"accounts": ["U123"], "selectedAccount": "U123"})
        if request.url.path == "/v1/api/portfolio/U123/summary":
            return httpx.Response(
                200,
                json={
                    "netliquidation": {"amount": 50000, "currency": "USD"},
                    "totalcashvalue": {"amount": 20000, "currency": "USD"},
                    "availablefunds": {"amount": 18000, "currency": "USD"},
                },
            )
        if request.url.path == "/v1/api/portfolio/U123/positions/0":
            return httpx.Response(
                200,
                json=[
                    {
                        "ticker": "MSFT",
                        "position": 10,
                        "avgPrice": 400,
                        "mktPrice": 410,
                        "unrealizedPnl": 100,
                    }
                ],
            )
        if request.url.path == "/v1/api/portfolio/U123/positions/1":
            return httpx.Response(200, json=[])
        if request.url.path == "/v1/api/iserver/account/orders":
            return httpx.Response(
                200,
                json={
                    "orders": [
                        {
                            "orderId": 99,
                            "ticker": "MSFT",
                            "side": "BUY",
                            "totalSize": 10,
                            "filledQuantity": 10,
                            "status": "Filled",
                            "lastExecutionTime_r": 1785542400000,
                            "avgPrice": 400,
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected IBKR path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://localhost:5000/v1/api"
    ) as client:
        snapshot = await IBKRObserver(client=client, account_id="U123").snapshot()

    assert snapshot.provider == "ibkr"
    assert snapshot.account_id == "U123"
    assert snapshot.mode == "gateway-read-only"
    assert snapshot.equity == 50000
    assert snapshot.positions[0].symbol == "MSFT"
    assert snapshot.orders[0].order_id == "99"


@pytest.mark.asyncio
async def test_ibkr_observer_reads_all_position_pages() -> None:
    from app.broker.ibkr import IBKRObserver

    requested_position_pages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/api/iserver/accounts":
            return httpx.Response(200, json={"accounts": ["U123"], "selectedAccount": "U123"})
        if request.url.path == "/v1/api/portfolio/U123/summary":
            return httpx.Response(
                200,
                json={
                    "netliquidation": {"amount": 50000, "currency": "USD"},
                    "totalcashvalue": {"amount": 20000, "currency": "USD"},
                    "availablefunds": {"amount": 18000, "currency": "USD"},
                },
            )
        if request.url.path.startswith("/v1/api/portfolio/U123/positions/"):
            requested_position_pages.append(request.url.path)
            page = request.url.path.rsplit("/", 1)[-1]
            if page == "0":
                return httpx.Response(
                    200,
                    json=[
                        {
                            "ticker": "MSFT",
                            "position": 10,
                            "avgPrice": 400,
                            "mktPrice": 410,
                            "pageSize": 1,
                        }
                    ],
                )
            if page == "1":
                return httpx.Response(
                    200,
                    json=[
                        {
                            "ticker": "NVDA",
                            "position": 5,
                            "avgPrice": 150,
                            "mktPrice": 155,
                            "pageSize": 1,
                        }
                    ],
                )
            if page == "2":
                return httpx.Response(200, json=[])
        if request.url.path == "/v1/api/iserver/account/orders":
            return httpx.Response(200, json={"orders": []})
        raise AssertionError(f"Unexpected IBKR path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://localhost:5000/v1/api"
    ) as client:
        snapshot = await IBKRObserver(client=client, account_id="U123").snapshot()

    assert [position.symbol for position in snapshot.positions] == ["MSFT", "NVDA"]
    assert requested_position_pages == [
        "/v1/api/portfolio/U123/positions/0",
        "/v1/api/portfolio/U123/positions/1",
        "/v1/api/portfolio/U123/positions/2",
    ]
