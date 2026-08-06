from __future__ import annotations

import asyncio
from decimal import Decimal

from app.broker.base import AccountObserver
from app.broker.factory import build_account_observers
from app.broker.paper import PaperBroker
from app.domain.models import ExternalAccountSnapshot, RiskLimits
from app.market.binance import BinanceKlineFeed
from app.market.hub import MarketHub
from app.market.replay import ReplayFeed
from app.risk.engine import RiskEngine
from app.settings import Settings
from app.store.sqlite import SQLiteStore


class ApplicationState:
    def __init__(
        self,
        settings: Settings,
        *,
        observers: list[AccountObserver] | None = None,
    ) -> None:
        self.settings = settings
        self.store = SQLiteStore(settings.database_path, starting_cash=settings.starting_cash)
        self.hub = MarketHub(queue_size=200)
        self.broker = PaperBroker(self.store)
        self.risk = RiskEngine(
            RiskLimits(
                allowed_symbols=settings.allowed_symbols,
                max_order_notional=settings.max_order_notional,
                max_gross_exposure=settings.max_gross_exposure,
                daily_loss_limit=settings.daily_loss_limit,
            )
        )
        if settings.market_source == "binance":
            self.feed = BinanceKlineFeed(
                symbol=settings.market_symbol,
                interval=settings.market_interval,
            )
        elif settings.market_source == "replay":
            self.feed = ReplayFeed(
                symbol=settings.market_symbol,
                interval=settings.market_interval,
                seed=settings.replay_seed,
                delay_seconds=settings.replay_delay_seconds,
            )
        else:
            raise ValueError(f"Unsupported market source: {settings.market_source}")
        selected_observers = (
            observers if observers is not None else build_account_observers(settings)
        )
        self.observers = {observer.name: observer for observer in selected_observers}
        self.account_snapshots: dict[str, ExternalAccountSnapshot] = {}
        self.account_errors: dict[str, str] = {}
        self._feed_task: asyncio.Task[None] | None = None
        self._account_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._feed_task is None:
            self._feed_task = asyncio.create_task(self._run_feed(), name="market-feed")
        if self.observers and self._account_task is None:
            self._account_task = asyncio.create_task(
                self._run_account_observers(), name="account-observers"
            )

    async def stop(self) -> None:
        tasks = [task for task in (self._feed_task, self._account_task) if task is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._feed_task = None
        self._account_task = None

    async def _run_feed(self) -> None:
        async for candle in self.feed.stream():
            self.store.upsert_candle(candle)
            self.store.mark_position(candle.symbol, Decimal(str(candle.close)))
            await self.hub.publish(candle)

    async def _run_account_observers(self) -> None:
        while True:
            await asyncio.gather(
                *(self._poll_observer(name, observer) for name, observer in self.observers.items())
            )
            await asyncio.sleep(self.settings.account_poll_seconds)

    async def _poll_observer(self, name: str, observer: AccountObserver) -> None:
        try:
            self.account_snapshots[name] = await observer.snapshot()
            self.account_errors.pop(name, None)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.account_errors[name] = f"{type(exc).__name__}: {exc}"
