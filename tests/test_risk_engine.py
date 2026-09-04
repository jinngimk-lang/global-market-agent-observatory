from decimal import Decimal

from app.domain.models import (
    OrderIntent,
    PortfolioSnapshot,
    Position,
    RiskContext,
    RiskLimits,
    Side,
    TradingState,
)
from app.risk.engine import RiskEngine


def make_intent(
    symbol: str = "BTCUSDT",
    side: Side = Side.BUY,
    quantity: str = "1",
    price: str = "100",
) -> OrderIntent:
    return OrderIntent(
        client_order_id="test-1",
        symbol=symbol,
        side=side,
        quantity=Decimal(quantity),
        reference_price=Decimal(price),
    )


def test_rejects_symbol_outside_allowlist() -> None:
    engine = RiskEngine(RiskLimits(allowed_symbols={"ETHUSDT"}))

    decision = engine.evaluate(make_intent(), PortfolioSnapshot(cash=Decimal("10000")))

    assert decision.allowed is False
    assert decision.code == "symbol_not_allowed"


def test_rejects_non_positive_quantity() -> None:
    engine = RiskEngine(RiskLimits(allowed_symbols={"BTCUSDT"}))

    decision = engine.evaluate(make_intent(quantity="0"), PortfolioSnapshot(cash=Decimal("10000")))

    assert decision.allowed is False
    assert decision.code == "invalid_quantity"


def test_rejects_order_above_notional_limit() -> None:
    engine = RiskEngine(
        RiskLimits(allowed_symbols={"BTCUSDT"}, max_order_notional=Decimal("99"))
    )

    decision = engine.evaluate(make_intent(), PortfolioSnapshot(cash=Decimal("10000")))

    assert decision.allowed is False
    assert decision.code == "order_notional_limit"


def test_rejects_projected_gross_exposure() -> None:
    engine = RiskEngine(
        RiskLimits(
            allowed_symbols={"BTCUSDT", "ETHUSDT"},
            max_order_notional=Decimal("10000"),
            max_gross_exposure=Decimal("150"),
        )
    )
    portfolio = PortfolioSnapshot(
        cash=Decimal("10000"),
        positions=[
            Position(
                symbol="ETHUSDT",
                quantity=Decimal("1"),
                average_price=Decimal("100"),
                market_price=Decimal("100"),
            )
        ],
    )

    decision = engine.evaluate(make_intent(), portfolio)

    assert decision.allowed is False
    assert decision.code == "gross_exposure_limit"


def test_sell_reducing_a_long_position_is_allowed() -> None:
    engine = RiskEngine(
        RiskLimits(
            allowed_symbols={"BTCUSDT"},
            max_order_notional=Decimal("1000"),
            max_gross_exposure=Decimal("100"),
        )
    )
    portfolio = PortfolioSnapshot(
        cash=Decimal("10000"),
        positions=[
            Position(
                symbol="BTCUSDT",
                quantity=Decimal("1"),
                average_price=Decimal("100"),
                market_price=Decimal("100"),
            )
        ],
    )

    decision = engine.evaluate(make_intent(side=Side.SELL, quantity="0.5"), portfolio)

    assert decision.allowed is True
    assert decision.code == "approved"


def test_reducing_exit_is_not_blocked_by_loss_or_drawdown_lockouts() -> None:
    engine = RiskEngine(
        RiskLimits(
            allowed_symbols={"BTCUSDT"},
            daily_loss_limit=Decimal("500"),
            max_portfolio_drawdown=Decimal("1000"),
        )
    )
    portfolio = PortfolioSnapshot(
        cash=Decimal("10000"),
        realized_pnl_today=Decimal("-500"),
        positions=[
            Position(
                symbol="BTCUSDT",
                quantity=Decimal("1"),
                average_price=Decimal("100"),
                market_price=Decimal("100"),
            )
        ],
    )

    decision = engine.evaluate(
        make_intent(side=Side.SELL, quantity="1"),
        portfolio,
        RiskContext(
            trading_state=TradingState.REDUCING,
            portfolio_drawdown=Decimal("1000"),
        ),
    )

    assert decision.allowed is True
    assert decision.code == "approved"


