"""Integrity-verified governance-chain reconstruction from the durable store.

Operates entirely from persisted product records + external audit projections. It
recomputes fingerprints, verifies the event chain, verifies referenced records and
their fingerprints, verifies tenant/revision consistency, and requires the
execution-disabled marker. No live network client is used in this phase.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Mapping, Optional, Tuple

from .errors import EventChainError, IntegrityFailure, TenantIsolationError
from .recorder import (
    rid_actiongate_projection,
    rid_cer_projection,
    rid_clearance_request,
    rid_decision_projection,
    rid_prepared_action,
)
from .schema import RecordType, ReconstructionMode
from .sqlite import DurableShadowStore


class DurableReconstructionState(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    STALE = "STALE"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    EVENT_CHAIN_BROKEN = "EVENT_CHAIN_BROKEN"
    SCHEMA_INCOMPATIBLE = "SCHEMA_INCOMPATIBLE"


@dataclass(frozen=True)
class DurableReconstructionResult:
    state: DurableReconstructionState
    workflow_revision_id: str
    verified_links: Tuple[str, ...] = ()
    issues: Tuple[str, ...] = ()
    execution_status: str = "DISABLED"

    @property
    def is_complete(self) -> bool:
        return self.state is DurableReconstructionState.COMPLETE


def _find(store, tenant_id, revision_id, record_type):
    for env in store.list_for_revision(tenant_id, revision_id):
        if env.record_type == record_type.value:
            return env
    return None


def reconstruct_from_store(
    store: DurableShadowStore,
    tenant_id: str,
    revision_id: str,
    *,
    mode: ReconstructionMode = ReconstructionMode.STORED_PROJECTION_ONLY,
    current_head_sha: Optional[str] = None,
    resolver: Optional[Callable[[str, str], Optional[str]]] = None,
) -> DurableReconstructionResult:
    """Reconstruct + verify a governance chain from the durable store."""
    issues = []
    verified = []
    index = store.get_index(tenant_id, revision_id)
    if index is None:
        return DurableReconstructionResult(
            DurableReconstructionState.INCOMPLETE, revision_id,
            issues=("workflow revision not found",))
    workflow_id = index["workflow_id"]

    # Integrity + event-chain verification.
    try:
        store.verify_records(tenant_id, workflow_id)
    except TenantIsolationError:
        return DurableReconstructionResult(DurableReconstructionState.TENANT_MISMATCH, revision_id,
                                           issues=("record tenant mismatch",))
    except IntegrityFailure as exc:
        return DurableReconstructionResult(DurableReconstructionState.INTEGRITY_FAILURE, revision_id,
                                           issues=(str(exc),))
    try:
        store.verify_event_chain(tenant_id, workflow_id)
    except EventChainError as exc:
        return DurableReconstructionResult(DurableReconstructionState.EVENT_CHAIN_BROKEN, revision_id,
                                           issues=(str(exc),))
    verified.append("event_chain")

    chain_env = _find(store, tenant_id, revision_id, RecordType.GOVERNANCE_CHAIN)
    if chain_env is None:
        return DurableReconstructionResult(
            DurableReconstructionState.INCOMPLETE, revision_id,
            issues=("governance chain record missing",), verified_links=tuple(verified))
    if chain_env.tenant_id != tenant_id:
        return DurableReconstructionResult(DurableReconstructionState.TENANT_MISMATCH, revision_id,
                                           issues=("chain tenant mismatch",))
    chain = chain_env.canonical_payload

    # Execution-disabled marker is mandatory.
    if chain.get("execution_status") != "DISABLED":
        return DurableReconstructionResult(
            DurableReconstructionState.INTEGRITY_FAILURE, revision_id,
            issues=("execution-disabled marker missing/altered",))
    verified.append("execution_disabled")

    # Mandatory linked records present in the store.
    def require(record_type, record_id, label):
        env = store.get_record(tenant_id, record_id)
        if env is None:
            issues.append(f"REFERENCE_MISSING:{label}")
        elif env.record_type != record_type.value:
            issues.append(f"REFERENCE_MISMATCH:{label}")
        else:
            verified.append(label)

    if chain.get("claim_manifest_ref"):
        require(RecordType.CLAIM_MANIFEST, chain["claim_manifest_ref"], "claim_manifest")
    else:
        issues.append("REFERENCE_MISSING:claim_manifest")
    for eid in chain.get("evidence_refs", []):
        require(RecordType.EVIDENCE_RECORD, eid, f"evidence:{eid[:8]}")
    if chain.get("decision_record_id"):
        require(RecordType.DECISION_RECORD_PROJECTION,
                rid_decision_projection(chain["decision_record_id"]), "decision_projection")
    if chain.get("cer_id"):
        require(RecordType.CONTEXT_ENVELOPE_PROJECTION,
                rid_cer_projection(chain["cer_id"]), "cer_projection")
    if chain.get("prepared_action_ref"):
        require(RecordType.PREPARED_MERGE_ACTION,
                rid_prepared_action(chain["prepared_action_ref"]), "prepared_action")
    if chain.get("action_result_fingerprint"):
        require(RecordType.ACTIONGATE_RESULT_PROJECTION,
                rid_actiongate_projection(chain["action_result_fingerprint"]), "actiongate_projection")

    # Clearance linkage: evaluated vs legitimately-not-evaluated-upstream.
    acs = chain.get("action_clearance_status")
    if acs and acs != "ACTION_CLEARANCE_NOT_EVALUATED":
        if chain.get("clearance_evaluation_ref"):
            require(RecordType.ACTION_CLEARANCE_EVALUATION,
                    chain["clearance_evaluation_ref"], "clearance_evaluation")
        else:
            issues.append("REFERENCE_MISSING:clearance_evaluation")
        if acs == "EVALUATED":
            if chain.get("clearance_request_fingerprint"):
                require(RecordType.CLEARANCE_REQUEST_PROJECTION,
                        rid_clearance_request(chain["clearance_request_fingerprint"]),
                        "clearance_request")
            else:
                issues.append("REFERENCE_MISSING:clearance_request")
        if chain.get("intervention_assessment_ref"):
            require(RecordType.HUMAN_INTERVENTION_ASSESSMENT,
                    chain["intervention_assessment_ref"], "intervention_assessment")
        else:
            issues.append("REFERENCE_MISSING:intervention_assessment")

    # Optional resolver verification (compares stored external hashes; no network).
    if mode is ReconstructionMode.VERIFY_WITH_SUPPLIED_RESOLVER and resolver is not None:
        if chain.get("cer_id"):
            expected = resolver("cer", chain["cer_id"])
            if expected is not None and expected != chain.get("cer_content_hash"):
                issues.append("REFERENCE_MISMATCH:cer_content_hash")
            else:
                verified.append("resolver_cer")

    # Staleness against a caller-supplied current head (no network).
    if current_head_sha is not None and chain.get("head_sha") != current_head_sha:
        return DurableReconstructionResult(
            DurableReconstructionState.STALE, revision_id,
            issues=("chain head superseded by a newer revision",),
            verified_links=tuple(verified))

    if issues:
        state = DurableReconstructionState.INCOMPLETE
        if any(i.startswith("REFERENCE_MISMATCH") for i in issues):
            state = DurableReconstructionState.REFERENCE_MISMATCH
        return DurableReconstructionResult(state, revision_id, issues=tuple(issues),
                                           verified_links=tuple(verified))
    return DurableReconstructionResult(DurableReconstructionState.COMPLETE, revision_id,
                                       verified_links=tuple(verified))


__all__ = [
    "DurableReconstructionState",
    "DurableReconstructionResult",
    "reconstruct_from_store",
]
