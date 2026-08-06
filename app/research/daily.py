from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from app.research.github_releases import GitHubReleaseCollector
from app.research.sec import SECCollector

_DEFAULT_REPOSITORIES = [
    "ccxt/ccxt",
    "freqtrade/freqtrade",
    "hummingbot/hummingbot",
    "QuantConnect/Lean",
    "nautechsystems/nautilus_trader",
]


async def run_daily(output_dir: str | Path = "data/daily") -> Path:
    observed_at = datetime.now(UTC)
    repositories = [
        item.strip()
        for item in os.getenv(
            "GITHUB_RELEASE_REPOSITORIES", ",".join(_DEFAULT_REPOSITORIES)
        ).split(",")
        if item.strip()
    ]
    ciks = [item.strip() for item in os.getenv("SEC_CIKS", "").split(",") if item.strip()]

    evidence = await GitHubReleaseCollector().collect(repositories)
    if ciks:
        user_agent = os.getenv("SEC_USER_AGENT", "Observatory admin@example.com")
        sec_collector = SECCollector(user_agent=user_agent)
        for cik in ciks:
            evidence.extend(
                await sec_collector.collect_company(cik, observed_at=observed_at, years=3)
            )

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{observed_at.date().isoformat()}.json"
    payload = {
        "generated_at": observed_at.isoformat(),
        "records": [item.model_dump(mode="json") for item in evidence],
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


if __name__ == "__main__":
    print(asyncio.run(run_daily()))
