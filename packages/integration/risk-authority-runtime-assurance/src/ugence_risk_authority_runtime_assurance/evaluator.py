"""Trajectory evaluator — sequence-level risk interpretation (spec §6, §12–§14).

The evaluator reads a :class:`~.observer.Trajectory` (facts owned by the Agent
Runtime) and the resolved :class:`~.policy.TrajectoryPolicy` content (owned by
WorkflowIR), and produces a neutral :class:`~.contracts.TrajectoryAssessment`. It
**risk-types** existing state; it does not maintain accounting (D3) and it never
returns authority (invariant I9).

Rules are deterministic and explainable — plain comparisons, **no weighted risk
score** that could convert to authority:

  * ``CUMULATIVE_EXPOSURE``      — individually-safe actions summing past a ceiling
  * ``NEAR_BOUNDARY_REPEAT``     — repeated at/near a per-action ceiling fraction
  * ``RETRY_LOOP``               — one action id recurring past a threshold
  * ``DATA_CLASS_PROGRESSION``   — escalation past the allowed data-access class
  * ``CONTEXT_EXPANSION``        — context size past the allowed bound (spec §14)

Failure semantics (spec §20): a missing/unknown/stale policy, a missing window
segment, or an evaluator fault yields ``UNKNOWN`` — never a fabricated escalation,
never authority widening. A custom evaluator plug-in is wrapped so a malformed
return can only degrade to ``UNKNOWN`` (the RA-6 F-1 lesson; spec §24).
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Protocol, Tuple, runtime_checkable

from .contracts import (
    AssessmentOutcome,
    ReasonCode,
    RuntimeRiskLevel,
    TrajectoryAssessment,
    TrajectoryPolicyRef,
)
from .observer import Trajectory
from .policy import TrajectoryPolicy, TrajectoryPolicyReader

__all__ = [
    "EVALUATOR_IDENTITY",
    "EVALUATOR_VERSION",
    "RuntimeAssuranceEvaluator",
    "ReferenceTrajectoryEvaluator",
    "SafeEvaluator",
]

EVALUATOR_IDENTITY = "ra7-reference-trajectory-evaluator"
EVALUATOR_VERSION = "0.1.0"


@runtime_checkable
class RuntimeAssuranceEvaluator(Protocol):
    """Produce a neutral assessment for a trajectory (spec §12)."""

    def evaluate(
        self,
        trajectory: Trajectory,
        *,
        assessment_id: str,
        produced_at: datetime,
    ) -> TrajectoryAssessment:
        ...


def _unknown(
    trajectory: Trajectory,
    *,
    assessment_id: str,
    produced_at: datetime,
    reasons: Tuple[str, ...],
    policy_ref: Optional[TrajectoryPolicyRef],
    identity: str = EVALUATOR_IDENTITY,
    version: str = EVALUATOR_VERSION,
) -> TrajectoryAssessment:
    return TrajectoryAssessment(
        assessment_id=assessment_id,
        tenant_id=trajectory.tenant_id,
        workflow_instance_id=trajectory.workflow_instance_id,
        envelope_id=trajectory.envelope_id,
        risk_level=RuntimeRiskLevel.UNKNOWN,
        outcome=AssessmentOutcome.UNKNOWN_ASSESSMENT,
        produced_at=produced_at,
        evaluator_identity=identity,
        evaluator_version=version,
        policy_ref=policy_ref,
        reasons=reasons,
        observed_window=trajectory.event_refs,
    )


class ReferenceTrajectoryEvaluator:
    """Deterministic reference sequence-risk evaluator.

    Resolves the trajectory's policy reference through the injected reader; an
    unresolvable/unknown policy ⇒ ``UNKNOWN`` (spec §20). Otherwise applies the
    explainable rules and returns ``ESCALATED`` with structured reason codes on any
    breach, else ``NORMAL``.
    """

    def __init__(self, policy_reader: TrajectoryPolicyReader) -> None:
        if policy_reader is None:
            raise ValueError("ReferenceTrajectoryEvaluator requires a policy reader")
        self._reader = policy_reader

    def evaluate(
        self,
        trajectory: Trajectory,
        *,
        assessment_id: str,
        produced_at: datetime,
    ) -> TrajectoryAssessment:
        ref = trajectory.policy_ref
        if ref is None or ref.is_empty():
            return _unknown(
                trajectory,
                assessment_id=assessment_id,
                produced_at=produced_at,
                reasons=("no trajectory policy reference bound",),
                policy_ref=ref,
            )
        policy = self._reader.resolve(ref)
        if policy is None:
            return _unknown(
                trajectory,
                assessment_id=assessment_id,
                produced_at=produced_at,
                reasons=(
                    f"trajectory policy {ref.policy_id!r} version "
                    f"{ref.version!r} unresolvable/unknown",
                ),
                policy_ref=ref,
            )

        reason_codes: List[ReasonCode] = []
        reasons: List[str] = []
        supporting: List[str] = []

        self._check_cumulative_exposure(trajectory, policy, reason_codes, reasons)
        self._check_near_boundary(trajectory, policy, reason_codes, reasons)
        self._check_retry_loop(trajectory, policy, reason_codes, reasons, supporting)
        self._check_data_class(trajectory, policy, reason_codes, reasons)
        self._check_context_expansion(trajectory, policy, reason_codes, reasons)
        self._check_model_behavior(trajectory, policy, reason_codes, reasons)

        if reason_codes:
            return TrajectoryAssessment(
                assessment_id=assessment_id,
                tenant_id=trajectory.tenant_id,
                workflow_instance_id=trajectory.workflow_instance_id,
                envelope_id=trajectory.envelope_id,
                risk_level=RuntimeRiskLevel.ESCALATED,
                outcome=AssessmentOutcome.SIGNAL_REASSESS,
                produced_at=produced_at,
                evaluator_identity=EVALUATOR_IDENTITY,
                evaluator_version=EVALUATOR_VERSION,
                policy_ref=ref,
                reason_codes=tuple(dict.fromkeys(reason_codes)),
                reasons=tuple(reasons),
                supporting_event_refs=tuple(supporting) or trajectory.event_refs,
                observed_window=trajectory.event_refs,
            )

        return TrajectoryAssessment(
            assessment_id=assessment_id,
            tenant_id=trajectory.tenant_id,
            workflow_instance_id=trajectory.workflow_instance_id,
            envelope_id=trajectory.envelope_id,
            risk_level=RuntimeRiskLevel.NORMAL,
            outcome=AssessmentOutcome.NO_SIGNAL,
            produced_at=produced_at,
            evaluator_identity=EVALUATOR_IDENTITY,
            evaluator_version=EVALUATOR_VERSION,
            policy_ref=ref,
            observed_window=trajectory.event_refs,
        )

    # -- rules --------------------------------------------------------------
    @staticmethod
    def _check_cumulative_exposure(
        trajectory: Trajectory,
        policy: TrajectoryPolicy,
        reason_codes: List[ReasonCode],
        reasons: List[str],
    ) -> None:
        if not policy.cumulative_exposure_limits:
            return
        totals = trajectory.cumulative_exposure()
        for dim, limit in policy.cumulative_exposure_limits.items():
            total = totals.get(dim, 0.0)
            if total > limit:
                reason_codes.append(ReasonCode.CUMULATIVE_EXPOSURE)
                reasons.append(
                    f"cumulative {dim} exposure {total:g} exceeds ceiling {limit:g}"
                )

    @staticmethod
    def _check_near_boundary(
        trajectory: Trajectory,
        policy: TrajectoryPolicy,
        reason_codes: List[ReasonCode],
        reasons: List[str],
    ) -> None:
        frac = policy.near_boundary_fraction
        repeat = policy.near_boundary_repeat
        if frac is None or repeat is None or not policy.cumulative_exposure_limits:
            return
        per_dim = trajectory.per_action_amounts()
        for dim, limit in policy.cumulative_exposure_limits.items():
            if limit <= 0:
                continue
            threshold = frac * limit
            near = [a for (_aid, a) in per_dim.get(dim, []) if a >= threshold]
            if len(near) >= repeat:
                reason_codes.append(ReasonCode.NEAR_BOUNDARY_REPEAT)
                reasons.append(
                    f"{len(near)} {dim} actions at/above {frac:g}×ceiling "
                    f"(≥{threshold:g}); repeat bound {repeat}"
                )

    @staticmethod
    def _check_retry_loop(
        trajectory: Trajectory,
        policy: TrajectoryPolicy,
        reason_codes: List[ReasonCode],
        reasons: List[str],
        supporting: List[str],
    ) -> None:
        threshold = policy.retry_loop_threshold
        if threshold is None:
            return
        for action_id, count in trajectory.attempts_by_action().items():
            if count >= threshold:
                reason_codes.append(ReasonCode.RETRY_LOOP)
                reasons.append(
                    f"action {action_id!r} recurred {count} times (retry-loop "
                    f"bound {threshold})"
                )

    @staticmethod
    def _check_data_class(
        trajectory: Trajectory,
        policy: TrajectoryPolicy,
        reason_codes: List[ReasonCode],
        reasons: List[str],
    ) -> None:
        if not policy.data_class_order or policy.max_data_class_rank is None:
            return
        for dc in trajectory.data_class_sequence():
            rank = policy.data_class_rank(dc)
            if rank is not None and rank > policy.max_data_class_rank:
                reason_codes.append(ReasonCode.DATA_CLASS_PROGRESSION)
                reasons.append(
                    f"data-access class {dc!r} (rank {rank}) exceeds permitted "
                    f"rank {policy.max_data_class_rank}"
                )
                break

    @staticmethod
    def _check_context_expansion(
        trajectory: Trajectory,
        policy: TrajectoryPolicy,
        reason_codes: List[ReasonCode],
        reasons: List[str],
    ) -> None:
        limit = policy.context_expansion_limit
        if limit is None:
            return
        size = trajectory.latest_detail("context_size")
        if isinstance(size, bool) or not isinstance(size, (int, float)):
            return
        if float(size) > limit:
            reason_codes.append(ReasonCode.CONTEXT_EXPANSION)
            reasons.append(
                f"context size {float(size):g} exceeds bound {limit:g}"
            )

    @staticmethod
    def _check_model_behavior(
        trajectory: Trajectory,
        policy: TrajectoryPolicy,
        reason_codes: List[ReasonCode],
        reasons: List[str],
    ) -> None:
        # A represented model/runtime behavior change (spec §9 reason code). Only
        # fires when the runtime explicitly surfaces it as a neutral fact.
        flag = trajectory.latest_detail("model_behavior_changed")
        if flag is True:
            reason_codes.append(ReasonCode.MODEL_BEHAVIOR_CHANGED)
            reasons.append("runtime reported a model/runtime behavior change")


class SafeEvaluator:
    """Wrap any evaluator so a malformed/faulty return degrades to ``UNKNOWN``.

    The RA-6 F-1 lesson (spec §24): a plug-in's return contract is treated
    strictly. If the wrapped evaluator raises, or returns anything that is not a
    well-formed :class:`TrajectoryAssessment` whose bindings match the trajectory
    and whose ``risk_level`` is a real :class:`RuntimeRiskLevel`, the result is
    replaced with ``UNKNOWN`` — a truthy custom value can never become ``NORMAL``
    or a spurious ``ESCALATED``.
    """

    def __init__(self, inner: RuntimeAssuranceEvaluator) -> None:
        if inner is None:
            raise ValueError("SafeEvaluator requires an inner evaluator")
        self._inner = inner

    def evaluate(
        self,
        trajectory: Trajectory,
        *,
        assessment_id: str,
        produced_at: datetime,
    ) -> TrajectoryAssessment:
        try:
            result = self._inner.evaluate(
                trajectory, assessment_id=assessment_id, produced_at=produced_at
            )
        except Exception as exc:  # noqa: BLE001 - evaluator fault fails safe
            return _unknown(
                trajectory,
                assessment_id=assessment_id,
                produced_at=produced_at,
                reasons=("evaluator raised", repr(exc)),
                policy_ref=trajectory.policy_ref,
            )
        errors = _assessment_contract_errors(result, trajectory)
        if errors:
            return _unknown(
                trajectory,
                assessment_id=assessment_id,
                produced_at=produced_at,
                reasons=("evaluator returned malformed assessment",) + errors,
                policy_ref=trajectory.policy_ref,
            )
        return result


def _assessment_contract_errors(
    result: object, trajectory: Trajectory
) -> Tuple[str, ...]:
    """Strictly validate a plug-in's assessment return (spec §24)."""

    errors: List[str] = []
    if not isinstance(result, TrajectoryAssessment):
        return ("not a TrajectoryAssessment",)
    # risk_level must be an exact enum member — a truthy stand-in cannot pass.
    if type(result.risk_level) is not RuntimeRiskLevel:
        errors.append("risk_level is not a RuntimeRiskLevel")
    if type(result.outcome) is not AssessmentOutcome:
        errors.append("outcome is not an AssessmentOutcome")
    if result.tenant_id != trajectory.tenant_id:
        errors.append("tenant binding mismatch")
    if result.workflow_instance_id != trajectory.workflow_instance_id:
        errors.append("workflow binding mismatch")
    if result.envelope_id != trajectory.envelope_id:
        errors.append("envelope binding mismatch")
    if not isinstance(result.reason_codes, tuple):
        errors.append("reason_codes must be a tuple")
    elif any(type(rc) is not ReasonCode for rc in result.reason_codes):
        errors.append("reason_codes must all be ReasonCode members")
    if not isinstance(result.produced_at, datetime):
        errors.append("produced_at must be a datetime")
    # A material (ESCALATED) verdict must justify itself with at least one code.
    if (
        type(result.risk_level) is RuntimeRiskLevel
        and result.risk_level is RuntimeRiskLevel.ESCALATED
        and not result.reason_codes
    ):
        errors.append("ESCALATED assessment carries no reason codes")
    return tuple(errors)
