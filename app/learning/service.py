from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.models import Candle, TradingMode
from app.innovation.models import PromotionEvidence
from app.innovation.store import SQLiteStrategyEvidenceStore
from app.learning.models import (
    StrategyEvaluationPartition,
    StrategyHealth,
    StrategyHealthPolicy,
    StrategyObservation,
    StrategyObservationStatus,
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
        health_policy: StrategyHealthPolicy | None = None,
        walk_forward_calibration_observations: int = 20,
        walk_forward_holdout_observations: int = 10,
    ) -> None:
        if evaluation_horizon_seconds <= 0:
            raise ValueError("evaluation_horizon_seconds must be positive")
        if transaction_cost_bps < 0:
            raise ValueError("transaction_cost_bps must be non-negative")
        if walk_forward_calibration_observations <= 0:
            raise ValueError("walk_forward_calibration_observations must be positive")
        if walk_forward_holdout_observations <= 0:
            raise ValueError("walk_forward_holdout_observations must be positive")
        self._store = store
        self._evidence_store = evidence_store
        self._mode = mode
        self._horizon_seconds = evaluation_horizon_seconds
        self._transaction_cost_bps = transaction_cost_bps
        self._policy = health_policy or StrategyHealthPolicy()
        self._walk_forward_calibration_observations = (
            walk_forward_calibration_observations
        )
        self._walk_forward_holdout_observations = walk_forward_holdout_observations

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
            entry_price = signal.entry_price or exit_price
            if entry_price <= 0:
                continue
            observation = self._observation_from_signal(signal, entry_price)
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
        closed_observations = len(returns)
        expectancy = (
            sum(returns, Decimal("0")) / Decimal(closed_observations)
            if closed_observations
            else None
        )
        win_rate = (
            Decimal(sum(1 for value in returns if value > 0)) / Decimal(closed_observations)
            if closed_observations
            else None
        )
        max_drawdown = self._max_drawdown(returns) if returns else None

        reasons: list[str] = []
        if closed_observations >= self._policy.min_observations:
            if (
                expectancy is not None
                and expectancy <= self._policy.min_expectancy_after_costs
            ):
                reasons.append("negative_expectancy")
            if max_drawdown is not None and max_drawdown > self._policy.max_drawdown:
                reasons.append("drawdown_limit")

        health = StrategyHealth(
            strategy_id=strategy_id.strip().lower(),
            version=version.strip(),
            closed_observations=closed_observations,
            expectancy_after_costs=expectancy,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            degraded=bool(reasons),
            degradation_reasons=reasons,
            updated_at=self._now_from_observations(observations),
        )
        self._store.upsert_health(health)
        self._sync_promotion_evidence(health)
        return health

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
        entry_price: Decimal,
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
        return StrategyObservation(
            observation_id=observation_id,
            strategy_id=normalized_id,
            version=version,
            symbol=signal.symbol.strip().upper(),
            mode=self._mode,
            action=signal.action,
            entry_price=entry_price,
            observed_at=signal.generated_at,
            due_at=signal.generated_at + timedelta(seconds=self._horizon_seconds),
            transaction_cost_bps=self._transaction_cost_bps,
            evaluation_partition=partition,
            walk_forward_fold=fold,
        )

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
        gross_return = (
            (exit_price - observation.entry_price) / observation.entry_price
            if observation.action is StrategyAction.BUY
            else (observation.entry_price - exit_price) / observation.entry_price
        )
        cost = observation.transaction_cost_bps / Decimal("10000")
        return observation.model_copy(
            update={
                "status": StrategyObservationStatus.CLOSED,
                "exit_price": exit_price,
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

        refs = list(existing.evidence_refs)
        if health.closed_observations > 0:
            reference = (
                f"runtime-learning:{health.strategy_id}@{health.version}:"
                f"{health.closed_observations}"
            )
            if reference not in refs:
                refs.append(reference)

        # Runtime forward observations are supplemental evidence. They must
        # never erase stronger replay/walk-forward evidence already persisted.
        preserve_existing_metrics = (
            existing.out_of_sample_verified
            or existing_total > runtime_total
        )
        expectancy = (
            existing.expectancy_after_costs
            if preserve_existing_metrics and existing.expectancy_after_costs is not None
            else health.expectancy_after_costs
        )
        max_drawdown = (
            existing.max_drawdown
            if preserve_existing_metrics and existing.max_drawdown is not None
            else health.max_drawdown
        )

        updated = existing.model_copy(
            update={
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
