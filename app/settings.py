from __future__ import annotations

import os
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from app.domain.models import ExecutionProvider, TradingMode

LIVE_CONFIRMATION_PHRASE = "I_UNDERSTAND_LIVE_TRADING"


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_name: str = "Global Market Autonomous Trading Platform"
    database_path: str = "data/observatory.db"
    trading_mode: TradingMode = TradingMode.PAPER
    execution_provider: ExecutionProvider = ExecutionProvider.PAPER
    auto_trading_enabled: bool = False
    trading_universe: set[str] = Field(default_factory=lambda: {"NVDA", "SPCX", "KLAC"})
    symbol_groups: dict[str, str] = Field(
        default_factory=lambda: {
            "NVDA": "semiconductor-ai",
            "KLAC": "semiconductor-ai",
            "SPCX": "growth-tech",
        }
    )
    risk_fraction_per_trade: Decimal = Decimal("0.01")
    max_group_exposure: Decimal = Decimal("25000")
    reduce_fraction: Decimal = Decimal("0.5")
    market_source: str = "replay"
    market_symbol: str = "BTCUSDT"
    market_interval: str = "1m"
    alpaca_market_data_feed: str = "iex"
    replay_delay_seconds: float = 0.4
    replay_seed: int = 42
    starting_cash: Decimal = Decimal("100000")
    allowed_symbols: set[str] = Field(
        default_factory=lambda: {"NVDA", "SPCX", "KLAC", "BTCUSDT", "ETHUSDT"}
    )
    max_order_notional: Decimal = Decimal("10000")
    max_symbol_exposure: Decimal = Decimal("25000")
    max_gross_exposure: Decimal = Decimal("50000")
    daily_loss_limit: Decimal = Decimal("2000")
    max_portfolio_drawdown: Decimal = Decimal("5000")
    market_data_max_age_seconds: float = 5.0
    account_state_max_age_seconds: float = 30.0
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
    ibkr_paper: bool = True
    ibkr_auto_confirm_message_ids: set[str] = Field(default_factory=set)
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

    @field_validator("allowed_symbols", "trading_universe")
    @classmethod
    def normalize_symbol_sets(cls, values: set[str]) -> set[str]:
        return {value.strip().upper() for value in values if value.strip()}

    @field_validator("symbol_groups")
    @classmethod
    def normalize_symbol_groups(cls, values: dict[str, str]) -> dict[str, str]:
        return {
            symbol.strip().upper(): group.strip()
            for symbol, group in values.items()
            if symbol.strip() and group.strip()
        }

    @field_validator("risk_fraction_per_trade", "reduce_fraction")
    @classmethod
    def validate_fraction(cls, value: Decimal) -> Decimal:
        if value <= 0 or value > 1:
            raise ValueError("portfolio fractions must be in (0, 1]")
        return value

    @field_validator("max_group_exposure")
    @classmethod
    def validate_group_exposure(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("MAX_GROUP_EXPOSURE must be positive")
        return value

    @model_validator(mode="after")
    def validate_runtime_safety(self) -> Settings:
        if self.auto_trading_enabled and not self.trading_universe:
            raise ValueError("AUTO_TRADING_ENABLED requires a non-empty TRADING_UNIVERSE")
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
            for item in os.getenv(
                "ALLOWED_SYMBOLS",
                "NVDA,SPCX,KLAC,BTCUSDT,ETHUSDT",
            ).split(",")
            if item.strip()
        }
        trading_universe = {
            item.strip().upper()
            for item in os.getenv("TRADING_UNIVERSE", "NVDA,SPCX,KLAC").split(",")
            if item.strip()
        }
        symbol_groups: dict[str, str] = {}
        raw_groups = os.getenv(
            "SYMBOL_GROUPS",
            "NVDA=semiconductor-ai,KLAC=semiconductor-ai,SPCX=growth-tech",
        )
        for item in raw_groups.split(","):
            if not item.strip() or "=" not in item:
                continue
            symbol, group = item.split("=", 1)
            if symbol.strip() and group.strip():
                symbol_groups[symbol.strip().upper()] = group.strip()
        sec_ciks = [item.strip() for item in os.getenv("SEC_CIKS", "").split(",") if item.strip()]
        ibkr_auto_confirm_message_ids = {
            item.strip()
            for item in os.getenv("IBKR_AUTO_CONFIRM_MESSAGE_IDS", "").split(",")
            if item.strip()
        }
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
            execution_provider=os.getenv(
                "EXECUTION_PROVIDER", ExecutionProvider.PAPER.value
            ).strip().lower(),
            auto_trading_enabled=os.getenv("AUTO_TRADING_ENABLED", "false").lower()
            in {"1", "true", "yes"},
            trading_universe=trading_universe,
            symbol_groups=symbol_groups,
            risk_fraction_per_trade=Decimal(os.getenv("RISK_FRACTION_PER_TRADE", "0.01")),
            max_group_exposure=Decimal(os.getenv("MAX_GROUP_EXPOSURE", "25000")),
            reduce_fraction=Decimal(os.getenv("REDUCE_FRACTION", "0.5")),
            market_source=os.getenv("MARKET_SOURCE", "replay").strip().lower(),
            market_symbol=os.getenv("MARKET_SYMBOL", "BTCUSDT"),
            market_interval=os.getenv("MARKET_INTERVAL", "1m"),
            alpaca_market_data_feed=os.getenv("ALPACA_MARKET_DATA_FEED", "iex").strip().lower(),
            replay_delay_seconds=float(os.getenv("REPLAY_DELAY_SECONDS", "0.4")),
            replay_seed=int(os.getenv("REPLAY_SEED", "42")),
            starting_cash=Decimal(os.getenv("STARTING_CASH", "100000")),
            allowed_symbols=allowed_symbols,
            max_order_notional=Decimal(os.getenv("MAX_ORDER_NOTIONAL", "10000")),
            max_symbol_exposure=Decimal(os.getenv("MAX_SYMBOL_EXPOSURE", "25000")),
            max_gross_exposure=Decimal(os.getenv("MAX_GROSS_EXPOSURE", "50000")),
            daily_loss_limit=Decimal(os.getenv("DAILY_LOSS_LIMIT", "2000")),
            max_portfolio_drawdown=Decimal(os.getenv("MAX_PORTFOLIO_DRAWDOWN", "5000")),
            market_data_max_age_seconds=float(os.getenv("MARKET_DATA_MAX_AGE_SECONDS", "5")),
            account_state_max_age_seconds=float(os.getenv("ACCOUNT_STATE_MAX_AGE_SECONDS", "30")),
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
            ibkr_paper=os.getenv("IBKR_PAPER", "true").lower() in {"1", "true", "yes"},
            ibkr_auto_confirm_message_ids=ibkr_auto_confirm_message_ids,
            sec_user_agent=os.getenv("SEC_USER_AGENT", "Observatory admin@example.com"),
            sec_ciks=sec_ciks,
            github_release_repositories=repositories,
        )
