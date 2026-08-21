from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from app.audit.service import AuditService
from app.broker.base import AccountObserver
from app.broker.execution_factory import build_execution_adapter
from app.broker.factory import build_account_observers
from app.broker.paper import PaperBroker
from app.domain.models import ExternalAccountSnapshot, RiskLimits, TradingState
from app.execution.controller import ExecutionController
from app.innovation.registry import RuntimeStrategyPromotion, StrategyPromotionRegistry
from app.innovation.store import SQLiteStrategyEvidenceStore
from app.learning.models import StrategyHealth, StrategyHealthPolicy
from app.learning.service import StrategyLearningService
from app.learning.store import SQLiteStrategyLearningStore
from app.market.alpaca import AlpacaStockBarFeed
from app.market.alpaca_options import AlpacaOptionsChainClient
from app.market.binance import BinanceKlineFeed
from app.market.hub import MarketHub
from app.market.options_structure import OptionsChainSource, OptionsStructureService
from app.market.replay import ReplayFeed
from app.portfolio.engine import PortfolioAllocator, PortfolioPolicy
from app.risk.engine import RiskEngine
from app.settings import Settings
from app.store.sqlite import SQLiteStore
from app.strategy.gamma_levels import GammaLevelsStrategy
from app.strategy.manifests import strategy_hypotheses
from app.strategy.vwap import VWAPStrategy
from app.trading.autonomous import AutonomousTradingEngine, TradingCycleResult
from app.trading.orchestrator import TradingOrchestrator
from app.trading.portfolio_source import (
    BrokerPortfolioSource,
    LocalPaperPortfolioSource,
    PortfolioSource,
)
from app.trading.state_store import SQLiteTradingStateStore


