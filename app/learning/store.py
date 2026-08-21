from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.domain.models import TradingMode
from app.learning.models import StrategyHealth, StrategyObservation


class SQLiteStrategyLearningStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS strategy_learning_observations (
                    observation_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_strategy_learning_due
                ON strategy_learning_observations(symbol, status, due_at);

                CREATE TABLE IF NOT EXISTS strategy_learning_health (
                    strategy_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY(strategy_id, version)
                );
                """
            )
            connection.commit()

    def add_observation(self, observation: StrategyObservation) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO strategy_learning_observations(
                    observation_id, strategy_id, version, symbol, mode, status, due_at, payload
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.observation_id,
                    observation.strategy_id,
                    observation.version,
                    observation.symbol,
                    observation.mode.value,
                    observation.status.value,
                    observation.due_at.isoformat(),
                    observation.model_dump_json(),
                ),
            )
            connection.commit()
            return cursor.rowcount == 1

    def update_observation(self, observation: StrategyObservation) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE strategy_learning_observations
                SET status = ?, due_at = ?, payload = ?
                WHERE observation_id = ?
                """,
                (
                    observation.status.value,
                    observation.due_at.isoformat(),
                    observation.model_dump_json(),
                    observation.observation_id,
                ),
            )
            connection.commit()

    def list_due(self, symbol: str, at: datetime) -> list[StrategyObservation]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM strategy_learning_observations
                WHERE symbol = ? AND status = 'pending' AND due_at <= ?
                ORDER BY due_at, observation_id
                """,
                (symbol.strip().upper(), at.isoformat()),
            ).fetchall()
        return [StrategyObservation.model_validate_json(row["payload"]) for row in rows]

    def list_observations(
        self,
        strategy_id: str,
        version: str,
        *,
        closed_only: bool = False,
        limit: int | None = None,
    ) -> list[StrategyObservation]:
        query = (
            "SELECT payload FROM strategy_learning_observations "
            "WHERE strategy_id = ? AND version = ?"
        )
        values: list[object] = [strategy_id.strip().lower(), version.strip()]
        if closed_only:
            query += " AND status = 'closed'"
        query += " ORDER BY due_at"
        if limit is not None:
            query += " LIMIT ?"
            values.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, tuple(values)).fetchall()
        return [StrategyObservation.model_validate_json(row["payload"]) for row in rows]

    def count_closed_by_mode(self, strategy_id: str, version: str) -> dict[TradingMode, int]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT mode, COUNT(*) AS count
                FROM strategy_learning_observations
                WHERE strategy_id = ? AND version = ? AND status = 'closed'
                GROUP BY mode
                """,
                (strategy_id.strip().lower(), version.strip()),
            ).fetchall()
        return {TradingMode(str(row["mode"])): int(row["count"]) for row in rows}

    def upsert_health(self, health: StrategyHealth) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO strategy_learning_health(strategy_id, version, payload)
                VALUES(?, ?, ?)
                ON CONFLICT(strategy_id, version) DO UPDATE SET payload=excluded.payload
                """,
                (health.strategy_id, health.version, health.model_dump_json()),
            )
            connection.commit()

    def get_health(self, strategy_id: str, version: str) -> StrategyHealth | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM strategy_learning_health
                WHERE strategy_id = ? AND version = ?
                """,
                (strategy_id.strip().lower(), version.strip()),
            ).fetchone()
        if row is None:
            return None
        return StrategyHealth.model_validate_json(row["payload"])

    def list_health(self) -> list[StrategyHealth]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM strategy_learning_health ORDER BY strategy_id, version"
            ).fetchall()
        return [StrategyHealth.model_validate_json(row["payload"]) for row in rows]
