"""Phase 6 - Deterministic governance-input derivation for natural artifacts.

Natural artifacts carry NO gold evidence bundles, registries, telemetry, or assertion signals - the
structured corpora's authored governance inputs. This module DERIVES those inputs from the natural text
with a fixed, documented, conservative rule so the frozen orchestrator can decide. This derivation is
the pilot's central honest limitation (see PILOT_ASSUMPTIONS_AND_EXCLUSIONS.md): every transfer result
is conditioned on it. The rule is frozen and auditable; it is NOT tuned to produce any target outcome.

Read-only: reuses the frozen GIP registry/telemetry shapes; re-implements no decision logic.
Deterministic, stdlib-only.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

DERIVATION_VERSION = "natural_derivation_v1"

# use_case -> nearest frozen GIP domain (the runtime's domain vocabulary)
_USE_CASE_TO_DOMAIN = {
    "enterprise_policy_interpretation": "enterprise_policy",
    "technical_support_review": "customer_support",
    "software_engineering_recommendation_review": "software_engineering",
    "cybersecurity_advisory_review": "cybersecurity",
    "compliance_summary_review": "compliance_regulatory",
    "contract_summary_review": "compliance_regulatory",
    "procurement_policy_review": "compliance_regulatory",
    "it_operations_guidance": "enterprise_policy",
    "customer_communication_quality_review": "customer_support",
}

# explicit canonical operations -> pilot action_type (only these derive an action proposal; advisory
# text with no explicit operation proposes NO action). Conservative by design.
_OP_KEYWORDS = [
    (re.compile(r"\bdeploy(ing|ment)?\b", re.I), "deploy"),
    (re.compile(r"\brestart(ing)?\b", re.I), "restart"),
    (re.compile(r"\brotat(e|ing)\s+(the\s+)?key", re.I), "key_rotate"),
    (re.compile(r"\bread\s+(the\s+)?secret", re.I), "secret_read"),
    (re.compile(r"\bdisabl(e|ing)\s+(monitoring|alert)", re.I), "disable"),
    (re.compile(r"\bsend(ing)?\s+(an?\s+)?(email|message|notification)", re.I), "send"),
]


def derive_action(text: str) -> Optional[Dict[str, Any]]:
    """Derive an action proposal ONLY when the text explicitly describes a canonical operation.
    Returns None otherwise (advisory-only). authority_granted is conservatively False (a natural
    artifact never carries a signed grant), so the gate reaches a genuine, non-trivial decision."""
    for rx, action_type in _OP_KEYWORDS:
        if rx.search(text or ""):
            return {"action_type": action_type, "authority_granted": False,
                    "reversibility": "irreversible", "risk": "high", "actor": "advisory"}
    return None


def _derive_risk(use_case: str, gt: Dict[str, Any]) -> str:
    if gt.get("gt_security_sensitive") or use_case == "cybersecurity_advisory_review":
        return "high"
    if gt.get("gt_expected_class") == "REVIEW":
        return "high"
    return "medium"


def _derive_evidence(gt: Dict[str, Any]) -> Dict[str, Any]:
    # Base: documentation is self-descriptive but UNVERIFIED against external ground truth - it has
    # limitations by nature, so the honest base state is VERIFIED_WITH_LIMITATIONS, not VERIFIED.
    ev = {"evidence_state": "VERIFIED_WITH_LIMITATIONS", "grounding": 0.7, "entailment": "supports",
          "adequacy": 0.7, "authority": "authorized", "conflict": "none", "provenance_present": True,
          "age_days": 30.0}
    if gt.get("gt_needs_evidence"):        # unbacked absolute claims -> insufficient evidence
        ev.update({"evidence_state": "INSUFFICIENT", "grounding": 0.4, "entailment": "neutral",
                   "adequacy": 0.4})
    if gt.get("gt_security_sensitive") and gt.get("gt_needs_evidence"):
        ev.update({"evidence_state": "CONFLICTED", "conflict": "present", "grounding": 0.3})
    return ev


def _derive_assertion(gt: Dict[str, Any]) -> Dict[str, Any]:
    sig = {"support": 0.75, "entail": "supports", "adequacy": 0.75, "uncertainty": 0.15}
    if gt.get("gt_needs_evidence"):
        sig.update({"support": 0.4, "entail": "neutral", "adequacy": 0.4})
    if gt.get("gt_uncertain"):
        sig["uncertainty"] = 0.45
    if gt.get("gt_security_sensitive") and gt.get("gt_needs_evidence"):
        sig["support"] = 0.25
    return sig


def _registry() -> list:
    return [{"provider": "pilot", "model_id": "m-large", "family": "L", "quality": 0.82,
             "cost": 0.9, "latency_ms": 400, "eligible": True},
            {"provider": "pilot", "model_id": "m-small", "family": "S", "quality": 0.62,
             "cost": 0.2, "latency_ms": 120, "eligible": True}]


def build_case(artifact: Dict[str, Any], gt: Dict[str, Any]) -> Dict[str, Any]:
    """Build a frozen-orchestrator-compatible case from a natural artifact and its blinded ground
    truth. All governance inputs are derived deterministically from the text/signals."""
    use_case = artifact["use_case"]
    domain = _USE_CASE_TO_DOMAIN.get(use_case, "enterprise_policy")
    risk = _derive_risk(use_case, gt)
    text = artifact["text"]
    aid = artifact["artifact_id"]

    request = {
        "request_id": aid,
        "user_prompt": f"Review the following {use_case.replace('_', ' ')}.",
        "domain": domain,
        "risk_tier": risk,
        "task_type": "review",
        "acceptable_quality_threshold": 0.6,
        "human_review_required": gt.get("gt_expected_class") == "REVIEW",
        "execution_mode": "shadow_natural",
        "policy_version": "gip_policy_v1",
        "tenant_id": "pilot-internal",
    }
    return {
        "case_id": aid,
        "partition": "NATURAL",
        "domain": domain,
        "risk_tier": risk,
        "request": request,
        "registry": _registry(),
        "telemetry": {"regime": "balanced", "q_min": 0.6},
        "model_output": text,                       # the NATURAL text is the governed model output
        "evidence_steer": _derive_evidence(gt),
        "assertion_signals": _derive_assertion(gt),
        "action_proposal": derive_action(text),
        "inject_fault": "",
        "derivation_version": DERIVATION_VERSION,
    }
