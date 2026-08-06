from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from app.api.state import ApplicationState
from app.broker.base import AccountObserver
from app.domain.models import OrderIntent, OrderRecord, PortfolioSnapshot, Side
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
    live_trading_enabled: bool
    market_source: str
    market_symbol: str
    subscribers: int


def create_app(
    settings: Settings | None = None, *, observers: list[AccountObserver] | None = None
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

    app = FastAPI(title=resolved_settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.runtime = runtime

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
        return HealthResponse(
            status="ok",
            trading_mode="paper",
            live_trading_enabled=resolved_settings.live_trading_enabled,
            market_source=resolved_settings.market_source,
            market_symbol=resolved_settings.market_symbol,
            subscribers=runtime.hub.subscriber_count,
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
        symbol = request.symbol.strip().upper()
        latest = runtime.store.latest_candle(symbol, interval=resolved_settings.market_interval)
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
        return runtime.broker.snapshot()

    @app.get("/api/orders")
    async def orders(limit: int = Query(default=200, ge=1, le=1000)) -> list[dict]:
        return [item.model_dump(mode="json") for item in runtime.store.list_orders(limit=limit)]

    @app.get("/api/accounts")
    async def accounts() -> dict:
        return {
            "live_execution_enabled": False,
            "accounts": [
                {
                    "name": name,
                    "status": "error" if name in runtime.account_errors else (
                        "connected" if name in runtime.account_snapshots else "connecting"
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
        return [item.model_dump(mode="json") for item in runtime.store.list_evidence(limit=limit)]

    @app.get("/api/research/crisis-winners")
    async def crisis_winners(limit: int = Query(default=200, ge=1, le=2000)) -> list[dict]:
        return [
            item.model_dump(mode="json")
            for item in runtime.store.list_crisis_winners(limit=limit)
        ]

    @app.get("/api/research/partnerships")
    async def partnerships(limit: int = Query(default=200, ge=1, le=2000)) -> list[dict]:
        source_items = [
            item
            for item in runtime.store.list_evidence(limit=limit)
            if "partnership" in item.tags or "material-agreement" in item.tags
        ]
        return [assess_partnership(item).model_dump(mode="json") for item in source_items]

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
            raise HTTPException(status_code=404, detail="Dashboard assets are not installed")
        return FileResponse(index_path)

    return app


app = create_app()
