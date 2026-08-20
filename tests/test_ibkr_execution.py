from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest

from app.broker.ibkr import IBKRExecutionAdapter
from app.domain.models import OrderIntent, OrderStatus, OrderType, Side


def make_intent(*, order_type: OrderType = OrderType.MARKET) -> OrderIntent:
    return OrderIntent(
        client_order_id="nvda-ibkr-1",
        symbol="NVDA",
        side=Side.BUY,
        quantity=Decimal("2"),
        reference_price=Decimal("200"),
        order_type=order_type,
        limit_price=(Decimal("199.50") if order_type is OrderType.LIMIT else None),
    )


def search_response() -> list[dict[str, object]]:
    return [
        {
            "conid": 4815747,
            "symbol": "NVDA",
            "description": "NVIDIA CORP",
            "sections": [{"secType": "STK"}],
        }
    ]


@pytest.mark.asyncio
async def test_ibkr_submit_resolves_stock_contract_and_uses_client_order_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/api/iserver/secdef/search":
            assert request.method == "POST"
            assert json.loads(request.content) == {"symbol": "NVDA", "secType": "STK", "name": False}
            return httpx.Response(200, json=search_response())
        if request.url.path == "/v1/api/iserver/account/U123/orders":
            body = json.loads(request.content)
            assert body == {
                "orders": [
                    {
                        "acctId": "U123",
                        "cOID": "nvda-ibkr-1",
                        "conid": 4815747,
                        "orderType": "MKT",
                        "side": "BUY",
                        "tif": "DAY",
                        "quantity": 2.0,
                    }
                ]
            }
            return httpx.Response(
                200,
                json=[
                    {
                        "order_id": "ibkr-1",
                        "order_status": "Submitted",
                        "local_order_id": "nvda-ibkr-1",
                    }
                ],
            )
        raise AssertionError(f"Unexpected path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://localhost:5000/v1/api"
    ) as client:
        adapter = IBKRExecutionAdapter(account_id="U123", client=client)
        result = await adapter.submit(make_intent())

    assert result.status is OrderStatus.ACCEPTED
    assert result.broker_order_id == "ibkr-1"
    assert result.client_order_id == "nvda-ibkr-1"


@pytest.mark.asyncio
async def test_ibkr_limit_order_includes_price() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/secdef/search"):
            return httpx.Response(200, json=search_response())
        body = json.loads(request.content)
        assert body["orders"][0]["orderType"] == "LMT"
        assert body["orders"][0]["price"] == 199.5
        return httpx.Response(
            200,
            json=[{"order_id": "ibkr-lmt", "order_status": "PreSubmitted", "local_order_id": "nvda-ibkr-1"}],
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://localhost:5000/v1/api"
    ) as client:
        adapter = IBKRExecutionAdapter(account_id="U123", client=client)
        result = await adapter.submit(make_intent(order_type=OrderType.LIMIT))

    assert result.status is OrderStatus.ACCEPTED


@pytest.mark.asyncio
async def test_ibkr_reply_message_is_not_auto_confirmed_unless_allowlisted() -> None:
    confirmation_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal confirmation_called
        if request.url.path.endswith("/secdef/search"):
            return httpx.Response(200, json=search_response())
        if request.url.path.endswith("/orders") and request.method == "POST":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "reply-1",
                        "message": ["Price exceeds precautionary limit"],
                        "messageIds": ["o163"],
                    }
                ],
            )
        if "/iserver/reply/" in request.url.path:
            confirmation_called = True
            return httpx.Response(200, json={"order_id": "should-not-happen"})
        raise AssertionError(f"Unexpected path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://localhost:5000/v1/api"
    ) as client:
        adapter = IBKRExecutionAdapter(account_id="U123", client=client)
        result = await adapter.submit(make_intent())

    assert result.status is OrderStatus.REJECTED
    assert result.code == "ibkr_confirmation_required"
    assert confirmation_called is False


