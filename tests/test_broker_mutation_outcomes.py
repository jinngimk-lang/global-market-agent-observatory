from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from app.broker.alpaca import AlpacaExecutionAdapter
from app.broker.ibkr import IBKRExecutionAdapter
from app.domain.models import OrderIntent, OrderStatus, Side


def intent(client_order_id: str) -> OrderIntent:
    return OrderIntent(
        client_order_id=client_order_id,
        symbol="NVDA",
        side=Side.BUY,
        quantity=Decimal("1"),
        reference_price=Decimal("200"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [408, 429])
async def test_alpaca_submit_ambiguous_http_status_is_unknown(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/orders"
        return httpx.Response(status_code, json={"message": "request outcome uncertain"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://paper-api.alpaca.markets",
    ) as client:
        adapter = AlpacaExecutionAdapter(api_key="key", api_secret="secret", client=client)
        result = await adapter.submit(intent("alpaca-ambiguous"))

    assert result.status is OrderStatus.UNKNOWN
    assert result.code == "alpaca_submit_http_unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [408, 429])
async def test_alpaca_cancel_ambiguous_http_status_is_unknown(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        return httpx.Response(status_code, json={"message": "cancel outcome uncertain"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://paper-api.alpaca.markets",
    ) as client:
        adapter = AlpacaExecutionAdapter(api_key="key", api_secret="secret", client=client)
        result = await adapter.cancel("alpaca-order-1")

    assert result.status is OrderStatus.UNKNOWN
    assert result.code == "alpaca_cancel_http_unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [408, 429])
async def test_ibkr_submit_ambiguous_http_status_is_unknown(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/secdef/search"):
            return httpx.Response(
                200,
                json=[
                    {
                        "conid": 4815747,
                        "symbol": "NVDA",
                        "sections": [{"secType": "STK"}],
                    }
                ],
            )
        assert request.url.path.endswith("/account/U123/orders")
        return httpx.Response(status_code, json={"error": "request outcome uncertain"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://localhost:5000/v1/api",
    ) as client:
        adapter = IBKRExecutionAdapter(account_id="U123", client=client)
        result = await adapter.submit(intent("ibkr-ambiguous"))

    assert result.status is OrderStatus.UNKNOWN
    assert result.code == "ibkr_submit_http_unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [408, 429])
async def test_ibkr_confirmation_ambiguous_http_status_is_unknown(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/secdef/search"):
            return httpx.Response(
                200,
                json=[
                    {
                        "conid": 4815747,
                        "symbol": "NVDA",
                        "sections": [{"secType": "STK"}],
                    }
                ],
            )
        if request.url.path.endswith("/account/U123/orders"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "reply-1",
                        "message": ["warning"],
                        "messageIds": ["o163"],
                    }
                ],
            )
        assert request.url.path.endswith("/iserver/reply/reply-1")
        return httpx.Response(status_code, json={"error": "confirmation outcome uncertain"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://localhost:5000/v1/api",
    ) as client:
        adapter = IBKRExecutionAdapter(
            account_id="U123",
            auto_confirm_message_ids={"o163"},
            client=client,
        )
        result = await adapter.submit(intent("ibkr-confirm-ambiguous"))

    assert result.status is OrderStatus.UNKNOWN
    assert result.code == "ibkr_confirmation_http_unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [408, 429])
async def test_ibkr_cancel_ambiguous_http_status_is_unknown(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        return httpx.Response(status_code, json={"error": "cancel outcome uncertain"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://localhost:5000/v1/api",
    ) as client:
        adapter = IBKRExecutionAdapter(account_id="U123", client=client)
        result = await adapter.cancel("99")

    assert result.status is OrderStatus.UNKNOWN
    assert result.code == "ibkr_cancel_http_unknown"
