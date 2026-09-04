from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from app.api.market_history import build_market_history_router
from app.api.operator import build_operator_router
from app.api.state import ApplicationState
from app.broker.base import AccountObserver
from app.domain.models import (
    ExecutionProvider,
    OrderIntent,
    OrderRecord,
    PortfolioSnapshot,
    Side,
    TradingMode,
)
from app.market.coverage import MarketCoverageSnapshot, build_market_coverage
from app.research.github_releases import GitHubReleaseCollector
from app.research.partnerships import assess_partnership
from app.research.sec import SECCollector
from app.settings import Settings


class OrderRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_order_id: str
    symbol: str
    side: Side
    quantity: Decimal


class HealthResponse(BaseModel):
    status: str
    trading_mode: str
    execution_provider: str
    auto_trading_enabled: bool
    promotion_execution_allowed: bool
    autonomous_execution_enabled: bool
    strategy_promotion_blocked: int
    strategy_learning_enabled: bool
    strategy_health_execution_allowed: bool
    strategy_degraded: int
    continuous_improvement_error: str | None
    live_execution_permitted: bool
    trading_state: str
    market_source: str
    market_symbol: str
    trading_universe: list[str]
    subscribers: int
    cycle_error_count: int


def create_app(
    settings: Settings | None = None,
    *,
    observers: list[AccountObserver] | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    runtime = ApplicationState(resolved_settings, observers=observers)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(title=resolved_settings.app_name, version="0.2.0", lifespan=lifespan)
    app.state.runtime = runtime
    app.include_router(
        build_operator_router(settings=resolved_settings, runtime=runtime)
    )
    app.include_router(
        build_market_history_router(settings=resolved_settings, runtime=runtime)
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        response.headers["Content-Security-Policy"] = "; ".join(
            [
                "default-src 'self'",
                "script-src 'self' https://unpkg.com",
                "style-src 'self'",
                "connect-src 'self' ws: wss:",
                "img-src 'self' data:",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "frame-ancestors 'none'",
            ]
        )
        return response

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        blocked = sum(1 for item in runtime.strategy_promotion_reports if not item.allowed)
        degraded = sum(1 for item in runtime.strategy_health_reports if item.degraded)
        return HealthResponse(
            status="ok" if runtime.trading_state.value != "halted" else "halted",
            trading_mode=resolved_settings.trading_mode.value,
            execution_provider=resolved_settings.execution_provider.value,
            auto_trading_enabled=resolved_settings.auto_trading_enabled,
            promotion_execution_allowed=runtime.promotion_execution_allowed,
            autonomous_execution_enabled=runtime.autonomous_execution_enabled,
            strategy_promotion_blocked=blocked,
            strategy_learning_enabled=resolved_settings.strategy_learning_enabled,
            strategy_health_execution_allowed=(
                runtime.strategy_health_execution_allowed
            ),
            strategy_degraded=degraded,
            continuous_improvement_error=runtime.last_improvement_error,
            live_execution_permitted=resolved_settings.live_execution_permitted,
            trading_state=runtime.trading_state.value,
            market_source=resolved_settings.market_source,
            market_symbol=resolved_settings.market_symbol,
            trading_universe=sorted(resolved_settings.trading_universe),
            subscribers=runtime.hub.subscriber_count,
            cycle_error_count=len(runtime.last_cycle_errors),
        )

    def task_running(task) -> bool:
        return task is not None and not task.done()

    @app.get("/api/trading/status")
    async def trading_status() -> dict:
        return {
            "trading_mode": resolved_settings.trading_mode.value,
            "execution_provider": resolved_settings.execution_provider.value,
            "auto_trading_enabled": resolved_settings.auto_trading_enabled,
            "promotion_execution_allowed": runtime.promotion_execution_allowed,
            "autonomous_execution_enabled": runtime.autonomous_execution_enabled,
            "strategy_promotion": [
                item.model_dump(mode="json")
                for item in runtime.strategy_promotion_reports
            ],
            "continuous_improvement": {
                "enabled": resolved_settings.strategy_learning_enabled,
                "interval_seconds": (
                    resolved_settings.strategy_improvement_interval_seconds
                ),
                "health_execution_allowed": (
                    runtime.strategy_health_execution_allowed
                ),
                "last_error": runtime.last_improvement_error,
                "strategy_health": [
                    item.model_dump(mode="json")
                    for item in runtime.strategy_health_reports
                ],
            },
            "runtime_loops": {
                "market_feed": {
                    "running": task_running(runtime._feed_task),
                    "failure_count": runtime.market_feed_failure_count,
                    "last_error": runtime.last_market_feed_error,
                    "retry_seconds": resolved_settings.market_feed_retry_seconds,
                    "retry_max_seconds": resolved_settings.market_feed_retry_max_seconds,
                },
                "continuous_improvement": {
                    "enabled": resolved_settings.strategy_learning_enabled,
                    "running": task_running(runtime._improvement_task),
                    "last_error": runtime.last_improvement_error,
                },
                "options_structure": {
                    "enabled": resolved_settings.options_structure_enabled,
                    "configured": runtime.options_structure is not None,
                    "running": task_running(runtime._options_structure_task),
                    "failure_count": runtime.options_structure_loop_failure_count,
                    "last_error": runtime.last_options_structure_loop_error,
                    "symbol_errors": dict(sorted(runtime.options_structure_errors.items())),
                    "refresh_seconds": resolved_settings.options_structure_refresh_seconds,
                    "max_age_seconds": resolved_settings.options_structure_max_age_seconds,
                },
                "account_observers": {
                    "configured": len(runtime.observers),
                    "running": task_running(runtime._account_task),
                    "errors": dict(sorted(runtime.account_errors.items())),
                },
            },
            "live_execution_permitted": resolved_settings.live_execution_permitted,
            "trading_state": runtime.trading_state.value,
            "market_source": resolved_settings.market_source,
            "trading_universe": sorted(resolved_settings.trading_universe),
            "last_cycles": {
                symbol: cycle.model_dump(mode="json")
                for symbol, cycle in sorted(runtime.last_cycle_results.items())
            },
            "cycle_errors": dict(sorted(runtime.last_cycle_errors.items())),
        }

    @app.get("/api/market/structure")
    async def market_structure_status() -> dict:
        generated_at = datetime.now(UTC)
        latest = runtime.autonomous.latest_structure_results
        symbols = sorted(set(resolved_settings.trading_universe) | set(latest))
        payload: dict[str, dict] = {}

        for symbol in symbols:
            cycle = latest.get(symbol)
            if (
                cycle is None
                or cycle.structure is None
                or cycle.observed_at is None
            ):
                payload[symbol] = {
                    "status": "missing",
                    "symbol": symbol,
                    "market_source": None,
                    "latest_price": None,
                    "observed_at": None,
                    "market_age_seconds": None,
                    "market_data_stale": True,
                    "options_age_seconds": None,
                    "options_structure_stale": True,
                    "availability": {
                        "vwap": False,
                        "order_flow_imbalance": False,
                        "options_structure": False,
                    },
                    "structure": None,
                    "provenance": {},
                }
                continue

            observed_at = cycle.observed_at
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=UTC)
            observed_at = observed_at.astimezone(UTC)
            market_age = max((generated_at - observed_at).total_seconds(), 0.0)
            structure = cycle.structure
            options_available = any(
                value is not None
                for value in (
                    structure.net_gex_1pct,
                    structure.gamma_flip,
                    structure.call_wall,
                    structure.put_wall,
                )
            )
            provenance = dict(structure.methodology)
            provenance["market_source"] = cycle.market_source or "unknown"

            options_age: float | None = None
            options_stale = not options_available
            options_fetched_at = provenance.get("options_fetched_at")
            if options_available and options_fetched_at:
                try:
                    parsed = datetime.fromisoformat(
                        options_fetched_at.replace("Z", "+00:00")
                    )
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=UTC)
                    options_age = max(
                        (generated_at - parsed.astimezone(UTC)).total_seconds(),
                        0.0,
                    )
                    options_stale = (
                        options_age > resolved_settings.options_structure_max_age_seconds
                    )
                except ValueError:
                    options_stale = True

            payload[symbol] = {
                "status": "observed",
                "symbol": symbol,
                "market_source": cycle.market_source,
                "latest_price": cycle.reference_price,
                "observed_at": observed_at.isoformat(),
                "market_age_seconds": market_age,
                "market_data_stale": (
                    market_age > resolved_settings.market_data_max_age_seconds
                ),
                "options_age_seconds": options_age,
                "options_structure_stale": options_stale,
                "availability": {
                    "vwap": structure.vwap is not None,
                    "order_flow_imbalance": (
                        structure.order_flow_imbalance is not None
                    ),
                    "options_structure": options_available,
                },
                "structure": structure.model_dump(mode="json"),
                "provenance": provenance,
            }

        return {
            "generated_at": generated_at.isoformat(),
            "symbols": payload,
        }

    @app.get("/api/market/coverage", response_model=MarketCoverageSnapshot)
    async def market_coverage() -> MarketCoverageSnapshot:
        return build_market_coverage(
            store=runtime.store,
            symbols=resolved_settings.trading_universe,
            interval=resolved_settings.market_interval,
            market_source=resolved_settings.market_source,
            max_age_seconds=resolved_settings.market_data_max_age_seconds,
            last_cycle_results=runtime.last_cycle_results,
            last_cycle_errors=runtime.last_cycle_errors,
        )

    @app.get("/api/candles/{symbol}")
    async def candles(
        symbol: str,
        interval: str = Query(default="1m"),
        limit: int = Query(default=500, ge=1, le=5000),
    ) -> list[dict]:
        return [
            item.model_dump(mode="json")
            for item in runtime.store.list_candles(symbol, interval=interval, limit=limit)
        ]

    @app.post("/api/orders", response_model=OrderRecord, status_code=status.HTTP_201_CREATED)
    async def submit_order(request: OrderRequest) -> OrderRecord:
        if (
            resolved_settings.execution_provider is not ExecutionProvider.PAPER
            or resolved_settings.trading_mode
            not in {TradingMode.REPLAY, TradingMode.PAPER}
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "legacy_order_api_disabled",
                    "message": (
                        "The unauthenticated legacy order endpoint is restricted to "
                        "local paper execution and can never route to a live broker."
                    ),
                },
            )

        symbol = request.symbol.strip().upper()
        latest = runtime.store.latest_candle(
            symbol,
            interval=resolved_settings.market_interval,
        )
        if latest is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "market_price_unavailable",
                    "message": "No market price is available.",
                },
            )
        reference_price = Decimal(str(latest.close))
        intent = OrderIntent(
            client_order_id=request.client_order_id,
            symbol=symbol,
            side=request.side,
            quantity=request.quantity,
            reference_price=reference_price,
        )
        decision = runtime.risk.evaluate(intent, runtime.broker.snapshot())
        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=decision.model_dump(mode="json"),
            )
        return runtime.broker.submit(intent, reference_price)

    @app.get("/api/portfolio", response_model=PortfolioSnapshot)
    async def portfolio() -> PortfolioSnapshot:
        try:
            state = await runtime.portfolio_source.snapshot()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "portfolio_reconciliation_unavailable",
                    "message": f"{type(exc).__name__}: {exc}",
                },
            ) from exc
        return state.portfolio

    @app.get("/api/orders")
    async def orders(limit: int = Query(default=200, ge=1, le=1000)) -> list[dict]:
        return [
            item.model_dump(mode="json")
            for item in runtime.store.list_orders(limit=limit)
        ]

    @app.get("/api/audit")
    async def audit(limit: int = Query(default=200, ge=1, le=2000)) -> list[dict]:
        return [
            item.model_dump(mode="json")
            for item in runtime.audit.list_events(limit=limit)
        ]

    @app.get("/api/accounts")
    async def accounts() -> dict:
        return {
            "execution_provider": resolved_settings.execution_provider.value,
            "live_execution_permitted": resolved_settings.live_execution_permitted,
            "accounts": [
                {
                    "name": name,
                    "status": (
                        "error"
                        if name in runtime.account_errors
                        else (
                            "connected"
                            if name in runtime.account_snapshots
                            else "connecting"
                        )
                    ),
                    "error": runtime.account_errors.get(name),
                    "snapshot": (
                        runtime.account_snapshots[name].model_dump(mode="json")
                        if name in runtime.account_snapshots
                        else None
                    ),
                }
                for name in sorted(runtime.observers)
            ],
        }

    @app.get("/api/evidence")
    async def evidence(limit: int = Query(default=200, ge=1, le=2000)) -> list[dict]:
        return [
            item.model_dump(mode="json")
            for item in runtime.store.list_evidence(limit=limit)
        ]

    @app.get("/api/research/crisis-winners")
    async def crisis_winners(
        limit: int = Query(default=200, ge=1, le=2000),
    ) -> list[dict]:
        return [
            item.model_dump(mode="json")
            for item in runtime.store.list_crisis_winners(limit=limit)
        ]

    @app.get("/api/research/partnerships")
    async def partnerships(
        limit: int = Query(default=200, ge=1, le=2000),
    ) -> list[dict]:
        source_items = [
            item
            for item in runtime.store.list_evidence(limit=limit)
            if "partnership" in item.tags or "material-agreement" in item.tags
        ]
        return [
            assess_partnership(item).model_dump(mode="json")
            for item in source_items
        ]

    @app.post("/api/research/refresh")
    async def refresh_research() -> dict[str, int]:
        collected = await GitHubReleaseCollector().collect(
            resolved_settings.github_release_repositories
        )
        if resolved_settings.sec_ciks:
            sec_collector = SECCollector(user_agent=resolved_settings.sec_user_agent)
            for cik in resolved_settings.sec_ciks:
                collected.extend(await sec_collector.collect_company(cik, years=3))
        for item in collected:
            runtime.store.add_evidence(item)
        return {"collected": len(collected), "stored": len(collected)}

    @app.websocket("/ws/market")
    async def market_websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            async with runtime.hub.subscribe() as queue:
                while True:
                    candle = await queue.get()
                    await websocket.send_json(
                        {"type": "candle", "data": candle.model_dump(mode="json")}
                    )
        except WebSocketDisconnect:
            return

    web_root = Path(__file__).resolve().parents[1] / "web"
    app.mount("/static", StaticFiles(directory=web_root), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        index_path = web_root / "index.html"
        if not index_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Dashboard assets are not installed",
            )
        return FileResponse(index_path)

    return app


app = create_app()