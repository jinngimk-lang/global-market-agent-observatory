from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.models import Candle, OrderStatus, TradingMode
from app.innovation.models import PromotionEvidence
from app.innovation.store import SQLiteStrategyEvidenceStore
from app.learning.models import (
    StrategyEntryPriceSource,
    StrategyEvaluationPartition,
    StrategyHealth,
    StrategyHealthPolicy,
    StrategyObservation,
    StrategyObservationStatus,
    StrategyOOSRegimeAttribution,
    StrategyRegimeAttribution,
    StrategySymbolAttribution,
)
from app.learning.store import SQLiteStrategyLearningStore
from app.strategy.base import StrategyAction, StrategySignal
from app.trading.autonomous import TradingCycleResult


class StrategyLearningService:
    def __init__(
        self,
        *,
        store: SQLiteStrategyLearningStore,
        evidence_store: SQLiteStrategyEvidenceStore,
        mode: TradingMode,
        evaluation_horizon_seconds: float,
        transaction_cost_bps: Decimal,
        modeled_entry_slippage_bps: Decimal = Decimal("0"),
        modeled_exit_slippage_bps: Decimal = Decimal("0"),
        health_policy: StrategyHealthPolicy | None = None,
        walk_forward_calibration_observations: int = 20,
        walk_forward_holdout_observations: int = 10,
        oos_min_holdout_observations: int = 20,
        oos_min_completed_folds: int = 2,
    ) -> None:
        if evaluation_horizon_seconds <= 0:
            raise ValueError("evaluation_horizon_seconds must be positive")
        if transaction_cost_bps < 0:
            raise ValueError("transaction_cost_bps must be non-negative")
        if modeled_entry_slippage_bps < 0 or modeled_exit_slippage_bps < 0:
            raise ValueError("modeled slippage bps must be non-negative")
        if walk_forward_calibration_observations <= 0:
            raise ValueError("walk_forward_calibration_observations must be positive")
        if walk_forward_holdout_observations <= 0:
            raise ValueError("walk_forward_holdout_observations must be positive")
        if oos_min_holdout_observations <= 0:
            raise ValueError("oos_min_holdout_observations must be positive")
        if oos_min_completed_folds <= 0:
            raise ValueError("oos_min_completed_folds must be positive")
        self._store = store
        self._evidence_store = evidence_store
        self._mode = mode
        self._horizon_seconds = evaluation_horizon_seconds
        self._transaction_cost_bps = transaction_cost_bps
        self._modeled_entry_slippage_bps = modeled_entry_slippage_bps
        self._modeled_exit_slippage_bps = modeled_exit_slippage_bps
        self._policy = health_policy or StrategyHealthPolicy()
        self._walk_forward_calibration_observations = (
            walk_forward_calibration_observations
        )
        self._walk_forward_holdout_observations = walk_forward_holdout_observations
        self._oos_min_holdout_observations = oos_min_holdout_observations
        self._oos_min_completed_folds = oos_min_completed_folds

    @property
    def store(self) -> SQLiteStrategyLearningStore:
        return self._store

    def observe_cycle(self, candle: Candle, cycle: TradingCycleResult) -> list[StrategyHealth]:
        affected: set[tuple[str, str]] = set()
        exit_price = Decimal(str(candle.close))
        for observation in self._store.list_due(candle.symbol, candle.close_time):
            closed = self._close_observation(observation, exit_price, candle.close_time)
            self._store.update_observation(closed)
            affected.add((closed.strategy_id, closed.version))

        for signal in cycle.signals:
            if signal.action not in {StrategyAction.BUY, StrategyAction.SELL}:
                continue
            signal_entry_price = signal.entry_price or exit_price
            if signal_entry_price <= 0:
                continue
            observation = self._observation_from_signal(
                signal,
                signal_entry_price,
                cycle,
            ).model_copy(
                update={
                    "market_regime": self._market_regime(cycle, signal_entry_price)
                }
            )
            self._store.add_observation(observation)
            affected.add((observation.strategy_id, observation.version))

        return [
            self.refresh_strategy(strategy_id, version)
            for strategy_id, version in sorted(affected)
        ]

    def refresh_strategy(self, strategy_id: str, version: str) -> StrategyHealth:
        observations = self._store.list_observations(
            strategy_id,
            version,
            closed_only=True,
        )
        recent = observations[-self._policy.window_observations :]
        returns = [item.net_return for item in recent if item.net_return is not None]
        closed_observations, expectancy, win_rate, max_drawdown = self._metrics(returns)
        reasons = self._degradation_reasons(
            closed_observations,
            expectancy,
            max_drawdown,
        )

        symbol_attribution: list[StrategySymbolAttribution] = []
        symbols = sorted({item.symbol for item in observations})
        for symbol in symbols:
            symbol_observations = [item for item in observations if item.symbol == symbol]
            symbol_recent = symbol_observations[-self._policy.window_observations :]
            symbol_returns = [
                item.net_return for item in symbol_recent if item.net_return is not None
            ]
            (
                symbol_count,
                symbol_expectancy,
                symbol_win_rate,
                symbol_drawdown,
            ) = self._metrics(symbol_returns)
            symbol_reasons = self._degradation_reasons(
                symbol_count,
                symbol_expectancy,
                symbol_drawdown,
            )
            attribution = StrategySymbolAttribution(
                symbol=symbol,
                closed_observations=symbol_count,
                expectancy_after_costs=symbol_expectancy,
                max_drawdown=symbol_drawdown,
                win_rate=symbol_win_rate,
                degraded=bool(symbol_reasons),
                degradation_reasons=symbol_reasons,
            )
            symbol_attribution.append(attribution)
            if attribution.degraded:
                reasons.append(f"symbol_degraded:{symbol}")

        regime_attribution: list[StrategyRegimeAttribution] = []
        regimes = sorted(
            {item.market_regime for item in observations if item.market_regime is not None}
        )
        for regime in regimes:
            regime_observations = [
                item for item in observations if item.market_regime == regime
            ]
            regime_recent = regime_observations[-self._policy.window_observations :]
            regime_returns = [
                item.net_return for item in regime_recent if item.net_return is not None
            ]
            (
                regime_count,
                regime_expectancy,
                regime_win_rate,
                regime_drawdown,
            ) = self._metrics(regime_returns)
            regime_reasons = self._degradation_reasons(
                regime_count,
                regime_expectancy,
                regime_drawdown,
            )
            regime_attribution.append(
                StrategyRegimeAttribution(
                    regime=regime,
                    closed_observations=regime_count,
                    expectancy_after_costs=regime_expectancy,
                    max_drawdown=regime_drawdown,
                    win_rate=regime_win_rate,
                    degraded=bool(regime_reasons),
                    degradation_reasons=regime_reasons,
                )
            )

        reasons = list(dict.fromkeys(reasons))
        health = StrategyHealth(
            strategy_id=strategy_id.strip().lower(),
            version=version.strip(),
            closed_observations=closed_observations,
            expectancy_after_costs=expectancy,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            degraded=bool(reasons),
            degradation_reasons=reasons,
            symbol_attribution=symbol_attribution,
            regime_attribution=regime_attribution,
            oos_regime_attribution=self._oos_regime_attribution(observations),
            updated_at=self._now_from_observations(observations),
        )
        self._store.upsert_health(health)
        self._sync_promotion_evidence(health)
        return health

    @staticmethod
    def _metrics(
        returns: list[Decimal],
    ) -> tuple[int, Decimal | None, Decimal | None, Decimal | None]:
        count = len(returns)
        expectancy = (
            sum(returns, Decimal("0")) / Decimal(count)
            if count
            else None
        )
        win_rate = (
            Decimal(sum(1 for value in returns if value > 0)) / Decimal(count)
            if count
            else None
        )
        max_drawdown = StrategyLearningService._max_drawdown(returns) if returns else None
        return count, expectancy, win_rate, max_drawdown

    def _degradation_reasons(
        self,
        closed_observations: int,
        expectancy: Decimal | None,
        max_drawdown: Decimal | None,
    ) -> list[str]:
        reasons: list[str] = []
        if closed_observations < self._policy.min_observations:
            return reasons
        if (
            expectancy is not None
            and expectancy <= self._policy.min_expectancy_after_costs
        ):
            reasons.append("negative_expectancy")
        if max_drawdown is not None and max_drawdown > self._policy.max_drawdown:
            reasons.append("drawdown_limit")
        return reasons

    def refresh_all(self, strategies: list[object]) -> list[StrategyHealth]:
        reports: list[StrategyHealth] = []
        for strategy in strategies:
            strategy_id = str(getattr(strategy, "strategy_id", "")).strip().lower()
            version = str(getattr(strategy, "version", "")).strip()
            if strategy_id and version:
                reports.append(self.refresh_strategy(strategy_id, version))
        return reports

    def _observation_from_signal(
        self,
        signal: StrategySignal,
        signal_entry_price: Decimal,
        cycle: TradingCycleResult | None = None,
    ) -> StrategyObservation:
        normalized_id = signal.strategy_id.strip().lower()
        version = signal.version.strip()
        raw_id = "|".join(
            (
                normalized_id,
                version,
                signal.symbol.strip().upper(),
                signal.action.value,
                signal.generated_at.isoformat(),
            )
        )
        observation_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()
        partition, fold = self._next_walk_forward_partition(normalized_id, version)
        observed_fill = self._matching_observed_fill(signal, cycle)
        if observed_fill is None:
            entry_price = self._adverse_price(
                signal_entry_price,
                signal.action,
                self._modeled_entry_slippage_bps,
                is_entry=True,
            )
            entry_source = StrategyEntryPriceSource.MODELED
            observed_slippage = None
            latency_seconds = None
            execution_client_order_id = None
        else:
            entry_price = observed_fill.filled_price
            assert entry_price is not None
            entry_source = StrategyEntryPriceSource.OBSERVED_FILL
            observed_slippage = self._observed_entry_slippage_bps(
                signal.action,
                signal_entry_price,
                entry_price,
            )
            latency_seconds = self._execution_latency_seconds(
                signal.generated_at,
                observed_fill.observed_at,
            )
            execution_client_order_id = observed_fill.client_order_id

        return StrategyObservation(
            observation_id=observation_id,
            strategy_id=normalized_id,
            version=version,
            symbol=signal.symbol.strip().upper(),
            mode=self._mode,
            action=signal.action,
            signal_entry_price=signal_entry_price,
            entry_price=entry_price,
            entry_price_source=entry_source,
            modeled_entry_slippage_bps=self._modeled_entry_slippage_bps,
            modeled_exit_slippage_bps=self._modeled_exit_slippage_bps,
            observed_entry_slippage_bps=observed_slippage,
            execution_latency_seconds=latency_seconds,
            execution_client_order_id=execution_client_order_id,
            observed_at=signal.generated_at,
            due_at=signal.generated_at + timedelta(seconds=self._horizon_seconds),
            transaction_cost_bps=self._transaction_cost_bps,
            evaluation_partition=partition,
            walk_forward_fold=fold,
        )

    @staticmethod
    def _same_signal(left: StrategySignal, right: StrategySignal) -> bool:
        return (
            left.strategy_id.strip().lower() == right.strategy_id.strip().lower()
            and left.version.strip() == right.version.strip()
            and left.symbol.strip().upper() == right.symbol.strip().upper()
            and left.action is right.action
            and left.generated_at == right.generated_at
        )

    @classmethod
    def _matching_observed_fill(
        cls,
        signal: StrategySignal,
        cycle: TradingCycleResult | None,
    ):
        if cycle is None:
            return None
        client_order_ids = {
            allocation.intent.client_order_id
            for allocation in cycle.allocations
            if allocation.intent is not None and cls._same_signal(allocation.signal, signal)
        }
        if not client_order_ids:
            return None
        for execution in cycle.executions:
            if (
                execution.client_order_id in client_order_ids
                and execution.status is OrderStatus.FILLED
                and execution.filled_price is not None
                and execution.filled_price > 0
                and execution.filled_quantity > 0
            ):
                return execution
        return None

    @staticmethod
    def _observed_entry_slippage_bps(
        action: StrategyAction,
        reference_price: Decimal,
        fill_price: Decimal,
    ) -> Decimal:
        if action is StrategyAction.BUY:
            adverse_move = fill_price - reference_price
        else:
            adverse_move = reference_price - fill_price
        return adverse_move / reference_price * Decimal("10000")

    @staticmethod
    def _execution_latency_seconds(generated_at: datetime, observed_at: datetime) -> Decimal:
        generated = (
            generated_at
            if generated_at.tzinfo is not None
            else generated_at.replace(tzinfo=UTC)
        )
        observed = (
            observed_at
            if observed_at.tzinfo is not None
            else observed_at.replace(tzinfo=UTC)
        )
        seconds = max(
            (observed.astimezone(UTC) - generated.astimezone(UTC)).total_seconds(),
            0.0,
        )
        return Decimal(str(seconds))

    @staticmethod
    def _adverse_price(
        price: Decimal,
        action: StrategyAction,
        slippage_bps: Decimal,
        *,
        is_entry: bool,
    ) -> Decimal:
        fraction = slippage_bps / Decimal("10000")
        if action is StrategyAction.BUY:
            multiplier = (
                Decimal("1") + fraction if is_entry else Decimal("1") - fraction
            )
        else:
            multiplier = (
                Decimal("1") - fraction if is_entry else Decimal("1") + fraction
            )
        return price * multiplier

    @staticmethod
    def _market_regime(cycle: TradingCycleResult, reference_price: Decimal) -> str | None:
        structure = cycle.structure
        if structure is None:
            return None
        net_gex = structure.net_gex_1pct
        vwap = structure.vwap
        if net_gex is None:
            gamma = "gamma-unknown"
        elif net_gex > 0:
            gamma = "positive-gamma"
        elif net_gex < 0:
            gamma = "negative-gamma"
        else:
            gamma = "neutral-gamma"
        if vwap is None:
            location = "vwap-unknown"
        elif reference_price > vwap:
            location = "above-vwap"
        elif reference_price < vwap:
            location = "below-vwap"
        else:
            location = "at-vwap"
        return f"{gamma}|{location}"

    def _next_walk_forward_partition(
        self,
        strategy_id: str,
        version: str,
    ) -> tuple[StrategyEvaluationPartition, int]:
        index = self._store.count_walk_forward_observations(strategy_id, version)
        fold_size = (
            self._walk_forward_calibration_observations
            + self._walk_forward_holdout_observations
        )
        fold = index // fold_size
        offset = index % fold_size
        partition = (
            StrategyEvaluationPartition.CALIBRATION
            if offset < self._walk_forward_calibration_observations
            else StrategyEvaluationPartition.HOLDOUT
        )
        return partition, fold

    @staticmethod
    def _close_observation(
        observation: StrategyObservation,
        exit_price: Decimal,
        closed_at: datetime,
    ) -> StrategyObservation:
        modeled_exit_price = StrategyLearningService._adverse_price(
            exit_price,
            observation.action,
            observation.modeled_exit_slippage_bps,
            is_entry=False,
        )
        gross_return = (
            (modeled_exit_price - observation.entry_price) / observation.entry_price
            if observation.action is StrategyAction.BUY
            else (observation.entry_price - modeled_exit_price) / observation.entry_price
        )
        cost = observation.transaction_cost_bps / Decimal("10000")
        return observation.model_copy(
            update={
                "status": StrategyObservationStatus.CLOSED,
                "exit_price": modeled_exit_price,
                "net_return": gross_return - cost,
                "closed_at": closed_at,
            }
        )

    @staticmethod
    def _max_drawdown(returns: list[Decimal]) -> Decimal:
        equity = Decimal("1")
        peak = Decimal("1")
        max_drawdown = Decimal("0")
        for value in returns:
            equity += value
            peak = max(peak, equity)
            if peak <= 0:
                drawdown = Decimal("1")
            else:
                drawdown = max((peak - equity) / peak, Decimal("0"))
            max_drawdown = max(max_drawdown, drawdown)
        return min(max_drawdown, Decimal("1"))

    @staticmethod
    def _now_from_observations(observations: list[StrategyObservation]) -> datetime:
        closed_times = [item.closed_at for item in observations if item.closed_at is not None]
        if closed_times:
            return max(closed_times)
        return datetime.now(UTC)

    def _completed_walk_forward_folds(
        self,
        observations: list[StrategyObservation],
    ) -> list[int]:
        fold_counts: dict[int, dict[StrategyEvaluationPartition, int]] = {}
        for observation in observations:
            fold = observation.walk_forward_fold
            if fold is None:
                continue
            if observation.evaluation_partition not in {
                StrategyEvaluationPartition.CALIBRATION,
                StrategyEvaluationPartition.HOLDOUT,
            }:
                continue
            counts = fold_counts.setdefault(
                fold,
                {
                    StrategyEvaluationPartition.CALIBRATION: 0,
                    StrategyEvaluationPartition.HOLDOUT: 0,
                },
            )
            counts[observation.evaluation_partition] += 1
        return sorted(
            fold
            for fold, counts in fold_counts.items()
            if counts[StrategyEvaluationPartition.CALIBRATION]
            >= self._walk_forward_calibration_observations
            and counts[StrategyEvaluationPartition.HOLDOUT]
            >= self._walk_forward_holdout_observations
        )

    def _oos_regime_attribution(
        self,
        observations: list[StrategyObservation],
    ) -> list[StrategyOOSRegimeAttribution]:
        completed_folds = set(self._completed_walk_forward_folds(observations))
        holdout = [
            observation
            for observation in observations
            if observation.walk_forward_fold in completed_folds
            and observation.evaluation_partition is StrategyEvaluationPartition.HOLDOUT
            and observation.net_return is not None
            and observation.market_regime is not None
        ]
        reports: list[StrategyOOSRegimeAttribution] = []
        regimes = sorted({observation.market_regime for observation in holdout})
        for regime in regimes:
            regime_observations = [
                observation for observation in holdout if observation.market_regime == regime
            ]
            returns = [
                observation.net_return
                for observation in regime_observations
                if observation.net_return is not None
            ]
            count, expectancy, win_rate, max_drawdown = self._metrics(returns)
            regime_folds = {
                observation.walk_forward_fold
                for observation in regime_observations
                if observation.walk_forward_fold is not None
            }
            completed_fold_count = len(regime_folds)
            reports.append(
                StrategyOOSRegimeAttribution(
                    regime=regime,
                    holdout_observations=count,
                    completed_folds=completed_fold_count,
                    expectancy_after_costs=expectancy,
                    max_drawdown=max_drawdown,
                    win_rate=win_rate,
                    verified=(
                        count >= self._oos_min_holdout_observations
                        and completed_fold_count >= self._oos_min_completed_folds
                    ),
                )
            )
        return reports

    def _walk_forward_oos_metrics(
        self,
        strategy_id: str,
        version: str,
    ) -> tuple[bool, int, int, Decimal | None, Decimal | None]:
        observations = self._store.list_observations(
            strategy_id,
            version,
            closed_only=True,
        )
        completed_folds = self._completed_walk_forward_folds(observations)
        holdout_returns = [
            observation.net_return
            for observation in observations
            if observation.walk_forward_fold in completed_folds
            and observation.evaluation_partition is StrategyEvaluationPartition.HOLDOUT
            and observation.net_return is not None
        ]
        holdout_observations = len(holdout_returns)
        completed_fold_count = len(completed_folds)
        expectancy = (
            sum(holdout_returns, Decimal("0")) / Decimal(holdout_observations)
            if holdout_observations
            else None
        )
        max_drawdown = self._max_drawdown(holdout_returns) if holdout_returns else None
        verified = (
            holdout_observations >= self._oos_min_holdout_observations
            and completed_fold_count >= self._oos_min_completed_folds
        )
        return (
            verified,
            holdout_observations,
            completed_fold_count,
            expectancy,
            max_drawdown,
        )

    def _sync_promotion_evidence(self, health: StrategyHealth) -> None:
        counts = self._store.count_closed_by_mode(health.strategy_id, health.version)
        existing = (
            self._evidence_store.get(health.strategy_id, health.version)
            or PromotionEvidence()
        )
        runtime_replay = counts.get(TradingMode.REPLAY, 0)
        runtime_paper = counts.get(TradingMode.PAPER, 0)
        runtime_broker_paper = counts.get(TradingMode.BROKER_PAPER, 0)
        runtime_total = runtime_replay + runtime_paper + runtime_broker_paper
        existing_total = (
            existing.replay_observations
            + existing.paper_observations
            + existing.broker_paper_observations
        )
        (
            runtime_oos_verified,
            runtime_holdout_observations,
            runtime_completed_folds,
            runtime_oos_expectancy,
            runtime_oos_drawdown,
        ) = self._walk_forward_oos_metrics(health.strategy_id, health.version)

        refs = list(existing.evidence_refs)
        if health.closed_observations > 0:
            reference = (
                f"runtime-learning:{health.strategy_id}@{health.version}:"
                f"{health.closed_observations}"
            )
            if reference not in refs:
                refs.append(reference)
        if runtime_oos_verified:
            reference = (
                f"walk-forward-oos:{health.strategy_id}@{health.version}:"
                f"folds={runtime_completed_folds}:"
                f"holdout={runtime_holdout_observations}"
            )
            if reference not in refs:
                refs.append(reference)

        existing_oos_stronger = (
            existing.out_of_sample_verified
            and existing.oos_holdout_observations >= runtime_holdout_observations
            and existing.walk_forward_folds >= runtime_completed_folds
        )
        if runtime_oos_verified and not existing_oos_stronger:
            expectancy = runtime_oos_expectancy
            max_drawdown = runtime_oos_drawdown
        elif existing.out_of_sample_verified:
            expectancy = existing.expectancy_after_costs
            max_drawdown = existing.max_drawdown
        elif existing_total > runtime_total:
            expectancy = existing.expectancy_after_costs
            max_drawdown = existing.max_drawdown
        else:
            expectancy = health.expectancy_after_costs
            max_drawdown = health.max_drawdown

        updated = existing.model_copy(
            update={
                "out_of_sample_verified": (
                    existing.out_of_sample_verified or runtime_oos_verified
                ),
                "oos_holdout_observations": max(
                    existing.oos_holdout_observations,
                    runtime_holdout_observations,
                ),
                "walk_forward_folds": max(
                    existing.walk_forward_folds,
                    runtime_completed_folds,
                ),
                "replay_observations": max(existing.replay_observations, runtime_replay),
                "paper_observations": max(existing.paper_observations, runtime_paper),
                "broker_paper_observations": max(
                    existing.broker_paper_observations,
                    runtime_broker_paper,
                ),
                "transaction_cost_model_documented": (
                    existing.transaction_cost_model_documented
                    or health.closed_observations > 0
                ),
                "expectancy_after_costs": expectancy,
                "max_drawdown": max_drawdown,
                "degradation_rule_defined": True,
                "evidence_refs": refs,
            }
        )
        self._evidence_store.upsert(health.strategy_id, health.version, updated)
