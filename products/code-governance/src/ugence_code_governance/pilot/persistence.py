"""Durable persistence for pilot records — reuses the existing shadow store.

Pilot audit records live in the *same* durable store as the governance chain (no
second database). They are committed under a dedicated, hash-linked pilot lineage
(``workflow_id = "pilot:<pilot_id>"``) so the pilot audit trail is self-contained
and append-only. ``same id + same content`` is idempotent; ``same id + different
content`` is an integrity error.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from ..persistence.envelope import RecordEnvelope
from ..persistence.errors import RecordCollisionError
from ..persistence.recorder import DurableShadowRecorder
from ..persistence.schema import RecordType, WorkflowEventType
from ..persistence.sqlite import DurableShadowStore


class PilotDurableWriter:
    """Commits immutable pilot records into the existing durable shadow store."""

    def __init__(self, store: DurableShadowStore) -> None:
        self._store = store
        self._recorder = DurableShadowRecorder(store)

    @property
    def store(self) -> DurableShadowStore:
        return self._store

    def _wid(self, pilot_id: str) -> str:
        return f"pilot:{pilot_id}"

    def commit(
        self,
        *,
        tenant_id: str,
        pilot_id: str,
        revision_id: str,
        record_type: RecordType,
        record_id: str,
        payload: Mapping[str, Any],
        occurred_at: datetime,
        event_label: str,
    ) -> str:
        """Commit one immutable pilot record + one hash-linked pilot event.

        Idempotent at the record level: re-committing identical content is a no-op
        (no new event); the same record id with differing content is an integrity
        error. This keeps repeated metrics/report snapshots safe.
        """
        wid = self._wid(pilot_id)
        new_env = RecordEnvelope.build(
            record_id=record_id, record_type=record_type.value, tenant_id=tenant_id,
            workflow_id=wid, workflow_revision_id=revision_id, created_at=occurred_at,
            payload=payload)
        existing = self._store.get_record(tenant_id, record_id)
        if existing is not None:
            if existing.payload_fingerprint == new_env.payload_fingerprint:
                return self._store.last_event_fingerprint(tenant_id, wid)  # idempotent no-op
            raise RecordCollisionError(
                f"pilot record {record_id} already exists with different content")
        return self._recorder.commit_stage(
            tenant_id=tenant_id, workflow_id=wid, revision_id=revision_id,
            occurred_at=occurred_at, from_state="PILOT", to_state="PILOT",
            record_specs=[(record_type, record_id, payload)],
            event_type=WorkflowEventType.PILOT_STAGE_COMMITTED,
            event_id=f"{pilot_id}:{event_label}")

    def get(self, tenant_id: str, record_id: str):
        return self._store.get_record(tenant_id, record_id)

    def list_pilot_records(self, tenant_id: str, pilot_id: str):
        return self._store.list_for_workflow(tenant_id, self._wid(pilot_id))


__all__ = ["PilotDurableWriter"]
