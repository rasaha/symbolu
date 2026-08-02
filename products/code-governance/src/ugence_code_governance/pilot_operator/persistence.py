"""Durable persistence for pilot-operator records — reuses the existing store.

Operator records (deployment config, lifecycle events, run records, security
events, kill-switch state, reviewer-queue items, operator metrics) live in the
*same* durable shadow store as the governance chain and the 1D pilot records, under
a dedicated hash-linked ``op:<pilot_id>`` lineage. No second database is added.
``same id + same content`` is idempotent; ``same id + different content`` is an
integrity error.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional, Tuple

from ..persistence.envelope import RecordEnvelope
from ..persistence.errors import RecordCollisionError
from ..persistence.recorder import DurableShadowRecorder
from ..persistence.schema import RecordType, WorkflowEventType
from ..persistence.sqlite import DurableShadowStore


class OperatorDurableWriter:
    """Commits immutable pilot-operator records into the durable shadow store."""

    def __init__(self, store: DurableShadowStore) -> None:
        self._store = store
        self._recorder = DurableShadowRecorder(store)

    @property
    def store(self) -> DurableShadowStore:
        return self._store

    def _wid(self, pilot_id: str) -> str:
        return f"op:{pilot_id}"

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
        allow_replace: bool = False,
    ) -> str:
        """Commit one immutable operator record + one hash-linked operator event.

        Idempotent at the record level. For mutable-pointer records (kill switch,
        latest lifecycle pointer) the caller uses a content-addressed record id so
        each distinct state is its own immutable record; the newest is resolved by
        ordering, never by overwrite.
        """
        wid = self._wid(pilot_id)
        new_env = RecordEnvelope.build(
            record_id=record_id, record_type=record_type.value, tenant_id=tenant_id,
            workflow_id=wid, workflow_revision_id=revision_id, created_at=occurred_at,
            payload=payload)
        existing = self._store.get_record(tenant_id, record_id)
        if existing is not None:
            if existing.payload_fingerprint == new_env.payload_fingerprint:
                return self._store.last_event_fingerprint(tenant_id, wid)
            raise RecordCollisionError(
                f"operator record {record_id} already exists with different content")
        return self._recorder.commit_stage(
            tenant_id=tenant_id, workflow_id=wid, revision_id=revision_id,
            occurred_at=occurred_at, from_state="OPERATOR", to_state="OPERATOR",
            record_specs=[(record_type, record_id, payload)],
            event_type=WorkflowEventType.PILOT_OPERATOR_EVENT, event_id=f"{pilot_id}:{event_label}")

    def get(self, tenant_id: str, record_id: str):
        return self._store.get_record(tenant_id, record_id)

    def list_operator_records(self, tenant_id: str, pilot_id: str) -> Tuple[Any, ...]:
        return self._store.list_for_workflow(tenant_id, self._wid(pilot_id))

    def latest_of_type(self, tenant_id: str, pilot_id: str, record_type: RecordType):
        """Return the most-recently-committed record of a type (by event order)."""
        wid = self._wid(pilot_id)
        events = self._store.events_for_workflow(tenant_id, wid)
        by_id = {e.record_id: None for e in ()}  # placeholder for clarity
        # Walk events newest-first; return the first record of the type.
        records = {r.record_id: r for r in self._store.list_for_workflow(tenant_id, wid)}
        for ev in reversed(events):
            for rid in ev.referenced_record_ids:
                rec = records.get(rid)
                if rec is not None and rec.record_type == record_type.value:
                    return rec
        return None


__all__ = ["OperatorDurableWriter"]
