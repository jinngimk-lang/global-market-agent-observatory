from __future__ import annotations

import hashlib
from datetime import UTC, timedelta
from decimal import Decimal

from app.domain.models import Candle, TradingMode
from app.innovation.models import PromotionEvidence
from app.innovation.store import SQLiteStrategyEvidenceStore
from app.learning.models import (
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
    ) -> None:
        if evaluation_horizon_seconds <= 0:
            raise ValueError("evaluation_horizon_seconds must be positive")
        if transaction_cost_bps < 0:
            raise ValueError("transaction_cost_bps must be non-negative")
        self._store = store
        self._evidence_store = evidence_store
        self._mode = mode
        self._horizon_seconds = evaluation_horizon_seconds
        self._transaction_cost_bps = transaction_cost_bps
        self._policy = health_policy or StrategyHealthPolicy()

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
        returns = [
            item.net_return
            for item in recent
            if item.net_return is not None
        ]
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
            if expectancy is not None and expectancy <= self._policy.min_expectancy_after_costs:
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
        raw_id = "|".join(
            (
                normalized_id,
                signal.version.strip(),
                signal.symbol.strip().upper(),
                signal.action.value,
                signal.generated_at.isoformat(),
            )
        )
        observation_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()
        return StrategyObservation(
            observation_id=observation_id,
            strategy_id=normalized_id,
            version=signal.version.strip(),
            symbol=signal.symbol.strip().upper(),
            mode=self._mode,
            action=signal.action,
            entry_price=entry_price,
            observed_at=signal.generated_at,
            due_at=signal.generated_at + timedelta(seconds=self._horizon_seconds),
            transaction_cost_bps=self._transaction_cost_bps,
        )

    @staticmethod
    def _close_observation(
        observation: StrategyObservation,
        exit_price: Decimal,
        closed_at,
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
    def _now_from_observations(observations: list[StrategyObservation]):
        closed_times = [item.closed_at for item in observations if item.closed_at is not None]
        if closed_times:
            return max(closed_times)
        return __import__("datetime").datetime.now(UTC)

    def _sync_promotion_evidence(self, health: StrategyHealth) -> None:
        counts = self._store.count_closed_by_mode(health.strategy_id, health.version)
        existing = self._evidence_store.get(health.strategy_id, health.version) or PromotionEvidence()
        reference = (
            f"runtime-learning:{health.strategy_id}@{health.version}:"
            f"{health.closed_observations}"
        )
        refs = list(existing.evidence_refs)
        if reference not in refs:
            refs.append(reference)
        updated = existing.model_copy(
            update={
                "replay_observations": counts.get(TradingMode.REPLAY, 0),
                "paper_observations": counts.get(TradingMode.PAPER, 0),
                "broker_paper_observations": counts.get(TradingMode.BROKER_PAPER, 0),
                "transaction_cost_model_documented": True,
                "expectancy_after_costs": health.expectancy_after_costs,
                "max_drawdown": health.max_drawdown,
                "degradation_rule_defined": True,
                "evidence_refs": refs,
            }
        )
        self._evidence_store.upsert(health.strategy_id, health.version, updated)
