from __future__ import annotations

from typing import Any

from app.broker.alpaca import AlpacaObserver
from app.broker.base import AccountObserver
from app.broker.ccxt_observer import CCXTObserver
from app.broker.ibkr import IBKRObserver
from app.settings import Settings


def build_account_observers(settings: Settings) -> list[AccountObserver]:
    observers: list[AccountObserver] = []
    if settings.alpaca_api_key and settings.alpaca_api_secret:
        observers.append(
            AlpacaObserver(
                api_key=settings.alpaca_api_key.get_secret_value(),
                api_secret=settings.alpaca_api_secret.get_secret_value(),
                base_url=settings.alpaca_base_url,
            )
        )

    if settings.ibkr_enabled:
        observers.append(
            IBKRObserver(
                account_id=settings.ibkr_account_id,
                base_url=settings.ibkr_base_url,
                verify_ssl=settings.ibkr_verify_ssl,
            )
        )

    if settings.ccxt_exchange_id:
        try:
            import ccxt  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "CCXT observer configured but ccxt is not installed; install the crypto extra"
            ) from exc
        exchange_class: Any = getattr(ccxt, settings.ccxt_exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Unknown CCXT exchange: {settings.ccxt_exchange_id}")
        config: dict[str, Any] = {"enableRateLimit": True}
        if settings.ccxt_api_key:
            config["apiKey"] = settings.ccxt_api_key.get_secret_value()
        if settings.ccxt_secret:
            config["secret"] = settings.ccxt_secret.get_secret_value()
        if settings.ccxt_password:
            config["password"] = settings.ccxt_password.get_secret_value()
        exchange = exchange_class(config)
        if settings.ccxt_sandbox and hasattr(exchange, "set_sandbox_mode"):
            exchange.set_sandbox_mode(True)
        observers.append(
            CCXTObserver(
                exchange=exchange,
                mode="sandbox-read-only" if settings.ccxt_sandbox else "live-read-only",
            )
        )
    return observers
