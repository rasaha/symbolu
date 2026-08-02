"""Product-owned immutable Action Clearance evaluation record.

Links the Code Governance workflow revision to the canonical Action Clearance
result. This is **not** an execution receipt and **not** enforcement-grade: it is a
shadow/reference record. It never implies one-time consumption, revocation, or
production durability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple

from ..fingerprints import domain_hash
from ..models.enums import ActionClearanceStatus, ActionEvaluationMode


@dataclass(frozen=True)
class ActionClearanceEvaluationRecord:
    """Immutable product record of one shadow Action Clearance evaluation."""

    record_id: str
    tenant_id: str
    workflow_id: str
    workflow_revision_id: str
    change_fingerprint: str
    prepared_action_fingerprint: str
    stage_state: ActionClearanceStatus
    # ActionGate linkage
    action_request_fingerprint: str
    action_result_fingerprint: str
    actiongate_outcome: str
    # canonical clearance linkage (empty when not evaluated)
    clearance_request_fingerprint: str = ""
    clearance_result_id: str = ""
    clearance_result_fingerprint: str = ""
    clearance_status: str = ""            # canonical CLEAR/HOLD/BLOCK/ESCALATE (or "")
    reason_codes: Tuple[str, ...] = ()
    effective_constraints: Tuple[str, ...] = ()
    effective_obligations: Tuple[str, ...] = ()
    signal_refs: Tuple[str, ...] = ()
    signal_bundle_fingerprint: str = ""
    clearance_policy_ref: str = ""
    evaluated_at: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    policy_refs: Tuple[str, ...] = ()
    mode: ActionEvaluationMode = ActionEvaluationMode.SHADOW_ONLY

    @property
    def fingerprint(self) -> str:
        return domain_hash("action_clearance_evaluation.v1", {
            "tenant_id": self.tenant_id,
            "workflow_revision_id": self.workflow_revision_id,
            "change_fingerprint": self.change_fingerprint,
            "prepared_action_fingerprint": self.prepared_action_fingerprint,
            "stage_state": self.stage_state.value,
            "actiongate_outcome": self.actiongate_outcome,
            "action_result_fingerprint": self.action_result_fingerprint,
            "clearance_request_fingerprint": self.clearance_request_fingerprint,
            "clearance_result_fingerprint": self.clearance_result_fingerprint,
            "clearance_status": self.clearance_status,
            "reason_codes": sorted(self.reason_codes),
            "signal_refs": sorted(self.signal_refs),
            "signal_bundle_fingerprint": self.signal_bundle_fingerprint,
            "clearance_policy_ref": self.clearance_policy_ref,
        })


def evaluation_record_id(workflow_revision_id: str, action_result_fingerprint: str) -> str:
    return "acer_" + domain_hash("action_clearance_evaluation_id.v1", {
        "workflow_revision_id": workflow_revision_id,
        "action_result_fingerprint": action_result_fingerprint,
    })


__all__ = ["ActionClearanceEvaluationRecord", "evaluation_record_id"]
