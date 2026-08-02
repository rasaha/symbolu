"""Durable persistence for pilot-study records — reuses the existing store.

Study records (manifest, freeze, amendments, candidate selection, annotations,
checkpoints, adverse cases, calibration recommendations, readiness verdict,
evidence pack) live in the same durable shadow store under a hash-linked
``study:<pilot_id>`` lineage. No external database is added. ``same id + same
content`` is idempotent; ``same id + different content`` is an integrity error.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Tuple

from ..persistence.envelope import RecordEnvelope
from ..persistence.errors import RecordCollisionError
from ..persistence.recorder import DurableShadowRecorder
from ..persistence.schema import RecordType, WorkflowEventType
from ..persistence.sqlite import DurableShadowStore


class StudyDurableWriter:
    """Commits immutable pilot-study records into the durable shadow store."""

    def __init__(self, store: DurableShadowStore) -> None:
        self._store = store
        self._recorder = DurableShadowRecorder(store)

    @property
    def store(self) -> DurableShadowStore:
        return self._store

    def _wid(self, pilot_id: str) -> str:
        return f"study:{pilot_id}"

    def commit(self, *, tenant_id: str, pilot_id: str, record_type: RecordType,
               record_id: str, payload: Mapping[str, Any], occurred_at: datetime,
               event_label: str) -> str:
        wid = self._wid(pilot_id)
        new_env = RecordEnvelope.build(
            record_id=record_id, record_type=record_type.value, tenant_id=tenant_id,
            workflow_id=wid, workflow_revision_id=record_id, created_at=occurred_at, payload=payload)
        existing = self._store.get_record(tenant_id, record_id)
        if existing is not None:
            if existing.payload_fingerprint == new_env.payload_fingerprint:
                return self._store.last_event_fingerprint(tenant_id, wid)
            raise RecordCollisionError(
                f"study record {record_id} already exists with different content")
        return self._recorder.commit_stage(
            tenant_id=tenant_id, workflow_id=wid, revision_id=record_id, occurred_at=occurred_at,
            from_state="STUDY", to_state="STUDY", record_specs=[(record_type, record_id, payload)],
            event_type=WorkflowEventType.PILOT_STUDY_EVENT, event_id=f"{pilot_id}:{event_label}")

    def get(self, tenant_id: str, record_id: str):
        return self._store.get_record(tenant_id, record_id)

    def list_study_records(self, tenant_id: str, pilot_id: str) -> Tuple[Any, ...]:
        return self._store.list_for_workflow(tenant_id, self._wid(pilot_id))

    def list_of_type(self, tenant_id: str, pilot_id: str, record_type: RecordType) -> Tuple[Any, ...]:
        return tuple(r for r in self.list_study_records(tenant_id, pilot_id)
                     if r.record_type == record_type.value)


__all__ = ["StudyDurableWriter"]
