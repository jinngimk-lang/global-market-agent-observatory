from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.intelligence.models import ContextItem


class SQLiteContextStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS context_items (
                    item_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    category TEXT NOT NULL,
                    event_time TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_context_items_provider_time
                    ON context_items(provider, event_time DESC);
                CREATE INDEX IF NOT EXISTS idx_context_items_category_time
                    ON context_items(category, event_time DESC);

                CREATE TABLE IF NOT EXISTS context_item_symbols (
                    item_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    PRIMARY KEY (item_id, symbol),
                    FOREIGN KEY (item_id) REFERENCES context_items(item_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_context_item_symbols_symbol
                    ON context_item_symbols(symbol, item_id);
                """
            )

    def upsert(self, item: ContextItem) -> None:
        payload = item.model_dump_json()
        event_time = item.event_time.astimezone(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO context_items (
                    item_id, provider, category, event_time, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    provider = excluded.provider,
                    category = excluded.category,
                    event_time = excluded.event_time,
                    payload_json = excluded.payload_json
                """,
                (
                    item.item_id,
                    item.source.provider,
                    item.category,
                    event_time,
                    payload,
                ),
            )
            connection.execute(
                "DELETE FROM context_item_symbols WHERE item_id = ?",
                (item.item_id,),
            )
            connection.executemany(
                "INSERT INTO context_item_symbols (item_id, symbol) VALUES (?, ?)",
                [(item.item_id, symbol) for symbol in item.symbols],
            )

    def recent(
        self,
        symbol: str,
        *,
        category: str | None = None,
        limit: int = 50,
    ) -> list[ContextItem]:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol or limit <= 0:
            return []

        parameters: list[object] = [normalized_symbol]
        category_clause = ""
        if category is not None:
            category_clause = " AND item.category = ?"
            parameters.append(category.strip())
        parameters.append(limit)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT item.payload_json
                FROM context_items AS item
                JOIN context_item_symbols AS symbol_map
                  ON symbol_map.item_id = item.item_id
                WHERE symbol_map.symbol = ?{category_clause}
                ORDER BY item.event_time DESC, item.item_id DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [ContextItem.model_validate_json(row["payload_json"]) for row in rows]

    def latest_provider_event(self, provider: str) -> datetime | None:
        normalized_provider = provider.strip()
        if not normalized_provider:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT MAX(event_time) AS event_time FROM context_items WHERE provider = ?",
                (normalized_provider,),
            ).fetchone()
        if row is None or row["event_time"] is None:
            return None
        parsed = datetime.fromisoformat(str(row["event_time"]))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
