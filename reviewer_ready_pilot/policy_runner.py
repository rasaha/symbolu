"""Phase 13 - Frozen policy runner.

Runs the FROZEN minimal evidence-obligation policy read-only and passes its result through the frozen,
read-only EvidenceAssurance and (for action-bearing claims) the native ActionGate. Produces the immutable
SystemResult that the review interface reveals to a reviewer at Stage B - never before.

Guarantees (by construction):
  * No frozen component is modified, tuned, or re-thresholded here (policy, EA, ActionGate all read-only).
  * The native ActionGate outcome is preserved verbatim (6 outcomes, never collapsed to allow/deny).
  * `enforced` is ALWAYS False - the runner computes a result; it never executes an external action.
  * A deterministic replay signature is attached so an auditor can reproduce the result.

Deterministic, stdlib-only aside from the frozen components it consumes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from minimal_evidence_policy import classifier as policy            # frozen (read-only)
from minimal_evidence_policy import adapters as policy_adapters      # frozen (read-only)
from governed_inference_pilot.adapters import evidence_assurance as ea   # frozen (read-only)
from bounded_shadow_pilot import actiongate_contract as ag           # native ActionGate (read-only)

RUNNER_VERSION = "reviewer_ready_policy_runner_v1"

# native ActionGate outcomes - the canonical set, preserved verbatim.
NATIVE_ACTIONGATE_OUTCOMES = ("ALLOW", "ALLOW_WITH_CONSTRAINTS", "DENY", "ESCALATE_TO_HUMAN",
                              "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY")


@dataclass
class SystemResult:
    artifact_id: str
    risk_floor: str
    modifiers_applied: List[str]
    invariants_triggered: List[str]
    final_obligation: str
    reason_codes: List[str]
    rationale: str
    review_required: bool
    policy_version: str
    evidence_state: str
    ea_delivery: str
    native_actiongate_outcome: Optional[str] = None
    action_present: bool = False
    enforced: bool = False                    # ALWAYS False
    runner_version: str = RUNNER_VERSION
    replay_signature: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {"artifact_id": self.artifact_id, "final_obligation": self.final_obligation,
                "risk_floor": self.risk_floor, "modifiers_applied": self.modifiers_applied,
                "invariants_triggered": self.invariants_triggered, "reason_codes": self.reason_codes,
                "rationale": self.rationale, "review_required": self.review_required,
                "policy_version": self.policy_version, "evidence_state": self.evidence_state,
                "ea_delivery": self.ea_delivery,
                "native_actiongate_outcome": self.native_actiongate_outcome,
                "action_present": self.action_present, "enforced": self.enforced,
                "runner_version": self.runner_version, "replay_signature": self.replay_signature}


def _is_action(item: Dict[str, Any]) -> bool:
    return (item.get("claim_actionability") in ("action_proposal", "action_directive", "action_recommendation")
            or item.get("claim_family") == "action_proposal")


def run(item: Dict[str, Any]) -> SystemResult:
    d = policy.classify(item)                 # frozen policy, read-only
    steer = policy_adapters.to_evidence_steer(d, item)
    delivery = ea.run(steer, item.get("risk_tier", "medium")).local_disposition   # frozen EA, read-only

    action_present = _is_action(item)
    native_outcome: Optional[str] = None
    if action_present:
        # native ActionGate decides read-only; the 6-outcome vocabulary is preserved.
        nad = ag.evaluate({"action_type": "grant",
                           "authority_granted": bool(item.get("approval_evidence"))})
        native_outcome = nad.native_outcome if nad else None
        assert native_outcome is None or native_outcome in NATIVE_ACTIONGATE_OUTCOMES, native_outcome

    return SystemResult(
        artifact_id=item.get("artifact_id", "c"),
        risk_floor=d.risk_floor, modifiers_applied=d.modifiers_applied,
        invariants_triggered=d.invariants_triggered, final_obligation=d.final_obligation,
        reason_codes=d.reason_codes, rationale=d.rationale, review_required=d.review_required,
        policy_version=d.policy_version, evidence_state=steer["evidence_state"], ea_delivery=delivery,
        native_actiongate_outcome=native_outcome, action_present=action_present, enforced=False,
        replay_signature=policy.replay_signature(d))


def reveal_view(r: SystemResult) -> Dict[str, Any]:
    """The Stage-B post-reveal view shown to a reviewer (after Stage A is locked)."""
    return {
        "obligation": r.final_obligation, "risk_floor": r.risk_floor,
        "modifiers": r.modifiers_applied, "invariants": r.invariants_triggered,
        "rationale": r.rationale, "evidence_assurance": r.ea_delivery,
        "native_actiongate_outcome": r.native_actiongate_outcome, "review_required": r.review_required,
        "policy_version": r.policy_version, "enforced": r.enforced,
    }
