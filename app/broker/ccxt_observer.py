from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.models import (
    ExternalAccountSnapshot,
    ObservedBalance,
    ObservedOrder,
    ObservedPosition,
)


class CCXTObserver:
    name = "ccxt"

    def __init__(self, *, exchange: Any, mode: str = "read-only") -> None:
        self._exchange = exchange
        self._mode = mode
        self.name = f"ccxt:{getattr(exchange, 'id', 'unknown')}"

    async def snapshot(self) -> ExternalAccountSnapshot:
        balance, positions, orders = await asyncio.gather(
            asyncio.to_thread(self._exchange.fetch_balance),
            asyncio.to_thread(self._fetch_positions),
            asyncio.to_thread(self._fetch_orders),
        )
        exchange_id = str(getattr(self._exchange, "id", "unknown"))
        return ExternalAccountSnapshot(
            provider=f"ccxt:{exchange_id}",
            account_id=exchange_id,
            mode=self._mode,
            balances=self._map_balances(balance),
            positions=[self._map_position(item) for item in positions],
            orders=[self._map_order(item) for item in orders],
        )

    def _fetch_positions(self) -> list[dict[str, Any]]:
        method = getattr(self._exchange, "fetch_positions", None)
        if method is None:
            return []
        try:
            return method() or []
        except Exception:
            return []

    def _fetch_orders(self) -> list[dict[str, Any]]:
        method = getattr(self._exchange, "fetch_open_orders", None)
        if method is None:
            return []
        return method() or []

    @classmethod
    def _map_balances(cls, payload: dict[str, Any]) -> list[ObservedBalance]:
        totals = payload.get("total") or {}
        free = payload.get("free") or {}
        balances = []
        for asset, total in totals.items():
            total_value = cls._decimal(total)
            if total_value is None or total_value == 0:
                continue
            balances.append(
                ObservedBalance(
                    asset=str(asset),
                    total=total_value,
                    available=cls._decimal(free.get(asset)),
                )
            )
        return sorted(balances, key=lambda item: item.asset)

    @classmethod
    def _map_position(cls, item: dict[str, Any]) -> ObservedPosition:
        quantity = item.get("contracts", item.get("amount", item.get("positionAmt", 0)))
        return ObservedPosition(
            symbol=str(item.get("symbol") or ""),
            quantity=cls._decimal(quantity) or Decimal("0"),
            average_price=cls._decimal(item.get("entryPrice", item.get("average"))),
            market_price=cls._decimal(item.get("markPrice", item.get("last"))),
            unrealized_pnl=cls._decimal(item.get("unrealizedPnl")),
        )

    @classmethod
    def _map_order(cls, item: dict[str, Any]) -> ObservedOrder:
        timestamp = item.get("timestamp")
        submitted_at = (
            datetime.fromtimestamp(float(timestamp) / 1000, tz=UTC) if timestamp else None
        )
        return ObservedOrder(
            order_id=str(item.get("id") or ""),
            symbol=str(item.get("symbol") or ""),
            side=str(item.get("side") or "unknown"),
            quantity=cls._decimal(item.get("amount")) or Decimal("0"),
            filled_quantity=cls._decimal(item.get("filled")) or Decimal("0"),
            status=str(item.get("status") or "unknown"),
            submitted_at=submitted_at,
            filled_price=cls._decimal(item.get("average")),
        )

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value in (None, ""):
            return None
        return Decimal(str(value))
