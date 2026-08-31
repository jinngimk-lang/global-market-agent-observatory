from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Protocol

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import Candle
from app.market.alpaca_history import AlpacaHistoricalBarsClient, HistoricalBarsResult
from app.market.levels import SupportResistanceLevels, derive_support_resistance
from app.settings import Settings

HistoricalTimeframe = Literal["1Day", "1Week", "1Month"]


class HistoricalBarsProvider(Protocol):
    async def fetch(
        self,
        symbol: str,
        *,
        timeframe: str,
        limit: int = 240,
    ) -> HistoricalBarsResult: ...


class MarketHistoryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: HistoricalTimeframe
    source: str
    feed: str
    coverage: str
    generated_at: datetime
    candles: list[Candle] = Field(default_factory=list)
    levels: SupportResistanceLevels


def build_market_history_router(*, settings: Settings, runtime: object) -> APIRouter:
    router = APIRouter(prefix="/api/market", tags=["market-history"])

    @router.get("/history/{symbol}", response_model=MarketHistoryResponse)
    async def market_history(
        symbol: str,
        timeframe: HistoricalTimeframe,
        limit: int = Query(default=240, ge=5, le=10_000),
    ) -> MarketHistoryResponse:
        normalized = symbol.strip().upper()
        permitted = settings.trading_universe & settings.allowed_symbols
        if normalized not in permitted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="symbol is not in the configured equity trading universe",
            )

        injected = hasattr(runtime, "historical_bars")
        provider = getattr(runtime, "historical_bars", None)
        owned_provider: AlpacaHistoricalBarsClient | None = None
        if provider is None and not injected:
            if settings.alpaca_api_key is None or settings.alpaca_api_secret is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="verified historical market-data provider is unavailable",
                )
            owned_provider = AlpacaHistoricalBarsClient(
                api_key=settings.alpaca_api_key.get_secret_value(),
                api_secret=settings.alpaca_api_secret.get_secret_value(),
                feed=settings.alpaca_market_data_feed,
            )
            provider = owned_provider
        elif provider is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="verified historical market-data provider is unavailable",
            )

        try:
            result = await provider.fetch(
                normalized,
                timeframe=timeframe,
                limit=limit,
            )
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="verified historical market-data request failed",
            ) from exc
        finally:
            if owned_provider is not None:
                await owned_provider.close()

        levels = derive_support_resistance(
            result.candles,
            pivot_width=2,
            lookback=min(limit, 120),
        )
        source = (
            result.candles[-1].source
            if result.candles
            else f"alpaca:{result.feed}:historical"
        )
        generated_at = datetime.now(UTC)
        return MarketHistoryResponse(
            symbol=result.symbol,
            timeframe=timeframe,
            source=source,
            feed=result.feed,
            coverage=result.coverage,
            generated_at=generated_at,
            candles=result.candles,
            levels=levels,
        )

    return router
