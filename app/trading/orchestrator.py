from __future__ import annotations

from app.audit.service import AuditService
from app.domain.models import (
    AuditEventType,
    OrderIntent,
    OrderStatus,
    PortfolioSnapshot,
    RiskContext,
    TradingState,
)
from app.execution.controller import ExecutionController
from app.execution.models import ExecutionResult


class TradingOrchestrator:
    def __init__(self, *, execution: ExecutionController, audit: AuditService) -> None:
        self._execution = execution
        self._audit = audit

    @property
    def trading_state(self) -> TradingState:
        return self._execution.trading_state

    def halt(self, reason: str) -> None:
        self._execution.set_trading_state(TradingState.HALTED)
        self._audit.record(
            AuditEventType.KILL_SWITCH,
            subject="runtime",
            payload={"state": TradingState.HALTED.value, "reason": reason},
        )

    def reduce_only(self, reason: str) -> None:
        self._execution.set_trading_state(TradingState.REDUCING)
        self._audit.record(
            AuditEventType.SYSTEM,
            subject="runtime",
            payload={"state": TradingState.REDUCING.value, "reason": reason},
        )

    def activate(self, reason: str = "operator activation") -> None:
        self._execution.set_trading_state(TradingState.ACTIVE)
        self._audit.record(
            AuditEventType.SYSTEM,
            subject="runtime",
            payload={"state": TradingState.ACTIVE.value, "reason": reason},
        )

    async def execute_intent(
        self,
        intent: OrderIntent,
        portfolio: PortfolioSnapshot,
        context: RiskContext | None = None,
    ) -> ExecutionResult:
        previous_state = self.trading_state
        attempt = await self._execution.submit_with_decision(intent, portfolio, context)

        if attempt.risk_decision is not None:
            decision = attempt.risk_decision
            self._audit.record(
                AuditEventType.RISK_DECISION,
                subject=intent.symbol,
                payload={
                    "client_order_id": intent.client_order_id,
                    "allowed": decision.allowed,
                    "code": decision.code,
                    "message": decision.message,
                    "order_notional": str(decision.order_notional),
                    "projected_gross_exposure": str(decision.projected_gross_exposure),
                },
            )

        result = attempt.result
        self._audit.record(
            AuditEventType.EXECUTION,
            subject=intent.symbol,
            payload={
                "client_order_id": result.client_order_id,
                "broker_order_id": result.broker_order_id,
                "status": result.status.value,
                "code": result.code,
                "message": result.message,
                "reused_existing": attempt.reused_existing,
            },
        )

        if (
            result.status is OrderStatus.UNKNOWN
            and previous_state is not TradingState.HALTED
            and self.trading_state is TradingState.HALTED
        ):
            self._audit.record(
                AuditEventType.KILL_SWITCH,
                subject="runtime",
                payload={
                    "state": TradingState.HALTED.value,
                    "reason": "unresolved_execution_state",
                },
            )

        return result
