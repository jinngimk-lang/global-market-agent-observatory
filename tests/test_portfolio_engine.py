from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.domain.models import PortfolioSnapshot, Position, Side
from app.portfolio.engine import PortfolioAllocator, PortfolioPolicy
from app.strategy.base import StrategyAction, StrategySignal


def signal(
    action: StrategyAction,
    *,
    symbol: str = "NVDA",
    confidence: str = "0.8",
    entry: str = "200",
    invalidation: str | None = "190",
    strategy_id: str = "test-strategy",
) -> StrategySignal:
    return StrategySignal(
        strategy_id=strategy_id,
        version="1.0.0",
        symbol=symbol,
        action=action,
        confidence=Decimal(confidence),
        rationale_codes=["test"],
        entry_price=Decimal(entry),
        invalidation_price=(Decimal(invalidation) if invalidation is not None else None),
        generated_at=datetime(2026, 8, 20, 14, 0, tzinfo=UTC),
    )


def policy() -> PortfolioPolicy:
    return PortfolioPolicy(
        risk_fraction_per_trade=Decimal("0.01"),
        max_order_notional=Decimal("5000"),
        max_group_exposure=Decimal("5000"),
        reduce_fraction=Decimal("0.5"),
        symbol_groups={
            "NVDA": "semiconductor-ai",
            "KLAC": "semiconductor-ai",
            "SPCX": "growth-tech",
        },
    )


def test_buy_quantity_is_sized_from_equity_risk_budget_and_stop_distance() -> None:
    allocator = PortfolioAllocator(policy())
    portfolio = PortfolioSnapshot(cash=Decimal("10000"))

    decision = allocator.allocate_signal(signal(StrategyAction.BUY), portfolio)

    assert decision.code == "allocated"
    assert decision.intent is not None
    assert decision.intent.side is Side.BUY
    assert decision.intent.quantity == Decimal("10")
    assert decision.risk_budget == Decimal("100")
    assert decision.requested_notional == Decimal("2000")


def test_buy_without_long_invalidation_is_rejected_before_order_intent() -> None:
    allocator = PortfolioAllocator(policy())

    decision = allocator.allocate_signal(
        signal(StrategyAction.BUY, invalidation=None),
        PortfolioSnapshot(cash=Decimal("10000")),
    )

    assert decision.intent is None
    assert decision.code == "missing_invalidation"


def test_buy_is_clamped_by_max_order_notional() -> None:
    allocator = PortfolioAllocator(
        policy().model_copy(update={"max_order_notional": Decimal("1000")})
    )

    decision = allocator.allocate_signal(
        signal(StrategyAction.BUY),
        PortfolioSnapshot(cash=Decimal("10000")),
    )

    assert decision.intent is not None
    assert decision.intent.quantity == Decimal("5")
    assert decision.requested_notional == Decimal("1000")


def test_correlated_group_exposure_resizes_new_order() -> None:
    allocator = PortfolioAllocator(
        policy().model_copy(update={"max_group_exposure": Decimal("2500")})
    )
    portfolio = PortfolioSnapshot(
        cash=Decimal("10000"),
        positions=[
            Position(
                symbol="KLAC",
                quantity=Decimal("10"),
                average_price=Decimal("190"),
                market_price=Decimal("200"),
            )
        ],
    )

    decision = allocator.allocate_signal(signal(StrategyAction.BUY), portfolio)

    assert decision.intent is not None
    assert decision.intent.quantity == Decimal("2.5")
    assert decision.requested_notional == Decimal("500")
    assert decision.code == "resized_group_exposure"


def test_no_group_capacity_rejects_new_correlated_exposure() -> None:
    allocator = PortfolioAllocator(
        policy().model_copy(update={"max_group_exposure": Decimal("2000")})
    )
    portfolio = PortfolioSnapshot(
        cash=Decimal("10000"),
        positions=[
            Position(
                symbol="KLAC",
                quantity=Decimal("10"),
                average_price=Decimal("190"),
                market_price=Decimal("200"),
            )
        ],
    )

    decision = allocator.allocate_signal(signal(StrategyAction.BUY), portfolio)

    assert decision.intent is None
    assert decision.code == "group_exposure_limit"


