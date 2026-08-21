from app.api.state import ApplicationState
from app.domain.models import TradingState
from app.settings import Settings
from app.trading.state_store import SQLiteTradingStateStore


def test_runtime_trading_state_defaults_active_and_persists(tmp_path) -> None:
    database = tmp_path / "runtime.db"
    state_store = SQLiteTradingStateStore(database)

    assert state_store.get() is TradingState.ACTIVE

    state_store.set(TradingState.HALTED, reason="unknown execution state")

    restarted = SQLiteTradingStateStore(database)
    assert restarted.get() is TradingState.HALTED
    assert restarted.last_reason() == "unknown execution state"


def test_application_state_recovers_persisted_halt_on_restart(tmp_path) -> None:
    database = tmp_path / "runtime.db"
    first = ApplicationState(Settings(database_path=str(database)))

    first.orchestrator.halt("operator emergency stop")
    restarted = ApplicationState(Settings(database_path=str(database)))

    assert restarted.trading_state is TradingState.HALTED


def test_explicit_reactivation_is_persisted(tmp_path) -> None:
    database = tmp_path / "runtime.db"
    first = ApplicationState(Settings(database_path=str(database)))
    first.orchestrator.halt("test halt")
    first.orchestrator.activate("review complete")

    restarted = ApplicationState(Settings(database_path=str(database)))

    assert restarted.trading_state is TradingState.ACTIVE
