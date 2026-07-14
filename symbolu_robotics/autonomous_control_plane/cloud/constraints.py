"""Deterministic cloud hard-constraint evaluator (V2 §6).

Consumes the repository's **real** ``cloud_controller`` logic — the readiness
checker, the deployment policy engine, and the safety-bounds module — and emits
frozen-core ``ConstraintResult`` objects plus a ``CloudOperationalEvidence``
record. It answers ACP's question only: *is this operation operationally safe
against the live cluster state right now?* It never answers ActionGate's question
(*is this operation authorized?*) — see ``ACP_ACTIONGATE_BOUNDARY.md``.

Design rules (all inherited from the frozen ACP core, unchanged):
* Every constraint is HARD and **non-compensatory** — no soft score can rescue a
  failed hard result (enforced by ``action_selection.filter_admissible``).
* **Fail-closed**: stale / missing / evaluator-failed state yields a single
  failing HARD result, so the candidate is inadmissible (never a permissive
  default).
* Each result binds to ``candidate.identity`` (via the constraint set) and
  ``world.version`` (via ``evidence_ref``) — state/action binding is preserved.

Source labels (for the reuse analysis, §10):
* ``READINESS_OK`` ← real ``cloud_controller.action.readiness.ReadinessChecker``
* ``REPLICA_WITHIN_LIMIT`` ← real ``cloud_controller.action.policy.PolicyEngine``
* ``BLAST_RADIUS_WITHIN_BOUND`` / ``MIN_AVAILABILITY_PRESERVED`` ← real
  ``cloud_controller.recommend.safety.SafetyBounds`` (+ ``SafetyConfig``)
* ``NO_ACTIVE_FREEZE`` ← real ``BlackoutWindow`` semantics (carried as a
  deterministic flag on the canonical state to keep identity timezone-independent)
* ``STATE_FRESH`` / ``TARGET_BOUND`` / ``DEPENDENCY_HEALTHY`` /
  ``CAPACITY_SUFFICIENT`` / ``ROLLBACK_AVAILABLE`` ← authored deterministic
  operational rules (no repository equivalent exists today).

Stdlib-only. The ``cloud_controller`` modules imported here are pure-Python,
deterministic, and do not touch the Kubernetes client.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..constraints import ConstraintKind, ConstraintResult
from .envelopes import (
    CloudActionCandidate,
    CloudOperation,
    CloudOperationalEvidence,
    CloudValidity,
    CloudWorldState,
)

EVALUATOR_NAME = "acp.cloud.CloudConstraintEvaluator"
EVALUATOR_VERSION = "1"

# Operations that mutate a rollout and therefore require a rollback path.
_ROLLBACK_REQUIRED = frozenset(
    {CloudOperation.ROLLOUT, CloudOperation.CONFIG_UPDATE, CloudOperation.DELETE}
)


@dataclass(frozen=True)
class CloudConstraintConfig:
    """Thresholds for the cloud constraints.

    ``readiness_config`` / ``policy_min_replicas`` / ``policy_max_replicas`` /
    ``safety_config`` seed the REAL ``cloud_controller`` objects so the numeric
    bounds come from the repository defaults, not re-authored constants. Only
    ``max_freshness_s`` (the staleness horizon) is ACP-authored.
    """

    max_freshness_s: float = 30.0
    policy_min_replicas: int = 1
    policy_max_replicas: int = 100
    require_dependency_healthy: bool = True

    @property
    def readiness_config(self):
        from cloud_controller.action.readiness import ReadinessConfig

        return ReadinessConfig()

    @property
    def safety_config(self):
        from cloud_controller.recommend.safety import SafetyConfig

        return SafetyConfig()


def _bool_result(
    cid: str, passed: bool, reason: str, evidence_ref: str
) -> ConstraintResult:
    return ConstraintResult(
        constraint_id=cid,
        kind=ConstraintKind.HARD,
        passed=passed,
        observed_value=1.0 if passed else 0.0,
        required_bound=1.0,
        comparator="bool",
        reason_code=reason,
        evidence_ref=evidence_ref,
    )


def _num_result(
    cid: str,
    passed: bool,
    observed: float,
    bound: float,
    comparator: str,
    reason: str,
    evidence_ref: str,
) -> ConstraintResult:
    return ConstraintResult(
        constraint_id=cid,
        kind=ConstraintKind.HARD,
        passed=passed,
        observed_value=float(observed),
        required_bound=float(bound),
        comparator=comparator,
        reason_code=reason,
        evidence_ref=evidence_ref,
    )


class CloudConstraintEvaluator:
    """Deterministic HARD-constraint evaluator for cloud operations.

    ``safety_critical = True`` marks it as an admissibility gate (mirrors the
    robotics evaluators). It is a pure function of ``(candidate, world, now_s,
    freshness_s)`` plus its config — no wall-clock, no randomness, no I/O.
    """

    safety_critical = True

    def __init__(self, config: Optional[CloudConstraintConfig] = None) -> None:
        self._config = config or CloudConstraintConfig()

    # ---- fail-closed evidence helpers -----------------------------------
    def _failed_evidence(
        self,
        candidate: CloudActionCandidate,
        state_version: str,
        now_s: float,
        freshness_s: float,
        validity: CloudValidity,
        reason: str,
    ) -> Tuple[CloudOperationalEvidence, Tuple[ConstraintResult, ...]]:
        evidence = CloudOperationalEvidence(
            candidate_identity=candidate.identity,
            state_version=state_version,
            evaluator=EVALUATOR_NAME,
            evaluator_version=EVALUATOR_VERSION,
            observation_time_s=now_s,
            freshness_s=max(freshness_s, 0.0),
            validity=validity,
            reason_codes=(reason,),
            note="fail-closed: no admissible evidence",
        )
        # A single failing HARD result => inadmissible (fail closed).
        results = (
            _bool_result(cid="STATE_FRESH", passed=False, reason=reason,
                         evidence_ref=state_version),
        )
        return evidence, results

    # ---- main entry -----------------------------------------------------
    def evaluate(
        self,
        candidate: CloudActionCandidate,
        world: Optional[CloudWorldState],
        *,
        now_s: float,
        freshness_s: float,
    ) -> Tuple[CloudOperationalEvidence, Tuple[ConstraintResult, ...]]:
        """Return ``(evidence, hard_results)`` for one candidate.

        ``world is None`` => MISSING (fail closed). Stale state => STALE (fail
        closed). Any exception from a real ``cloud_controller`` evaluator =>
        EVALUATOR_FAILED (fail closed) — never a silent pass.
        """
        cfg = self._config

        if world is None:
            return self._failed_evidence(
                candidate, state_version=candidate.origin_state_version,
                now_s=now_s, freshness_s=freshness_s,
                validity=CloudValidity.MISSING, reason="STATE_MISSING")

        state_version = world.version

        # State/action binding: candidate must reference THIS state.
        if candidate.origin_state_version != state_version:
            return self._failed_evidence(
                candidate, state_version=state_version, now_s=now_s,
                freshness_s=freshness_s, validity=CloudValidity.MISSING,
                reason="STATE_BINDING_MISMATCH")

        # Staleness (fail closed).
        if freshness_s < 0 or freshness_s > cfg.max_freshness_s:
            return self._failed_evidence(
                candidate, state_version=state_version, now_s=now_s,
                freshness_s=freshness_s, validity=CloudValidity.STALE,
                reason="STATE_STALE")

        try:
            return self._evaluate_valid(candidate, world, state_version,
                                        now_s=now_s, freshness_s=freshness_s)
        except Exception as exc:  # contained: any real-evaluator failure => closed
            return self._failed_evidence(
                candidate, state_version=state_version, now_s=now_s,
                freshness_s=freshness_s, validity=CloudValidity.EVALUATOR_FAILED,
                reason=f"EVALUATOR_FAILED:{type(exc).__name__}")

    # ---- the real-evaluator path ----------------------------------------
    def _evaluate_valid(
        self,
        candidate: CloudActionCandidate,
        world: CloudWorldState,
        state_version: str,
        *,
        now_s: float,
        freshness_s: float,
    ) -> Tuple[CloudOperationalEvidence, Tuple[ConstraintResult, ...]]:
        from cloud_controller.action.policy import (
            DeploymentPolicy,
            PolicyConfig,
            PolicyEngine,
        )
        from cloud_controller.action.readiness import ReadinessChecker
        from cloud_controller.recommend.safety import SafetyBounds

        cfg = self._config
        results: List[ConstraintResult] = []
        reason_codes: List[str] = []

        target = candidate.desired_replicas
        current = world.current_replicas
        delta = target - current

        # 1. TARGET_BOUND — candidate names THIS deployment/namespace.
        target_ok = (
            candidate.deployment == world.deployment
            and candidate.namespace == world.namespace
        )
        results.append(_bool_result(
            "TARGET_BOUND", target_ok,
            "TARGET_MATCH" if target_ok else "TARGET_MISMATCH", state_version))

        # 2. READINESS_OK — REAL ReadinessChecker.
        readiness = ReadinessChecker(cfg.readiness_config).check(
            plasticity=world.readiness_plasticity,
            stability=world.readiness_plasticity,
            last_action_time=now_s - world.seconds_since_last_action,
            active_rollback_watches=world.active_rollback_watches,
            current_time=now_s,
        )
        results.append(_num_result(
            "READINESS_OK", readiness.ready,
            observed=world.readiness_plasticity,
            bound=cfg.readiness_config.min_plasticity, comparator=">=",
            reason="READY" if readiness.ready else "NOT_READY",
            evidence_ref=state_version))

        # 3. REPLICA_WITHIN_LIMIT — REAL PolicyEngine (absolute bounds only;
        #    no blackout windows configured here => freeze handled separately).
        policy = PolicyEngine(PolicyConfig(default_policy=DeploymentPolicy(
            min_replicas=cfg.policy_min_replicas,
            max_replicas=cfg.policy_max_replicas)))
        policy_result = policy.check(
            deployment=world.deployment, namespace=world.namespace,
            current_replicas=current, target_replicas=target,
            current_time=now_s)
        results.append(_num_result(
            "REPLICA_WITHIN_LIMIT", policy_result.allowed,
            observed=float(target), bound=float(cfg.policy_max_replicas),
            comparator="<=",
            reason="WITHIN_LIMITS" if policy_result.allowed else "REPLICA_LIMIT_VIOLATION",
            evidence_ref=state_version))

        # 4/5. BLAST_RADIUS + MIN_AVAILABILITY — REAL SafetyBounds thresholds.
        safety = SafetyBounds(cfg.safety_config)
        safety_result = safety.check(
            current_replicas=current, proposed_delta=delta, current_time=now_s)
        frac = (cfg.safety_config.max_scale_out_fraction if delta >= 0
                else cfg.safety_config.max_scale_in_fraction)
        blast_bound = max(1, int(current * frac))
        if candidate.operation is CloudOperation.SCALE:
            blast_observed = abs(delta)
        else:
            blast_observed = candidate.blast_radius
        blast_ok = blast_observed <= blast_bound
        results.append(_num_result(
            "BLAST_RADIUS_WITHIN_BOUND", blast_ok,
            observed=float(blast_observed), bound=float(blast_bound),
            comparator="<=",
            reason="BLAST_OK" if blast_ok else "BLAST_RADIUS_EXCEEDED",
            evidence_ref=state_version))

        min_avail_ok = target >= cfg.safety_config.min_replicas
        results.append(_num_result(
            "MIN_AVAILABILITY_PRESERVED", min_avail_ok,
            observed=float(target), bound=float(cfg.safety_config.min_replicas),
            comparator=">=",
            reason="MIN_PRESERVED" if min_avail_ok else "BELOW_MIN_REPLICAS",
            evidence_ref=state_version))

        # 6. NO_ACTIVE_FREEZE — real BlackoutWindow semantics (carried flag).
        freeze_ok = not world.freeze_active
        results.append(_bool_result(
            "NO_ACTIVE_FREEZE", freeze_ok,
            "NO_FREEZE" if freeze_ok else "FREEZE_WINDOW_ACTIVE", state_version))

        # 7. DEPENDENCY_HEALTHY — operational input.
        dep_ok = (not cfg.require_dependency_healthy) or world.dependency_healthy
        results.append(_bool_result(
            "DEPENDENCY_HEALTHY", dep_ok,
            "DEPENDENCY_OK" if dep_ok else "DEPENDENCY_UNHEALTHY", state_version))

        # 8. CAPACITY_SUFFICIENT — at least one replica currently serving, so a
        #    mutating op does not act on an already-broken deployment.
        cap_margin = world.available_replicas - cfg.safety_config.min_replicas
        cap_ok = world.available_replicas >= cfg.safety_config.min_replicas
        results.append(_num_result(
            "CAPACITY_SUFFICIENT", cap_ok,
            observed=float(world.available_replicas),
            bound=float(cfg.safety_config.min_replicas), comparator=">=",
            reason="CAPACITY_OK" if cap_ok else "INSUFFICIENT_CAPACITY",
            evidence_ref=state_version))

        # 9. ROLLBACK_AVAILABLE — rollout/destructive ops need a rollback path.
        if candidate.operation in _ROLLBACK_REQUIRED:
            rb_ok = bool(candidate.rollback_ref)
            results.append(_bool_result(
                "ROLLBACK_AVAILABLE", rb_ok,
                "ROLLBACK_PRESENT" if rb_ok else "NO_ROLLBACK_REF",
                state_version))

        for r in results:
            if not r.passed:
                reason_codes.append(r.reason_code)

        evidence = CloudOperationalEvidence(
            candidate_identity=candidate.identity,
            state_version=state_version,
            evaluator=EVALUATOR_NAME,
            evaluator_version=EVALUATOR_VERSION,
            observation_time_s=now_s,
            freshness_s=freshness_s,
            validity=CloudValidity.VALID,
            readiness_ok=readiness.ready,
            readiness_status=readiness.status.value,
            capacity_margin_replicas=cap_margin,
            rollback_available=bool(candidate.rollback_ref),
            blast_radius=blast_observed,
            freeze_active=world.freeze_active,
            dependency_healthy=world.dependency_healthy,
            reason_codes=tuple(reason_codes),
            note=f"safety_clamped={safety_result.was_clamped}",
        )
        return evidence, tuple(results)
