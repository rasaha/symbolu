"""CER V0.2 profile-driven control-plane harness.

Reuses the frozen ActionGate v2 identity profile + ACP core + the V0.1 evidence
builder and observation loop unchanged. Profile-aware only via the envelope/ACP
mappings; the control plane itself receives ONLY the CER — no runtime_type and no
profile-specific branch beyond the mapping dispatch (which is data, not a runtime
switch).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import _paths  # noqa: F401
from . import envelope as env_mod
from .profiles import get_profile
from action_gate_ref import gate  # noqa: E402
from action_gate_ref import hashing  # noqa: E402
from action_gate_ref import projection  # noqa: E402

# reuse V0.1 frozen helpers (unchanged)
from cer_v0_1.control_plane import DEFAULT_SIGNED_POLICY, build_v2_evidence  # noqa: E402

from symbolu_robotics.autonomous_control_plane.cloud.adapter import CloudShadowAdapter  # noqa: E402
from symbolu_robotics.autonomous_control_plane.cloud.composition import AuthorizationVerdict  # noqa: E402

# risk tier is controlled by the profile/tool registry, never model-asserted.
_PROFILE_RISK = {"kubernetes.scale.v1": "GOVERNED", "kubernetes.rollout.v1": "GOVERNED"}


class RiskTierViolation(ValueError):
    pass


@dataclass(frozen=True)
class ControlPlaneResult:
    cer_digest: str
    profile: str
    risk_tier: str
    context_minimization: str
    actiongate_outcome: str
    actiongate_action_hash: str
    acp_decision: str
    cloud_recommendation: str
    combined_outcome: Optional[str]
    eligible: bool
    execution_identity: Optional[str]
    reason_codes: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in (
            "cer_digest", "profile", "risk_tier", "context_minimization",
            "actiongate_outcome", "actiongate_action_hash", "acp_decision",
            "cloud_recommendation", "combined_outcome", "eligible",
            "execution_identity")} | {"reason_codes": list(self.reason_codes),
            "retryable": self.actiongate_outcome in (
                "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY", "ESCALATE_TO_HUMAN")}


def _enforce_tier(cer: dict) -> str:
    prof = cer["profile"]
    auth = _PROFILE_RISK.get(prof, "GOVERNED")
    claimed = cer.get("risk_tier", auth)
    if auth == "GOVERNED" and claimed != "GOVERNED":
        raise RiskTierViolation(f"{prof} is GOVERNED; CER claimed {claimed!r}")
    return auth


def run_control_plane(cer: dict, *, now: str, signed_policy=None,
                      evidence: Optional[List[dict]] = None,
                      approvals: Optional[List[dict]] = None, used_nonces=(),
                      acp_enabled: bool = True, auto_evidence: bool = False) -> ControlPlaneResult:
    signed_policy = signed_policy or DEFAULT_SIGNED_POLICY
    tier = _enforce_tier(cer)
    # Context Minimization: only where an ActionGate-shaped span context is present.
    cm = "SKIPPED_NO_ACTIONGATE_CONTEXT"

    env = env_mod.to_envelope(cer)
    cer_digest = projection.action_hash(env, identity_profile="v2")
    if auto_evidence and evidence is None:
        evidence = build_v2_evidence(env, now=now)

    dec = gate.evaluate(env, signed_policy, evidence=evidence, approvals=approvals,
                        now=now, used_nonces=used_nonces, identity_profile="v2")
    av = AuthorizationVerdict(dec["outcome"])

    op = cer["state_binding"]["operational"]
    acp = CloudShadowAdapter(enabled=acp_enabled)
    res = acp.observe(decision_id=cer_digest[:16], world=env_mod.to_cloud_world(cer),
                      candidates=[env_mod.to_cloud_candidate(cer)],
                      now_s=float(op["observation_time_s"]), freshness_s=0.0,
                      authorization=av, tick=0)
    combined = res.composition.combined.value if res.composition else None
    eligible = combined == "PROCEED"
    exec_id = None
    if eligible:
        frame = f"{cer_digest}|{combined}|{dec['action_hash']}".encode("ascii")
        exec_id = hashing.domain_digest("EXECUTION_TOKEN", frame, schema_version="2.0.0")
    return ControlPlaneResult(
        cer_digest=cer_digest, profile=cer["profile"], risk_tier=tier,
        context_minimization=cm, actiongate_outcome=dec["outcome"],
        actiongate_action_hash=dec["action_hash"], acp_decision=str(res.acp_decision),
        cloud_recommendation=str(res.cloud_recommendation), combined_outcome=combined,
        eligible=eligible, execution_identity=exec_id,
        reason_codes=tuple(res.record.reason_codes) if res.record else ())
