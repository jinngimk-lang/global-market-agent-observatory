from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.broker.http_outcomes import is_ambiguous_mutation_http_status
from app.domain.models import (
    ExternalAccountSnapshot,
    ObservedOrder,
    ObservedPosition,
    OrderIntent,
    OrderStatus,
    OrderType,
)
from app.execution.models import ExecutionResult


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
        async with httpx.AsyncClient(base_url=self._base_url, timeout=20) as client:
            return await self._snapshot_with_client(client)

    async def _snapshot_with_client(self, client: httpx.AsyncClient) -> ExternalAccountSnapshot:
        account_response, positions_response, orders_response = await asyncio.gather(
            client.get("/v2/account", headers=self._headers),
            client.get("/v2/positions", headers=self._headers),
            client.get(
                "/v2/orders",
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
        equity = self._decimal(account.get("equity"))
        prior_equity = self._decimal(account.get("last_equity"))
        daily_pnl = (
            equity - prior_equity
            if equity is not None and prior_equity is not None
            else None
        )
        return ExternalAccountSnapshot(
            provider="alpaca",
            account_id=str(account.get("id") or "unknown"),
            mode=mode,
            status=str(account.get("status") or "unknown").lower(),
            base_currency=str(account.get("currency") or "USD"),
            equity=equity,
            prior_equity=prior_equity,
            daily_pnl=daily_pnl,
            cash=self._decimal(account.get("cash")),
            buying_power=self._decimal(account.get("buying_power")),
            trading_blocked=account.get("trading_blocked"),
            account_blocked=account.get("account_blocked"),
            trade_suspended_by_user=account.get("trade_suspended_by_user"),
            positions=positions,
            orders=orders,
        )

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


class AlpacaExecutionAdapter:
    """Broker execution boundary for Alpaca paper or live trading endpoints.

    The adapter deliberately does not decide whether live trading is permitted.
    Runtime mode and the explicit live gate are enforced before this adapter is
    selected by the execution factory.
    """

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
            "Content-Type": "application/json",
        }
        self._base_url = base_url.rstrip("/")
        self._client = client

    async def get_order_by_client_id(self, client_order_id: str) -> ExecutionResult | None:
        if self._client is not None:
            return await self._get_order_by_client_id(self._client, client_order_id)
        async with httpx.AsyncClient(base_url=self._base_url, timeout=20) as client:
            return await self._get_order_by_client_id(client, client_order_id)

    async def _get_order_by_client_id(
        self,
        client: httpx.AsyncClient,
        client_order_id: str,
    ) -> ExecutionResult | None:
        try:
            response = await client.get(
                "/v2/orders:by_client_order_id",
                headers=self._headers,
                params={"client_order_id": client_order_id},
            )
        except httpx.TransportError as exc:
            return ExecutionResult(
                client_order_id=client_order_id,
                status=OrderStatus.UNKNOWN,
                code="alpaca_lookup_unknown",
                message=str(exc),
            )
        if response.status_code == 404:
            return None
        if response.status_code >= 500:
            return ExecutionResult(
                client_order_id=client_order_id,
                status=OrderStatus.UNKNOWN,
                code="alpaca_lookup_unknown",
                message=self._response_message(response),
            )
        if response.is_error:
            return ExecutionResult(
                client_order_id=client_order_id,
                status=OrderStatus.REJECTED,
                code=f"alpaca_lookup_http_{response.status_code}",
                message=self._response_message(response),
            )
        payload = response.json()
        returned_client_order_id = str(payload.get("client_order_id") or "")
        if returned_client_order_id != client_order_id:
            return ExecutionResult(
                client_order_id=client_order_id,
                status=OrderStatus.UNKNOWN,
                code="alpaca_lookup_identity_mismatch",
                message=(
                    "Alpaca lookup response client_order_id did not match the queried order."
                ),
            )
        return self._map_execution_result(payload)

    async def submit(self, intent: OrderIntent) -> ExecutionResult:
        if intent.order_type is OrderType.LIMIT and intent.limit_price is None:
            return ExecutionResult(
                client_order_id=intent.client_order_id,
                status=OrderStatus.REJECTED,
                code="invalid_limit_order",
                message="A limit order requires limit_price.",
            )

        payload: dict[str, str] = {
            "symbol": intent.symbol,
            "qty": str(intent.quantity),
            "side": intent.side.value,
            "type": intent.order_type.value,
            "time_in_force": "day",
            "client_order_id": intent.client_order_id,
        }
        if intent.order_type is OrderType.LIMIT:
            payload["limit_price"] = str(intent.limit_price)

        if self._client is not None:
            return await self._submit(self._client, intent, payload)
        async with httpx.AsyncClient(base_url=self._base_url, timeout=20) as client:
            return await self._submit(client, intent, payload)

    async def _submit(
        self,
        client: httpx.AsyncClient,
        intent: OrderIntent,
        payload: dict[str, str],
    ) -> ExecutionResult:
        try:
            response = await client.post("/v2/orders", headers=self._headers, json=payload)
        except httpx.TransportError as exc:
            return ExecutionResult(
                client_order_id=intent.client_order_id,
                status=OrderStatus.UNKNOWN,
                code="alpaca_transport_unknown",
                message=str(exc),
            )
        if is_ambiguous_mutation_http_status(response.status_code):
            return ExecutionResult(
                client_order_id=intent.client_order_id,
                status=OrderStatus.UNKNOWN,
                code="alpaca_submit_http_unknown",
                message=self._response_message(response),
            )
        if response.status_code >= 500:
            return ExecutionResult(
                client_order_id=intent.client_order_id,
                status=OrderStatus.UNKNOWN,
                code="alpaca_server_unknown",
                message=self._response_message(response),
            )
        if response.is_error:
            return ExecutionResult(
                client_order_id=intent.client_order_id,
                status=OrderStatus.REJECTED,
                code=f"alpaca_http_{response.status_code}",
                message=self._response_message(response),
            )
        return self._map_execution_result(response.json())

    async def cancel(self, broker_order_id: str) -> ExecutionResult:
        if self._client is not None:
            return await self._cancel(self._client, broker_order_id)
        async with httpx.AsyncClient(base_url=self._base_url, timeout=20) as client:
            return await self._cancel(client, broker_order_id)

    async def _cancel(
        self,
        client: httpx.AsyncClient,
        broker_order_id: str,
    ) -> ExecutionResult:
        try:
            response = await client.delete(
                f"/v2/orders/{broker_order_id}",
                headers=self._headers,
            )
        except httpx.TransportError as exc:
            return ExecutionResult(
                broker_order_id=broker_order_id,
                status=OrderStatus.UNKNOWN,
                code="alpaca_cancel_unknown",
                message=str(exc),
            )
        if response.status_code == 204:
            return ExecutionResult(
                broker_order_id=broker_order_id,
                status=OrderStatus.CANCELLED,
                code="cancel_accepted",
                message="Alpaca accepted the cancellation request.",
            )
        if is_ambiguous_mutation_http_status(response.status_code):
            return ExecutionResult(
                broker_order_id=broker_order_id,
                status=OrderStatus.UNKNOWN,
                code="alpaca_cancel_http_unknown",
                message=self._response_message(response),
            )
        if response.status_code >= 500:
            return ExecutionResult(
                broker_order_id=broker_order_id,
                status=OrderStatus.UNKNOWN,
                code="alpaca_cancel_unknown",
                message=self._response_message(response),
            )
        return ExecutionResult(
            broker_order_id=broker_order_id,
            status=OrderStatus.REJECTED,
            code=f"alpaca_cancel_http_{response.status_code}",
            message=self._response_message(response),
        )

    @classmethod
    def _map_execution_result(cls, item: dict[str, Any]) -> ExecutionResult:
        raw_status = str(item.get("status") or "unknown").lower()
        if raw_status == "filled":
            status = OrderStatus.FILLED
        elif raw_status in {"canceled", "cancelled", "expired", "replaced", "done_for_day"}:
            status = OrderStatus.CANCELLED
        elif raw_status in {"rejected", "suspended"}:
            status = OrderStatus.REJECTED
        elif raw_status in {
            "new",
            "accepted",
            "pending_new",
            "partially_filled",
            "accepted_for_bidding",
            "pending_replace",
            "pending_cancel",
            "held",
            "stopped",
            "calculated",
        }:
            status = OrderStatus.ACCEPTED
        else:
            status = OrderStatus.UNKNOWN
        return ExecutionResult(
            client_order_id=str(item.get("client_order_id") or "") or None,
            broker_order_id=str(item.get("id") or "") or None,
            status=status,
            code="broker_result",
            message=f"Alpaca order status: {raw_status}",
            filled_quantity=cls._decimal(item.get("filled_qty")) or Decimal("0"),
            filled_price=cls._decimal(item.get("filled_avg_price")),
            raw_status=raw_status,
        )

    @staticmethod
    def _response_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text
        if isinstance(payload, dict):
            return str(payload.get("message") or payload.get("error") or payload)
        return str(payload)

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value in (None, ""):
            return None
        return Decimal(str(value))
