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
            daily_pnl=self._summary_amount(summary, "dailypnl"),
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


class IBKRExecutionAdapter:
    """Execution boundary for IBKR Client Portal / Trading Web API.

    Client order identifiers are sent as cOID. Precautionary reply messages are
    never auto-confirmed unless every returned messageId is explicitly allowlisted.
    """

    name = "ibkr"

    def __init__(
        self,
        *,
        account_id: str,
        base_url: str = "https://localhost:5000/v1/api",
        verify_ssl: bool = False,
        auto_confirm_message_ids: set[str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not account_id:
            raise ValueError("IBKR account_id is required for execution")
        self._account_id = account_id
        self._base_url = base_url.rstrip("/")
        self._verify_ssl = verify_ssl
        self._auto_confirm_message_ids = set(auto_confirm_message_ids or set())
        self._client = client

    async def get_order_by_client_id(self, client_order_id: str) -> ExecutionResult | None:
        if self._client is not None:
            return await self._lookup(self._client, client_order_id)
        async with httpx.AsyncClient(
            base_url=self._base_url,
            verify=self._verify_ssl,
            timeout=20,
        ) as client:
            return await self._lookup(client, client_order_id)

    async def _lookup(
        self,
        client: httpx.AsyncClient,
        client_order_id: str,
    ) -> ExecutionResult | None:
        try:
            response = await client.get(
                "/iserver/account/orders",
                params={"force": "true", "accountId": self._account_id},
            )
        except httpx.TransportError as exc:
            return ExecutionResult(
                client_order_id=client_order_id,
                status=OrderStatus.UNKNOWN,
                code="ibkr_lookup_unknown",
                message=str(exc),
            )
        if response.status_code >= 500:
            return ExecutionResult(
                client_order_id=client_order_id,
                status=OrderStatus.UNKNOWN,
                code="ibkr_lookup_unknown",
                message=self._response_message(response),
            )
        if response.is_error:
            return ExecutionResult(
                client_order_id=client_order_id,
                status=OrderStatus.REJECTED,
                code=f"ibkr_lookup_http_{response.status_code}",
                message=self._response_message(response),
            )
        payload = response.json() or {}
        orders = payload.get("orders", []) if isinstance(payload, dict) else []
        for item in orders:
            candidate = (
                item.get("order_ref")
                or item.get("local_order_id")
                or item.get("cOID")
                or item.get("client_order_id")
            )
            if str(candidate or "") == client_order_id:
                return self._map_execution_order(
                    item,
                    fallback_client_order_id=client_order_id,
                )

        try:
            trades_response = await client.get(
                "/iserver/account/trades",
                params={"days": 1},
            )
        except httpx.TransportError as exc:
            return ExecutionResult(
                client_order_id=client_order_id,
                status=OrderStatus.UNKNOWN,
                code="ibkr_trade_lookup_unknown",
                message=str(exc),
            )
        if trades_response.status_code >= 500 or trades_response.is_error:
            return ExecutionResult(
                client_order_id=client_order_id,
                status=OrderStatus.UNKNOWN,
                code="ibkr_trade_lookup_unknown",
                message=self._response_message(trades_response),
            )

        trades_payload = trades_response.json() or []
        trades = trades_payload if isinstance(trades_payload, list) else []
        matching_trades = [
            item
            for item in trades
            if str(item.get("order_ref") or "") == client_order_id
            and str(item.get("account") or item.get("accountCode") or self._account_id)
            == self._account_id
        ]
        if not matching_trades:
            return None

        broker_order_ids = {
            str(item.get("order_id"))
            for item in matching_trades
            if item.get("order_id") is not None
        }
        if len(broker_order_ids) != 1:
            return self._trade_reconciliation_unknown(
                client_order_id,
                matching_trades,
                message="IBKR trade history did not identify one broker order id.",
            )
        broker_order_id = next(iter(broker_order_ids))

        try:
            status_response = await client.get(
                f"/iserver/account/order/status/{broker_order_id}"
            )
        except httpx.TransportError as exc:
            return self._trade_reconciliation_unknown(
                client_order_id,
                matching_trades,
                broker_order_id=broker_order_id,
                message=str(exc),
            )
        if status_response.status_code >= 500 or status_response.is_error:
            return self._trade_reconciliation_unknown(
                client_order_id,
                matching_trades,
                broker_order_id=broker_order_id,
                message=self._response_message(status_response),
            )

        status_payload = status_response.json() or {}
        if not isinstance(status_payload, dict):
            return self._trade_reconciliation_unknown(
                client_order_id,
                matching_trades,
                broker_order_id=broker_order_id,
                message="IBKR order-status response was not an object.",
            )
        return self._map_execution_order(
            status_payload,
            fallback_client_order_id=client_order_id,
        )

    @classmethod
    def _trade_reconciliation_unknown(
        cls,
        client_order_id: str,
        trades: list[dict[str, Any]],
        *,
        broker_order_id: str | None = None,
        message: str,
    ) -> ExecutionResult:
        filled_quantity = sum(
            (cls._decimal(item.get("size")) or Decimal("0") for item in trades),
            Decimal("0"),
        )
        total_notional = sum(
            (
                (cls._decimal(item.get("size")) or Decimal("0"))
                * (cls._decimal(item.get("price")) or Decimal("0"))
                for item in trades
            ),
            Decimal("0"),
        )
        filled_price = (
            total_notional / filled_quantity if filled_quantity > Decimal("0") else None
        )
        return ExecutionResult(
            client_order_id=client_order_id,
            broker_order_id=broker_order_id,
            status=OrderStatus.UNKNOWN,
            code="ibkr_trade_reconciliation_unknown",
            message=message,
            filled_quantity=filled_quantity,
            filled_price=filled_price,
            raw_status="trade_seen_status_unknown",
        )

    async def submit(self, intent: OrderIntent) -> ExecutionResult:
        if intent.order_type is OrderType.LIMIT and intent.limit_price is None:
            return ExecutionResult(
                client_order_id=intent.client_order_id,
                status=OrderStatus.REJECTED,
                code="invalid_limit_order",
                message="A limit order requires limit_price.",
            )
        if self._client is not None:
            return await self._submit(self._client, intent)
        async with httpx.AsyncClient(
            base_url=self._base_url,
            verify=self._verify_ssl,
            timeout=20,
        ) as client:
            return await self._submit(client, intent)

    async def _submit(
        self,
        client: httpx.AsyncClient,
        intent: OrderIntent,
    ) -> ExecutionResult:
        conid_result = await self._resolve_stock_conid(client, intent.symbol)
        if isinstance(conid_result, ExecutionResult):
            return conid_result.model_copy(update={"client_order_id": intent.client_order_id})

        order: dict[str, Any] = {
            "acctId": self._account_id,
            "cOID": intent.client_order_id,
            "conid": conid_result,
            "orderType": "LMT" if intent.order_type is OrderType.LIMIT else "MKT",
            "side": intent.side.value.upper(),
            "tif": "DAY",
            "quantity": float(intent.quantity),
        }
        if intent.order_type is OrderType.LIMIT:
            order["price"] = float(intent.limit_price)

        try:
            response = await client.post(
                f"/iserver/account/{self._account_id}/orders",
                json={"orders": [order]},
            )
        except httpx.TransportError as exc:
            return ExecutionResult(
                client_order_id=intent.client_order_id,
                status=OrderStatus.UNKNOWN,
                code="ibkr_submit_unknown",
                message=str(exc),
            )
        if is_ambiguous_mutation_http_status(response.status_code):
            return ExecutionResult(
                client_order_id=intent.client_order_id,
                status=OrderStatus.UNKNOWN,
                code="ibkr_submit_http_unknown",
                message=self._response_message(response),
            )
        if response.status_code >= 500:
            return ExecutionResult(
                client_order_id=intent.client_order_id,
                status=OrderStatus.UNKNOWN,
                code="ibkr_submit_unknown",
                message=self._response_message(response),
            )
        if response.is_error:
            return ExecutionResult(
                client_order_id=intent.client_order_id,
                status=OrderStatus.REJECTED,
                code=f"ibkr_submit_http_{response.status_code}",
                message=self._response_message(response),
            )
        return await self._handle_submission_payload(
            client,
            response.json(),
            intent.client_order_id,
        )

    async def _resolve_stock_conid(
        self,
        client: httpx.AsyncClient,
        symbol: str,
    ) -> int | ExecutionResult:
        try:
            response = await client.post(
                "/iserver/secdef/search",
                json={"symbol": symbol, "secType": "STK", "name": False},
            )
        except httpx.TransportError as exc:
            return ExecutionResult(
                status=OrderStatus.REJECTED,
                code="ibkr_contract_lookup_failed",
                message=str(exc),
            )
        if response.is_error:
            return ExecutionResult(
                status=OrderStatus.REJECTED,
                code="ibkr_contract_lookup_failed",
                message=self._response_message(response),
            )

        payload = response.json() or []
        matches: list[int] = []
        if isinstance(payload, list):
            for item in payload:
                if str(item.get("symbol") or "").upper() != symbol.upper():
                    continue
                sections = item.get("sections") or []
                if sections and not any(
                    str(section.get("secType") or "").upper() == "STK"
                    for section in sections
                    if isinstance(section, dict)
                ):
                    continue
                if item.get("conid") is not None:
                    matches.append(int(item["conid"]))

        unique_matches = set(matches)
        if not unique_matches:
            return ExecutionResult(
                status=OrderStatus.REJECTED,
                code="ibkr_contract_not_found",
                message=f"No IBKR stock contract found for {symbol}.",
            )
        if len(unique_matches) > 1:
            return ExecutionResult(
                status=OrderStatus.REJECTED,
                code="ibkr_contract_ambiguous",
                message=f"Multiple IBKR stock contracts found for {symbol}.",
            )
        return next(iter(unique_matches))

    async def _handle_submission_payload(
        self,
        client: httpx.AsyncClient,
        payload: Any,
        client_order_id: str,
    ) -> ExecutionResult:
        item = self._first_item(payload)
        if item is None:
            return ExecutionResult(
                client_order_id=client_order_id,
                status=OrderStatus.UNKNOWN,
                code="ibkr_unrecognized_response",
                message=str(payload),
            )

        if item.get("id") and item.get("message"):
            message_ids = {str(value) for value in (item.get("messageIds") or [])}
            if not message_ids or not message_ids.issubset(self._auto_confirm_message_ids):
                return ExecutionResult(
                    client_order_id=client_order_id,
                    status=OrderStatus.REJECTED,
                    code="ibkr_confirmation_required",
                    message="; ".join(str(value) for value in (item.get("message") or [])),
                )

            reply_id = str(item["id"])
            try:
                response = await client.post(
                    f"/iserver/reply/{reply_id}",
                    json={"confirmed": True},
                )
            except httpx.TransportError as exc:
                return ExecutionResult(
                    client_order_id=client_order_id,
                    status=OrderStatus.UNKNOWN,
                    code="ibkr_confirmation_unknown",
                    message=str(exc),
                )
            if is_ambiguous_mutation_http_status(response.status_code):
                return ExecutionResult(
                    client_order_id=client_order_id,
                    status=OrderStatus.UNKNOWN,
                    code="ibkr_confirmation_http_unknown",
                    message=self._response_message(response),
                )
            if response.status_code >= 500:
                return ExecutionResult(
                    client_order_id=client_order_id,
                    status=OrderStatus.UNKNOWN,
                    code="ibkr_confirmation_unknown",
                    message=self._response_message(response),
                )
            if response.is_error:
                return ExecutionResult(
                    client_order_id=client_order_id,
                    status=OrderStatus.REJECTED,
                    code=f"ibkr_confirmation_http_{response.status_code}",
                    message=self._response_message(response),
                )
            return await self._handle_submission_payload(
                client,
                response.json(),
                client_order_id,
            )

        return self._map_execution_order(
            item,
            fallback_client_order_id=client_order_id,
        )

    async def cancel(self, broker_order_id: str) -> ExecutionResult:
        if self._client is not None:
            return await self._cancel(self._client, broker_order_id)
        async with httpx.AsyncClient(
            base_url=self._base_url,
            verify=self._verify_ssl,
            timeout=20,
        ) as client:
            return await self._cancel(client, broker_order_id)

    async def _cancel(
        self,
        client: httpx.AsyncClient,
        broker_order_id: str,
    ) -> ExecutionResult:
        try:
            response = await client.delete(
                f"/iserver/account/{self._account_id}/order/{broker_order_id}"
            )
        except httpx.TransportError as exc:
            return ExecutionResult(
                broker_order_id=broker_order_id,
                status=OrderStatus.UNKNOWN,
                code="ibkr_cancel_unknown",
                message=str(exc),
            )
        if is_ambiguous_mutation_http_status(response.status_code):
            return ExecutionResult(
                broker_order_id=broker_order_id,
                status=OrderStatus.UNKNOWN,
                code="ibkr_cancel_http_unknown",
                message=self._response_message(response),
            )
        if response.status_code >= 500:
            return ExecutionResult(
                broker_order_id=broker_order_id,
                status=OrderStatus.UNKNOWN,
                code="ibkr_cancel_unknown",
                message=self._response_message(response),
            )
        if response.is_error:
            return ExecutionResult(
                broker_order_id=broker_order_id,
                status=OrderStatus.REJECTED,
                code=f"ibkr_cancel_http_{response.status_code}",
                message=self._response_message(response),
            )
        payload = response.json() or {}
        return ExecutionResult(
            broker_order_id=str(payload.get("order_id") or broker_order_id),
            status=OrderStatus.ACCEPTED,
            code="cancel_requested",
            message=str(payload.get("msg") or "IBKR accepted cancellation request."),
            raw_status="cancel_requested",
        )

    @classmethod
    def _map_execution_order(
        cls,
        item: dict[str, Any],
        *,
        fallback_client_order_id: str | None = None,
    ) -> ExecutionResult:
        raw_status = str(item.get("order_status") or item.get("status") or "unknown")
        normalized = raw_status.lower().replace(" ", "")
        if normalized == "filled":
            status = OrderStatus.FILLED
        elif normalized in {"cancelled", "canceled"}:
            status = OrderStatus.CANCELLED
        elif normalized in {"rejected", "inactive"}:
            status = OrderStatus.REJECTED
        elif normalized in {
            "submitted",
            "presubmitted",
            "pendingsubmit",
            "apipending",
            "pendingcancel",
        }:
            status = OrderStatus.ACCEPTED
        else:
            status = OrderStatus.UNKNOWN

        client_order_id = (
            item.get("local_order_id")
            or item.get("order_ref")
            or item.get("cOID")
            or fallback_client_order_id
        )
        broker_order_id = item.get("order_id") or item.get("orderId")
        return ExecutionResult(
            client_order_id=(str(client_order_id) if client_order_id is not None else None),
            broker_order_id=(str(broker_order_id) if broker_order_id is not None else None),
            status=status,
            code="broker_result",
            message=f"IBKR order status: {raw_status}",
            filled_quantity=(
                cls._decimal(
                    item.get("filledQuantity")
                    or item.get("filled_quantity")
                    or item.get("cum_fill")
                )
                or Decimal("0")
            ),
            filled_price=cls._decimal(
                item.get("avgPrice")
                or item.get("avg_price")
                or item.get("average_price")
            ),
            raw_status=raw_status,
        )

    @staticmethod
    def _first_item(payload: Any) -> dict[str, Any] | None:
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0]
        return None

    @staticmethod
    def _response_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text
        if isinstance(payload, dict):
            return str(payload.get("error") or payload.get("message") or payload)
        return str(payload)

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value in (None, ""):
            return None
        return Decimal(str(value))
