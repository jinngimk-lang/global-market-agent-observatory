from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import SecretStr

from app.broker.alpaca import AlpacaExecutionAdapter
from app.broker.execution_factory import build_execution_adapter
from app.broker.paper_execution import PaperExecutionAdapter
from app.domain.models import ExecutionProvider, OrderIntent, OrderStatus, Side, TradingMode
from app.settings import Settings
from app.store.sqlite import SQLiteStore


def make_store(tmp_path) -> SQLiteStore:
    return SQLiteStore(tmp_path / "execution.db", starting_cash="10000")


def test_default_execution_provider_is_local_paper(tmp_path) -> None:
    settings = Settings()

    adapter = build_execution_adapter(settings, make_store(tmp_path))

    assert isinstance(adapter, PaperExecutionAdapter)


@pytest.mark.asyncio
async def test_local_paper_adapter_executes_through_common_contract(tmp_path) -> None:
    adapter = PaperExecutionAdapter.from_store(make_store(tmp_path))
    intent = OrderIntent(
        client_order_id="paper-nvda-1",
        symbol="NVDA",
        side=Side.BUY,
        quantity=Decimal("2"),
        reference_price=Decimal("200"),
    )

    result = await adapter.submit(intent)
    duplicate = await adapter.get_order_by_client_id(intent.client_order_id)

    assert result.status is OrderStatus.FILLED
    assert result.filled_price == Decimal("200")
    assert duplicate == result


def test_broker_paper_alpaca_requires_credentials(tmp_path) -> None:
    settings = Settings(
        trading_mode=TradingMode.BROKER_PAPER,
        execution_provider=ExecutionProvider.ALPACA,
    )

    with pytest.raises(ValueError, match="Alpaca credentials"):
        build_execution_adapter(settings, make_store(tmp_path))


def test_broker_paper_builds_alpaca_adapter_with_paper_endpoint(tmp_path) -> None:
    settings = Settings(
        trading_mode=TradingMode.BROKER_PAPER,
        execution_provider=ExecutionProvider.ALPACA,
        alpaca_api_key=SecretStr("key"),
        alpaca_api_secret=SecretStr("secret"),
        alpaca_base_url="https://paper-api.alpaca.markets",
    )

    adapter = build_execution_adapter(settings, make_store(tmp_path))

    assert isinstance(adapter, AlpacaExecutionAdapter)


def test_broker_paper_rejects_non_paper_alpaca_endpoint(tmp_path) -> None:
    settings = Settings(
        trading_mode=TradingMode.BROKER_PAPER,
        execution_provider=ExecutionProvider.ALPACA,
        alpaca_api_key=SecretStr("key"),
        alpaca_api_secret=SecretStr("secret"),
        alpaca_base_url="https://api.alpaca.markets",
    )

    with pytest.raises(ValueError, match="paper endpoint"):
        build_execution_adapter(settings, make_store(tmp_path))


def test_live_mode_rejects_local_paper_execution_provider(tmp_path) -> None:
    settings = Settings(
        trading_mode=TradingMode.LIVE,
        execution_provider=ExecutionProvider.PAPER,
        live_trading_enabled=True,
        live_trading_confirmation="I_UNDERSTAND_LIVE_TRADING",
    )

    with pytest.raises(ValueError, match="live-capable execution provider"):
        build_execution_adapter(settings, make_store(tmp_path))


def test_live_alpaca_rejects_paper_endpoint(tmp_path) -> None:
    settings = Settings(
        trading_mode=TradingMode.LIVE,
        execution_provider=ExecutionProvider.ALPACA,
        live_trading_enabled=True,
        live_trading_confirmation="I_UNDERSTAND_LIVE_TRADING",
        alpaca_api_key=SecretStr("key"),
        alpaca_api_secret=SecretStr("secret"),
        alpaca_base_url="https://paper-api.alpaca.markets",
    )

    with pytest.raises(ValueError, match="live endpoint"):
        build_execution_adapter(settings, make_store(tmp_path))


def test_explicit_live_alpaca_configuration_builds_live_adapter(tmp_path) -> None:
    settings = Settings(
        trading_mode=TradingMode.LIVE,
        execution_provider=ExecutionProvider.ALPACA,
        live_trading_enabled=True,
        live_trading_confirmation="I_UNDERSTAND_LIVE_TRADING",
        alpaca_api_key=SecretStr("key"),
        alpaca_api_secret=SecretStr("secret"),
        alpaca_base_url="https://api.alpaca.markets",
    )

    adapter = build_execution_adapter(settings, make_store(tmp_path))

    assert isinstance(adapter, AlpacaExecutionAdapter)
