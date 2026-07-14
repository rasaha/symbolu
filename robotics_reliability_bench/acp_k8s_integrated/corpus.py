"""Integrated ActionGate + ACP Kubernetes scenario corpus (V2.1 §6).

Base Deployment state is the REAL `action_gateway_k8s` integration fixture —
Deployment ``web`` / ``gw-web`` in namespace ``protected``, ``replicas: 1``
(`scripts/cluster_fixtures.sh:44-62`, `demos/scenarios.py:79-91`). That spec is
labelled ``REPOSITORY_INTEGRATION_FIXTURE``. resourceVersion, availableReplicas,
readiness, freeze windows, and dependency health have no offline source, so they
are authored and labelled ``AUTHORED_DETERMINISTIC`` (a live/kind cluster is
infeasible here — see `LIVE_K8S_SHADOW_METHOD.md`). Pure edge cases are
``SYNTHETIC_UNIT``. No local-cluster data is called production customer evidence.

Every scenario names an expected `CompositionClass`; the benchmark asserts the
REAL composed result matches (0 mismatches required, §10 correctness).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from robotics_reliability_bench.acp_k8s_integrated.composition import CompositionClass
from robotics_reliability_bench.acp_k8s_integrated.harness import CommitDrift
from robotics_reliability_bench.acp_k8s_integrated.identity_binding import (
    KubernetesOperation,
)


@dataclass(frozen=True)
class IntegratedScenario:
    scenario_id: str
    provenance: str
    description: str
    op: KubernetesOperation
    expected_class: CompositionClass
    freshness_s: float = 1.0
    ag_overrides: Optional[dict] = None
    acp_manifest_digest_override: Optional[str] = None
    commit_drift: Optional[CommitDrift] = None
    inject_shadow_error: bool = False
    # extra expectations for §11 commit revalidation
    expect_commit_still_valid: Optional[bool] = None
    expect_ag_rejects: Optional[bool] = None
    expect_acp_rejects: Optional[bool] = None


def _op(**kw) -> KubernetesOperation:
    """Base = real fixture Deployment web/protected/replicas:1, healthy + ready."""
    base = dict(
        cluster="ref-cp", namespace="protected", deployment="web",
        k8s_verb="SCALE", current_replicas=1, desired_replicas=2,
        resource_version="1001", generation=1, available_replicas=1,
        readiness_plasticity=0.80, seconds_since_last_action=600.0,
        dependency_healthy=True, freeze_active=False, active_rollback_watches=0,
        rollback_ref="", compliant_manifest=True,
        provenance="REPOSITORY_INTEGRATION_FIXTURE")
    base.update(kw)
    return KubernetesOperation(**base)


def build_corpus() -> List[IntegratedScenario]:
    C = CompositionClass
    s: List[IntegratedScenario] = []

    # 1. authorized healthy scale (both pass) — real fixture.
    s.append(IntegratedScenario(
        "authorized_healthy_scale", "REPOSITORY_INTEGRATION_FIXTURE",
        "web/protected 1->2 on a ready cluster; authorized + operationally safe",
        _op(), C.AUTHORIZED_AND_OPERATIONALLY_SAFE))

    # 2. unauthorized but operationally safe (ns out of ActionGate scope).
    s.append(IntegratedScenario(
        "unauthorized_but_safe", "AUTHORED_DETERMINISTIC",
        "scale in ns 'sandbox' (outside ActionGate allowed) though op-safe",
        _op(namespace="sandbox", deployment="web"), C.BLOCKED_BY_AUTHORIZATION))

    # 3. authorized during readiness cooldown (real ReadinessChecker blocks).
    s.append(IntegratedScenario(
        "authorized_readiness_cooldown", "AUTHORED_DETERMINISTIC",
        "authorized scale, but a scaling action 30s ago < 120s cooldown",
        _op(seconds_since_last_action=30.0), C.HELD_BY_OPERATIONAL_SAFETY))

    # 4. authorized exceeding replica/capacity limit (real SafetyBounds).
    s.append(IntegratedScenario(
        "authorized_excessive_replicas", "AUTHORED_DETERMINISTIC",
        "authorized scale 1->50 exceeds real SafetyBounds per-action bound",
        _op(desired_replicas=50), C.HELD_BY_OPERATIONAL_SAFETY))

    # 5. stale resourceVersion / operational state.
    s.append(IntegratedScenario(
        "stale_operational_state", "AUTHORED_DETERMINISTIC",
        "authorized, but ACP operational state older than the freshness horizon",
        _op(), C.REQUEST_FRESH_OPERATIONAL_STATE, freshness_s=99.0))

    # 6. state drift after both evaluations (commit-time TOCTOU).
    s.append(IntegratedScenario(
        "state_drift_after_eval", "SYNTHETIC_UNIT",
        "resourceVersion drifts between evaluation and commit — both layers reject",
        _op(), C.AUTHORIZED_AND_OPERATIONALLY_SAFE,
        commit_drift=CommitDrift(new_resource_version="2002"),
        expect_commit_still_valid=False, expect_ag_rejects=True,
        expect_acp_rejects=True))

    # 7. modified patch after evaluation (commit-time).
    s.append(IntegratedScenario(
        "modified_patch_after_eval", "SYNTHETIC_UNIT",
        "manifest/patch digest mutated after eval — both layers reject",
        _op(), C.AUTHORIZED_AND_OPERATIONALLY_SAFE,
        commit_drift=CommitDrift(mutated_manifest_digest="sha256:TAMPERED"),
        expect_commit_still_valid=False, expect_ag_rejects=True,
        expect_acp_rejects=True))

    # 8. missing rollback for a high-risk rollout (ACP holds; AG allows).
    s.append(IntegratedScenario(
        "rollout_missing_rollback", "AUTHORED_DETERMINISTIC",
        "authorized ROLLOUT with no rollback ref — ACP operational hold",
        _op(k8s_verb="ROLLOUT", desired_replicas=1, rollback_ref=""),
        C.HELD_BY_OPERATIONAL_SAFETY))

    # 9. active freeze / blackout window (ACP holds).
    s.append(IntegratedScenario(
        "active_freeze_window", "AUTHORED_DETERMINISTIC",
        "authorized scale during an active freeze window — ACP hold",
        _op(freeze_active=True), C.HELD_BY_OPERATIONAL_SAFETY))

    # 10. dependency / readiness failure (ACP holds).
    s.append(IntegratedScenario(
        "dependency_unhealthy", "AUTHORED_DETERMINISTIC",
        "authorized scale while a dependency is unhealthy — ACP hold",
        _op(dependency_healthy=False), C.HELD_BY_OPERATIONAL_SAFETY))

    # 11. both layers block (unauthorized ns + active freeze).
    s.append(IntegratedScenario(
        "blocked_by_both", "AUTHORED_DETERMINISTIC",
        "out-of-scope namespace AND active freeze — authorization + operational block",
        _op(namespace="sandbox", freeze_active=True), C.BLOCKED_BY_BOTH))

    # 12. ActionGate requests evidence while ACP passes (missing simulation).
    s.append(IntegratedScenario(
        "ag_requests_evidence_acp_passes", "AUTHORED_DETERMINISTIC",
        "authorized-but-not-final (missing dry-run simulation) while ACP is safe",
        _op(), C.REQUEST_MORE_EVIDENCE,
        ag_overrides={"include_simulation": False}))

    # 13. ActionGate passes while ACP requests fresh state.
    s.append(IntegratedScenario(
        "ag_passes_acp_requests_fresh", "AUTHORED_DETERMINISTIC",
        "ActionGate ALLOW while ACP operational state is stale",
        _op(), C.REQUEST_FRESH_OPERATIONAL_STATE, freshness_s=120.0))

    # 14. identity mismatch between the two layers.
    s.append(IntegratedScenario(
        "composition_identity_mismatch", "SYNTHETIC_UNIT",
        "ACP candidate bound to a different patch digest than ActionGate",
        _op(), C.COMPOSITION_IDENTITY_MISMATCH,
        acp_manifest_digest_override="sha256:DIVERGENT_PATCH"))

    # 15. evaluator exception (contained -> shadow error).
    s.append(IntegratedScenario(
        "evaluator_exception", "SYNTHETIC_UNIT",
        "an evaluator raises; the shadow harness contains it and fails closed",
        _op(), C.SHADOW_ERROR, inject_shadow_error=True))

    # 16. no safe rollout candidate (proposed op unsafe on multiple gates).
    s.append(IntegratedScenario(
        "no_safe_rollout_candidate", "AUTHORED_DETERMINISTIC",
        "authorized rollout but unsafe: freeze + cooldown + missing rollback",
        _op(k8s_verb="ROLLOUT", desired_replicas=1, rollback_ref="",
            freeze_active=True, seconds_since_last_action=10.0),
        C.HELD_BY_OPERATIONAL_SAFETY))

    # 17. destructive delete, fully authorized (approval) + operationally safe.
    s.append(IntegratedScenario(
        "authorized_delete_safe", "AUTHORED_DETERMINISTIC",
        "DELETE with dual-control approval + rollback; small blast, ready",
        _op(k8s_verb="DELETE", current_replicas=1, desired_replicas=0,
            available_replicas=1, rollback_ref="rev-1"),
        C.HELD_BY_OPERATIONAL_SAFETY,               # delete-to-zero trips min-availability
        ag_overrides={"include_approval": True}))

    # 18. delete without approval -> ActionGate escalates (pending).
    s.append(IntegratedScenario(
        "delete_escalates_to_human", "AUTHORED_DETERMINISTIC",
        "DELETE with evidence but no approval — ActionGate ESCALATE_TO_HUMAN",
        _op(k8s_verb="DELETE", current_replicas=2, desired_replicas=0,
            available_replicas=2, rollback_ref="rev-1"),
        C.REQUEST_MORE_EVIDENCE))

    return s


def provenance_counts(scenarios: List[IntegratedScenario]) -> dict:
    out: dict = {}
    for sc in scenarios:
        out[sc.provenance] = out.get(sc.provenance, 0) + 1
    return out
