from __future__ import annotations

from pydantic import SecretStr

from app.api.state import ApplicationState
from app.settings import Settings


def test_context_intelligence_disabled_is_present_but_sources_fail_closed(tmp_path) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "state.db"),
            context_intelligence_enabled=False,
        )
    )

    health = state.context_intelligence.source_health()

    assert health["alpaca-news"].configured is False
    assert health["sec-edgar"].configured is False
    assert health["federal-register"].configured is False


def test_context_intelligence_enabled_configures_sec_without_broker_credentials(
    tmp_path,
) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "state.db"),
            context_intelligence_enabled=True,
            alpaca_api_key=None,
            alpaca_api_secret=None,
        )
    )

    health = state.context_intelligence.source_health()

    assert health["sec-edgar"].configured is True
    assert health["alpaca-news"].configured is False


def test_context_intelligence_uses_alpaca_credentials_only_for_news(tmp_path) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "state.db"),
            context_intelligence_enabled=True,
            alpaca_api_key=SecretStr("paper-key"),
            alpaca_api_secret=SecretStr("paper-secret"),
        )
    )

    health = state.context_intelligence.source_health()

    assert health["sec-edgar"].configured is True
    assert health["alpaca-news"].configured is True
    assert state.context_intelligence.news_stream.api_key == "paper-key"
    assert state.context_intelligence.news_stream.api_secret == "paper-secret"


def test_context_runtime_settings_are_loaded_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("CONTEXT_INTELLIGENCE_ENABLED", "true")
    monkeypatch.setenv("CONTEXT_SEC_POLL_SECONDS", "45")
    monkeypatch.setenv("CONTEXT_GOVERNMENT_POLL_SECONDS", "240")
    monkeypatch.setenv("CONTEXT_RETRY_SECONDS", "2")
    monkeypatch.setenv("CONTEXT_RETRY_MAX_SECONDS", "50")
    monkeypatch.setenv("CONTEXT_RECENT_LIMIT", "12")

    settings = Settings.from_env()

    assert settings.context_intelligence_enabled is True
    assert settings.context_sec_poll_seconds == 45
    assert settings.context_government_poll_seconds == 240
    assert settings.context_retry_seconds == 2
    assert settings.context_retry_max_seconds == 50
    assert settings.context_recent_limit == 12
