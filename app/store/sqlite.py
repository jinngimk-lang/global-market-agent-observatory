from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.domain.models import Candle, EvidenceItem, OrderRecord, Position
from app.research.crisis import CrisisWinner


class SQLiteStore:
    def __init__(self, path: str | Path, *, starting_cash: str | Decimal = "100000") -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._starting_cash = Decimal(starting_cash)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS candles (
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    open_time TEXT NOT NULL,
                    close_time TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    source TEXT NOT NULL,
                    closed INTEGER NOT NULL,
                    PRIMARY KEY (symbol, interval, open_time)
                );

                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    observed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS account_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    cash TEXT NOT NULL,
                    realized_pnl_today TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS positions (
                    symbol TEXT PRIMARY KEY,
                    quantity TEXT NOT NULL,
                    average_price TEXT NOT NULL,
                    market_price TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    client_order_id TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL,
                    requested_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS fills (
                    fill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    price TEXT NOT NULL,
                    realized_pnl TEXT NOT NULL,
                    filled_at TEXT NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES orders(order_id)
                );


                CREATE TABLE IF NOT EXISTS crisis_winners (
                    case_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    observed_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO account_state(id, cash, realized_pnl_today)
                VALUES(1, ?, '0')
                """,
                (str(self._starting_cash),),
            )

    def upsert_candle(self, candle: Candle) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO candles(
                    symbol, interval, open_time, close_time, open, high, low, close,
                    volume, source, closed
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, interval, open_time) DO UPDATE SET
                    close_time=excluded.close_time,
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume=excluded.volume,
                    source=excluded.source,
                    closed=excluded.closed
                """,
                (
                    candle.symbol,
                    candle.interval,
                    candle.open_time.isoformat(),
                    candle.close_time.isoformat(),
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                    candle.source,
                    int(candle.closed),
                ),
            )

    def list_candles(self, symbol: str, *, interval: str = "1m", limit: int = 500) -> list[Candle]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM candles
                WHERE symbol = ? AND interval = ?
                ORDER BY open_time DESC
                LIMIT ?
                """,
                (symbol.strip().upper(), interval, limit),
            ).fetchall()
        candles = [
            Candle(
                symbol=row["symbol"],
                interval=row["interval"],
                open_time=datetime.fromisoformat(row["open_time"]),
                close_time=datetime.fromisoformat(row["close_time"]),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                source=row["source"],
                closed=bool(row["closed"]),
            )
            for row in rows
        ]
        candles.reverse()
        return candles

    def latest_candle(self, symbol: str, *, interval: str = "1m") -> Candle | None:
        candles = self.list_candles(symbol, interval=interval, limit=1)
        return candles[0] if candles else None

    def add_evidence(self, item: EvidenceItem) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO evidence(evidence_id, payload, observed_at)
                VALUES(?, ?, ?)
                ON CONFLICT(evidence_id) DO UPDATE SET
                    payload=excluded.payload,
                    observed_at=excluded.observed_at
                """,
                (item.evidence_id, item.model_dump_json(), item.observed_at.isoformat()),
            )

    def list_evidence(self, *, limit: int = 200) -> list[EvidenceItem]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM evidence ORDER BY observed_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [EvidenceItem.model_validate_json(row["payload"]) for row in rows]

    def add_crisis_winner(self, winner: CrisisWinner) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO crisis_winners(case_id, payload, observed_at)
                VALUES(?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    payload=excluded.payload,
                    observed_at=excluded.observed_at
                """,
                (
                    winner.case.case_id,
                    winner.model_dump_json(),
                    winner.case.closed_at.isoformat(),
                ),
            )

    def list_crisis_winners(self, *, limit: int = 200) -> list[CrisisWinner]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM crisis_winners ORDER BY observed_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [CrisisWinner.model_validate_json(row["payload"]) for row in rows]

    def get_account_state(self) -> tuple[Decimal, Decimal]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT cash, realized_pnl_today FROM account_state WHERE id = 1"
            ).fetchone()
        if row is None:
            raise RuntimeError("Account state is not initialized")
        return Decimal(row["cash"]), Decimal(row["realized_pnl_today"])

    def get_position(self, symbol: str) -> Position | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM positions WHERE symbol = ?", (symbol.strip().upper(),)
            ).fetchone()
        return self._position_from_row(row) if row else None

    def list_positions(self) -> list[Position]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM positions ORDER BY symbol").fetchall()
        return [self._position_from_row(row) for row in rows]

    def mark_position(self, symbol: str, market_price: Decimal) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE positions SET market_price = ? WHERE symbol = ?",
                (str(market_price), symbol.strip().upper()),
            )

    def get_order_by_client_id(self, client_order_id: str) -> OrderRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM orders WHERE client_order_id = ?", (client_order_id,)
            ).fetchone()
        return OrderRecord.model_validate_json(row["payload"]) if row else None

    def list_orders(self, *, limit: int = 200) -> list[OrderRecord]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM orders ORDER BY requested_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [OrderRecord.model_validate_json(row["payload"]) for row in rows]

    def apply_paper_fill(
        self,
        *,
        record: OrderRecord,
        cash: Decimal,
        realized_pnl_delta: Decimal,
        position: Position | None,
    ) -> None:
        if record.filled_price is None or record.filled_at is None:
            raise ValueError("Filled record must include price and timestamp")
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO orders(order_id, client_order_id, payload, requested_at)
                VALUES(?, ?, ?, ?)
                """,
                (
                    record.order_id,
                    record.intent.client_order_id,
                    record.model_dump_json(),
                    record.intent.requested_at.isoformat(),
                ),
            )
            account_row = connection.execute(
                "SELECT realized_pnl_today FROM account_state WHERE id = 1"
            ).fetchone()
            if account_row is None:
                raise RuntimeError("Account state is not initialized")
            realized_pnl_total = Decimal(account_row["realized_pnl_today"]) + realized_pnl_delta
            connection.execute(
                """
                UPDATE account_state
                SET cash = ?, realized_pnl_today = ?
                WHERE id = 1
                """,
                (str(cash), str(realized_pnl_total)),
            )
            if position is None or position.quantity == 0:
                connection.execute(
                    "DELETE FROM positions WHERE symbol = ?", (record.intent.symbol,)
                )
            else:
                connection.execute(
                    """
                    INSERT INTO positions(symbol, quantity, average_price, market_price)
                    VALUES(?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        quantity=excluded.quantity,
                        average_price=excluded.average_price,
                        market_price=excluded.market_price
                    """,
                    (
                        position.symbol,
                        str(position.quantity),
                        str(position.average_price),
                        str(position.market_price),
                    ),
                )
            connection.execute(
                """
                INSERT INTO fills(order_id, symbol, side, quantity, price, realized_pnl, filled_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.order_id,
                    record.intent.symbol,
                    record.intent.side.value,
                    str(record.intent.quantity),
                    str(record.filled_price),
                    str(realized_pnl_delta),
                    record.filled_at.isoformat(),
                ),
            )

    @staticmethod
    def _position_from_row(row: sqlite3.Row) -> Position:
        return Position(
            symbol=row["symbol"],
            quantity=Decimal(row["quantity"]),
            average_price=Decimal(row["average_price"]),
            market_price=Decimal(row["market_price"]),
        )

    def export_summary(self) -> dict[str, object]:
        cash, realized = self.get_account_state()
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "cash": str(cash),
            "realized_pnl_today": str(realized),
            "positions": [position.model_dump(mode="json") for position in self.list_positions()],
            "orders": [json.loads(order.model_dump_json()) for order in self.list_orders()],
            "evidence_count": len(self.list_evidence(limit=100000)),
        }
