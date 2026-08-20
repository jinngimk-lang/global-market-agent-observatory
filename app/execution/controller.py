from __future__ import annotations

from app.broker.base import ExecutionAdapter
from app.domain.models import OrderIntent, OrderStatus, PortfolioSnapshot, RiskContext, TradingState
from app.execution.models import ExecutionAttempt, ExecutionResult
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

    async def submit(
        self,
        intent: OrderIntent,
        portfolio: PortfolioSnapshot,
        context: RiskContext | None = None,
    ) -> ExecutionResult:
        attempt = await self.submit_with_decision(intent, portfolio, context)
        return attempt.result

    async def submit_with_decision(
        self,
        intent: OrderIntent,
        portfolio: PortfolioSnapshot,
        context: RiskContext | None = None,
    ) -> ExecutionAttempt:
        existing = await self._adapter.get_order_by_client_id(intent.client_order_id)
        if existing is not None:
            return ExecutionAttempt(result=existing, reused_existing=True)

        effective_context = (context or RiskContext()).model_copy(
            update={"trading_state": self._trading_state}
        )
        decision = self._risk_engine.evaluate(intent, portfolio, effective_context)
        if not decision.allowed:
            return ExecutionAttempt(
                result=ExecutionResult(
                    client_order_id=intent.client_order_id,
                    status=OrderStatus.REJECTED,
                    code=decision.code,
                    message=decision.message,
                ),
                risk_decision=decision,
            )

        result = await self._adapter.submit(intent)
        if result.status is OrderStatus.UNKNOWN:
            reconciled = await self._adapter.get_order_by_client_id(intent.client_order_id)
            if reconciled is not None:
                result = reconciled
            else:
                self._trading_state = TradingState.HALTED

        return ExecutionAttempt(result=result, risk_decision=decision)
