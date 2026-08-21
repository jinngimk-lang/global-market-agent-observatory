from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.domain.models import TradingState


class SQLiteTradingStateStore:
    """Persist fail-closed runtime state independently of process lifetime."""

    _KEY = "trading_state"

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
            connection.commit()

    def get(self) -> TradingState:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state FROM trading_runtime_state WHERE id = 1"
            ).fetchone()
        if row is None:
            return TradingState.HALTED
        try:
            return TradingState(str(row["state"]))
        except ValueError:
            # Corrupt/unknown persisted state must never silently unlock execution.
            return TradingState.HALTED

    def last_reason(self) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT reason FROM trading_runtime_state WHERE id = 1"
            ).fetchone()
        if row is None or row["reason"] is None:
            return None
        return str(row["reason"])

    def set(self, state: TradingState, *, reason: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO trading_runtime_state(id, state, reason, updated_at)
                VALUES(1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    state=excluded.state,
                    reason=excluded.reason,
                    updated_at=excluded.updated_at
                """,
                (state.value, reason, datetime.now(UTC).isoformat()),
            )
            connection.commit()


# Compatibility alias for earlier work on this branch.
TradingStateStore = SQLiteTradingStateStore
