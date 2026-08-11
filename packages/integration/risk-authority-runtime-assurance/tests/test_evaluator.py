"""Trajectory evaluator tests (spec §6, §12–§14, §20, §24; matrix 1,2,7,13–20,40).

Deterministic sequence-risk rules → NORMAL/ESCALATED, UNKNOWN on
missing/unknown/stale policy, and the strict SafeEvaluator malformed-return guard
(a truthy custom value can never become NORMAL).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from ugence_risk_authority_runtime_assurance import (
    AssessmentOutcome,
    ReasonCode,
    ReferenceTrajectoryEvaluator,
    ReferenceTrajectoryPolicyReader,
    RuntimeAssuranceObserver,
    RuntimeRiskLevel,
    SafeEvaluator,
    Trajectory,
    TrajectoryAssessment,
    TrajectoryPolicyRef,
)

from ra7_scenario import (
    FIXED_NOW,
    TENANT,
    WORKFLOW,
    default_policy,
    default_ref,
    make_observation,
)

NOW = FIXED_NOW


def _evaluator(policy=None):
    reader = ReferenceTrajectoryPolicyReader()
    reader.register(policy or default_policy())
    return ReferenceTrajectoryEvaluator(reader)


def _trajectory(observations):
    obs = RuntimeAssuranceObserver()
    for o in observations:
        obs.record(o)
    return obs.trajectory(TENANT, WORKFLOW)


def _assess(observations, policy=None):
    traj = _trajectory(observations)
    return _evaluator(policy).evaluate(traj, assessment_id="a1", produced_at=NOW)


# -- matrix 1: normal trajectory → NORMAL, no signal ------------------------
def test_normal_trajectory_is_normal():
    obs = [make_observation(i, detail={"exposure": {"model_cost": 100.0}}) for i in range(1, 4)]
    a = _assess(obs)
    assert a.risk_level is RuntimeRiskLevel.NORMAL
    assert a.outcome is AssessmentOutcome.NO_SIGNAL
    assert a.reason_codes == ()


# -- matrix 16: cumulative exposure ($9k×10 > $50k) → ESCALATED -------------
def test_cumulative_exposure_escalates():
    obs = [make_observation(i, detail={"exposure": {"model_cost": 9000.0}}) for i in range(1, 11)]
    a = _assess(obs)
    assert a.risk_level is RuntimeRiskLevel.ESCALATED
    assert ReasonCode.CUMULATIVE_EXPOSURE in a.reason_codes
    assert a.outcome is AssessmentOutcome.SIGNAL_REASSESS


# -- matrix 17: repeated near-boundary → ESCALATED -------------------------
def test_near_boundary_repeat_escalates():
    # ceiling 50000; 0.9×=45000; three actions at 46000 each = 138000 > ceiling too,
    # but use a higher ceiling so ONLY the near-boundary rule fires.
    policy = default_policy()
    policy = type(policy)(
        policy_id=policy.policy_id,
        version=policy.version,
        cumulative_exposure_limits={"model_cost": 50000.0},
        near_boundary_fraction=0.9,
        near_boundary_repeat=3,
    )
    obs = [make_observation(i, detail={"exposure": {"model_cost": 46000.0}}) for i in range(1, 4)]
    a = _assess(obs, policy=policy)
    assert a.risk_level is RuntimeRiskLevel.ESCALATED
    assert ReasonCode.NEAR_BOUNDARY_REPEAT in a.reason_codes


# -- matrix 18: retry-loop → ESCALATED -------------------------------------
def test_retry_loop_escalates():
    obs = [make_observation(i, action_id="looping", detail={"exposure": {"model_cost": 1.0}}) for i in range(1, 6)]
    a = _assess(obs)
    assert a.risk_level is RuntimeRiskLevel.ESCALATED
    assert ReasonCode.RETRY_LOOP in a.reason_codes


# -- matrix 19: context-expansion → ESCALATED ------------------------------
def test_context_expansion_escalates():
    obs = [make_observation(1, detail={"context_size": 250000.0})]
    a = _assess(obs)
    assert a.risk_level is RuntimeRiskLevel.ESCALATED
    assert ReasonCode.CONTEXT_EXPANSION in a.reason_codes


# -- data-class progression → ESCALATED ------------------------------------
def test_data_class_progression_escalates():
    obs = [
        make_observation(1, detail={"data_class": "public"}),
        make_observation(2, detail={"data_class": "restricted"}),  # rank 3 > max 2
    ]
    a = _assess(obs)
    assert a.risk_level is RuntimeRiskLevel.ESCALATED
    assert ReasonCode.DATA_CLASS_PROGRESSION in a.reason_codes


# -- matrix 20: model/runtime behavior change → ESCALATED ------------------
def test_model_behavior_change_escalates():
    obs = [make_observation(1, detail={"model_behavior_changed": True})]
    a = _assess(obs)
    assert a.risk_level is RuntimeRiskLevel.ESCALATED
    assert ReasonCode.MODEL_BEHAVIOR_CHANGED in a.reason_codes


# -- matrix 14: missing policy reference → UNKNOWN -------------------------
def test_missing_policy_ref_is_unknown():
    obs = [make_observation(1, policy_ref=TrajectoryPolicyRef(""))]
    a = _assess(obs)
    assert a.risk_level is RuntimeRiskLevel.UNKNOWN
    assert a.outcome is AssessmentOutcome.UNKNOWN_ASSESSMENT


# -- matrix 14: unknown policy id → UNKNOWN --------------------------------
def test_unknown_policy_id_is_unknown():
    obs = [make_observation(1, policy_ref=TrajectoryPolicyRef("no-such-policy", "1"))]
    a = _assess(obs)
    assert a.risk_level is RuntimeRiskLevel.UNKNOWN


# -- matrix 13: wrong policy version → UNKNOWN -----------------------------
def test_wrong_policy_version_is_unknown():
    obs = [make_observation(1, policy_ref=TrajectoryPolicyRef("traj-policy-1", "999"))]
    a = _assess(obs)
    assert a.risk_level is RuntimeRiskLevel.UNKNOWN


# -- matrix 15: policy substitution (unknown digest-less swap) → UNKNOWN ----
def test_policy_substitution_unknown_id_is_unknown():
    # A substituted policy that isn't registered resolves to None ⇒ UNKNOWN, never
    # a fabricated NORMAL that would mask drift.
    obs = [make_observation(1, policy_ref=TrajectoryPolicyRef("substituted", "1"),
                            detail={"exposure": {"model_cost": 9_000_000.0}})]
    a = _assess(obs)
    assert a.risk_level is RuntimeRiskLevel.UNKNOWN


# -- SafeEvaluator: evaluator exception → UNKNOWN (matrix 23) ---------------
def test_safe_evaluator_wraps_exception_as_unknown():
    class Boom:
        def evaluate(self, trajectory, *, assessment_id, produced_at):
            raise RuntimeError("evaluator fault")

    traj = _trajectory([make_observation(1)])
    a = SafeEvaluator(Boom()).evaluate(traj, assessment_id="a1", produced_at=NOW)
    assert a.risk_level is RuntimeRiskLevel.UNKNOWN
    assert a.outcome is AssessmentOutcome.UNKNOWN_ASSESSMENT


# -- matrix 40: malformed evaluator return cannot become NORMAL ------------
def test_safe_evaluator_rejects_non_assessment_return():
    class Liar:
        def evaluate(self, trajectory, *, assessment_id, produced_at):
            return "totally normal"  # truthy string

    traj = _trajectory([make_observation(1)])
    a = SafeEvaluator(Liar()).evaluate(traj, assessment_id="a1", produced_at=NOW)
    assert a.risk_level is RuntimeRiskLevel.UNKNOWN


def test_safe_evaluator_rejects_truthy_fake_risk_level():
    class FakeLevel(str):
        pass

    def _bad(trajectory, assessment_id):
        return TrajectoryAssessment(
            assessment_id=assessment_id,
            tenant_id=trajectory.tenant_id,
            workflow_instance_id=trajectory.workflow_instance_id,
            envelope_id=trajectory.envelope_id,
            risk_level=FakeLevel("NORMAL"),  # truthy stand-in, not the enum
            outcome=AssessmentOutcome.NO_SIGNAL,
            produced_at=NOW,
            evaluator_identity="x",
            evaluator_version="0",
        )

    class Liar:
        def evaluate(self, trajectory, *, assessment_id, produced_at):
            return _bad(trajectory, assessment_id)

    traj = _trajectory([make_observation(1)])
    a = SafeEvaluator(Liar()).evaluate(traj, assessment_id="a1", produced_at=NOW)
    assert a.risk_level is RuntimeRiskLevel.UNKNOWN, "a fake risk level cannot pass as NORMAL"


def test_safe_evaluator_rejects_binding_mismatch_return():
    def _mk(trajectory, assessment_id):
        return TrajectoryAssessment(
            assessment_id=assessment_id,
            tenant_id="ATTACKER_TENANT",  # mismatched binding
            workflow_instance_id=trajectory.workflow_instance_id,
            envelope_id=trajectory.envelope_id,
            risk_level=RuntimeRiskLevel.NORMAL,
            outcome=AssessmentOutcome.NO_SIGNAL,
            produced_at=NOW,
            evaluator_identity="x",
            evaluator_version="0",
        )

    class Liar:
        def evaluate(self, trajectory, *, assessment_id, produced_at):
            return _mk(trajectory, assessment_id)

    traj = _trajectory([make_observation(1)])
    a = SafeEvaluator(Liar()).evaluate(traj, assessment_id="a1", produced_at=NOW)
    assert a.risk_level is RuntimeRiskLevel.UNKNOWN


def test_safe_evaluator_rejects_escalated_without_reason_codes():
    def _mk(trajectory, assessment_id):
        return TrajectoryAssessment(
            assessment_id=assessment_id,
            tenant_id=trajectory.tenant_id,
            workflow_instance_id=trajectory.workflow_instance_id,
            envelope_id=trajectory.envelope_id,
            risk_level=RuntimeRiskLevel.ESCALATED,
            outcome=AssessmentOutcome.SIGNAL_REASSESS,
            produced_at=NOW,
            evaluator_identity="x",
            evaluator_version="0",
            reason_codes=(),  # material but unjustified
        )

    class Liar:
        def evaluate(self, trajectory, *, assessment_id, produced_at):
            return _mk(trajectory, assessment_id)

    traj = _trajectory([make_observation(1)])
    a = SafeEvaluator(Liar()).evaluate(traj, assessment_id="a1", produced_at=NOW)
    assert a.risk_level is RuntimeRiskLevel.UNKNOWN


def test_disabled_rules_do_not_fire():
    # A policy with no thresholds set risk-types nothing ⇒ NORMAL.
    from ugence_risk_authority_runtime_assurance import TrajectoryPolicy

    policy = TrajectoryPolicy(policy_id="traj-policy-1", version="1")
    obs = [make_observation(1, detail={"exposure": {"model_cost": 10_000_000.0}, "context_size": 1e9})]
    a = _assess(obs, policy=policy)
    assert a.risk_level is RuntimeRiskLevel.NORMAL
