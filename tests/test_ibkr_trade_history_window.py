from __future__ import annotations

import httpx
import pytest

from app.broker.ibkr_retention import IBKRRetentionAwareExecutionAdapter


@pytest.mark.asyncio
async def test_ibkr_closed_order_lookup_uses_full_supported_trade_history_window() -> None:
    observed_days: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/api/iserver/account/orders":
            return httpx.Response(200, json={"orders": []})
        if request.url.path == "/v1/api/iserver/account/trades":
            observed_days.append(request.url.params.get("days"))
            return httpx.Response(200, json=[])
        raise AssertionError(f"Unexpected path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://localhost:5000/v1/api"
    ) as client:
        adapter = IBKRRetentionAwareExecutionAdapter(account_id="U123", client=client)
        result = await adapter.get_order_by_client_id("nvda-ibkr-1")

    assert result is None
    assert observed_days == ["7"]
