from __future__ import annotations

import os
from pathlib import Path

from app.local_env import load_local_env


def test_load_local_env_reads_quoted_and_plain_values(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("LOCAL_ENV_TEST_SOURCE", raising=False)
    monkeypatch.delenv("LOCAL_ENV_TEST_SECRET", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LOCAL_ENV_TEST_SOURCE=alpaca\n"
        'LOCAL_ENV_TEST_SECRET="example-secret"\n',
        encoding="utf-8",
    )

    assert load_local_env(env_file) is True
    assert os.environ["LOCAL_ENV_TEST_SOURCE"] == "alpaca"
    assert os.environ["LOCAL_ENV_TEST_SECRET"] == "example-secret"


def test_load_local_env_never_overrides_process_environment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LOCAL_ENV_TEST_SOURCE", "process-value")
    env_file = tmp_path / ".env"
    env_file.write_text("LOCAL_ENV_TEST_SOURCE=file-value\n", encoding="utf-8")

    assert load_local_env(env_file) is True
    assert os.environ["LOCAL_ENV_TEST_SOURCE"] == "process-value"


def test_load_local_env_is_noop_when_file_is_missing(tmp_path: Path) -> None:
    assert load_local_env(tmp_path / "missing.env") is False
