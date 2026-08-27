from decimal import Decimal

import pytest

from app.domain.models import (
    OrderIntent,
    OrderStatus,
    PortfolioSnapshot,
    Position,
    RiskLimits,
    Side,
    TradingState,
)
from app.execution.controller import ExecutionController
from app.execution.models import ExecutionResult
from app.risk.engine import RiskEngine


class FakeExecutionAdapter:
    name = "fake"

    def __init__(self) -> None:
        self.submit_calls = 0
        self.existing: dict[str, ExecutionResult] = {}

    async def get_order_by_client_id(self, client_order_id: str) -> ExecutionResult | None:
        return self.existing.get(client_order_id)

    async def submit(self, intent: OrderIntent) -> ExecutionResult:
        self.submit_calls += 1
        result = ExecutionResult(
            client_order_id=intent.client_order_id,
            broker_order_id=f"broker-{self.submit_calls}",
            status=OrderStatus.ACCEPTED,
            message="accepted",
        )
        self.existing[intent.client_order_id] = result
        return result

    async def cancel(self, broker_order_id: str) -> ExecutionResult:
        return ExecutionResult(
            client_order_id="cancelled",
            broker_order_id=broker_order_id,
            status=OrderStatus.REJECTED,
            message="cancelled",
        )


def make_intent(
    *,
    client_order_id: str = "intent-1",
    symbol: str = "NVDA",
    side: Side = Side.BUY,
    quantity: str = "1",
    price: str = "200",
) -> OrderIntent:
    return OrderIntent(
        client_order_id=client_order_id,
        symbol=symbol,
        side=side,
        quantity=Decimal(quantity),
        reference_price=Decimal(price),
    )


def make_controller(
    adapter: FakeExecutionAdapter,
    *,
    state: TradingState = TradingState.ACTIVE,
    allowed_symbols: set[str] | None = None,
) -> ExecutionController:
    risk = RiskEngine(
        RiskLimits(
            allowed_symbols=allowed_symbols or {"NVDA"},
            max_order_notional=Decimal("10000"),
            max_gross_exposure=Decimal("50000"),
        )
    )
    return ExecutionController(adapter=adapter, risk_engine=risk, trading_state=state)


@pytest.mark.asyncio
async def test_halted_state_blocks_new_orders_before_adapter() -> None:
    adapter = FakeExecutionAdapter()
    controller = make_controller(adapter, state=TradingState.HALTED)

    result = await controller.submit(make_intent(), PortfolioSnapshot(cash=Decimal("10000")))

    assert result.status is OrderStatus.REJECTED
    assert result.code == "trading_halted"
    assert adapter.submit_calls == 0


@pytest.mark.asyncio
async def test_reducing_state_blocks_new_exposure() -> None:
    adapter = FakeExecutionAdapter()
    controller = make_controller(adapter, state=TradingState.REDUCING)

    result = await controller.submit(make_intent(), PortfolioSnapshot(cash=Decimal("10000")))

    assert result.status is OrderStatus.REJECTED
    assert result.code == "reducing_only"
    assert adapter.submit_calls == 0


@pytest.mark.asyncio
async def test_reducing_state_allows_position_reduction() -> None:
    adapter = FakeExecutionAdapter()
    controller = make_controller(adapter, state=TradingState.REDUCING)
    portfolio = PortfolioSnapshot(
        cash=Decimal("1000"),
        positions=[
            Position(
                symbol="NVDA",
                quantity=Decimal("2"),
                average_price=Decimal("195"),
                market_price=Decimal("200"),
            )
        ],
    )

    result = await controller.submit(
        make_intent(side=Side.SELL, quantity="1"),
        portfolio,
    )

    assert result.status is OrderStatus.ACCEPTED
    assert adapter.submit_calls == 1


@pytest.mark.asyncio
async def test_risk_rejection_never_reaches_adapter() -> None:
    adapter = FakeExecutionAdapter()
    controller = make_controller(adapter, allowed_symbols={"KLAC"})

    result = await controller.submit(make_intent(symbol="NVDA"), PortfolioSnapshot(cash=Decimal("10000")))

    assert result.status is OrderStatus.REJECTED
    assert result.code == "symbol_not_allowed"
    assert adapter.submit_calls == 0


@pytest.mark.asyncio
async def test_duplicate_client_order_id_returns_existing_result_without_resubmit() -> None:
    adapter = FakeExecutionAdapter()
    controller = make_controller(adapter)
    existing = ExecutionResult(
        client_order_id="intent-1",
        broker_order_id="broker-existing",
        status=OrderStatus.FILLED,
        message="already filled",
    )
    adapter.existing["intent-1"] = existing

    result = await controller.submit(make_intent(), PortfolioSnapshot(cash=Decimal("10000")))

    assert result == existing
    assert adapter.submit_calls == 0


@pytest.mark.asyncio
async def test_unknown_submit_halts_when_reconciliation_remains_unknown() -> None:
    class UnknownExecutionAdapter(FakeExecutionAdapter):
        def __init__(self) -> None:
            super().__init__()
            self.lookup_calls = 0

        async def get_order_by_client_id(self, client_order_id: str) -> ExecutionResult | None:
            self.lookup_calls += 1
            if self.lookup_calls == 1:
                return None
            return ExecutionResult(
                client_order_id=client_order_id,
                status=OrderStatus.UNKNOWN,
                code="lookup_unknown",
                message="Broker truth is still unavailable.",
            )

        async def submit(self, intent: OrderIntent) -> ExecutionResult:
            self.submit_calls += 1
            return ExecutionResult(
                client_order_id=intent.client_order_id,
                status=OrderStatus.UNKNOWN,
                code="submit_unknown",
                message="Submission outcome is ambiguous.",
            )

    adapter = UnknownExecutionAdapter()
    controller = make_controller(adapter)

    result = await controller.submit(make_intent(), PortfolioSnapshot(cash=Decimal("10000")))

    assert result.status is OrderStatus.UNKNOWN
    assert controller.trading_state is TradingState.HALTED
