"""Restart-safe recovery from the durable shadow store.

Recovery validates store schema + record/event integrity, loads immutable workflow
state, identifies the last fully-committed stage and any incomplete/rolled-back
stage, and returns a structured result. It performs **no external capability call**
and **no automatic transition** — the caller must explicitly continue. Recovery is
NOT execution reconciliation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from .errors import (
    DurableStoreError,
    EventChainError,
    IntegrityFailure,
    TenantIsolationError,
)
from .schema import RecordType, RecoveryStatus
from .sqlite import DurableShadowStore

# Forward workflow states (value strings) and their terminal classes.
_TERMINAL_COMPLETE = {"SHADOW_COMPLETE"}
_FAIL_CLOSED = {
    "CLAIMS_INCOMPLETE", "DECISION_REQUIRED", "CHAIN_INCOMPLETE", "BLOCKED", "ESCALATED",
    "ERROR", "STALE_ARTIFACT", "CLEARANCE_INPUT_INCOMPLETE", "CLEARANCE_INTEGRITY_FAILURE",
    "CLEARANCE_EVALUATION_ERROR",
}


@dataclass(frozen=True)
class RecoveryResult:
    """Structured outcome of a restart recovery. Advisory; requires explicit action."""

    status: RecoveryStatus
    tenant_id: str
    workflow_id: str
    workflow_revision_id: str
    last_committed_state: str
    last_event_fingerprint: str
    record_count: int
    event_count: int
    chain_id: Optional[str] = None
    stale: bool = False
    issues: Tuple[str, ...] = ()
    #: The execution posture never changes on recovery.
    execution_status: str = "DISABLED"

    @property
    def requires_explicit_action(self) -> bool:
        return self.status in (RecoveryStatus.RECOVERED_PENDING, RecoveryStatus.RECOVERED_STALE)


def _change_identity_payload(store: DurableShadowStore, tenant_id: str, revision_id: str):
    for env in store.list_for_revision(tenant_id, revision_id):
        if env.record_type == RecordType.GOVERNED_CHANGE_IDENTITY.value:
            return env.canonical_payload
    return None


def recover_workflow(
    store: DurableShadowStore,
    tenant_id: str,
    revision_id: str,
    *,
    current_identity: Optional[Mapping[str, str]] = None,
) -> RecoveryResult:
    """Recover a workflow revision from the durable store (no external calls)."""
    index = store.get_index(tenant_id, revision_id)
    if index is None:
        return RecoveryResult(
            status=RecoveryStatus.REFERENCE_MISSING, tenant_id=tenant_id, workflow_id="",
            workflow_revision_id=revision_id, last_committed_state="", last_event_fingerprint="",
            record_count=0, event_count=0, issues=("workflow revision not found in store",))
    workflow_id = index["workflow_id"]

    # Integrity: recompute record fingerprints + verify event-chain linkage.
    try:
        store.verify_records(tenant_id, workflow_id)
        store.verify_event_chain(tenant_id, workflow_id)
    except TenantIsolationError:
        return _fail(RecoveryStatus.TENANT_MISMATCH, tenant_id, workflow_id, revision_id, index,
                     store, "tenant isolation violation")
    except (IntegrityFailure, EventChainError) as exc:
        return _fail(RecoveryStatus.INTEGRITY_FAILURE, tenant_id, workflow_id, revision_id, index,
                     store, str(exc))

    records = store.list_for_revision(tenant_id, revision_id)
    events = [e for e in store.events_for_workflow(tenant_id, workflow_id)
              if e.workflow_revision_id == revision_id]
    state = index["current_state"]

    # Stale-artifact detection against caller-supplied current identity (no network).
    stale = False
    if current_identity is not None:
        ci = _change_identity_payload(store, tenant_id, revision_id)
        if ci is not None:
            for key in ("base_sha", "head_sha", "repository"):
                if key in current_identity and str(current_identity[key]) != str(ci.get(key)):
                    stale = True
                    break

    if stale:
        status = RecoveryStatus.RECOVERED_STALE
    elif state in _TERMINAL_COMPLETE:
        status = RecoveryStatus.RECOVERED_COMPLETE
    elif state in _FAIL_CLOSED:
        status = RecoveryStatus.RECOVERED_BLOCKED
    else:
        status = RecoveryStatus.RECOVERED_PENDING

    return RecoveryResult(
        status=status, tenant_id=tenant_id, workflow_id=workflow_id,
        workflow_revision_id=revision_id, last_committed_state=state,
        last_event_fingerprint=index["last_event_fingerprint"], record_count=len(records),
        event_count=len(events), chain_id=index.get("chain_id"), stale=stale)


def _fail(status, tenant_id, workflow_id, revision_id, index, store, issue) -> RecoveryResult:
    return RecoveryResult(
        status=status, tenant_id=tenant_id, workflow_id=workflow_id or (index or {}).get("workflow_id", ""),
        workflow_revision_id=revision_id,
        last_committed_state=(index or {}).get("current_state", ""),
        last_event_fingerprint=(index or {}).get("last_event_fingerprint", ""),
        record_count=0, event_count=0, chain_id=(index or {}).get("chain_id"),
        issues=(issue,))


__all__ = ["RecoveryResult", "recover_workflow"]
