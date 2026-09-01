from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

_SAFE_VALUES = {
    "TRADING_MODE": "paper",
    "EXECUTION_PROVIDER": "paper",
    "AUTO_TRADING_ENABLED": "false",
    "MARKET_SOURCE": "alpaca",
    "CONTEXT_INTELLIGENCE_ENABLED": "true",
}
_TRUE_VALUES = {"1", "true", "yes", "on"}


def _parse_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        normalized_key = key.strip()
        if normalized_key:
            values[normalized_key] = value.strip()
    return values


def _backup_path(path: Path) -> Path:
    first = path.with_name(f"{path.name}.before-readonly-realtime")
    if not first.exists():
        return first
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    candidate = path.with_name(f"{path.name}.before-readonly-realtime-{stamp}")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(
            f"{path.name}.before-readonly-realtime-{stamp}-{counter}"
        )
        counter += 1
    return candidate


def _replace_values(text: str, replacements: dict[str, str]) -> str:
    remaining = dict(replacements)
    output: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(raw_line)

    if remaining:
        if output and output[-1] != "":
            output.append("")
        output.append("# Safe read-only realtime mode managed by scripts/enable_readonly_realtime.py")
        for key, value in replacements.items():
            if key in remaining:
                output.append(f"{key}={value}")

    return "\n".join(output).rstrip("\n") + "\n"


def enable_readonly_realtime(env_path: Path | str = Path(".env")) -> Path:
    """Safely switch an existing local environment to read-only Alpaca observation.

    This helper deliberately cannot enable live trading or autonomous execution.
    It preserves broker credentials and unrelated settings without logging secrets.
    """

    path = Path(env_path)
    if not path.exists() or not path.is_file():
        raise RuntimeError(f"Environment file not found: {path}")

    original = path.read_text(encoding="utf-8")
    values = _parse_values(original)

    trading_mode = values.get("TRADING_MODE", "paper").strip().lower()
    live_enabled = values.get("LIVE_TRADING_ENABLED", "false").strip().lower()
    if trading_mode == "live" or live_enabled in _TRUE_VALUES:
        raise RuntimeError(
            "Refusing to modify a live trading configuration; switch it to paper manually first."
        )

    api_key = values.get("ALPACA_API_KEY", "").strip()
    api_secret = values.get("ALPACA_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise RuntimeError(
            "Alpaca API credentials are required locally before enabling verified realtime data."
        )

    backup = _backup_path(path)
    backup.write_text(original, encoding="utf-8")

    updated = _replace_values(original, _SAFE_VALUES)
    temporary = path.with_name(f"{path.name}.readonly-realtime.tmp")
    try:
        temporary.write_text(updated, encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()

    return backup


def main() -> None:
    path = Path(".env")
    backup = enable_readonly_realtime(path)
    print("readonly-realtime-enabled")
    print(f"env={path.resolve()}")
    print(f"backup={backup.resolve()}")
    print("trading_mode=paper")
    print("execution_provider=paper")
    print("auto_trading_enabled=false")
    print("market_source=alpaca")
    print("context_intelligence_enabled=true")


if __name__ == "__main__":
    main()
