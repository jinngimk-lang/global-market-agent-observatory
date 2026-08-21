from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.domain.models import Candle


class SQLiteCycleCheckpointStore:
    """Persist completed market-cycle identities across process restarts.

    A cycle is marked complete only after the engine reaches a known terminal
    decision for that market observation. Unknown execution outcomes and raised
    exceptions must not be checkpointed so reconciliation/recovery can revisit them.
    """

    def __init__(self, database_path: str | Path) -> None:
        self._path = str(database_path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS market_cycle_checkpoints (
                    cycle_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    open_time TEXT NOT NULL,
                    completed_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    @staticmethod
    def cycle_id(candle: Candle) -> str:
        opened = candle.open_time
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=UTC)
        return f"{candle.symbol}:{candle.interval}:{opened.astimezone(UTC).isoformat()}"

    def is_completed(self, candle: Candle) -> bool:
        cycle_id = self.cycle_id(candle)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM market_cycle_checkpoints WHERE cycle_id = ?",
                (cycle_id,),
            ).fetchone()
        return row is not None

    def mark_completed(self, candle: Candle) -> None:
        cycle_id = self.cycle_id(candle)
        opened = candle.open_time
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=UTC)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO market_cycle_checkpoints(
                    cycle_id, symbol, interval, open_time, completed_at
                ) VALUES(?, ?, ?, ?, ?)
                """,
                (
                    cycle_id,
                    candle.symbol,
                    candle.interval,
                    opened.astimezone(UTC).isoformat(),
                    datetime.now(UTC).isoformat(),
                ),
            )
            connection.commit()
