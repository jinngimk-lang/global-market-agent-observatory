from decimal import Decimal

import pytest
from pydantic import SecretStr, ValidationError

from app.domain.models import TradingMode
from app.settings import Settings


def test_default_runtime_is_not_live_or_auto_executing() -> None:
    settings = Settings()

    assert settings.trading_mode is TradingMode.PAPER
    assert settings.live_execution_permitted is False
    assert settings.auto_trading_enabled is False


def test_default_equity_universe_and_factor_groups_are_configured() -> None:
    settings = Settings()

    assert settings.trading_universe == {"NVDA", "SPCX", "KLAC"}
    assert settings.symbol_groups["NVDA"] == "semiconductor-ai"
    assert settings.symbol_groups["KLAC"] == "semiconductor-ai"
    assert settings.symbol_groups["SPCX"] == "growth-tech"
    assert settings.risk_fraction_per_trade == Decimal("0.01")
    assert settings.reduce_fraction == Decimal("0.5")


def test_broker_credentials_alone_never_enable_live_execution() -> None:
    settings = Settings(
        alpaca_api_key=SecretStr("example-key"),
        alpaca_api_secret=SecretStr("example-secret"),
    )

    assert settings.trading_mode is TradingMode.PAPER
    assert settings.live_execution_permitted is False
    assert settings.auto_trading_enabled is False


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


def test_from_env_loads_autonomous_universe_and_portfolio_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTO_TRADING_ENABLED", "true")
    monkeypatch.setenv("TRADING_UNIVERSE", "nvda,klac,spcx")
    monkeypatch.setenv("ALPACA_MARKET_DATA_FEED", "sip")
    monkeypatch.setenv("RISK_FRACTION_PER_TRADE", "0.005")
    monkeypatch.setenv("MAX_GROUP_EXPOSURE", "12000")
    monkeypatch.setenv("REDUCE_FRACTION", "0.25")
    monkeypatch.setenv(
        "SYMBOL_GROUPS",
        "NVDA=chips,KLAC=chips,SPCX=aerospace-growth",
    )

    settings = Settings.from_env()

    assert settings.auto_trading_enabled is True
    assert settings.trading_universe == {"NVDA", "KLAC", "SPCX"}
    assert settings.alpaca_market_data_feed == "sip"
    assert settings.risk_fraction_per_trade == Decimal("0.005")
    assert settings.max_group_exposure == Decimal("12000")
    assert settings.reduce_fraction == Decimal("0.25")
    assert settings.symbol_groups == {
        "NVDA": "chips",
        "KLAC": "chips",
        "SPCX": "aerospace-growth",
    }
