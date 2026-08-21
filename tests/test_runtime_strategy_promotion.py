from app.api.state import ApplicationState
from app.domain.models import TradingMode
from app.innovation.models import PromotionEvidence
from app.innovation.store import SQLiteStrategyEvidenceStore
from app.settings import Settings


def replay_evidence() -> PromotionEvidence:
    return PromotionEvidence(
        deterministic_implementation=True,
        data_provenance_complete=True,
        replayable_data=True,
        transaction_cost_model_documented=True,
    )


def seed_replay_evidence(path) -> None:
    evidence_store = SQLiteStrategyEvidenceStore(path)
    evidence_store.upsert("vwap", "1.0.0", replay_evidence())
    evidence_store.upsert("gamma-levels", "1.0.0", replay_evidence())


def test_auto_paper_is_blocked_when_strategies_are_only_replay_promoted(tmp_path) -> None:
    database = tmp_path / "runtime.db"
    seed_replay_evidence(database)
    runtime = ApplicationState(
        Settings(
            database_path=str(database),
            trading_mode=TradingMode.PAPER,
            auto_trading_enabled=True,
            market_source="replay",
        )
    )

    assert runtime.promotion_execution_allowed is False
    assert runtime.autonomous.execution_enabled is False
    assert {item.strategy_id for item in runtime.strategy_promotion_reports} == {
        "vwap",
        "gamma-levels",
    }
    assert all(not item.allowed for item in runtime.strategy_promotion_reports)


def test_auto_replay_can_execute_only_after_replay_evidence_is_persisted(tmp_path) -> None:
    database = tmp_path / "runtime.db"
    seed_replay_evidence(database)
    runtime = ApplicationState(
        Settings(
            database_path=str(database),
            trading_mode=TradingMode.REPLAY,
            auto_trading_enabled=True,
            market_source="replay",
        )
    )

    assert runtime.promotion_execution_allowed is True
    assert runtime.autonomous.execution_enabled is True
    assert all(item.allowed for item in runtime.strategy_promotion_reports)


def test_auto_replay_without_persisted_evidence_remains_monitor_only(tmp_path) -> None:
    runtime = ApplicationState(
        Settings(
            database_path=str(tmp_path / "runtime.db"),
            trading_mode=TradingMode.REPLAY,
            auto_trading_enabled=True,
            market_source="replay",
        )
    )

    assert runtime.promotion_execution_allowed is False
    assert runtime.autonomous.execution_enabled is False
    assert any(item.blockers for item in runtime.strategy_promotion_reports)