def test_reducing_exit_can_exceed_new_risk_notional_and_gross_bounds() -> None:
    engine = RiskEngine(
        RiskLimits(
            allowed_symbols={"BTCUSDT", "ETHUSDT"},
            max_order_notional=Decimal("50"),
            max_symbol_exposure=Decimal("50"),
            max_gross_exposure=Decimal("50"),
        )
    )
    portfolio = PortfolioSnapshot(
        cash=Decimal("10000"),
        positions=[
            Position(
                symbol="BTCUSDT",
                quantity=Decimal("1"),
                average_price=Decimal("100"),
                market_price=Decimal("100"),
            ),
            Position(
                symbol="ETHUSDT",
                quantity=Decimal("1"),
                average_price=Decimal("100"),
                market_price=Decimal("100"),
            ),
        ],
    )

    decision = engine.evaluate(
        make_intent(side=Side.SELL, quantity="1"),
        portfolio,
        RiskContext(trading_state=TradingState.REDUCING),
    )

    assert decision.allowed is True
    assert decision.code == "approved"
    assert decision.projected_gross_exposure == Decimal("100")


def test_reducing_state_rejects_position_reversal() -> None:
    engine = RiskEngine(RiskLimits(allowed_symbols={"BTCUSDT"}))
    portfolio = PortfolioSnapshot(
        cash=Decimal("10000"),
        positions=[
            Position(
                symbol="BTCUSDT",
                quantity=Decimal("1"),
                average_price=Decimal("100"),
                market_price=Decimal("100"),
            )
        ],
    )

    decision = engine.evaluate(
        make_intent(side=Side.SELL, quantity="2"),
        portfolio,
        RiskContext(trading_state=TradingState.REDUCING),
    )

    assert decision.allowed is False
    assert decision.code == "reducing_only"


def test_rejects_after_daily_loss_limit_is_reached() -> None:
    engine = RiskEngine(
        RiskLimits(allowed_symbols={"BTCUSDT"}, daily_loss_limit=Decimal("500"))
    )
    portfolio = PortfolioSnapshot(
        cash=Decimal("10000"), realized_pnl_today=Decimal("-500")
    )

    decision = engine.evaluate(make_intent(), portfolio)

    assert decision.allowed is False
    assert decision.code == "daily_loss_lockout"


def test_rejects_projected_symbol_exposure() -> None:
    engine = RiskEngine(
        RiskLimits(
            allowed_symbols={"BTCUSDT"},
            max_order_notional=Decimal("10000"),
            max_symbol_exposure=Decimal("150"),
            max_gross_exposure=Decimal("50000"),
        )
    )

    decision = engine.evaluate(
        make_intent(quantity="2", price="100"),
        PortfolioSnapshot(cash=Decimal("10000")),
    )

    assert decision.allowed is False
    assert decision.code == "symbol_exposure_limit"


def test_rejects_stale_market_data() -> None:
    engine = RiskEngine(
        RiskLimits(allowed_symbols={"BTCUSDT"}, market_data_max_age_seconds=5.0)
    )

    decision = engine.evaluate(
        make_intent(),
        PortfolioSnapshot(cash=Decimal("10000")),
        RiskContext(market_data_age_seconds=5.1),
    )

    assert decision.allowed is False
    assert decision.code == "stale_market_data"


def test_rejects_stale_account_state() -> None:
    engine = RiskEngine(
        RiskLimits(allowed_symbols={"BTCUSDT"}, account_state_max_age_seconds=30.0)
    )

    decision = engine.evaluate(
        make_intent(),
        PortfolioSnapshot(cash=Decimal("10000")),
        RiskContext(account_state_age_seconds=31.0),
    )

    assert decision.allowed is False
    assert decision.code == "stale_account_state"


def test_halted_risk_context_blocks_orders() -> None:
    engine = RiskEngine(RiskLimits(allowed_symbols={"BTCUSDT"}))

    decision = engine.evaluate(
        make_intent(),
        PortfolioSnapshot(cash=Decimal("10000")),
        RiskContext(trading_state=TradingState.HALTED),
    )

    assert decision.allowed is False
    assert decision.code == "trading_halted"


def test_reducing_context_rejects_exposure_increase() -> None:
    engine = RiskEngine(RiskLimits(allowed_symbols={"BTCUSDT"}))

    decision = engine.evaluate(
        make_intent(),
        PortfolioSnapshot(cash=Decimal("10000")),
        RiskContext(trading_state=TradingState.REDUCING),
    )

    assert decision.allowed is False
    assert decision.code == "reducing_only"


def test_drawdown_lockout_blocks_new_orders() -> None:
    engine = RiskEngine(
        RiskLimits(
            allowed_symbols={"BTCUSDT"},
            max_portfolio_drawdown=Decimal("1000"),
        )
    )

    decision = engine.evaluate(
        make_intent(),
        PortfolioSnapshot(cash=Decimal("10000")),
        RiskContext(portfolio_drawdown=Decimal("1000")),
    )

    assert decision.allowed is False
    assert decision.code == "portfolio_drawdown_lockout"
