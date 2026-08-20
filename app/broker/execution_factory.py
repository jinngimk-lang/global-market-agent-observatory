from __future__ import annotations

from app.broker.alpaca import AlpacaExecutionAdapter
from app.broker.base import ExecutionAdapter
from app.broker.paper_execution import PaperExecutionAdapter
from app.domain.models import ExecutionProvider, TradingMode
from app.settings import Settings
from app.store.sqlite import SQLiteStore


def build_execution_adapter(settings: Settings, store: SQLiteStore) -> ExecutionAdapter:
    """Build the explicit execution boundary for the selected runtime mode.

    Broker credentials never select a provider or live mode implicitly.
    """

    provider = settings.execution_provider

    if provider is ExecutionProvider.PAPER:
        if settings.trading_mode is TradingMode.LIVE:
            raise ValueError("Live mode requires a live-capable execution provider.")
        if settings.trading_mode is TradingMode.BROKER_PAPER:
            raise ValueError("Broker-paper mode requires a broker execution provider.")
        return PaperExecutionAdapter.from_store(store)

    if provider is ExecutionProvider.ALPACA:
        if not settings.alpaca_api_key or not settings.alpaca_api_secret:
            raise ValueError("Alpaca credentials are required for Alpaca execution.")

        is_paper_endpoint = "paper" in settings.alpaca_base_url.lower()
        if settings.trading_mode is TradingMode.BROKER_PAPER:
            if not is_paper_endpoint:
                raise ValueError("Broker-paper mode requires the Alpaca paper endpoint.")
        elif settings.trading_mode is TradingMode.LIVE:
            if not settings.live_execution_permitted:
                raise ValueError("Live Alpaca execution is not explicitly permitted.")
            if is_paper_endpoint:
                raise ValueError("Live mode requires the Alpaca live endpoint.")
        else:
            raise ValueError("Alpaca execution requires broker-paper or live trading mode.")

        return AlpacaExecutionAdapter(
            api_key=settings.alpaca_api_key.get_secret_value(),
            api_secret=settings.alpaca_api_secret.get_secret_value(),
            base_url=settings.alpaca_base_url,
        )

    if provider is ExecutionProvider.IBKR:
        raise ValueError("IBKR execution adapter is not wired yet.")

    raise ValueError(f"Unsupported execution provider: {provider}")
