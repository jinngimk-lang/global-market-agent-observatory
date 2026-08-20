from __future__ import annotations

import os
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from app.domain.models import TradingMode

LIVE_CONFIRMATION_PHRASE = "I_UNDERSTAND_LIVE_TRADING"


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_name: str = "Global Market Autonomous Trading Platform"
    database_path: str = "data/observatory.db"
    trading_mode: TradingMode = TradingMode.PAPER
    market_source: str = "replay"
    market_symbol: str = "BTCUSDT"
    market_interval: str = "1m"
    replay_delay_seconds: float = 0.4
    replay_seed: int = 42
    starting_cash: Decimal = Decimal("100000")
    allowed_symbols: set[str] = Field(default_factory=lambda: {"BTCUSDT", "ETHUSDT"})
    max_order_notional: Decimal = Decimal("10000")
    max_gross_exposure: Decimal = Decimal("50000")
    daily_loss_limit: Decimal = Decimal("2000")
    live_trading_enabled: bool = False
    live_trading_confirmation: str | None = None
    account_poll_seconds: float = 15.0
    alpaca_api_key: SecretStr | None = None
    alpaca_api_secret: SecretStr | None = None
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    ccxt_exchange_id: str | None = None
    ccxt_api_key: SecretStr | None = None
    ccxt_secret: SecretStr | None = None
    ccxt_password: SecretStr | None = None
    ccxt_sandbox: bool = True
    ibkr_enabled: bool = False
    ibkr_account_id: str | None = None
    ibkr_base_url: str = "https://localhost:5000/v1/api"
    ibkr_verify_ssl: bool = False
    sec_user_agent: str = "Observatory admin@example.com"
    sec_ciks: list[str] = Field(default_factory=list)
    github_release_repositories: list[str] = Field(
        default_factory=lambda: [
            "ccxt/ccxt",
            "freqtrade/freqtrade",
            "hummingbot/hummingbot",
            "QuantConnect/Lean",
            "nautechsystems/nautilus_trader",
        ]
    )

    @field_validator("market_symbol")
    @classmethod
    def normalize_market_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("allowed_symbols")
    @classmethod
    def normalize_allowed_symbols(cls, values: set[str]) -> set[str]:
        return {value.strip().upper() for value in values}

    @model_validator(mode="after")
    def validate_live_execution_gate(self) -> Settings:
        if self.trading_mode is not TradingMode.LIVE:
            return self
        if not self.live_trading_enabled:
            raise ValueError("TRADING_MODE=live requires LIVE_TRADING_ENABLED=true")
        if self.live_trading_confirmation != LIVE_CONFIRMATION_PHRASE:
            raise ValueError(
                "TRADING_MODE=live requires "
                "LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_TRADING"
            )
        return self

    @property
    def live_execution_permitted(self) -> bool:
        return (
            self.trading_mode is TradingMode.LIVE
            and self.live_trading_enabled
            and self.live_trading_confirmation == LIVE_CONFIRMATION_PHRASE
        )

    @classmethod
    def from_env(cls) -> Settings:
        allowed_symbols = {
            item.strip().upper()
            for item in os.getenv("ALLOWED_SYMBOLS", "BTCUSDT,ETHUSDT").split(",")
            if item.strip()
        }
        sec_ciks = [item.strip() for item in os.getenv("SEC_CIKS", "").split(",") if item.strip()]
        repositories = [
            item.strip()
            for item in os.getenv(
                "GITHUB_RELEASE_REPOSITORIES",
                (
                    "ccxt/ccxt,freqtrade/freqtrade,hummingbot/hummingbot,"
                    "QuantConnect/Lean,nautechsystems/nautilus_trader"
                ),
            ).split(",")
            if item.strip()
        ]
        return cls(
            database_path=os.getenv("DATABASE_PATH", "data/observatory.db"),
            trading_mode=os.getenv("TRADING_MODE", TradingMode.PAPER.value).strip().lower(),
            market_source=os.getenv("MARKET_SOURCE", "replay").strip().lower(),
            market_symbol=os.getenv("MARKET_SYMBOL", "BTCUSDT"),
            market_interval=os.getenv("MARKET_INTERVAL", "1m"),
            replay_delay_seconds=float(os.getenv("REPLAY_DELAY_SECONDS", "0.4")),
            replay_seed=int(os.getenv("REPLAY_SEED", "42")),
            starting_cash=Decimal(os.getenv("STARTING_CASH", "100000")),
            allowed_symbols=allowed_symbols,
            max_order_notional=Decimal(os.getenv("MAX_ORDER_NOTIONAL", "10000")),
            max_gross_exposure=Decimal(os.getenv("MAX_GROSS_EXPOSURE", "50000")),
            daily_loss_limit=Decimal(os.getenv("DAILY_LOSS_LIMIT", "2000")),
            live_trading_enabled=os.getenv("LIVE_TRADING_ENABLED", "false").lower()
            in {"1", "true", "yes"},
            live_trading_confirmation=os.getenv("LIVE_TRADING_CONFIRMATION") or None,
            account_poll_seconds=float(os.getenv("ACCOUNT_POLL_SECONDS", "15")),
            alpaca_api_key=(
                SecretStr(os.environ["ALPACA_API_KEY"])
                if os.getenv("ALPACA_API_KEY")
                else None
            ),
            alpaca_api_secret=(
                SecretStr(os.environ["ALPACA_API_SECRET"])
                if os.getenv("ALPACA_API_SECRET")
                else None
            ),
            alpaca_base_url=os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
            ccxt_exchange_id=os.getenv("CCXT_EXCHANGE_ID") or None,
            ccxt_api_key=(
                SecretStr(os.environ["CCXT_API_KEY"]) if os.getenv("CCXT_API_KEY") else None
            ),
            ccxt_secret=SecretStr(os.environ["CCXT_SECRET"]) if os.getenv("CCXT_SECRET") else None,
            ccxt_password=(
                SecretStr(os.environ["CCXT_PASSWORD"])
                if os.getenv("CCXT_PASSWORD")
                else None
            ),
            ccxt_sandbox=os.getenv("CCXT_SANDBOX", "true").lower() in {"1", "true", "yes"},
            ibkr_enabled=os.getenv("IBKR_ENABLED", "false").lower() in {"1", "true", "yes"},
            ibkr_account_id=os.getenv("IBKR_ACCOUNT_ID") or None,
            ibkr_base_url=os.getenv("IBKR_BASE_URL", "https://localhost:5000/v1/api"),
            ibkr_verify_ssl=os.getenv("IBKR_VERIFY_SSL", "false").lower() in {"1", "true", "yes"},
            sec_user_agent=os.getenv("SEC_USER_AGENT", "Observatory admin@example.com"),
            sec_ciks=sec_ciks,
            github_release_repositories=repositories,
        )
