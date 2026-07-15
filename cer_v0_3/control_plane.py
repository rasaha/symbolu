"""CER V0.3 control-plane harness (cross-domain).

Receives ONLY the CER. Dispatches the operational-safety layer by the CER's
**profile family** (data carried in the CER, never a runtime switch):
  * Kubernetes profiles -> the frozen V0.2 control plane (unchanged);
  * ``database.mutation.v1`` -> the frozen ActionGate v2 gate + the new database
    operational-safety adapter, composed with the FROZEN ACP ``compose()``.

Invariants (identical to V0.1/V0.2): no ``runtime_type`` reaches the control plane;
no runtime-specific branch anywhere; ActionGate DENY is final; ACP can only hold,
never authorize; nothing actuates (shadow-only); deterministic (caller supplies now).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import _paths  # noqa: F401
from . import envelope as env_mod
from action_gate_ref import gate  # noqa: E402
from action_gate_ref import hashing  # noqa: E402
from action_gate_ref import projection  # noqa: E402

# frozen helpers reused unchanged
from cer_v0_1.control_plane import DEFAULT_SIGNED_POLICY, build_v2_evidence  # noqa: E402
from cer_v0_2 import control_plane as v2cp  # noqa: E402

from .acp_db.adapter import DbShadowAdapter  # noqa: E402
from .acp_db.envelopes import DbActionCandidate, DbWorldState  # noqa: E402
from symbolu_robotics.autonomous_control_plane.cloud.composition import AuthorizationVerdict  # noqa: E402

_V2_PROFILES = {"kubernetes.scale.v1", "kubernetes.rollout.v1"}
# risk tier is authoritative from the profile registry, never model-asserted.
_PROFILE_RISK = {"database.mutation.v1": "GOVERNED"}


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
            "execution_identity")} | {"reason_codes": list(self.reason_codes)}


def _db_world(cer: dict) -> DbWorldState:
    op = cer["state_binding"]["operational"]
    tgt = cer["actuation"]["target"]
    return DbWorldState(
        connection_ref=tgt["connection_ref"], schema=tgt["schema"], table=tgt["table"],
        observed_row_version=str(op["observed_row_version"]),
        reachable=bool(op["reachable"]), healthy=bool(op["healthy"]),
        active_transactions=int(op["active_transactions"]),
        max_transactions=int(op["max_transactions"]),
        max_affected_rows=int(op["max_affected_rows"]),
        migration_active=bool(op["migration_active"]), freeze_active=bool(op["freeze_active"]),
        replication_healthy=bool(op["replication_healthy"]),
        replication_lag_s=float(op["replication_lag_s"]),
        max_replication_lag_s=float(op["max_replication_lag_s"]),
        lock_contention_ok=bool(op["lock_contention_ok"]),
        backup_available=bool(op["backup_available"]),
        observation_time_s=float(op["observation_time_s"]))


def _db_candidate(cer: dict, world: DbWorldState) -> DbActionCandidate:
    act = cer["actuation"]
    scope = act["affected_scope"]
    return DbActionCandidate(
        candidate_id="cand:db-mutation", connection_ref=act["target"]["connection_ref"],
        schema=act["target"]["schema"], table=act["target"]["table"],
        sql_operation=act["sql_operation"], estimated_rows=int(scope["estimated_rows"]),
        unbounded=bool(scope["unbounded"]), reversibility=act["reversibility"],
        expected_row_version=act["expected_row_version"],
        compensation_ref=act.get("compensation_ref", ""),
        origin_state_version=world.version)


def _run_database(cer: dict, *, now: str, signed_policy, evidence, approvals,
                  used_nonces, acp_enabled: bool, auto_evidence: bool) -> ControlPlaneResult:
    signed_policy = signed_policy or DEFAULT_SIGNED_POLICY
    tier = _PROFILE_RISK.get(cer["profile"], "GOVERNED")
    claimed = cer.get("risk_tier", tier)
    if tier == "GOVERNED" and claimed != "GOVERNED":
        raise ValueError(f"{cer['profile']} is GOVERNED; CER claimed {claimed!r}")
    cm = "SKIPPED_NO_ACTIONGATE_CONTEXT"

    env = env_mod.to_envelope(cer)
    cer_digest = projection.action_hash(env, identity_profile="v2")
    if auto_evidence and evidence is None:
        evidence = build_v2_evidence(env, now=now)

    dec = gate.evaluate(env, signed_policy, evidence=evidence, approvals=approvals,
                        now=now, used_nonces=used_nonces, identity_profile="v2")
    av = AuthorizationVerdict(dec["outcome"])

    op = cer["state_binding"]["operational"]
    world = _db_world(cer)
    cand = _db_candidate(cer, world)
    acp = DbShadowAdapter(enabled=acp_enabled)
    res = acp.observe(decision_id=cer_digest[:16], world=world, candidate=cand,
                      now_s=float(op["observation_time_s"]), freshness_s=0.0, authorization=av)
    combined = res.combined_outcome if res else None
    eligible = combined == "PROCEED"
    exec_id = None
    if eligible:
        frame = f"{cer_digest}|{combined}|{dec['action_hash']}".encode("ascii")
        exec_id = hashing.domain_digest("EXECUTION_TOKEN", frame, schema_version="2.0.0")
    return ControlPlaneResult(
        cer_digest=cer_digest, profile=cer["profile"], risk_tier=tier,
        context_minimization=cm, actiongate_outcome=dec["outcome"],
        actiongate_action_hash=dec["action_hash"],
        acp_decision=res.acp_decision if res else "DISABLED",
        cloud_recommendation=res.cloud_recommendation if res else "DISABLED",
        combined_outcome=combined, eligible=eligible, execution_identity=exec_id,
        reason_codes=res.reason_codes if res else ())


def run_control_plane(cer: dict, *, now: str, signed_policy=None,
                      evidence: Optional[List[dict]] = None,
                      approvals: Optional[List[dict]] = None, used_nonces=(),
                      acp_enabled: bool = True, auto_evidence: bool = False
                      ) -> ControlPlaneResult:
    if cer.get("profile") in _V2_PROFILES:
        r = v2cp.run_control_plane(cer, now=now, signed_policy=signed_policy,
                                   evidence=evidence, approvals=approvals,
                                   used_nonces=used_nonces, acp_enabled=acp_enabled,
                                   auto_evidence=auto_evidence)
        return ControlPlaneResult(
            cer_digest=r.cer_digest, profile=r.profile, risk_tier=r.risk_tier,
            context_minimization=r.context_minimization,
            actiongate_outcome=r.actiongate_outcome,
            actiongate_action_hash=r.actiongate_action_hash, acp_decision=r.acp_decision,
            cloud_recommendation=r.cloud_recommendation, combined_outcome=r.combined_outcome,
            eligible=r.eligible, execution_identity=r.execution_identity,
            reason_codes=r.reason_codes)
    return _run_database(cer, now=now, signed_policy=signed_policy, evidence=evidence,
                         approvals=approvals, used_nonces=used_nonces,
                         acp_enabled=acp_enabled, auto_evidence=auto_evidence)
