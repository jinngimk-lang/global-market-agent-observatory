from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, field_validator

from app.settings import Settings


class OperatorControlRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    reason: str

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("operator control reason must not be empty")
        if len(normalized) > 240:
            raise ValueError("operator control reason must be at most 240 characters")
        return normalized


def build_operator_router(*, settings: Settings, runtime: Any) -> APIRouter:
    router = APIRouter(prefix="/api/operator", tags=["operator"])

    def require_operator(request: Request) -> None:
        configured = settings.operator_api_token
        if configured is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "operator_auth_not_configured",
                    "message": "Operator controls are disabled until OPERATOR_API_TOKEN is configured.",
                },
            )

        authorization = request.headers.get("authorization", "")
        scheme, separator, supplied = authorization.partition(" ")
        expected = configured.get_secret_value()
        valid = (
            bool(separator)
            and scheme.lower() == "bearer"
            and bool(supplied)
            and secrets.compare_digest(supplied, expected)
        )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "operator_auth_failed",
                    "message": "Valid operator bearer authentication is required.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

    def state_payload() -> dict[str, object]:
        return {
            "trading_state": runtime.trading_state.value,
            "promotion_execution_allowed": runtime.promotion_execution_allowed,
            "strategy_health_execution_allowed": runtime.strategy_health_execution_allowed,
            "autonomous_execution_enabled": runtime.autonomous_execution_enabled,
        }

    @router.post("/halt")
    async def halt(request: Request, control: OperatorControlRequest) -> dict[str, object]:
        require_operator(request)
        runtime.orchestrator.halt(f"operator:{control.reason}")
        return state_payload()

    @router.post("/activate")
    async def activate(request: Request, control: OperatorControlRequest) -> dict[str, object]:
        require_operator(request)
        if not runtime.strategy_health_execution_allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "strategy_health_blocked",
                    "message": "Strategy health must recover before operator activation.",
                },
            )
        runtime.orchestrator.activate(f"operator:{control.reason}")
        return state_payload()

    return router
