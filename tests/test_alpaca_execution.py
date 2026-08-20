from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest

from app.broker.alpaca import AlpacaExecutionAdapter
from app.domain.models import OrderIntent, OrderStatus, OrderType, Side


def make_intent(*, order_type: OrderType = OrderType.MARKET) -> OrderIntent:
    return OrderIntent(
        client_order_id="nvda-strategy-1",
        symbol="NVDA",
        side=Side.BUY,
        quantity=Decimal("2"),
        reference_price=Decimal("200"),
        order_type=order_type,
        limit_price=(Decimal("199.50") if order_type is OrderType.LIMIT else None),
    )


@pytest.mark.asyncio
async def test_alpaca_submit_maps_broker_neutral_market_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/orders"
        assert request.method == "POST"
        assert request.headers["APCA-API-KEY-ID"] == "key"
        body = json.loads(request.content)
        assert body == {
            "symbol": "NVDA",
            "qty": "2",
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
            "client_order_id": "nvda-strategy-1",
        }
        return httpx.Response(
            200,
            json={
                "id": "alpaca-1",
                "client_order_id": "nvda-strategy-1",
                "status": "new",
                "filled_qty": "0",
                "filled_avg_price": None,
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://paper-api.alpaca.markets"
    ) as client:
        adapter = AlpacaExecutionAdapter(api_key="key", api_secret="secret", client=client)
        result = await adapter.submit(make_intent())

    assert result.status is OrderStatus.ACCEPTED
    assert result.broker_order_id == "alpaca-1"
    assert result.client_order_id == "nvda-strategy-1"


@pytest.mark.asyncio
async def test_alpaca_submit_limit_order_includes_limit_price() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["type"] == "limit"
        assert body["limit_price"] == "199.50"
        return httpx.Response(
            200,
            json={
                "id": "alpaca-limit",
                "client_order_id": "nvda-strategy-1",
                "status": "accepted",
                "filled_qty": "0",
                "filled_avg_price": None,
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://paper-api.alpaca.markets"
    ) as client:
        adapter = AlpacaExecutionAdapter(api_key="key", api_secret="secret", client=client)
        result = await adapter.submit(make_intent(order_type=OrderType.LIMIT))

    assert result.status is OrderStatus.ACCEPTED


@pytest.mark.asyncio
async def test_alpaca_get_by_client_id_returns_none_for_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/orders:by_client_order_id"
        assert request.url.params["client_order_id"] == "missing"
        return httpx.Response(404, json={"message": "order not found"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://paper-api.alpaca.markets"
    ) as client:
        adapter = AlpacaExecutionAdapter(api_key="key", api_secret="secret", client=client)
        result = await adapter.get_order_by_client_id("missing")

    assert result is None


@pytest.mark.asyncio
async def test_alpaca_maps_filled_order_state() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "alpaca-filled",
                "client_order_id": "nvda-strategy-1",
                "status": "filled",
                "filled_qty": "2",
                "filled_avg_price": "201.25",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://paper-api.alpaca.markets"
    ) as client:
        adapter = AlpacaExecutionAdapter(api_key="key", api_secret="secret", client=client)
        result = await adapter.get_order_by_client_id("nvda-strategy-1")

    assert result is not None
    assert result.status is OrderStatus.FILLED
    assert result.filled_quantity == Decimal("2")
    assert result.filled_price == Decimal("201.25")


@pytest.mark.asyncio
async def test_alpaca_cancel_maps_204_to_cancelled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/v2/orders/alpaca-1"
        return httpx.Response(204)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://paper-api.alpaca.markets"
    ) as client:
        adapter = AlpacaExecutionAdapter(api_key="key", api_secret="secret", client=client)
        result = await adapter.cancel("alpaca-1")

    assert result.status is OrderStatus.CANCELLED
    assert result.broker_order_id == "alpaca-1"


@pytest.mark.asyncio
async def test_alpaca_submit_transport_failure_is_unknown_not_safe_to_retry() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection dropped", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://paper-api.alpaca.markets"
    ) as client:
        adapter = AlpacaExecutionAdapter(api_key="key", api_secret="secret", client=client)
        result = await adapter.submit(make_intent())

    assert result.status is OrderStatus.UNKNOWN
    assert result.code == "alpaca_transport_unknown"


@pytest.mark.asyncio
async def test_alpaca_submit_server_error_is_unknown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "temporarily unavailable"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://paper-api.alpaca.markets"
    ) as client:
        adapter = AlpacaExecutionAdapter(api_key="key", api_secret="secret", client=client)
        result = await adapter.submit(make_intent())

    assert result.status is OrderStatus.UNKNOWN
    assert result.code == "alpaca_server_unknown"
