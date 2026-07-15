"""Frozen AI Control Plane harness for CER V0.1.

Pipeline for a governed CER (milestone §6), using the REAL frozen components:
    CER -> [Context Minimization iff ActionGate-shaped context present] ->
    real ActionGate (identity_profile=v2) -> real ACP cloud operational safety ->
    deterministic composition -> hypothetical execution eligibility/identity.

Hard rules:
* The control plane receives ONLY the CER. There is NO ``runtime_type`` switch and
  no LangGraph/Ugence-specific branch anywhere here or downstream.
* Nothing actuates. ACP is shadow-only; no token is minted against a real system;
  the "execution identity" is hypothetical (eligible iff both layers pass).
* Deterministic: no wall clock / randomness. ``now`` is supplied by the caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from . import _paths  # noqa: F401
from . import risk_tier, spec
from action_gate_ref import evidence as evidence_mod  # noqa: E402
from action_gate_ref import gate  # noqa: E402
from action_gate_ref import hashing  # noqa: E402
from action_gate_ref import policy as policy_mod  # noqa: E402
from action_gate_ref import projection  # noqa: E402

from symbolu_robotics.autonomous_control_plane.cloud.adapter import CloudShadowAdapter  # noqa: E402
from symbolu_robotics.autonomous_control_plane.cloud.composition import AuthorizationVerdict  # noqa: E402

# One frozen signed policy for the experiment (built once, deterministic).
DEFAULT_SIGNED_POLICY = policy_mod.sign_policy(policy_mod.build_bundle())

_ALLOW_LIKE = {"ALLOW", "ALLOW_WITH_CONSTRAINTS"}


@dataclass(frozen=True)
class ControlPlaneResult:
    cer_digest: str
    risk_tier: str
    context_minimization: str  # "SKIPPED_NO_ACTIONGATE_CONTEXT" | "APPLIED"
    actiongate_outcome: str
    actiongate_action_hash: str
    acp_decision: str
    cloud_recommendation: str
    combined_outcome: Optional[str]
    eligible: bool
    execution_identity: Optional[str]
    reason_codes: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "cer_digest": self.cer_digest, "risk_tier": self.risk_tier,
            "context_minimization": self.context_minimization,
            "actiongate_outcome": self.actiongate_outcome,
            "actiongate_action_hash": self.actiongate_action_hash,
            "acp_decision": self.acp_decision,
            "cloud_recommendation": self.cloud_recommendation,
            "combined_outcome": self.combined_outcome,
            "eligible": self.eligible,
            "execution_identity": self.execution_identity,
            "reason_codes": list(self.reason_codes),
            # for the LangGraph governed-loop callback
            "retryable": self.actiongate_outcome in (
                "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY", "ESCALATE_TO_HUMAN"),
        }


def build_v2_evidence(envelope: dict, *, now: str, kinds=("signed_artifact", "simulation")) -> List[dict]:
    """Evidence bound to the v2 action_hash (proves binding under the new profile)."""
    ah = projection.action_hash(envelope, identity_profile="v2")
    out = []
    if "signed_artifact" in kinds:
        out.append(evidence_mod.build_evidence(
            bound_to=ah, producer="registry", generated_at=now,
            valid_until="2030-01-01T00:00:00.000Z", evidence_version="1",
            kind="signed_artifact", fidelity_or_confidence="HIGH",
            content={"artifact": "sha256:abc", "signed": "yes"}))
    if "simulation" in kinds:
        out.append(evidence_mod.build_evidence(
            bound_to=ah, producer="terraform-plan", generated_at=now,
            valid_until="2030-01-01T00:00:00.000Z", evidence_version="1",
            kind="simulation", fidelity_or_confidence="HIGH", is_simulation=True,
            content={"coverage": "0.9", "predicted_changes": [], "affected_resources": []}))
    return out


def _has_actiongate_context(cer: dict) -> bool:
    """Context Minimization runs ONLY where the ActionGate-shaped context contract
    is present. CER V0.1 carries no such span-context, so it is honestly skipped
    (not generalized beyond its implemented guarantee)."""
    ctx = cer.get("context_bundle")
    return isinstance(ctx, dict) and bool(ctx.get("actiongate_spans"))


def run_control_plane(
    cer: dict, *, now: str, signed_policy: Optional[dict] = None,
    evidence: Optional[List[dict]] = None, approvals: Optional[List[dict]] = None,
    used_nonces=(), acp_enabled: bool = True, auto_evidence: bool = False,
) -> ControlPlaneResult:
    """Run the full frozen control plane on one CER. Receives ONLY the CER."""
    signed_policy = signed_policy or DEFAULT_SIGNED_POLICY

    # 0. risk tier — authoritative from the tool profile (not model-asserted)
    tier = risk_tier.enforce_tier(cer)

    # 1. Context Minimization — only if the ActionGate-shaped context is present.
    cm = "APPLIED" if _has_actiongate_context(cer) else "SKIPPED_NO_ACTIONGATE_CONTEXT"

    # 2. derive the canonical envelope + identity (v2)
    env = spec.to_envelope(cer)
    cer_digest = projection.action_hash(env, identity_profile="v2")

    if auto_evidence and evidence is None:
        evidence = build_v2_evidence(env, now=now)

    # 3. real ActionGate (v2 identity — provenance excluded)
    dec = gate.evaluate(
        env, signed_policy, evidence=evidence, approvals=approvals,
        now=now, used_nonces=used_nonces, identity_profile="v2")
    ag_outcome = dec["outcome"]
    ag_ah = dec["action_hash"]

    # 4. real ACP cloud operational safety, composed with the AG verdict
    av = AuthorizationVerdict(ag_outcome)
    acp = CloudShadowAdapter(enabled=acp_enabled)
    op = cer["identity"]["external_state_binding"]["operational"]
    now_s = float(op["observation_time_s"])
    res = acp.observe(
        decision_id=cer_digest[:16], world=spec.to_cloud_world(cer),
        candidates=[spec.to_cloud_candidate(cer)], now_s=now_s, freshness_s=0.0,
        authorization=av, tick=0)
    acp_decision = str(res.acp_decision)
    cloud_rec = str(res.cloud_recommendation)
    combined = res.composition.combined.value if res.composition else None
    eligible = combined == "PROCEED"

    # 5. hypothetical execution identity — bound to (cer_digest, composed), only
    #    when eligible. Never a real token; ACP is shadow-only.
    exec_id = None
    if eligible:
        frame = f"{cer_digest}|{combined}|{ag_ah}".encode("ascii")
        exec_id = hashing.domain_digest(
            "EXECUTION_TOKEN", frame, schema_version="2.0.0")

    return ControlPlaneResult(
        cer_digest=cer_digest, risk_tier=tier, context_minimization=cm,
        actiongate_outcome=ag_outcome, actiongate_action_hash=ag_ah,
        acp_decision=acp_decision, cloud_recommendation=cloud_rec,
        combined_outcome=combined, eligible=eligible, execution_identity=exec_id,
        reason_codes=tuple(res.record.reason_codes) if res.record else (),
    )