@pytest.mark.asyncio
async def test_ibkr_allowlisted_reply_is_confirmed_and_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/secdef/search"):
            return httpx.Response(200, json=search_response())
        if request.url.path.endswith("/orders") and request.method == "POST":
            return httpx.Response(
                200,
                json=[{"id": "reply-1", "message": ["warning"], "messageIds": ["o163"]}],
            )
        if request.url.path.endswith("/iserver/reply/reply-1"):
            assert json.loads(request.content) == {"confirmed": True}
            return httpx.Response(
                200,
                json={
                    "order_id": "ibkr-confirmed",
                    "order_status": "Submitted",
                    "local_order_id": "nvda-ibkr-1",
                },
            )
        raise AssertionError(f"Unexpected path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://localhost:5000/v1/api"
    ) as client:
        adapter = IBKRExecutionAdapter(
            account_id="U123",
            auto_confirm_message_ids={"o163"},
            client=client,
        )
        result = await adapter.submit(make_intent())

    assert result.status is OrderStatus.ACCEPTED
    assert result.broker_order_id == "ibkr-confirmed"


@pytest.mark.asyncio
async def test_ibkr_confirmation_transport_failure_is_unknown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/secdef/search"):
            return httpx.Response(200, json=search_response())
        if request.url.path.endswith("/orders") and request.method == "POST":
            return httpx.Response(
                200,
                json=[{"id": "reply-1", "message": ["warning"], "messageIds": ["o163"]}],
            )
        if request.url.path.endswith("/iserver/reply/reply-1"):
            raise httpx.ConnectError("connection lost", request=request)
        raise AssertionError(f"Unexpected path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://localhost:5000/v1/api"
    ) as client:
        adapter = IBKRExecutionAdapter(
            account_id="U123",
            auto_confirm_message_ids={"o163"},
            client=client,
        )
        result = await adapter.submit(make_intent())

    assert result.status is OrderStatus.UNKNOWN
    assert result.code == "ibkr_confirmation_unknown"


@pytest.mark.asyncio
async def test_ibkr_lookup_matches_client_order_reference_and_filled_state() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/api/iserver/account/orders"
        return httpx.Response(
            200,
            json={
                "orders": [
                    {
                        "orderId": 99,
                        "order_ref": "nvda-ibkr-1",
                        "ticker": "NVDA",
                        "status": "Filled",
                        "filledQuantity": 2,
                        "avgPrice": 201.25,
                    }
                ]
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://localhost:5000/v1/api"
    ) as client:
        adapter = IBKRExecutionAdapter(account_id="U123", client=client)
        result = await adapter.get_order_by_client_id("nvda-ibkr-1")

    assert result is not None
    assert result.status is OrderStatus.FILLED
    assert result.filled_quantity == Decimal("2")
    assert result.filled_price == Decimal("201.25")


@pytest.mark.asyncio
async def test_ibkr_cancel_acknowledgement_is_not_misreported_as_cancelled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/v1/api/iserver/account/U123/order/99"
        return httpx.Response(
            200,
            json={"msg": "Request was submitted", "order_id": 99, "account": "U123"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://localhost:5000/v1/api"
    ) as client:
        adapter = IBKRExecutionAdapter(account_id="U123", client=client)
        result = await adapter.cancel("99")

    assert result.status is OrderStatus.ACCEPTED
    assert result.code == "cancel_requested"


@pytest.mark.asyncio
async def test_ibkr_order_submit_server_error_is_unknown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/secdef/search"):
            return httpx.Response(200, json=search_response())
        return httpx.Response(503, json={"error": "temporarily unavailable"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://localhost:5000/v1/api"
    ) as client:
        adapter = IBKRExecutionAdapter(account_id="U123", client=client)
        result = await adapter.submit(make_intent())

    assert result.status is OrderStatus.UNKNOWN
    assert result.code == "ibkr_submit_unknown"
