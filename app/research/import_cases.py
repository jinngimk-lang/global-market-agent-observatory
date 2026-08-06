from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from app.research.crisis import (
    CrisisWindow,
    CrisisWinner,
    TradeCase,
    find_verified_crisis_winners,
)
from app.store.sqlite import SQLiteStore


def parse_import_payload(payload: dict[str, Any]) -> list[CrisisWinner]:
    windows = [CrisisWindow.model_validate(item) for item in payload.get("windows", [])]
    cases = [TradeCase.model_validate(item) for item in payload.get("cases", [])]
    return find_verified_crisis_winners(cases, windows)


def import_file(path: str | Path, *, database_path: str | Path) -> int:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    winners = parse_import_payload(payload)
    store = SQLiteStore(database_path)
    for winner in winners:
        store.add_crisis_winner(winner)
    return len(winners)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import evidence-backed crisis trade cases into the observatory database."
    )
    parser.add_argument("path", help="JSON file containing windows and cases")
    parser.add_argument(
        "--database",
        default=os.getenv("DATABASE_PATH", "data/observatory.db"),
        help="SQLite database path",
    )
    args = parser.parse_args()
    imported = import_file(args.path, database_path=args.database)
    print(f"Imported {imported} verified crisis winners")


if __name__ == "__main__":
    main()
