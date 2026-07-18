"""Cloud shadow evaluation corpus (V2 §9).

Every scenario carries an explicit ``provenance`` label:

* ``REPOSITORY_MANIFEST``     — grounded in a real ``deploy/gke/*.yaml`` manifest.
* ``REPOSITORY_SCENARIO``     — mirrors a real ``cloud_controller`` config/behaviour.
* ``INTEGRATION_TEST_FIXTURE``— mirrors an ActionGate K8s demo fixture.
* ``AUTHORED_DETERMINISTIC``  — hand-authored operational fixture (documented).
* ``SYNTHETIC_UNIT``          — synthetic edge case for an invariant.

The two decisive cross-domain scenarios are ``ag_allows_acp_holds`` and
``ag_denies_acp_safe`` — they prove ActionGate and ACP answer *different*
questions (§9, §14 boundary verdict).

Deterministic + stdlib-only. Times are fixed constants (no wall clock).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from symbolu_robotics.autonomous_control_plane.cloud import (
    AuthorizationVerdict,
    CloudActionCandidate,
    CloudOperation,
    CloudWorldState,
)

NOW_S = 1_000_000.0  # fixed decision time for the whole corpus


@dataclass(frozen=True)
class CloudScenario:
    """One deterministic shadow scenario."""
    scenario_id: str
    provenance: str
    description: str
    world: Optional[CloudWorldState]
    candidates: Tuple[CloudActionCandidate, ...]
    freshness_s: float
    authorization: Optional[AuthorizationVerdict] = None
    # Expected (for the harness to score; not fed to the evaluator):
    expect_permissive: bool = False          # ACP would let it proceed
    expect_combined: Optional[str] = None    # combined outcome if AG given
    # Commit-revalidation drift (optional second world for TOCTOU scenarios):
    drift_world: Optional[CloudWorldState] = None
    drift_manifest_candidate: Optional[CloudActionCandidate] = None
    notes: str = field(default="")


def _ws(**kw) -> CloudWorldState:
    base = dict(
        cluster="gke-prod-us", namespace="default", deployment="demo-app",
        resource_version="1001", generation=3, desired_replicas=3,
        current_replicas=3, available_replicas=3, readiness_plasticity=0.80,
        active_rollback_watches=0, seconds_since_last_action=600.0,
        dependency_healthy=True, freeze_active=False, observation_time_s=NOW_S,
    )
    base.update(kw)
    return CloudWorldState(**base)


def _cand(version: str, **kw) -> CloudActionCandidate:
    base = dict(
        candidate_id="c", operation=CloudOperation.SCALE, namespace="default",
        deployment="demo-app", current_replicas=3, desired_replicas=4,
        manifest_digest="", rollback_ref="", rollout_strategy="RollingUpdate",
        max_unavailable=1, max_surge=1, timeout_s=60.0,
        origin_state_version=version,
    )
    base.update(kw)
    return CloudActionCandidate(**base)


def build_corpus() -> List[CloudScenario]:
    scenarios: List[CloudScenario] = []

    # 1. healthy rollout — real demo-app manifest (replicas: 3, RollingUpdate).
    ws = _ws(provenance="REPOSITORY_MANIFEST:deploy/gke/demo-app.yaml")
    scenarios.append(CloudScenario(
        "healthy_rollout", "REPOSITORY_MANIFEST",
        "demo-app scale 3->4 on a healthy, ready cluster",
        ws, (_cand(ws.version, candidate_id="scale_up",
                   provenance="REPOSITORY_MANIFEST:deploy/gke/demo-app.yaml"),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=True, expect_combined="PROCEED"))

    # 2. insufficient capacity — deployment currently serving 0 available.
    ws = _ws(available_replicas=0)
    scenarios.append(CloudScenario(
        "insufficient_capacity", "AUTHORED_DETERMINISTIC",
        "mutating op on a deployment with 0 available replicas (already broken)",
        ws, (_cand(ws.version, candidate_id="scale_broken"),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=False, expect_combined="HELD_BY_ACP"))

    # 3. stale state — freshness beyond the 30s horizon.
    ws = _ws()
    scenarios.append(CloudScenario(
        "stale_state", "AUTHORED_DETERMINISTIC",
        "cluster state older than the freshness horizon => fail closed",
        ws, (_cand(ws.version, candidate_id="scale_stale"),),
        freshness_s=90.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=False, expect_combined="HELD_BY_ACP"))

    # 4. invalid manifest — ROLLOUT with empty manifest_digest AND no rollback.
    ws = _ws()
    scenarios.append(CloudScenario(
        "invalid_manifest", "AUTHORED_DETERMINISTIC",
        "ROLLOUT with no rollback ref (invalid/unsafe rollout artifact)",
        ws, (_cand(ws.version, candidate_id="bad_rollout",
                   operation=CloudOperation.ROLLOUT, desired_replicas=3,
                   manifest_digest="sha256:deadbeef", rollback_ref=""),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=False, expect_combined="HELD_BY_ACP"))

    # 5. excessive replica increase — 3 -> 90 (> +50% real SafetyBounds bound).
    ws = _ws()
    scenarios.append(CloudScenario(
        "excessive_replica_increase", "REPOSITORY_SCENARIO",
        "scale 3->90 exceeds the real SafetyBounds +50% per-action bound",
        ws, (_cand(ws.version, candidate_id="scale_huge", desired_replicas=90),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=False, expect_combined="HELD_BY_ACP"))

    # 6. excessive blast radius — DELETE of an 8-replica deployment.
    ws = _ws(desired_replicas=8, current_replicas=8, available_replicas=8)
    scenarios.append(CloudScenario(
        "excessive_blast_radius", "AUTHORED_DETERMINISTIC",
        "DELETE takes out all 8 replicas — operational blast radius too large",
        ws, (_cand(ws.version, candidate_id="delete_all",
                   operation=CloudOperation.DELETE, current_replicas=8,
                   desired_replicas=0, rollback_ref="rb-1"),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=False, expect_combined="HELD_BY_ACP"))

    # 7. missing rollback — CONFIG_UPDATE without a rollback ref.
    ws = _ws()
    scenarios.append(CloudScenario(
        "missing_rollback", "AUTHORED_DETERMINISTIC",
        "CONFIG_UPDATE with no rollback path => not admissible",
        ws, (_cand(ws.version, candidate_id="cfg_norb",
                   operation=CloudOperation.CONFIG_UPDATE, desired_replicas=3,
                   manifest_digest="sha256:cfg", rollback_ref=""),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=False, expect_combined="HELD_BY_ACP"))

    # 8. dependency unhealthy — upstream dependency down.
    ws = _ws(dependency_healthy=False)
    scenarios.append(CloudScenario(
        "dependency_unhealthy", "AUTHORED_DETERMINISTIC",
        "a required dependency is unhealthy => hold",
        ws, (_cand(ws.version, candidate_id="scale_dep"),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=False, expect_combined="HELD_BY_ACP"))

    # 9. active freeze window — real BlackoutWindow semantics (carried flag).
    ws = _ws(freeze_active=True)
    scenarios.append(CloudScenario(
        "active_freeze_window", "REPOSITORY_SCENARIO",
        "a cloud_controller BlackoutWindow is active => hold",
        ws, (_cand(ws.version, candidate_id="scale_freeze"),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=False, expect_combined="HELD_BY_ACP"))

    # 10. safe constrained rollout — real rollout with rollback + small surge.
    ws = _ws(deployment="demo-app")
    scenarios.append(CloudScenario(
        "safe_constrained_rollout", "REPOSITORY_MANIFEST:deploy/gke/demo-app.yaml",
        "RollingUpdate rollout, rollback present, surge 1 within bound",
        ws, (_cand(ws.version, candidate_id="rollout_ok",
                   operation=CloudOperation.ROLLOUT, desired_replicas=3,
                   manifest_digest="sha256:img125", rollback_ref="rev-2",
                   max_surge=1, max_unavailable=0),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW_WITH_CONSTRAINTS,
        expect_permissive=True, expect_combined="PROCEED"))

    # 11. destructive delete (guarded) — DELETE with rollback but on ready state.
    ws = _ws(desired_replicas=2, current_replicas=2, available_replicas=2)
    scenarios.append(CloudScenario(
        "destructive_delete_small", "AUTHORED_DETERMINISTIC",
        "DELETE of a 2-replica deployment: blast within bound but destructive",
        ws, (_cand(ws.version, candidate_id="delete_small",
                   operation=CloudOperation.DELETE, current_replicas=2,
                   desired_replicas=0, rollback_ref="rb-2"),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ESCALATE_TO_HUMAN,
        expect_permissive=False, expect_combined="PENDING_AUTHORIZATION"))

    # 12. modified manifest after eval — commit revalidation must reject.
    ws = _ws()
    orig = _cand(ws.version, candidate_id="rollout_mut",
                 operation=CloudOperation.ROLLOUT, desired_replicas=3,
                 manifest_digest="sha256:orig", rollback_ref="rev-1")
    mutated = _cand(ws.version, candidate_id="rollout_mut",
                    operation=CloudOperation.ROLLOUT, desired_replicas=3,
                    manifest_digest="sha256:TAMPERED", rollback_ref="rev-1")
    scenarios.append(CloudScenario(
        "modified_manifest_after_eval", "SYNTHETIC_UNIT",
        "manifest digest changes between decision and commit => revalidation rejects",
        ws, (orig,), freshness_s=2.0,
        authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=True, expect_combined="PROCEED",
        drift_manifest_candidate=mutated,
        notes="commit_revalidate must return still_valid=False (action rebound)"))

    # 13. state drift — resourceVersion changes between decision and commit.
    ws = _ws(resource_version="2001")
    drift = _ws(resource_version="2002", current_replicas=5, desired_replicas=5,
                available_replicas=5)
    scenarios.append(CloudScenario(
        "state_drift", "SYNTHETIC_UNIT",
        "cluster resourceVersion drifts between decision and commit (TOCTOU)",
        ws, (_cand(ws.version, candidate_id="scale_drift"),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=True, expect_combined="PROCEED",
        drift_world=drift,
        notes="commit_revalidate must return still_valid=False (state changed)"))

    # 14. all strategies unsafe — every candidate fails a distinct hard gate.
    ws = _ws(freeze_active=True, dependency_healthy=False, available_replicas=0)
    cands = (
        _cand(ws.version, candidate_id="a_freeze"),
        _cand(ws.version, candidate_id="a_huge", desired_replicas=99),
        _cand(ws.version, candidate_id="a_delete",
              operation=CloudOperation.DELETE, current_replicas=3,
              desired_replicas=0, rollback_ref=""),
    )
    scenarios.append(CloudScenario(
        "all_strategies_unsafe", "SYNTHETIC_UNIT",
        "no candidate is operationally admissible => NO_SAFE_ACTION / HOLD",
        ws, cands, freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=False, expect_combined="HELD_BY_ACP"))

    # 15. ActionGate ALLOWS but ACP HOLDS — the decisive boundary case.
    #     Authorized to scale (identity/RBAC/nonce all fine) but the live
    #     cluster is not ready (recent action 30s ago < 120s real threshold).
    ws = _ws(seconds_since_last_action=30.0, readiness_plasticity=0.80)
    scenarios.append(CloudScenario(
        "ag_allows_acp_holds", "REPOSITORY_SCENARIO",
        "authorized scale, but real ReadinessChecker blocks (action 30s ago < 120s)",
        ws, (_cand(ws.version, candidate_id="scale_notready"),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=False, expect_combined="HELD_BY_ACP",
        notes="proves ACP answers a question ActionGate does not: live readiness"))

    # 16. ActionGate DENIES but ACP would find SAFE — the mirror boundary case.
    #     Operationally perfectly safe scale, but authorization is denied
    #     (e.g. missing approver / RBAC). ACP safe finding must NOT override.
    ws = _ws()
    scenarios.append(CloudScenario(
        "ag_denies_acp_safe", "REPOSITORY_SCENARIO",
        "operationally-safe scale, but ActionGate DENY => blocked (ACP cannot override)",
        ws, (_cand(ws.version, candidate_id="scale_denied"),),
        freshness_s=2.0, authorization=AuthorizationVerdict.DENY,
        expect_permissive=True, expect_combined="BLOCKED_BY_AUTHORIZATION",
        notes="proves an ACP safe verdict never mints authorization"))

    # 17. missing state — no cluster snapshot => fail closed.
    scenarios.append(CloudScenario(
        "missing_state", "SYNTHETIC_UNIT",
        "no cluster state snapshot available => fail closed to HOLD",
        None, (_cand("nonexistent-version", candidate_id="scale_nostate"),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=False, expect_combined="HELD_BY_ACP"))

    # 18. state binding mismatch — candidate references a different state version.
    ws = _ws()
    scenarios.append(CloudScenario(
        "state_binding_mismatch", "SYNTHETIC_UNIT",
        "candidate built against a stale state version => fail closed",
        ws, (_cand("wrong-version", candidate_id="scale_wrongbind"),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=False, expect_combined="HELD_BY_ACP"))

    # 19. ncc-controller real manifest — single-replica controller (replicas: 1).
    ws = _ws(cluster="gke-ncc", namespace="ncc", deployment="ncc-controller",
             desired_replicas=1, current_replicas=1, available_replicas=1,
             provenance="REPOSITORY_MANIFEST:deploy/gke/deployment.yaml")
    scenarios.append(CloudScenario(
        "ncc_controller_scale", "REPOSITORY_MANIFEST:deploy/gke/deployment.yaml",
        "scale the real ncc-controller 1->1 (no-op safe) — min replicas honoured",
        ws, (_cand(ws.version, candidate_id="ncc_noop", namespace="ncc",
                   deployment="ncc-controller", current_replicas=1,
                   desired_replicas=1),),
        freshness_s=2.0, authorization=AuthorizationVerdict.ALLOW,
        expect_permissive=True, expect_combined="PROCEED"))

    return scenarios


# Provenance tally for the results header.
def provenance_counts(scenarios: List[CloudScenario]) -> dict:
    out: dict = {}
    for s in scenarios:
        key = s.provenance.split(":", 1)[0]
        out[key] = out.get(key, 0) + 1
    return out
