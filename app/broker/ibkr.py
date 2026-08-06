from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.domain.models import (
    ExternalAccountSnapshot,
    ObservedOrder,
    ObservedPosition,
)


class IBKRObserver:
    name = "ibkr"

    def __init__(
        self,
        *,
        account_id: str | None = None,
        base_url: str = "https://localhost:5000/v1/api",
        verify_ssl: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._account_id = account_id
        self._base_url = base_url.rstrip("/")
        self._verify_ssl = verify_ssl
        self._client = client

    async def snapshot(self) -> ExternalAccountSnapshot:
        if self._client is not None:
            return await self._snapshot_with_client(self._client)
        async with httpx.AsyncClient(
            base_url=self._base_url,
            verify=self._verify_ssl,
            timeout=20,
        ) as client:
            return await self._snapshot_with_client(client)

    async def _snapshot_with_client(self, client: httpx.AsyncClient) -> ExternalAccountSnapshot:
        accounts_response = await client.get("/iserver/accounts")
        accounts_response.raise_for_status()
        accounts_payload = accounts_response.json()
        account_id = self._account_id or accounts_payload.get("selectedAccount")
        if not account_id:
            accounts = accounts_payload.get("accounts") or []
            account_id = accounts[0] if accounts else None
        if not account_id:
            raise RuntimeError("IBKR gateway returned no account id")

        summary_response, positions_response, orders_response = await asyncio.gather(
            client.get(f"/portfolio/{account_id}/summary"),
            client.get(f"/portfolio/{account_id}/positions/0"),
            client.get("/iserver/account/orders"),
        )
        for response in (summary_response, positions_response, orders_response):
            response.raise_for_status()

        summary: dict[str, Any] = summary_response.json()
        positions_payload = positions_response.json() or []
        orders_payload = (orders_response.json() or {}).get("orders", [])
        currency = self._summary_currency(summary)
        return ExternalAccountSnapshot(
            provider="ibkr",
            account_id=str(account_id),
            mode="gateway-read-only",
            status="connected",
            base_currency=currency,
            equity=self._summary_amount(summary, "netliquidation"),
            cash=self._summary_amount(summary, "totalcashvalue"),
            buying_power=self._summary_amount(summary, "availablefunds"),
            positions=[self._map_position(item) for item in positions_payload],
            orders=[self._map_order(item) for item in orders_payload],
        )

    @classmethod
    def _map_position(cls, item: dict[str, Any]) -> ObservedPosition:
        return ObservedPosition(
            symbol=str(item.get("ticker") or item.get("contractDesc") or item.get("conid") or ""),
            quantity=cls._decimal(item.get("position")) or Decimal("0"),
            average_price=cls._decimal(item.get("avgPrice")),
            market_price=cls._decimal(item.get("mktPrice")),
            unrealized_pnl=cls._decimal(item.get("unrealizedPnl")),
        )

    @classmethod
    def _map_order(cls, item: dict[str, Any]) -> ObservedOrder:
        timestamp = item.get("lastExecutionTime_r") or item.get("lastExecutionTime")
        submitted_at = None
        if timestamp:
            try:
                numeric = float(timestamp)
                submitted_at = datetime.fromtimestamp(
                    numeric / 1000 if numeric > 10_000_000_000 else numeric,
                    tz=UTC,
                )
            except (TypeError, ValueError, OSError):
                submitted_at = None
        return ObservedOrder(
            order_id=str(item.get("orderId") or item.get("order_id") or ""),
            symbol=str(item.get("ticker") or item.get("contractDesc") or item.get("conid") or ""),
            side=str(item.get("side") or "unknown").lower(),
            quantity=cls._decimal(item.get("totalSize")) or Decimal("0"),
            filled_quantity=cls._decimal(item.get("filledQuantity")) or Decimal("0"),
            status=str(item.get("status") or "unknown").lower(),
            submitted_at=submitted_at,
            filled_price=cls._decimal(item.get("avgPrice")),
        )

    @classmethod
    def _summary_amount(cls, summary: dict[str, Any], key: str) -> Decimal | None:
        value = summary.get(key)
        if isinstance(value, dict):
            value = value.get("amount")
        return cls._decimal(value)

    @staticmethod
    def _summary_currency(summary: dict[str, Any]) -> str | None:
        for key in ("netliquidation", "totalcashvalue", "availablefunds"):
            value = summary.get(key)
            if isinstance(value, dict) and value.get("currency"):
                return str(value["currency"])
        return None

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value in (None, ""):
            return None
        return Decimal(str(value))
