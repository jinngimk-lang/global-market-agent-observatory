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


class AlpacaObserver:
    name = "alpaca"

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        base_url: str = "https://paper-api.alpaca.markets",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError("Alpaca API key and secret are required")
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
            "Accept": "application/json",
        }
        self._base_url = base_url.rstrip("/")
        self._client = client

    async def snapshot(self) -> ExternalAccountSnapshot:
        if self._client is not None:
            return await self._snapshot_with_client(self._client)
        async with httpx.AsyncClient(timeout=20) as client:
            return await self._snapshot_with_client(client)

    async def _snapshot_with_client(self, client: httpx.AsyncClient) -> ExternalAccountSnapshot:
        account_response, positions_response, orders_response = await asyncio.gather(
            client.get(self._url("/v2/account"), headers=self._headers),
            client.get(self._url("/v2/positions"), headers=self._headers),
            client.get(
                self._url("/v2/orders"),
                headers=self._headers,
                params={"status": "all", "limit": 100, "direction": "desc"},
            ),
        )
        for response in (account_response, positions_response, orders_response):
            response.raise_for_status()

        account: dict[str, Any] = account_response.json()
        positions = [self._map_position(item) for item in positions_response.json()]
        orders = [self._map_order(item) for item in orders_response.json()]
        mode = "paper-read-only" if "paper" in self._base_url else "live-read-only"
        return ExternalAccountSnapshot(
            provider="alpaca",
            account_id=str(account.get("id") or "unknown"),
            mode=mode,
            status=str(account.get("status") or "unknown").lower(),
            base_currency=str(account.get("currency") or "USD"),
            equity=self._decimal(account.get("equity")),
            cash=self._decimal(account.get("cash")),
            buying_power=self._decimal(account.get("buying_power")),
            positions=positions,
            orders=orders,
        )

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    @classmethod
    def _map_position(cls, item: dict[str, Any]) -> ObservedPosition:
        return ObservedPosition(
            symbol=str(item.get("symbol") or ""),
            quantity=cls._decimal(item.get("qty")) or Decimal("0"),
            average_price=cls._decimal(item.get("avg_entry_price")),
            market_price=cls._decimal(item.get("current_price")),
            unrealized_pnl=cls._decimal(item.get("unrealized_pl")),
        )

    @classmethod
    def _map_order(cls, item: dict[str, Any]) -> ObservedOrder:
        submitted_at = item.get("submitted_at")
        return ObservedOrder(
            order_id=str(item.get("id") or ""),
            symbol=str(item.get("symbol") or ""),
            side=str(item.get("side") or "unknown"),
            quantity=cls._decimal(item.get("qty")) or Decimal("0"),
            filled_quantity=cls._decimal(item.get("filled_qty")) or Decimal("0"),
            status=str(item.get("status") or "unknown"),
            submitted_at=(
                datetime.fromisoformat(str(submitted_at).replace("Z", "+00:00")).astimezone(UTC)
                if submitted_at
                else None
            ),
            filled_price=cls._decimal(item.get("filled_avg_price")),
        )

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value in (None, ""):
            return None
        return Decimal(str(value))
