import pytest
from pydantic import SecretStr, ValidationError

from app.domain.models import TradingMode
from app.settings import Settings


def test_default_runtime_is_not_live() -> None:
    settings = Settings()

    assert settings.trading_mode is TradingMode.PAPER
    assert settings.live_execution_permitted is False


def test_broker_credentials_alone_never_enable_live_execution() -> None:
    settings = Settings(
        alpaca_api_key=SecretStr("example-key"),
        alpaca_api_secret=SecretStr("example-secret"),
    )

    assert settings.trading_mode is TradingMode.PAPER
    assert settings.live_execution_permitted is False


def test_live_mode_requires_explicit_enable_gate() -> None:
    with pytest.raises(ValidationError, match="LIVE_TRADING_ENABLED"):
        Settings(
            trading_mode=TradingMode.LIVE,
            live_trading_confirmation="I_UNDERSTAND_LIVE_TRADING",
        )


def test_live_mode_requires_exact_confirmation_phrase() -> None:
    with pytest.raises(ValidationError, match="LIVE_TRADING_CONFIRMATION"):
        Settings(
            trading_mode=TradingMode.LIVE,
            live_trading_enabled=True,
            live_trading_confirmation="yes",
        )


def test_explicit_live_configuration_can_enable_execution() -> None:
    settings = Settings(
        trading_mode=TradingMode.LIVE,
        live_trading_enabled=True,
        live_trading_confirmation="I_UNDERSTAND_LIVE_TRADING",
    )

    assert settings.live_execution_permitted is True


def test_from_env_requires_both_live_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    monkeypatch.setenv("LIVE_TRADING_CONFIRMATION", "I_UNDERSTAND_LIVE_TRADING")

    settings = Settings.from_env()

    assert settings.trading_mode is TradingMode.LIVE
    assert settings.live_execution_permitted is True
