from __future__ import annotations

import os
from pathlib import Path


def _valid_env_key(key: str) -> bool:
    if not key or not (key[0].isalpha() or key[0] == "_"):
        return False
    return all(character.isalnum() or character == "_" for character in key)


def load_local_env(path: Path | str = Path(".env")) -> bool:
    """Load a local dotenv file without overriding real process environment values.

    The loader intentionally stays small and silent: it never prints values, and
    process/container environment variables remain authoritative over local files.
    """

    env_path = Path(path)
    if not env_path.is_file():
        return False

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not _valid_env_key(key) or key in os.environ:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value

    return True