class ApplicationState:
    def __init__(
        self,
        settings: Settings,
        *,
        observers: list[AccountObserver] | None = None,
        options_chain_source: OptionsChainSource | None = None,
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
        self.trading_state_store = SQLiteTradingStateStore(settings.database_path)
        persisted_trading_state = self.trading_state_store.get()
        self.execution = ExecutionController(
            adapter=self.execution_adapter,
            risk_engine=self.risk,
            trading_state=persisted_trading_state,
        )
        self.orchestrator = TradingOrchestrator(
            execution=self.execution,
            audit=self.audit,
            state_store=self.trading_state_store,
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

        self.strategies = [VWAPStrategy(), GammaLevelsStrategy()]
        self.strategy_evidence_store = SQLiteStrategyEvidenceStore(settings.database_path)
        self.strategy_promotion = StrategyPromotionRegistry(
            manifests=strategy_hypotheses(),
            evidence_store=self.strategy_evidence_store,
        )
        self.strategy_promotion_reports: list[RuntimeStrategyPromotion] = (
            self.strategy_promotion.evaluate_runtime(
                self.strategies,
                settings.trading_mode,
            )
        )
        self.promotion_execution_allowed = self._promotion_allowed()

        self.strategy_learning_store = SQLiteStrategyLearningStore(settings.database_path)
        self.learning = StrategyLearningService(
            store=self.strategy_learning_store,
            evidence_store=self.strategy_evidence_store,
            mode=settings.trading_mode,
            evaluation_horizon_seconds=settings.strategy_evaluation_horizon_seconds,
            transaction_cost_bps=settings.strategy_transaction_cost_bps,
            health_policy=StrategyHealthPolicy(
                min_observations=settings.strategy_degradation_min_observations,
                window_observations=settings.strategy_degradation_window_observations,
                min_expectancy_after_costs=(
                    settings.strategy_degradation_min_expectancy_after_costs
                ),
                max_drawdown=settings.strategy_degradation_max_drawdown,
            ),
        )
        self.strategy_health_reports: list[StrategyHealth] = []
        self.strategy_health_execution_allowed = True
        self.last_improvement_error: str | None = None

        autonomous_execution_enabled = (
            settings.auto_trading_enabled
            and self.promotion_execution_allowed
            and self.strategy_health_execution_allowed
        )
        self.autonomous = AutonomousTradingEngine(
            store=self.store,
            strategies=self.strategies,
            allocator=self.allocator,
            portfolio_source=self.portfolio_source,
            orchestrator=self.orchestrator,
            audit=self.audit,
            execution_enabled=autonomous_execution_enabled,
        )

        self.feed = self._build_market_feed()
        self._owns_options_chain_source = False
        selected_options_source = options_chain_source
        if (
            selected_options_source is None
            and settings.options_structure_enabled
            and settings.alpaca_api_key
            and settings.alpaca_api_secret
        ):
            selected_options_source = AlpacaOptionsChainClient(
                api_key=settings.alpaca_api_key.get_secret_value(),
                api_secret=settings.alpaca_api_secret.get_secret_value(),
                feed=settings.alpaca_options_feed,
            )
            self._owns_options_chain_source = True
        self.options_chain_source = selected_options_source
        self.options_structure = (
            OptionsStructureService(
                source=selected_options_source,
                expiration_horizon_days=settings.options_expiration_horizon_days,
                max_age_seconds=settings.options_structure_max_age_seconds,
            )
            if settings.options_structure_enabled and selected_options_source is not None
            else None
        )
        self.options_structure_errors: dict[str, str] = {}
        self.last_options_structure_loop_error: str | None = None
        self.options_structure_loop_failure_count = 0

        self.account_snapshots: dict[str, ExternalAccountSnapshot] = {}
        self.account_errors: dict[str, str] = {}
        self.last_cycle_results: dict[str, TradingCycleResult] = {}
        self.last_cycle_errors: dict[str, str] = {}
        self.last_market_feed_error: str | None = None
        self.market_feed_failure_count = 0
        self._feed_task: asyncio.Task[None] | None = None
        self._account_task: asyncio.Task[None] | None = None
        self._improvement_task: asyncio.Task[None] | None = None
        self._options_structure_task: asyncio.Task[None] | None = None

    @property
    def trading_state(self) -> TradingState:
        return self.orchestrator.trading_state

    @property
    def autonomous_execution_enabled(self) -> bool:
        return (
            self.autonomous.execution_enabled
            and self.strategy_health_execution_allowed
        )

    def _promotion_allowed(self) -> bool:
        return bool(self.strategy_promotion_reports) and all(
            report.allowed for report in self.strategy_promotion_reports
        )

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
        if self.settings.strategy_learning_enabled and self._improvement_task is None:
            self._improvement_task = asyncio.create_task(
                self._run_continuous_improvement(),
                name="continuous-improvement",
            )
        if self.options_structure is not None and self._options_structure_task is None:
            self._options_structure_task = asyncio.create_task(
                self._run_options_structure(),
                name="options-structure",
            )

    async def stop(self) -> None:
        tasks = [
            task
            for task in (
                self._feed_task,
                self._account_task,
                self._improvement_task,
                self._options_structure_task,
            )
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
        self._improvement_task = None
        self._options_structure_task = None
        if self._owns_options_chain_source and self.options_chain_source is not None:
            close = getattr(self.options_chain_source, "close", None)
            if close is not None:
                await close()

    async def process_candle(self, candle) -> TradingCycleResult:
        self.store.mark_position(candle.symbol, Decimal(str(candle.close)))
        structure = (
            self.options_structure.structure_for(candle.symbol, candle.close_time)
            if self.options_structure is not None
            else None
        )
        cycle = await self.autonomous.on_candle(candle, structure=structure)
        if (
            self.settings.strategy_learning_enabled
            and cycle.skipped_reason != "market_revision"
        ):
            self.learning.observe_cycle(candle, cycle)
            self._apply_strategy_health(self.strategy_learning_store.list_health())
        return cycle

    async def _run_feed(self) -> None:
        retry_seconds = min(
            self.settings.market_feed_retry_seconds,
            self.settings.market_feed_retry_max_seconds,
        )
        while True:
            try:
                async for candle in self.feed.stream():
                    retry_seconds = min(
                        self.settings.market_feed_retry_seconds,
                        self.settings.market_feed_retry_max_seconds,
                    )
                    try:
                        cycle = await self.process_candle(candle)
                        self.last_cycle_results[candle.symbol] = cycle
                        self.last_cycle_errors.pop(candle.symbol, None)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        message = f"{type(exc).__name__}: {exc}"
                        self.last_cycle_errors[candle.symbol] = message
                        if (
                            self.autonomous_execution_enabled
                            and self.trading_state is not TradingState.HALTED
                        ):
                            self.orchestrator.halt(f"autonomous_cycle_error: {message}")
                    await self.hub.publish(candle)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.market_feed_failure_count += 1
                self.last_market_feed_error = f"{type(exc).__name__}: {exc}"
                await asyncio.sleep(retry_seconds)
                retry_seconds = min(
                    self.settings.market_feed_retry_max_seconds,
                    retry_seconds * 2,
                )

    async def refresh_options_structure_once(
        self,
        *,
        observed_at: datetime | None = None,
    ) -> None:
        if self.options_structure is None:
            return
        observed = observed_at or datetime.now(UTC)
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=UTC)
        observed = observed.astimezone(UTC)
        for symbol in sorted(self.settings.trading_universe):
            latest = self.store.latest_candle(
                symbol,
                interval=self.settings.market_interval,
            )
            if latest is None:
                continue
            try:
                await self.options_structure.refresh(
                    symbol,
                    Decimal(str(latest.close)),
                    observed_at=observed,
                )
                self.options_structure_errors.pop(symbol, None)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.options_structure.invalidate(symbol)
                self.options_structure_errors[symbol] = f"{type(exc).__name__}: {exc}"

    async def _run_options_structure(self) -> None:
        while True:
            try:
                await self.refresh_options_structure_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.options_structure_loop_failure_count += 1
                self.last_options_structure_loop_error = f"{type(exc).__name__}: {exc}"
                if self.options_structure is not None:
                    for symbol in self.settings.trading_universe:
                        self.options_structure.invalidate(symbol)
            await asyncio.sleep(self.settings.options_structure_refresh_seconds)

    def refresh_continuous_improvement(self) -> list[StrategyHealth]:
        if not self.settings.strategy_learning_enabled:
            self.strategy_health_reports = []
            self.strategy_health_execution_allowed = True
            return []

        reports = self.learning.refresh_all(self.strategies)
        self._apply_strategy_health(reports)

        # Learning evidence may change promotion eligibility, but this only
        # updates the blocker report. It never mutates a manifest promotion
        # stage or automatically turns execution on.
        self.strategy_promotion_reports = self.strategy_promotion.evaluate_runtime(
            self.strategies,
            self.settings.trading_mode,
        )
        self.promotion_execution_allowed = self._promotion_allowed()
        self.last_improvement_error = None
        return reports

    def _apply_strategy_health(self, reports: list[StrategyHealth]) -> None:
        self.strategy_health_reports = reports
        degraded = [report for report in reports if report.degraded]
        self.strategy_health_execution_allowed = not degraded
        if (
            degraded
            and self.settings.auto_trading_enabled
            and self.trading_state is TradingState.ACTIVE
        ):
            identities = ",".join(
                f"{report.strategy_id}@{report.version}" for report in degraded
            )
            self.orchestrator.reduce_only(f"strategy_degradation:{identities}")
        # Deliberately no auto-reactivation here. A recovered strategy can
        # clear the health blocker, but REDUCING/HALTED remains latched until
        # a separate authenticated/operator-controlled recovery path exists.

    async def _run_continuous_improvement(self) -> None:
        while True:
            try:
                self.refresh_continuous_improvement()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_improvement_error = f"{type(exc).__name__}: {exc}"
                if (
                    self.settings.auto_trading_enabled
                    and self.trading_state is TradingState.ACTIVE
                ):
                    self.orchestrator.reduce_only("continuous_improvement_failure")
            await asyncio.sleep(self.settings.strategy_improvement_interval_seconds)

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
