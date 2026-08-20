from __future__ import annotations

from uuid import uuid4

from app.domain.models import AuditEvent, AuditEventType
from app.store.sqlite import SQLiteStore


class AuditService:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    def record(
        self,
        event_type: AuditEventType,
        *,
        subject: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            subject=subject,
            payload=payload or {},
        )
        self._store.append_audit_event(event)
        return event

    def list_events(self, *, limit: int = 200) -> list[AuditEvent]:
        return self._store.list_audit_events(limit=limit)
