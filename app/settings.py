from __future__ import annotations

import os
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from app.domain.models import ExecutionProvider, TradingMode

LIVE_CONFIRMATION_PHRASE = "I_UNDERSTAND_LIVE_TRADING"
DEFAULT_CONTEXT_GOVERNMENT_TERMS: dict[str, list[str]] = {
    "NVDA": ["NVIDIA", "advanced computing", "semiconductor", "export control"],
    "KLAC": ["KLA", "semiconductor equipment", "advanced computing", "export control"],
    "SPCX": ["SpaceX", "Starlink", "commercial space"],
}


def _parse_context_government_terms(raw: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in raw.split(";"):
        if not item.strip() or "=" not in item:
            continue
        symbol, raw_terms = item.split("=", 1)
        terms = [term.strip() for term in raw_terms.split("|") if term.strip()]
        if symbol.strip() and terms:
            result[symbol.strip().upper()] = terms
    return result


def _default_context_government_terms() -> dict[str, list[str]]:
    return {
        symbol: list(terms)
        for symbol, terms in DEFAULT_CONTEXT_GOVERNMENT_TERMS.items()
    }


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
    market_feed_retry_seconds: float = 1.0
    market_feed_retry_max_seconds: float = 30.0
    alpaca_options_feed: str = "indicative"
    options_structure_enabled: bool = True
    options_structure_refresh_seconds: float = 60.0
    options_structure_max_age_seconds: float = 120.0
    options_expiration_horizon_days: int = 45
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

    # Read-only external context is isolated from the capital-permission chain.
    # It is opt-in so upgrades do not unexpectedly start outbound source loops.
    context_intelligence_enabled: bool = False
    context_sec_poll_seconds: float = 60.0
    context_government_poll_seconds: float = 300.0
    context_government_terms: dict[str, list[str]] = Field(
        default_factory=_default_context_government_terms
    )
    context_retry_seconds: float = 2.0
    context_retry_max_seconds: float = 60.0
    context_recent_limit: int = 20

    # Continuous strategy evidence and degradation monitoring. This loop may
    # reduce/disable risk, but it never mutates strategy code/parameters or
    # promotes a strategy stage automatically.
    strategy_learning_enabled: bool = True
    strategy_improvement_interval_seconds: float = 30.0
    strategy_evaluation_horizon_seconds: float = 300.0
    strategy_transaction_cost_bps: Decimal = Decimal("10")
    strategy_modeled_entry_slippage_bps: Decimal = Decimal("0")
    strategy_modeled_exit_slippage_bps: Decimal = Decimal("0")
    strategy_degradation_min_observations: int = 30
    strategy_degradation_window_observations: int = 50
    strategy_degradation_min_expectancy_after_costs: Decimal = Decimal("0")
    strategy_degradation_max_drawdown: Decimal = Decimal("0.10")
    strategy_walk_forward_calibration_observations: int = 20
    strategy_walk_forward_holdout_observations: int = 10
    strategy_oos_min_holdout_observations: int = 20
    strategy_oos_min_completed_folds: int = 2

    # Separate operator-plane credential. It is deliberately unrelated to
    # broker credentials and only gates explicit risk-state control endpoints.
    operator_api_token: SecretStr | None = None

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

    @field_validator("context_government_terms")
    @classmethod
    def normalize_context_government_terms(
        cls,
        values: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        normalized: dict[str, list[str]] = {}
        for symbol, terms in values.items():
            clean_terms = [term.strip() for term in terms if term.strip()]
            if symbol.strip() and clean_terms:
                normalized[symbol.strip().upper()] = clean_terms
        return normalized

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

    @field_validator(
        "strategy_improvement_interval_seconds",
        "strategy_evaluation_horizon_seconds",
        "options_structure_refresh_seconds",
        "options_structure_max_age_seconds",
        "market_feed_retry_seconds",
        "market_feed_retry_max_seconds",
        "context_sec_poll_seconds",
        "context_government_poll_seconds",
        "context_retry_seconds",
        "context_retry_max_seconds",
    )
    @classmethod
    def validate_positive_runtime_seconds(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("runtime intervals must be positive")
        return value

    @field_validator("context_recent_limit")
    @classmethod
    def validate_context_recent_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("CONTEXT_RECENT_LIMIT must be positive")
        return value

    @field_validator("options_expiration_horizon_days")
    @classmethod
    def validate_options_horizon(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("OPTIONS_EXPIRATION_HORIZON_DAYS must be positive")
        return value

    @field_validator(
        "strategy_transaction_cost_bps",
        "strategy_modeled_entry_slippage_bps",
        "strategy_modeled_exit_slippage_bps",
    )
    @classmethod
    def validate_strategy_costs(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("strategy execution friction bps must be non-negative")
        return value

    @field_validator(
        "strategy_degradation_min_observations",
        "strategy_degradation_window_observations",
        "strategy_walk_forward_calibration_observations",
        "strategy_walk_forward_holdout_observations",
        "strategy_oos_min_holdout_observations",
        "strategy_oos_min_completed_folds",
    )
    @classmethod
    def validate_strategy_observation_counts(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("strategy observation counts must be positive")
        return value

    @field_validator("strategy_degradation_max_drawdown")
    @classmethod
    def validate_strategy_degradation_drawdown(cls, value: Decimal) -> Decimal:
        if value <= 0 or value > 1:
            raise ValueError("STRATEGY_DEGRADATION_MAX_DRAWDOWN must be in (0, 1]")
        return value

    @model_validator(mode="after")
    def validate_runtime_safety(self) -> Settings:
        if self.auto_trading_enabled and not self.trading_universe:
            raise ValueError("AUTO_TRADING_ENABLED requires a non-empty TRADING_UNIVERSE")
        if self.context_retry_seconds > self.context_retry_max_seconds:
            raise ValueError("CONTEXT_RETRY_SECONDS must be <= CONTEXT_RETRY_MAX_SECONDS")
        if (
            self.strategy_degradation_window_observations
            < self.strategy_degradation_min_observations
        ):
            raise ValueError(
                "STRATEGY_DEGRADATION_WINDOW_OBSERVATIONS must be >= "
                "STRATEGY_DEGRADATION_MIN_OBSERVATIONS"
            )
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
        default_government_terms = ";".join(
            f"{symbol}={'|'.join(terms)}"
            for symbol, terms in DEFAULT_CONTEXT_GOVERNMENT_TERMS.items()
        )
        context_government_terms = _parse_context_government_terms(
            os.getenv("CONTEXT_GOVERNMENT_TERMS", default_government_terms)
        )
        sec_ciks = [
            item.strip() for item in os.getenv("SEC_CIKS", "").split(",") if item.strip()
        ]
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
            market_feed_retry_seconds=float(os.getenv("MARKET_FEED_RETRY_SECONDS", "1")),
            market_feed_retry_max_seconds=float(
                os.getenv("MARKET_FEED_RETRY_MAX_SECONDS", "30")
            ),
            alpaca_options_feed=os.getenv("ALPACA_OPTIONS_FEED", "indicative").strip().lower(),
            options_structure_enabled=os.getenv("OPTIONS_STRUCTURE_ENABLED", "true").lower()
            in {"1", "true", "yes"},
            options_structure_refresh_seconds=float(
                os.getenv("OPTIONS_STRUCTURE_REFRESH_SECONDS", "60")
            ),
            options_structure_max_age_seconds=float(
                os.getenv("OPTIONS_STRUCTURE_MAX_AGE_SECONDS", "120")
            ),
            options_expiration_horizon_days=int(
                os.getenv("OPTIONS_EXPIRATION_HORIZON_DAYS", "45")
            ),
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
            context_intelligence_enabled=os.getenv(
                "CONTEXT_INTELLIGENCE_ENABLED", "false"
            ).lower()
            in {"1", "true", "yes"},
            context_sec_poll_seconds=float(os.getenv("CONTEXT_SEC_POLL_SECONDS", "60")),
            context_government_poll_seconds=float(
                os.getenv("CONTEXT_GOVERNMENT_POLL_SECONDS", "300")
            ),
            context_government_terms=context_government_terms,
            context_retry_seconds=float(os.getenv("CONTEXT_RETRY_SECONDS", "2")),
            context_retry_max_seconds=float(
                os.getenv("CONTEXT_RETRY_MAX_SECONDS", "60")
            ),
            context_recent_limit=int(os.getenv("CONTEXT_RECENT_LIMIT", "20")),
            strategy_learning_enabled=os.getenv("STRATEGY_LEARNING_ENABLED", "true").lower()
            in {"1", "true", "yes"},
            strategy_improvement_interval_seconds=float(
                os.getenv("STRATEGY_IMPROVEMENT_INTERVAL_SECONDS", "30")
            ),
            strategy_evaluation_horizon_seconds=float(
                os.getenv("STRATEGY_EVALUATION_HORIZON_SECONDS", "300")
            ),
            strategy_transaction_cost_bps=Decimal(
                os.getenv("STRATEGY_TRANSACTION_COST_BPS", "10")
            ),
            strategy_modeled_entry_slippage_bps=Decimal(
                os.getenv("STRATEGY_MODELED_ENTRY_SLIPPAGE_BPS", "0")
            ),
            strategy_modeled_exit_slippage_bps=Decimal(
                os.getenv("STRATEGY_MODELED_EXIT_SLIPPAGE_BPS", "0")
            ),
            strategy_degradation_min_observations=int(
                os.getenv("STRATEGY_DEGRADATION_MIN_OBSERVATIONS", "30")
            ),
            strategy_degradation_window_observations=int(
                os.getenv("STRATEGY_DEGRADATION_WINDOW_OBSERVATIONS", "50")
            ),
            strategy_degradation_min_expectancy_after_costs=Decimal(
                os.getenv("STRATEGY_DEGRADATION_MIN_EXPECTANCY_AFTER_COSTS", "0")
            ),
            strategy_degradation_max_drawdown=Decimal(
                os.getenv("STRATEGY_DEGRADATION_MAX_DRAWDOWN", "0.10")
            ),
            strategy_walk_forward_calibration_observations=int(
                os.getenv("STRATEGY_WALK_FORWARD_CALIBRATION_OBSERVATIONS", "20")
            ),
            strategy_walk_forward_holdout_observations=int(
                os.getenv("STRATEGY_WALK_FORWARD_HOLDOUT_OBSERVATIONS", "10")
            ),
            strategy_oos_min_holdout_observations=int(
                os.getenv("STRATEGY_OOS_MIN_HOLDOUT_OBSERVATIONS", "20")
            ),
            strategy_oos_min_completed_folds=int(
                os.getenv("STRATEGY_OOS_MIN_COMPLETED_FOLDS", "2")
            ),
            operator_api_token=(
                SecretStr(os.environ["OPERATOR_API_TOKEN"])
                if os.getenv("OPERATOR_API_TOKEN")
                else None
            ),
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
                SecretStr(os.environ["CCXT_API_KEY"])
                if os.getenv("CCXT_API_KEY")
                else None
            ),
            ccxt_secret=(
                SecretStr(os.environ["CCXT_SECRET"])
                if os.getenv("CCXT_SECRET")
                else None
            ),
            ccxt_password=(
                SecretStr(os.environ["CCXT_PASSWORD"])
                if os.getenv("CCXT_PASSWORD")
                else None
            ),
            ccxt_sandbox=os.getenv("CCXT_SANDBOX", "true").lower()
            in {"1", "true", "yes"},
            ibkr_enabled=os.getenv("IBKR_ENABLED", "false").lower()
            in {"1", "true", "yes"},
            ibkr_account_id=os.getenv("IBKR_ACCOUNT_ID") or None,
            ibkr_base_url=os.getenv("IBKR_BASE_URL", "https://localhost:5000/v1/api"),
            ibkr_verify_ssl=os.getenv("IBKR_VERIFY_SSL", "false").lower()
            in {"1", "true", "yes"},
            ibkr_paper=os.getenv("IBKR_PAPER", "true").lower()
            in {"1", "true", "yes"},
            ibkr_auto_confirm_message_ids=ibkr_auto_confirm_message_ids,
            sec_user_agent=os.getenv("SEC_USER_AGENT", "Observatory admin@example.com"),
            sec_ciks=sec_ciks,
            github_release_repositories=repositories,
        )
