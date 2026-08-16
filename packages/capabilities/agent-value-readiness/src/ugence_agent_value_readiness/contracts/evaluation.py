"""Evaluation case / result / trace contracts for the GV-3R-b evaluator.

These are the immutable input and output shapes for the deterministic readiness
evaluator. The :class:`ReadinessEvaluationCase` carries the complete
``ReadinessPolicy`` body (the authoritative gate inventory) plus the structurally
supplied indicator/gate/condition results — but **never** a caller-selected
``ReadinessClassification``; the evaluator selects that itself.

Structural malformations (cross-tenant binding, a gate bound to another policy,
an embedded ``PolicyGate`` that does not match the policy's gate of the same id,
a duplicate/mismatched-target gate, a policy body that does not match its
reference) raise :class:`ReadinessEvaluationError` at construction. *Incomplete
but well-formed* cases (a missing applicable gate result, a mandatory
indeterminate) are not errors here — the evaluator returns ``NOT_ASSESSABLE``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from ugence_uvi_policy_contracts.api import (
    AssessmentContext,
    PolicyFamily,
    PolicyReference,
    PolicyScope,
    ReadinessPolicy,
    ReadinessTarget,
    RequirementClass,
)

from ._util import canonical_digest, coerce_tuple, require_nonempty, require_tzaware
from .composite import AdvisoryComposite
from .conditions import ConditionSet
from .determination import AgentValueReadinessDetermination
from .enums import ReadinessClassification
from .errors import ReadinessContractError
from .gates import GateResult
from .indicators import (
    AdoptionReadinessResult,
    CapabilityReadinessResult,
    IntelligenceFitnessResult,
)

__all__ = [
    "ReadinessEvaluationError",
    "ReadinessRule",
    "ReadinessReasonCode",
    "ReadinessEvaluationCase",
    "EvaluationTrace",
    "ReadinessEvaluationResult",
]


class ReadinessEvaluationError(ReadinessContractError):
    """A structurally malformed evaluation case (not an incomplete assessment).

    An *incomplete* but well-formed case yields ``NOT_ASSESSABLE`` from the
    evaluator; only genuine structural contradictions raise this.
    """


class ReadinessRule(str, Enum):
    """The single deterministic rule that selected the classification."""

    NOT_ASSESSABLE_INCOMPLETE = "NOT_ASSESSABLE_INCOMPLETE"
    NOT_ASSESSABLE_MANDATORY_INDETERMINATE = "NOT_ASSESSABLE_MANDATORY_INDETERMINATE"
    NOT_READY_MANDATORY_FAIL = "NOT_READY_MANDATORY_FAIL"
    NOT_READY_CONDITIONAL_NONCOMPENSABLE = "NOT_READY_CONDITIONAL_NONCOMPENSABLE"
    NOT_READY_CONDITIONAL_UNCOVERED = "NOT_READY_CONDITIONAL_UNCOVERED"
    PILOT_READY = "PILOT_READY"
    READY_WITH_CONDITIONS = "READY_WITH_CONDITIONS"
    DEPLOYMENT_READY = "DEPLOYMENT_READY"


class ReadinessReasonCode(str, Enum):
    """Stable reason codes recorded in the evaluation trace."""

    # assessability gaps
    MISSING_APPLICABLE_MANDATORY_GATE = "MISSING_APPLICABLE_MANDATORY_GATE"
    MISSING_APPLICABLE_CONDITIONAL_GATE = "MISSING_APPLICABLE_CONDITIONAL_GATE"
    MANDATORY_GATE_INDETERMINATE = "MANDATORY_GATE_INDETERMINATE"
    # negative
    MANDATORY_GATE_FAIL = "MANDATORY_GATE_FAIL"
    CONDITIONAL_CONCERN_NONCOMPENSABLE = "CONDITIONAL_CONCERN_NONCOMPENSABLE"
    CONDITIONAL_CONCERN_UNCOVERED = "CONDITIONAL_CONCERN_UNCOVERED"
    # positive / structural
    ALL_MANDATORY_PASS = "ALL_MANDATORY_PASS"
    CONDITIONAL_CONCERN_COMPENSATED = "CONDITIONAL_CONCERN_COMPENSATED"
    NO_UNRESOLVED_CONCERNS = "NO_UNRESOLVED_CONCERNS"
    CONDITION_INACTIVE_AT_EVALUATION = "CONDITION_INACTIVE_AT_EVALUATION"
    CONDITION_DOES_NOT_COVER_CONCERN = "CONDITION_DOES_NOT_COVER_CONCERN"
    # advisories (trust boundary — always present)
    ADVISORY_POLICY_AUTHENTICITY_NOT_VERIFIED = "ADVISORY_POLICY_AUTHENTICITY_NOT_VERIFIED"
    ADVISORY_CONDITION_APPROVAL_NOT_VERIFIED = "ADVISORY_CONDITION_APPROVAL_NOT_VERIFIED"
    ADVISORY_EVIDENCE_RETAINS_SOURCE_CLASSIFICATION = "ADVISORY_EVIDENCE_RETAINS_SOURCE_CLASSIFICATION"
    ADVISORY_NOT_DEPLOYMENT_AUTHORIZATION = "ADVISORY_NOT_DEPLOYMENT_AUTHORIZATION"


def _require_ref_match(policy: ReadinessPolicy, ref: PolicyReference) -> None:
    if not isinstance(ref, PolicyReference):
        raise ReadinessEvaluationError("readiness_policy_ref must be a PolicyReference")
    if ref.policy_family is not PolicyFamily.READINESS:
        raise ReadinessEvaluationError("readiness_policy_ref must reference a READINESS policy")
    derived = policy.reference
    if derived != ref:
        raise ReadinessEvaluationError(
            "readiness_policy body does not match readiness_policy_ref "
            "(id/version/digest/family/tenant must be identical)"
        )


@dataclass(frozen=True)
class ReadinessEvaluationCase:
    """The immutable input to :func:`evaluate_readiness` — no classification."""

    case_id: str
    tenant_id: str
    subject_id: str
    context: AssessmentContext
    readiness_policy: ReadinessPolicy
    readiness_policy_ref: PolicyReference
    requested_target: ReadinessTarget
    intelligence_results: tuple[IntelligenceFitnessResult, ...] = ()
    capability_results: tuple[CapabilityReadinessResult, ...] = ()
    adoption_results: tuple[AdoptionReadinessResult, ...] = ()
    gate_results: tuple[GateResult, ...] = ()
    conditions: tuple[ConditionSet, ...] = ()
    advisory_composite: Optional[AdvisoryComposite] = None

    def __post_init__(self) -> None:
        require_nonempty(self.case_id, "ReadinessEvaluationCase.case_id")
        require_nonempty(self.tenant_id, "ReadinessEvaluationCase.tenant_id")
        require_nonempty(self.subject_id, "ReadinessEvaluationCase.subject_id")

        if not isinstance(self.context, AssessmentContext):
            raise ReadinessEvaluationError("case.context must be an AssessmentContext")
        if self.context.tenant_id != self.tenant_id:
            raise ReadinessEvaluationError(
                f"cross-tenant: context tenant {self.context.tenant_id!r} != {self.tenant_id!r}"
            )
        if self.context.subject_id != self.subject_id:
            raise ReadinessEvaluationError(
                f"cross-subject: context subject {self.context.subject_id!r} != {self.subject_id!r}"
            )
        if not isinstance(self.readiness_policy, ReadinessPolicy):
            raise ReadinessEvaluationError("case.readiness_policy must be a ReadinessPolicy")
        _require_ref_match(self.readiness_policy, self.readiness_policy_ref)
        # A TENANT-scoped policy must belong to the case tenant.
        if self.readiness_policy_ref.scope is PolicyScope.TENANT and self.readiness_policy_ref.tenant_id != self.tenant_id:
            raise ReadinessEvaluationError("readiness_policy_ref belongs to a different tenant")
        if not isinstance(self.requested_target, ReadinessTarget):
            raise ReadinessEvaluationError("case.requested_target must be a ReadinessTarget")
        if self.requested_target not in self.readiness_policy.readiness_targets:
            raise ReadinessEvaluationError(
                f"requested_target {self.requested_target.value} is not governed by this ReadinessPolicy "
                f"(targets: {[t.value for t in self.readiness_policy.readiness_targets]})"
            )
        if self.advisory_composite is not None and not isinstance(self.advisory_composite, AdvisoryComposite):
            raise ReadinessEvaluationError("case.advisory_composite must be an AdvisoryComposite")

        self._check_results("intelligence_results", IntelligenceFitnessResult)
        self._check_results("capability_results", CapabilityReadinessResult)
        self._check_results("adoption_results", AdoptionReadinessResult)
        self._check_gates()
        self._check_conditions()

    def _check_results(self, field: str, expected) -> None:
        coerced = coerce_tuple(getattr(self, field), f"case.{field}")
        seen: set[str] = set()
        for r in coerced:
            if not isinstance(r, expected):
                raise ReadinessEvaluationError(f"case.{field} entries must be {expected.__name__}")
            if r.tenant_id != self.tenant_id or r.subject_id != self.subject_id:
                raise ReadinessEvaluationError(f"case.{field} contains a cross-tenant/subject result")
            if r.context_id != self.context.context_id:
                raise ReadinessEvaluationError(f"case.{field} result bound to a different AssessmentContext")
            if r.result_id in seen:
                raise ReadinessEvaluationError(f"case.{field} duplicates result_id {r.result_id!r}")
            seen.add(r.result_id)
        # Canonicalize by stable id so evaluation is independent of input order.
        object.__setattr__(self, field, tuple(sorted(coerced, key=lambda r: r.result_id)))

    def _check_gates(self) -> None:
        coerced = coerce_tuple(self.gate_results, "case.gate_results")
        policy_gates = {g.gate_id: g for g in self.readiness_policy.gates}
        seen: set[str] = set()
        for gr in coerced:
            if not isinstance(gr, GateResult):
                raise ReadinessEvaluationError("case.gate_results entries must be GateResult")
            if gr.requested_target is not self.requested_target:
                raise ReadinessEvaluationError(
                    f"case.gate_results gate {gr.gate_id!r} evaluated for {gr.requested_target.value}, "
                    f"not the requested {self.requested_target.value}"
                )
            if gr.readiness_policy_ref != self.readiness_policy_ref:
                raise ReadinessEvaluationError(
                    f"case.gate_results gate {gr.gate_id!r} is bound to a different ReadinessPolicy"
                )
            pg = policy_gates.get(gr.gate_id)
            if pg is None:
                raise ReadinessEvaluationError(
                    f"case.gate_results gate {gr.gate_id!r} is not a gate of the supplied ReadinessPolicy"
                )
            if gr.policy_gate != pg:
                raise ReadinessEvaluationError(
                    f"case.gate_results gate {gr.gate_id!r} embeds a PolicyGate that does not match the "
                    "ReadinessPolicy's gate of the same id (metadata tamper)"
                )
            if gr.gate_id in seen:
                raise ReadinessEvaluationError(f"case.gate_results duplicates gate_id {gr.gate_id!r}")
            seen.add(gr.gate_id)
        object.__setattr__(self, "gate_results", tuple(sorted(coerced, key=lambda g: g.gate_id)))

    def _check_conditions(self) -> None:
        coerced = coerce_tuple(self.conditions, "case.conditions")
        seen: set[str] = set()
        for c in coerced:
            if not isinstance(c, ConditionSet):
                raise ReadinessEvaluationError("case.conditions entries must be ConditionSet")
            if c.condition_id in seen:
                raise ReadinessEvaluationError(f"case.conditions duplicates condition_id {c.condition_id!r}")
            seen.add(c.condition_id)
        object.__setattr__(self, "conditions", tuple(sorted(coerced, key=lambda c: c.condition_id)))

    def canonical_digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class EvaluationTrace:
    """A deterministic, explanatory trace of one evaluation. Not authority."""

    evaluator_version: str
    selected_rule: ReadinessRule
    requested_target: ReadinessTarget
    applicable_gate_ids: tuple[str, ...]
    diagnostic_gate_ids: tuple[str, ...]
    mandatory_fail_gate_ids: tuple[str, ...]
    mandatory_indeterminate_gate_ids: tuple[str, ...]
    unresolved_conditional_gate_ids: tuple[str, ...]
    accepted_condition_ids: tuple[str, ...]
    rejected_condition_reasons: tuple[str, ...]
    assessability_gap_codes: tuple[ReadinessReasonCode, ...]
    reason_codes: tuple[ReadinessReasonCode, ...]
    input_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.selected_rule, ReadinessRule):
            raise ReadinessEvaluationError("EvaluationTrace.selected_rule must be a ReadinessRule")

    def canonical_digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class ReadinessEvaluationResult:
    """The evaluator output: the selected determination + its trace."""

    determination: AgentValueReadinessDetermination
    trace: EvaluationTrace

    def __post_init__(self) -> None:
        if not isinstance(self.determination, AgentValueReadinessDetermination):
            raise ReadinessEvaluationError("result.determination must be an AgentValueReadinessDetermination")
        if not isinstance(self.trace, EvaluationTrace):
            raise ReadinessEvaluationError("result.trace must be an EvaluationTrace")

    @property
    def classification(self) -> ReadinessClassification:
        return self.determination.classification

    @property
    def is_advisory(self) -> bool:
        """Always advisory — never a deployment authorization."""

        return True

    def canonical_digest(self) -> str:
        return canonical_digest(self)
