"""Durable shadow recorder — maps product records to immutable envelopes per stage.

The recorder assembles the record envelopes a workflow stage produces, plus one
append-only workflow event, and commits them in a single atomic transaction. A
stage never becomes visible as completed if a required record failed to persist.

Externally-owned authoritative records (DecisionRecord, CER, ActionGate result,
TAP result) are persisted only as **immutable audit projections** — reference +
content hash + minimal linkage — never as newly issued authority records.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .envelope import RecordEnvelope, WorkflowEventRecord
from .schema import RecordType, WorkflowEventType
from .sqlite import DurableShadowStore


class DurableShadowRecorder:
    """Assembles + atomically commits durable envelopes for a workflow stage."""

    def __init__(self, store: DurableShadowStore) -> None:
        self._store = store

    @property
    def store(self) -> DurableShadowStore:
        return self._store

    def commit_stage(
        self,
        *,
        tenant_id: str,
        workflow_id: str,
        revision_id: str,
        occurred_at,
        from_state: str,
        to_state: str,
        record_specs: List[Tuple[RecordType, str, object]],
        event_type: WorkflowEventType = WorkflowEventType.STAGE_COMMITTED,
        chain_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> str:
        """Build envelopes + a workflow event and commit them atomically.

        ``record_specs`` is a list of ``(RecordType, record_id, payload)``. Returns
        the new last-event fingerprint. ``event_id`` defaults to
        ``f"{revision_id}:{to_state}"``; supply an explicit value when a single
        state can be committed more than once (e.g. per-evidence commits).
        """
        envelopes: List[RecordEnvelope] = []
        for record_type, record_id, payload in record_specs:
            envelopes.append(RecordEnvelope.build(
                record_id=record_id, record_type=record_type.value, tenant_id=tenant_id,
                workflow_id=workflow_id, workflow_revision_id=revision_id,
                created_at=occurred_at, payload=payload))
        prev = self._store.last_event_fingerprint(tenant_id, workflow_id)
        event = WorkflowEventRecord.build(
            event_id=event_id or f"{revision_id}:{to_state}", tenant_id=tenant_id, workflow_id=workflow_id,
            workflow_revision_id=revision_id, previous_event_fingerprint=prev,
            from_state=from_state, to_state=to_state, event_type=event_type.value,
            referenced_record_ids=tuple(rid for (_, rid, _) in record_specs),
            occurred_at=occurred_at)
        self._store.commit_stage(
            tenant_id=tenant_id, workflow_id=workflow_id, revision_id=revision_id,
            records=envelopes, event=event, current_state=to_state, chain_id=chain_id)
        return event.event_fingerprint


# --- record-id helpers (deterministic, content/reference-derived) ---------
def rid_change_identity(change_fingerprint: str) -> str:
    return "gci:" + change_fingerprint


def rid_decision_projection(decision_id: str) -> str:
    return "decproj:" + decision_id


def rid_cer_projection(cer_id: str) -> str:
    return "cerproj:" + cer_id


def rid_actiongate_projection(result_fingerprint: str) -> str:
    return "agproj:" + result_fingerprint


def rid_tap_projection(manifest_fingerprint: str) -> str:
    return "tapproj:" + manifest_fingerprint


def rid_prepared_action(action_fingerprint: str) -> str:
    return "pma:" + action_fingerprint


def rid_clearance_request(request_fingerprint: str) -> str:
    return "clreq:" + request_fingerprint


def rid_operational_snapshot(revision_id: str, bundle_fingerprint: str) -> str:
    return "opsnap:" + bundle_fingerprint


def rid_workflow_revision(revision_id: str) -> str:
    return "rev:" + revision_id


__all__ = [
    "DurableShadowRecorder",
    "rid_change_identity", "rid_decision_projection", "rid_cer_projection",
    "rid_actiongate_projection", "rid_tap_projection", "rid_prepared_action",
    "rid_clearance_request", "rid_operational_snapshot", "rid_workflow_revision",
]
