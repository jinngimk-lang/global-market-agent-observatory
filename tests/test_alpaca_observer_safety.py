from decimal import Decimal

import httpx
import pytest

from app.broker.alpaca import AlpacaObserver


@pytest.mark.asyncio
async def test_alpaca_observer_defaults_to_paper_read_only_mode():
    responses = {
        "/v2/account": {"id": "paper-1", "status": "ACTIVE", "currency": "USD", "equity": "0", "cash": "0"},
        "/v2/positions": [],
        "/v2/orders": [],
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses[request.url.path])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        observer = AlpacaObserver(
            api_key="test-key",
            api_secret="test-secret",
            client=client,
        )
        snapshot = await observer.snapshot()

    assert snapshot.mode == "paper-read-only"
    assert snapshot.provider == "alpaca"
    assert snapshot.equity == Decimal("0")
