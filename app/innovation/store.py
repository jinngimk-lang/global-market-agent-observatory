from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.innovation.models import PromotionEvidence


class SQLiteStrategyEvidenceStore:
    """Persist evidence by exact strategy id/version in the runtime SQLite database."""

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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_promotion_evidence (
                    strategy_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(strategy_id, version)
                )
                """
            )
            connection.commit()

    def get(self, strategy_id: str, version: str) -> PromotionEvidence | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM strategy_promotion_evidence
                WHERE strategy_id = ? AND version = ?
                """,
                (strategy_id.strip().lower(), version.strip()),
            ).fetchone()
        if row is None:
            return None
        return PromotionEvidence.model_validate_json(row["payload"])

    def upsert(
        self,
        strategy_id: str,
        version: str,
        evidence: PromotionEvidence,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO strategy_promotion_evidence(strategy_id, version, payload, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(strategy_id, version) DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (
                    strategy_id.strip().lower(),
                    version.strip(),
                    evidence.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                ),
            )
            connection.commit()

    def list_all(self) -> dict[tuple[str, str], PromotionEvidence]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT strategy_id, version, payload
                FROM strategy_promotion_evidence
                ORDER BY strategy_id, version
                """
            ).fetchall()
        return {
            (str(row["strategy_id"]), str(row["version"])): PromotionEvidence.model_validate_json(
                row["payload"]
            )
            for row in rows
        }
