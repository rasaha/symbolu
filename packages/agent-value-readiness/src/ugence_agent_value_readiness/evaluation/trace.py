"""The deterministic evaluation trace and the evaluator's result wrapper.

The trace is **explanatory only**. It is not evidence, not an audit authority,
not a signed record, and not a durable event — no event bus, signing, or
persistence is introduced in this phase. It exists so that a human reading a
determination can see exactly which gates, conditions and gaps produced it.

Every collection on the trace is canonically ordered (by gate id, condition id,
or code declaration order), never by the order the caller supplied its inputs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from ugence_uvi_policy_contracts.api import ReadinessTarget

from ..contracts._util import canonical_digest, require_nonempty, require_tzaware, validate_digest
from ..contracts.determination import AgentValueReadinessDetermination
from ..contracts.enums import ReadinessClassification
from .errors import ReadinessEvaluationError

__all__ = ["ConditionDecision", "ReadinessEvaluationTrace", "ReadinessEvaluationResult"]


@dataclass(frozen=True)
class ConditionDecision:
    """Why one supplied ``ConditionSet`` was accepted or rejected as coverage.

    ``accepted`` records only that the control was *structurally* usable as
    coverage at the evaluation time. It never asserts that a real authority
    approved it, that the mitigation exists, or that monitoring is running.
    """

    condition_id: str
    source_gate_or_finding_ref: str
    decision_code: str
    accepted: bool

    def __post_init__(self) -> None:
        require_nonempty(self.condition_id, "ConditionDecision.condition_id")
        require_nonempty(
            self.source_gate_or_finding_ref, "ConditionDecision.source_gate_or_finding_ref"
        )
        require_nonempty(self.decision_code, "ConditionDecision.decision_code")
        if not isinstance(self.accepted, bool):
            raise ReadinessEvaluationError("ConditionDecision.accepted must be a bool")

    def canonical_digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class ReadinessEvaluationTrace:
    """A minimal, deterministic explanation of one readiness evaluation."""

    evaluator_id: str
    formula_version: str
    rule_id: str
    classification: ReadinessClassification
    requested_target: ReadinessTarget
    evaluation_time: datetime
    applicable_gate_ids: tuple[str, ...] = ()
    diagnostic_gate_ids: tuple[str, ...] = ()
    missing_required_gate_ids: tuple[str, ...] = ()
    mandatory_failure_gate_ids: tuple[str, ...] = ()
    mandatory_indeterminate_gate_ids: tuple[str, ...] = ()
    unresolved_conditional_gate_ids: tuple[str, ...] = ()
    non_compensable_conditional_gate_ids: tuple[str, ...] = ()
    uncovered_conditional_gate_ids: tuple[str, ...] = ()
    accepted_condition_ids: tuple[str, ...] = ()
    condition_decisions: tuple[ConditionDecision, ...] = ()
    assessability_gap_codes: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    advisory_codes: tuple[str, ...] = ()
    input_ref_ids: tuple[str, ...] = ()
    input_digest: str = ""
    advisory_composite_carried: bool = False

    def __post_init__(self) -> None:
        require_nonempty(self.evaluator_id, "ReadinessEvaluationTrace.evaluator_id")
        require_nonempty(self.formula_version, "ReadinessEvaluationTrace.formula_version")
        require_nonempty(self.rule_id, "ReadinessEvaluationTrace.rule_id")
        if not isinstance(self.classification, ReadinessClassification):
            raise ReadinessEvaluationError(
                "ReadinessEvaluationTrace.classification must be a ReadinessClassification"
            )
        if not isinstance(self.requested_target, ReadinessTarget):
            raise ReadinessEvaluationError(
                "ReadinessEvaluationTrace.requested_target must be a ReadinessTarget"
            )
        require_tzaware(self.evaluation_time, "ReadinessEvaluationTrace.evaluation_time")
        for name in (
            "applicable_gate_ids",
            "diagnostic_gate_ids",
            "missing_required_gate_ids",
            "mandatory_failure_gate_ids",
            "mandatory_indeterminate_gate_ids",
            "unresolved_conditional_gate_ids",
            "non_compensable_conditional_gate_ids",
            "uncovered_conditional_gate_ids",
            "accepted_condition_ids",
            "assessability_gap_codes",
            "reason_codes",
            "advisory_codes",
            "input_ref_ids",
        ):
            value = getattr(self, name)
            if not isinstance(value, tuple) or any(not isinstance(v, str) for v in value):
                raise ReadinessEvaluationError(
                    f"ReadinessEvaluationTrace.{name} must be a tuple of strings"
                )
        if not isinstance(self.condition_decisions, tuple) or any(
            not isinstance(d, ConditionDecision) for d in self.condition_decisions
        ):
            raise ReadinessEvaluationError(
                "ReadinessEvaluationTrace.condition_decisions must be a tuple of ConditionDecision"
            )
        validate_digest(self.input_digest, "ReadinessEvaluationTrace.input_digest", required=False)
        if not isinstance(self.advisory_composite_carried, bool):
            raise ReadinessEvaluationError(
                "ReadinessEvaluationTrace.advisory_composite_carried must be a bool"
            )

    @property
    def is_explanatory_only(self) -> bool:
        """Always ``True`` — the trace explains, it never authorizes or attests."""

        return True

    def canonical_digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class ReadinessEvaluationResult:
    """An evaluator-selected determination plus its deterministic trace.

    The determination is **advisory**: it is not a deployment authorization, it
    does not verify evidence, it does not approve a policy, and it contains no
    financial quantity. The classification was selected by the evaluator from the
    complete applicable gate set — never supplied by the caller.
    """

    determination: AgentValueReadinessDetermination
    trace: ReadinessEvaluationTrace

    def __post_init__(self) -> None:
        if not isinstance(self.determination, AgentValueReadinessDetermination):
            raise ReadinessEvaluationError(
                "ReadinessEvaluationResult.determination must be an AgentValueReadinessDetermination"
            )
        if not isinstance(self.trace, ReadinessEvaluationTrace):
            raise ReadinessEvaluationError(
                "ReadinessEvaluationResult.trace must be a ReadinessEvaluationTrace"
            )
        if self.determination.classification is not self.trace.classification:
            raise ReadinessEvaluationError(
                "ReadinessEvaluationResult trace/determination classification disagree"
            )
        if self.determination.requested_target is not self.trace.requested_target:
            raise ReadinessEvaluationError(
                "ReadinessEvaluationResult trace/determination requested_target disagree"
            )

    @property
    def classification(self) -> ReadinessClassification:
        return self.determination.classification

    @property
    def rule_id(self) -> str:
        return self.trace.rule_id

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return self.trace.reason_codes

    @property
    def advisory_codes(self) -> tuple[str, ...]:
        return self.trace.advisory_codes

    @property
    def is_advisory(self) -> bool:
        """Always ``True``. This result never authorizes a deployment."""

        return True

    @property
    def authorizes_deployment(self) -> bool:
        """Always ``False`` — deployment governance is a separate process.

        Present so that a consumer asking the question gets an unambiguous
        ``False`` instead of inferring authority from a high readiness tier.
        """

        return False

    def canonical_digest(self) -> str:
        """Stable digest over the determination and its trace."""

        joined = f"{self.determination.canonical_digest()}:{self.trace.canonical_digest()}"
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()
