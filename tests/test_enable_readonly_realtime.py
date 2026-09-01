from __future__ import annotations

from pathlib import Path

import pytest

from scripts.enable_readonly_realtime import enable_readonly_realtime


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_enable_readonly_realtime_preserves_secrets_and_disables_execution(tmp_path) -> None:
    env = tmp_path / ".env"
    _write(
        env,
        "\n".join(
            [
                "TRADING_MODE=paper",
                "EXECUTION_PROVIDER=paper",
                "AUTO_TRADING_ENABLED=false",
                "MARKET_SOURCE=replay",
                "CONTEXT_INTELLIGENCE_ENABLED=false",
                "ALPACA_API_KEY=local-key",
                "ALPACA_API_SECRET=local-secret",
                "CUSTOM_SETTING=keep-me",
                "",
            ]
        ),
    )

    backup = enable_readonly_realtime(env)

    content = env.read_text(encoding="utf-8")
    assert "TRADING_MODE=paper" in content
    assert "EXECUTION_PROVIDER=paper" in content
    assert "AUTO_TRADING_ENABLED=false" in content
    assert "MARKET_SOURCE=alpaca" in content
    assert "CONTEXT_INTELLIGENCE_ENABLED=true" in content
    assert "ALPACA_API_KEY=local-key" in content
    assert "ALPACA_API_SECRET=local-secret" in content
    assert "CUSTOM_SETTING=keep-me" in content
    assert backup.exists()
    assert "MARKET_SOURCE=replay" in backup.read_text(encoding="utf-8")


def test_enable_readonly_realtime_refuses_live_configuration(tmp_path) -> None:
    env = tmp_path / ".env"
    original = "\n".join(
        [
            "TRADING_MODE=live",
            "LIVE_TRADING_ENABLED=true",
            "ALPACA_API_KEY=local-key",
            "ALPACA_API_SECRET=local-secret",
            "",
        ]
    )
    _write(env, original)

    with pytest.raises(RuntimeError, match="live"):
        enable_readonly_realtime(env)

    assert env.read_text(encoding="utf-8") == original


def test_enable_readonly_realtime_requires_local_alpaca_credentials(tmp_path) -> None:
    env = tmp_path / ".env"
    original = "TRADING_MODE=paper\nMARKET_SOURCE=replay\n"
    _write(env, original)

    with pytest.raises(RuntimeError, match="Alpaca"):
        enable_readonly_realtime(env)

    assert env.read_text(encoding="utf-8") == original