def test_cost_basis_does_not_change_fresh_signal_sizing() -> None:
    allocator = PortfolioAllocator(policy())
    low_cost = PortfolioSnapshot(
        cash=Decimal("10000"),
        positions=[
            Position(
                symbol="NVDA",
                quantity=Decimal("1"),
                average_price=Decimal("100"),
                market_price=Decimal("200"),
            )
        ],
    )
    high_cost = low_cost.model_copy(
        update={
            "positions": [
                Position(
                    symbol="NVDA",
                    quantity=Decimal("1"),
                    average_price=Decimal("300"),
                    market_price=Decimal("200"),
                )
            ]
        }
    )

    first = allocator.allocate_signal(signal(StrategyAction.BUY), low_cost)
    second = allocator.allocate_signal(signal(StrategyAction.BUY), high_cost)

    assert first.intent is not None
    assert second.intent is not None
    assert first.intent.quantity == second.intent.quantity
    assert first.requested_notional == second.requested_notional


def test_reduce_sells_configured_fraction_of_existing_long() -> None:
    allocator = PortfolioAllocator(policy())
    portfolio = PortfolioSnapshot(
        cash=Decimal("1000"),
        positions=[
            Position(
                symbol="NVDA",
                quantity=Decimal("6"),
                average_price=Decimal("195"),
                market_price=Decimal("200"),
            )
        ],
    )

    decision = allocator.allocate_signal(
        signal(StrategyAction.REDUCE, invalidation=None),
        portfolio,
    )

    assert decision.intent is not None
    assert decision.intent.side is Side.SELL
    assert decision.intent.quantity == Decimal("3")


def test_exit_sells_full_existing_long_position() -> None:
    allocator = PortfolioAllocator(policy())
    portfolio = PortfolioSnapshot(
        cash=Decimal("1000"),
        positions=[
            Position(
                symbol="NVDA",
                quantity=Decimal("6"),
                average_price=Decimal("195"),
                market_price=Decimal("200"),
            )
        ],
    )

    decision = allocator.allocate_signal(
        signal(StrategyAction.EXIT, invalidation=None),
        portfolio,
    )

    assert decision.intent is not None
    assert decision.intent.side is Side.SELL
    assert decision.intent.quantity == Decimal("6")


def test_hold_produces_no_order_intent() -> None:
    allocator = PortfolioAllocator(policy())

    decision = allocator.allocate_signal(
        signal(StrategyAction.HOLD, invalidation=None),
        PortfolioSnapshot(cash=Decimal("10000")),
    )

    assert decision.intent is None
    assert decision.code == "hold"


def test_same_signal_produces_stable_idempotent_client_order_id() -> None:
    allocator = PortfolioAllocator(policy())
    item = signal(StrategyAction.BUY)
    portfolio = PortfolioSnapshot(cash=Decimal("10000"))

    first = allocator.allocate_signal(item, portfolio)
    second = allocator.allocate_signal(item, portfolio)

    assert first.intent is not None
    assert second.intent is not None
    assert first.intent.client_order_id == second.intent.client_order_id


def test_risk_reducing_exit_wins_over_buy_for_same_symbol() -> None:
    allocator = PortfolioAllocator(policy())
    portfolio = PortfolioSnapshot(
        cash=Decimal("1000"),
        positions=[
            Position(
                symbol="NVDA",
                quantity=Decimal("4"),
                average_price=Decimal("195"),
                market_price=Decimal("200"),
            )
        ],
    )

    decisions = allocator.allocate(
        [
            signal(StrategyAction.BUY, confidence="0.95", strategy_id="momentum"),
            signal(StrategyAction.EXIT, confidence="0.55", invalidation=None, strategy_id="risk-exit"),
        ],
        portfolio,
    )

    assert len(decisions) == 1
    assert decisions[0].intent is not None
    assert decisions[0].intent.side is Side.SELL
    assert decisions[0].intent.quantity == Decimal("4")
