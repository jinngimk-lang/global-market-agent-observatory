from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.domain.models import TradingState


class TradingStateStore:
    """Persist fail-closed runtime state across process restarts."""

    def __init__(self, database_path: str | Path) -> None:
        self._path = str(database_path)
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
                CREATE TABLE IF NOT EXISTS trading_runtime_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    state TEXT NOT NULL,
                    reason TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO trading_runtime_state(id, state, reason, updated_at)
                VALUES(1, ?, ?, ?)
                """,
                (
                    TradingState.ACTIVE.value,
                    "initial_state",
                    datetime.now(UTC).isoformat(),
                ),
            )

    def get(self) -> tuple[TradingState, str | None]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state, reason FROM trading_runtime_state WHERE id = 1"
            ).fetchone()
        if row is None:
            raise RuntimeError("Trading runtime state is not initialized")
        return TradingState(row["state"]), row["reason"]

    def set(self, state: TradingState, *, reason: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE trading_runtime_state
                SET state = ?, reason = ?, updated_at = ?
                WHERE id = 1
                """,
                (state.value, reason, datetime.now(UTC).isoformat()),
            )
