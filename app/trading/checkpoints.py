from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class TradingCycleCheckpointStore:
    """Durably mark market observations only after their cycle fully completes."""

    def __init__(self, database_path: str | Path) -> None:
        self._path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trading_cycle_checkpoints (
                    cycle_id TEXT PRIMARY KEY,
                    completed_at TEXT NOT NULL
                )
                """
            )

    def is_complete(self, cycle_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM trading_cycle_checkpoints WHERE cycle_id = ?",
                (cycle_id,),
            ).fetchone()
        return row is not None

    def mark_complete(
        self,
        cycle_id: str,
        *,
        completed_at: datetime | None = None,
    ) -> None:
        timestamp = completed_at or datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO trading_cycle_checkpoints(cycle_id, completed_at)
                VALUES(?, ?)
                """,
                (cycle_id, timestamp.isoformat()),
            )
