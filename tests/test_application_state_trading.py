from __future__ import annotations

from pydantic import SecretStr

from app.api.state import ApplicationState
from app.broker.alpaca import AlpacaExecutionAdapter
from app.broker.paper_execution import PaperExecutionAdapter
from app.domain.models import ExecutionProvider, TradingMode
from app.market.alpaca import AlpacaStockBarFeed
from app.settings import Settings
from app.trading.portfolio_source import BrokerPortfolioSource, LocalPaperPortfolioSource


def test_default_application_state_uses_controlled_local_paper_execution(tmp_path) -> None:
    state = ApplicationState(Settings(database_path=str(tmp_path / "app.db")))

    assert isinstance(state.execution_adapter, PaperExecutionAdapter)
    assert isinstance(state.portfolio_source, LocalPaperPortfolioSource)
    assert state.autonomous.execution_enabled is False
    assert state.trading_state.value == "active"


def test_alpaca_market_source_streams_configured_equity_universe(tmp_path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "app.db"),
        market_source="alpaca",
        trading_universe={"NVDA", "KLAC", "SPCX"},
        alpaca_api_key=SecretStr("key"),
        alpaca_api_secret=SecretStr("secret"),
        alpaca_market_data_feed="iex",
    )

    state = ApplicationState(settings)

    assert isinstance(state.feed, AlpacaStockBarFeed)
    assert state.feed.symbols == {"NVDA", "KLAC", "SPCX"}
    assert state.feed.feed == "iex"


def test_auto_trading_flag_cannot_bypass_strategy_promotion_gate(tmp_path) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "app.db"),
            auto_trading_enabled=True,
        )
    )

    assert state.settings.auto_trading_enabled is True
    assert state.promotion_execution_allowed is False
    assert state.autonomous.execution_enabled is False


def test_alpaca_broker_paper_uses_broker_authoritative_portfolio_source(tmp_path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "app.db"),
        trading_mode=TradingMode.BROKER_PAPER,
        execution_provider=ExecutionProvider.ALPACA,
        alpaca_api_key=SecretStr("key"),
        alpaca_api_secret=SecretStr("secret"),
        alpaca_base_url="https://paper-api.alpaca.markets",
    )

    state = ApplicationState(settings)

    assert isinstance(state.execution_adapter, AlpacaExecutionAdapter)
    assert isinstance(state.portfolio_source, BrokerPortfolioSource)


def test_legacy_paper_broker_is_never_replaced_by_live_execution_adapter(tmp_path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "app.db"),
        trading_mode=TradingMode.LIVE,
        execution_provider=ExecutionProvider.ALPACA,
        live_trading_enabled=True,
        live_trading_confirmation="I_UNDERSTAND_LIVE_TRADING",
        alpaca_api_key=SecretStr("key"),
        alpaca_api_secret=SecretStr("secret"),
        alpaca_base_url="https://api.alpaca.markets",
    )

    state = ApplicationState(settings)

    assert isinstance(state.execution_adapter, AlpacaExecutionAdapter)
    assert state.broker.snapshot().mode == "paper"
