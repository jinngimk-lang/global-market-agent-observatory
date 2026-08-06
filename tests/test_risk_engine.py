from decimal import Decimal

from app.domain.models import OrderIntent, PortfolioSnapshot, Position, RiskLimits, Side
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
