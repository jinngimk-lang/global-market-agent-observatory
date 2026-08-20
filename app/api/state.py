from __future__ import annotations

import asyncio
from decimal import Decimal

from app.audit.service import AuditService
from app.broker.base import AccountObserver
from app.broker.execution_factory import build_execution_adapter
from app.broker.factory import build_account_observers
from app.broker.paper import PaperBroker
from app.domain.models import ExternalAccountSnapshot, RiskLimits, TradingState
from app.execution.controller import ExecutionController
from app.market.alpaca import AlpacaStockBarFeed
from app.market.binance import BinanceKlineFeed
from app.market.hub import MarketHub
from app.market.replay import ReplayFeed
from app.portfolio.engine import PortfolioAllocator, PortfolioPolicy
from app.risk.engine import RiskEngine
from app.settings import Settings
from app.store.sqlite import SQLiteStore
from app.strategy.gamma_levels import GammaLevelsStrategy
from app.strategy.vwap import VWAPStrategy
from app.trading.autonomous import AutonomousTradingEngine, TradingCycleResult
from app.trading.orchestrator import TradingOrchestrator
from app.trading.portfolio_source import (
    BrokerPortfolioSource,
    LocalPaperPortfolioSource,
    PortfolioSource,
)


class ApplicationState:
    def __init__(
        self,
        settings: Settings,
        *,
        observers: list[AccountObserver] | None = None,
    ) -> None:
        self.settings = settings
        self.store = SQLiteStore(
            settings.database_path,
            starting_cash=settings.starting_cash,
        )
        self.hub = MarketHub(queue_size=200)

        # Compatibility-only paper broker for legacy read/paper API endpoints.
        # It is never swapped for a live adapter.
        self.broker = PaperBroker(self.store)

        self.risk = RiskEngine(
            RiskLimits(
                allowed_symbols=settings.allowed_symbols,
                max_order_notional=settings.max_order_notional,
                max_symbol_exposure=settings.max_symbol_exposure,
                max_gross_exposure=settings.max_gross_exposure,
                daily_loss_limit=settings.daily_loss_limit,
                max_portfolio_drawdown=settings.max_portfolio_drawdown,
                market_data_max_age_seconds=settings.market_data_max_age_seconds,
                account_state_max_age_seconds=settings.account_state_max_age_seconds,
            )
        )
        self.audit = AuditService(self.store)
        self.execution_adapter = build_execution_adapter(settings, self.store)
        self.execution = ExecutionController(
            adapter=self.execution_adapter,
            risk_engine=self.risk,
        )
        self.orchestrator = TradingOrchestrator(
            execution=self.execution,
            audit=self.audit,
        )
        self.allocator = PortfolioAllocator(
            PortfolioPolicy(
                risk_fraction_per_trade=settings.risk_fraction_per_trade,
                max_order_notional=settings.max_order_notional,
                max_group_exposure=settings.max_group_exposure,
                reduce_fraction=settings.reduce_fraction,
                symbol_groups=settings.symbol_groups,
            )
        )

        selected_observers = (
            observers if observers is not None else build_account_observers(settings)
        )
        self.observers = {observer.name: observer for observer in selected_observers}
        self.portfolio_source = self._build_portfolio_source()
        self.autonomous = AutonomousTradingEngine(
            store=self.store,
            strategies=[VWAPStrategy(), GammaLevelsStrategy()],
            allocator=self.allocator,
            portfolio_source=self.portfolio_source,
            orchestrator=self.orchestrator,
            audit=self.audit,
            execution_enabled=settings.auto_trading_enabled,
        )

        self.feed = self._build_market_feed()
        self.account_snapshots: dict[str, ExternalAccountSnapshot] = {}
        self.account_errors: dict[str, str] = {}
        self.last_cycle_results: dict[str, TradingCycleResult] = {}
        self.last_cycle_errors: dict[str, str] = {}
        self._feed_task: asyncio.Task[None] | None = None
        self._account_task: asyncio.Task[None] | None = None

    @property
    def trading_state(self) -> TradingState:
        return self.orchestrator.trading_state

    def _build_market_feed(self):
        settings = self.settings
        if settings.market_source == "alpaca":
            if not settings.alpaca_api_key or not settings.alpaca_api_secret:
                raise ValueError("Alpaca market source requires Alpaca credentials.")
            return AlpacaStockBarFeed(
                symbols=settings.trading_universe,
                api_key=settings.alpaca_api_key.get_secret_value(),
                api_secret=settings.alpaca_api_secret.get_secret_value(),
                feed=settings.alpaca_market_data_feed,
            )
        if settings.market_source == "binance":
            return BinanceKlineFeed(
                symbol=settings.market_symbol,
                interval=settings.market_interval,
            )
        if settings.market_source == "replay":
            return ReplayFeed(
                symbol=settings.market_symbol,
                interval=settings.market_interval,
                seed=settings.replay_seed,
                delay_seconds=settings.replay_delay_seconds,
            )
        raise ValueError(f"Unsupported market source: {settings.market_source}")

    def _build_portfolio_source(self) -> PortfolioSource:
        provider = self.settings.execution_provider.value
        if provider == "paper":
            return LocalPaperPortfolioSource.from_store(self.store)
        observer = self.observers.get(provider)
        if observer is None:
            raise ValueError(
                f"Execution provider {provider} requires a matching account observer."
            )
        return BrokerPortfolioSource(observer, require_daily_pnl=True)

    async def start(self) -> None:
        if self._feed_task is None:
            self._feed_task = asyncio.create_task(self._run_feed(), name="market-feed")
        if self.observers and self._account_task is None:
            self._account_task = asyncio.create_task(
                self._run_account_observers(),
                name="account-observers",
            )

    async def stop(self) -> None:
        tasks = [
            task
            for task in (self._feed_task, self._account_task)
            if task is not None
        ]
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
            self.store.mark_position(candle.symbol, Decimal(str(candle.close)))
            try:
                cycle = await self.autonomous.on_candle(candle)
                self.last_cycle_results[candle.symbol] = cycle
                self.last_cycle_errors.pop(candle.symbol, None)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                self.last_cycle_errors[candle.symbol] = message
                if (
                    self.settings.auto_trading_enabled
                    and self.trading_state is not TradingState.HALTED
                ):
                    self.orchestrator.halt(f"autonomous_cycle_error: {message}")
            await self.hub.publish(candle)

    async def _run_account_observers(self) -> None:
        while True:
            await asyncio.gather(
                *(
                    self._poll_observer(name, observer)
                    for name, observer in self.observers.items()
                )
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
