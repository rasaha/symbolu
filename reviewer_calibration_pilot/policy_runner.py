"""Phase 8 - Frozen policy runner.

Runs the FROZEN minimal evidence-obligation policy read-only and passes its result through the frozen,
read-only EvidenceAssurance and (for action-bearing claims) the native ActionGate. Preserves the risk
floor, modifiers, invariants, final obligation, reason codes, review flag, policy version, and a
deterministic trace. Native ActionGate vocabulary is preserved (6 outcomes, never collapsed).

This module NEVER modifies any frozen component and NEVER enforces. Deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from minimal_evidence_policy import classifier as policy          # frozen (read-only)
from minimal_evidence_policy import adapters as policy_adapters    # frozen (read-only)
from minimal_evidence_policy import schema as mep_schema
from governed_inference_pilot.adapters import evidence_assurance as ea   # frozen (read-only)
from bounded_shadow_pilot import actiongate_contract as ag         # native ActionGate (read-only)

RUNNER_VERSION = "reviewer_calibration_policy_runner_v1"


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


def run(item: Dict[str, Any]) -> SystemResult:
    d = policy.classify(item)                 # frozen policy, read-only
    steer = policy_adapters.to_evidence_steer(d, item)
    delivery = ea.run(steer, item.get("risk_tier", "medium")).local_disposition   # frozen EA, read-only

    action_present = item.get("claim_actionability", "none") in ("action_proposal", "action_directive") \
        or item.get("claim_family") == "action_proposal"
    native_outcome = None
    if action_present:
        # native ActionGate decides read-only; vocabulary preserved (6 outcomes)
        nad = ag.evaluate({"action_type": "grant", "authority_granted": bool(item.get("approval_evidence"))})
        native_outcome = nad.native_outcome if nad else None

    return SystemResult(
        artifact_id=item.get("artifact_id", "c"),
        risk_floor=d.risk_floor, modifiers_applied=d.modifiers_applied,
        invariants_triggered=d.invariants_triggered, final_obligation=d.final_obligation,
        reason_codes=d.reason_codes, rationale=d.rationale, review_required=d.review_required,
        policy_version=d.policy_version, evidence_state=steer["evidence_state"], ea_delivery=delivery,
        native_actiongate_outcome=native_outcome, action_present=action_present, enforced=False,
        replay_signature=policy.replay_signature(d))


def reveal_view(r: SystemResult) -> Dict[str, Any]:
    """The Stage-B post-reveal view shown to a reviewer."""
    return {
        "obligation": r.final_obligation, "risk_floor": r.risk_floor,
        "modifiers": r.modifiers_applied, "invariants": r.invariants_triggered,
        "rationale": r.rationale, "evidence_assurance": r.ea_delivery,
        "native_actiongate_outcome": r.native_actiongate_outcome, "review_required": r.review_required,
        "policy_version": r.policy_version,
    }
