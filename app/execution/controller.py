from __future__ import annotations

from decimal import Decimal

from app.broker.base import ExecutionAdapter
from app.domain.models import OrderIntent, OrderStatus, PortfolioSnapshot, Side, TradingState
from app.execution.models import ExecutionResult
from app.risk.engine import RiskEngine


class ExecutionController:
    def __init__(
        self,
        *,
        adapter: ExecutionAdapter,
        risk_engine: RiskEngine,
        trading_state: TradingState = TradingState.ACTIVE,
    ) -> None:
        self._adapter = adapter
        self._risk_engine = risk_engine
        self._trading_state = trading_state

    @property
    def trading_state(self) -> TradingState:
        return self._trading_state

    def set_trading_state(self, state: TradingState) -> None:
        self._trading_state = state

    async def submit(self, intent: OrderIntent, portfolio: PortfolioSnapshot) -> ExecutionResult:
        existing = await self._adapter.get_order_by_client_id(intent.client_order_id)
        if existing is not None:
            return existing

        if self._trading_state is TradingState.HALTED:
            return self._reject(intent, "trading_halted", "Trading is halted.")

        if self._trading_state is TradingState.REDUCING and self._increases_exposure(
            intent, portfolio
        ):
            return self._reject(
                intent,
                "reducing_only",
                "Trading state permits exposure reductions only.",
            )

        risk = self._risk_engine.evaluate(intent, portfolio)
        if not risk.allowed:
            return self._reject(intent, risk.code, risk.message)

        return await self._adapter.submit(intent)

    @staticmethod
    def _increases_exposure(intent: OrderIntent, portfolio: PortfolioSnapshot) -> bool:
        current_quantity = Decimal("0")
        for position in portfolio.positions:
            if position.symbol == intent.symbol:
                current_quantity = position.quantity
                break

        signed_quantity = intent.quantity if intent.side is Side.BUY else -intent.quantity
        projected_quantity = current_quantity + signed_quantity
        if current_quantity == 0:
            return projected_quantity != 0
        if projected_quantity == 0:
            return False
        if current_quantity * projected_quantity < 0:
            return True
        return abs(projected_quantity) >= abs(current_quantity)

    @staticmethod
    def _reject(intent: OrderIntent, code: str, message: str) -> ExecutionResult:
        return ExecutionResult(
            client_order_id=intent.client_order_id,
            status=OrderStatus.REJECTED,
            code=code,
            message=message,
        )
