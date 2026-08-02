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

    # Future boundary — explicitly unavailable, never fabricated.
    action_clearance_status: ActionClearanceStatus = ActionClearanceStatus.NOT_EVALUATED
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
                "execution_status": self.execution_status.value,
            },
        )


def chain_id_for(workflow_id: str, revision_id: str) -> str:
    return domain_hash("governance_chain_id.v1",
                       {"workflow_id": workflow_id, "revision_id": revision_id})


__all__ = ["GovernanceChainRecord", "chain_id_for"]
