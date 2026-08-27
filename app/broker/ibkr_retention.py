from __future__ import annotations

from typing import Any

import httpx

from app.broker.ibkr import IBKRExecutionAdapter
from app.execution.models import ExecutionResult


class _TradeHistoryWindowClient:
    """Narrow proxy that asks IBKR for its full supported trade-history window."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        if url == "/iserver/account/trades":
            params = dict(params or {})
            params["days"] = 7
        return await self._client.get(url, params=params, **kwargs)


class IBKRRetentionAwareExecutionAdapter(IBKRExecutionAdapter):
    """IBKR execution adapter with complete supported closed-order recovery history."""

    async def _lookup(
        self,
        client: httpx.AsyncClient,
        client_order_id: str,
    ) -> ExecutionResult | None:
        return await super()._lookup(
            _TradeHistoryWindowClient(client),  # type: ignore[arg-type]
            client_order_id,
        )
