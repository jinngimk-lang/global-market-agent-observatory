import sqlite3

import pytest

from app.audit.service import AuditService
from app.domain.models import AuditEvent, AuditEventType
from app.store.sqlite import SQLiteStore


def test_trading_audit_events_are_append_only_and_ordered(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "audit.db")
    audit = AuditService(store)

    signal = audit.record(
        AuditEventType.STRATEGY_SIGNAL,
        subject="NVDA",
        payload={"strategy": "vwap-reclaim", "action": "buy"},
    )
    risk = audit.record(
        AuditEventType.RISK_DECISION,
        subject="NVDA",
        payload={"allowed": True, "code": "approved"},
    )
    execution = audit.record(
        AuditEventType.EXECUTION,
        subject="NVDA",
        payload={"client_order_id": "nvda-1", "status": "accepted"},
    )
    reconciliation = audit.record(
        AuditEventType.RECONCILIATION,
        subject="portfolio",
        payload={"status": "matched"},
    )
    kill_switch = audit.record(
        AuditEventType.KILL_SWITCH,
        subject="runtime",
        payload={"state": "halted"},
    )

    events = audit.list_events(limit=10)

    assert [event.event_id for event in events] == [
        signal.event_id,
        risk.event_id,
        execution.event_id,
        reconciliation.event_id,
        kill_switch.event_id,
    ]
    assert [event.event_type for event in events] == [
        AuditEventType.STRATEGY_SIGNAL,
        AuditEventType.RISK_DECISION,
        AuditEventType.EXECUTION,
        AuditEventType.RECONCILIATION,
        AuditEventType.KILL_SWITCH,
    ]


def test_store_rejects_duplicate_audit_event_ids(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "audit.db")
    event = AuditEvent(
        event_id="same-id",
        event_type=AuditEventType.EXECUTION,
        subject="NVDA",
        payload={"status": "accepted"},
    )

    store.append_audit_event(event)

    with pytest.raises(sqlite3.IntegrityError):
        store.append_audit_event(event)
