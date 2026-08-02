"""The reconstructable governance-chain record.

A :class:`GovernanceChainRecord` links every governance artifact for one workflow
revision so the entire shadow path can be reconstructed and verified. Action
Clearance and execution fields are **explicitly represented as unavailable** —
there are no fabricated placeholder authorization or clearance objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple

from ..fingerprints import domain_hash
from ..models.enums import (
    ActionClearanceStatus,
    ExecutionStatus,
    WorkflowMode,
)


@dataclass(frozen=True)
class GovernanceChainRecord:
    """Immutable, reconstructable link set for one workflow revision."""

    chain_id: str
    workflow_id: str
    revision_id: str
    tenant_id: str
    repository: str
    pull_request_number: int
    change_fingerprint: str
    base_sha: str
    head_sha: str

    evidence_refs: Tuple[str, ...]
    claim_manifest_ref: str
    claim_manifest_fingerprint: str
    tap_request_fingerprints: Tuple[str, ...]
    tap_result_fingerprints: Tuple[str, ...]
    recommendation_ref: Optional[str]
    decision_record_id: str
    cer_id: str
    cer_content_hash: str
    prepared_action_ref: str
    action_request_fingerprint: str
    action_result_fingerprint: str

    workflow_mode: WorkflowMode
    created_at: datetime
    evaluated_at: datetime
    policy_refs: Tuple[str, ...]

    # MVP 1B — shadow Action Clearance stage linkage (empty/NOT_EVALUATED in 1A).
    action_clearance_status: ActionClearanceStatus = ActionClearanceStatus.NOT_EVALUATED
    clearance_evaluation_ref: str = ""
    clearance_evaluation_fingerprint: str = ""
    clearance_request_fingerprint: str = ""
    clearance_result_id: str = ""
    clearance_result_fingerprint: str = ""
    clearance_status: str = ""                       # canonical CLEAR/HOLD/BLOCK/ESCALATE
    clearance_reason_codes: Tuple[str, ...] = ()
    clearance_signal_refs: Tuple[str, ...] = ()
    clearance_signal_bundle_fingerprint: str = ""
    clearance_policy_ref: str = ""
    clearance_evaluated_at: Optional[datetime] = None
    clearance_valid_until: Optional[datetime] = None
    clearance_effective_constraints: Tuple[str, ...] = ()
    clearance_effective_obligations: Tuple[str, ...] = ()
    intervention_assessment_ref: str = ""
    intervention_assessment_fingerprint: str = ""
    human_intervention_required: bool = False
    required_authorities: Tuple[str, ...] = ()
    # Execution remains disabled for every status.
    execution_status: ExecutionStatus = ExecutionStatus.DISABLED

    @property
    def fingerprint(self) -> str:
        return domain_hash(
            "governance_chain.v1",
            {
                "workflow_id": self.workflow_id,
                "revision_id": self.revision_id,
                "tenant_id": self.tenant_id,
                "change_fingerprint": self.change_fingerprint,
                "base_sha": self.base_sha,
                "head_sha": self.head_sha,
                "evidence_refs": sorted(self.evidence_refs),
                "claim_manifest_fingerprint": self.claim_manifest_fingerprint,
                "tap_result_fingerprints": sorted(self.tap_result_fingerprints),
                "recommendation_ref": self.recommendation_ref,
                "decision_record_id": self.decision_record_id,
                "cer_id": self.cer_id,
                "cer_content_hash": self.cer_content_hash,
                "prepared_action_ref": self.prepared_action_ref,
                "action_request_fingerprint": self.action_request_fingerprint,
                "action_result_fingerprint": self.action_result_fingerprint,
                "workflow_mode": self.workflow_mode.value,
                "action_clearance_status": self.action_clearance_status.value,
                "clearance_request_fingerprint": self.clearance_request_fingerprint,
                "clearance_result_fingerprint": self.clearance_result_fingerprint,
                "clearance_status": self.clearance_status,
                "clearance_reason_codes": sorted(self.clearance_reason_codes),
                "clearance_signal_refs": sorted(self.clearance_signal_refs),
                "clearance_signal_bundle_fingerprint": self.clearance_signal_bundle_fingerprint,
                "clearance_policy_ref": self.clearance_policy_ref,
                "intervention_assessment_fingerprint": self.intervention_assessment_fingerprint,
                "human_intervention_required": self.human_intervention_required,
                "required_authorities": sorted(self.required_authorities),
                "execution_status": self.execution_status.value,
            },
        )


def chain_id_for(workflow_id: str, revision_id: str) -> str:
    return domain_hash("governance_chain_id.v1",
                       {"workflow_id": workflow_id, "revision_id": revision_id})


__all__ = ["GovernanceChainRecord", "chain_id_for"]
