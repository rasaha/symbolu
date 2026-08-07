"""HiringRecommendation — the governed, advisory output of the decision plane.

Derived from the signed/versioned contract reference, admitted evidence,
dimension assessments, mandatory-gate results, eligibility, and confidence. It
is **advisory** (``actor_type=AI``, ``binding=False``) unless an external
Decision Authority makes it binding (via :class:`DecisionAuthorityPort`).

This module NEVER imports the analytics plane and takes no Overall Fit Index
input: the advisory disposition reasons over per-dimension evidence, gates, and
confidence only. ``NOT_ELIGIBLE`` is forced whenever eligibility != ELIGIBLE.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field, model_validator

from ..common import new_id
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from ..hiring_policy.enums import HiringEvidenceClass
from ..hiring_policy.workflow_ir import IRActionConstraints
from .assessment import DimensionAssessment
from .eligibility import Eligibility
from .enums import (
    AssessmentOutcome,
    EligibilityStatus,
    EmploymentType,
    RecommendationDisposition,
)
from .evidence import AdmittedEvidence
from .gates import GateResult
from .refs import ContractRef

# Advisory-disposition thresholds over dimension evidence + confidence (NOT the OFI).
_MIN_SCORE_FOR_ADVANCE = 60.0
_MIN_CONFIDENCE_FOR_ADVANCE = 0.6


class ProposedAction(DomainModel):
    """The action the recommendation proposes, bounded by the contract."""

    level: str
    salary: float = Field(ge=0)
    salary_currency: str = "USD"
    role: str
    location: str
    employment_type: EmploymentType = EmploymentType.FULL_TIME


class Confidence(DomainModel):
    aggregate: float = Field(ge=0.0, le=1.0)
    per_dimension: dict[str, float] = {}


class ReasonNode(DomainModel):
    claim: str
    basis: tuple[str, ...] = ()


class Explanation(DomainModel):
    summary: str
    reason_tree: tuple[ReasonNode, ...] = ()


class HiringRecommendation(DomainModel):
    """Advisory recommendation. Binding only if an external Decision Authority says so."""

    recommendation_id: str
    candidate_id: str
    role_id: str
    contract_ref: ContractRef
    compatibility_assessment: tuple[DimensionAssessment, ...]
    mandatory_gate_results: tuple[GateResult, ...]
    eligibility: Eligibility
    confidence: Confidence
    evidence_lineage: tuple[str, ...] = ()
    proposed_action: Optional[ProposedAction] = None
    recommendation: RecommendationDisposition
    explanation: Explanation
    actor_type: Literal["AI"] = "AI"
    advisory_only: Literal[True] = True
    binding: Literal[False] = False

    @model_validator(mode="after")
    def _validate(self) -> "HiringRecommendation":
        if not self.candidate_id.strip() or not self.role_id.strip():
            raise DomainValidationError("candidate_id and role_id are required")
        # NOT_ELIGIBLE is forced (and only allowed) when eligibility != ELIGIBLE.
        if self.eligibility.status is not EligibilityStatus.ELIGIBLE:
            if self.recommendation is not RecommendationDisposition.NOT_ELIGIBLE:
                raise DomainValidationError(
                    "recommendation must be NOT_ELIGIBLE when eligibility != ELIGIBLE"
                )
            if self.proposed_action is not None:
                raise DomainValidationError(
                    "a non-eligible recommendation must not carry a proposed action"
                )
        else:
            if self.recommendation is RecommendationDisposition.NOT_ELIGIBLE:
                raise DomainValidationError(
                    "recommendation must not be NOT_ELIGIBLE when eligibility == ELIGIBLE"
                )
        return self


def compute_confidence(assessments: tuple[DimensionAssessment, ...]) -> Confidence:
    """Aggregate confidence = mean of per-dimension confidences (0 if none)."""
    per = {a.dimension: a.confidence for a in assessments}
    aggregate = round(sum(per.values()) / len(per), 9) if per else 0.0
    return Confidence(aggregate=aggregate, per_dimension=per)


def _advisory_disposition(
    assessments: tuple[DimensionAssessment, ...], confidence: Confidence
) -> RecommendationDisposition:
    """Transparent advisory rule over dimension evidence + confidence — never the OFI."""
    scored = [a for a in assessments if a.outcome is AssessmentOutcome.SCORED]
    insufficient = [a for a in assessments if a.outcome is AssessmentOutcome.INSUFFICIENT_EVIDENCE]
    if insufficient or not scored:
        return RecommendationDisposition.HOLD  # need more admitted evidence
    lowest = min(a.score for a in scored if a.score is not None)
    if lowest >= _MIN_SCORE_FOR_ADVANCE and confidence.aggregate >= _MIN_CONFIDENCE_FOR_ADVANCE:
        return RecommendationDisposition.ADVANCE
    return RecommendationDisposition.DECLINE


def _action_within_constraints(
    action: ProposedAction, constraints: IRActionConstraints
) -> Optional[str]:
    """Return a violation string if the proposed action breaches the contract, else None."""
    if action.salary > constraints.salary_ceiling:
        return f"salary {action.salary:g} exceeds ceiling {constraints.salary_ceiling:g}"
    if action.level != constraints.approved_level:
        return f"level {action.level!r} != approved {constraints.approved_level!r}"
    if constraints.approved_roles and action.role not in constraints.approved_roles:
        return f"role {action.role!r} not in approved roles"
    if constraints.allowed_locations and action.location not in constraints.allowed_locations:
        return f"location {action.location!r} not in allowed locations"
    return None


def build_recommendation(
    *,
    candidate_id: str,
    role_id: str,
    contract_ref: ContractRef,
    admitted_evidence: tuple[AdmittedEvidence, ...],
    dimension_assessments: tuple[DimensionAssessment, ...],
    gate_results: tuple[GateResult, ...],
    eligibility: Eligibility,
    proposed_action: Optional[ProposedAction] = None,
    action_constraints: Optional[IRActionConstraints] = None,
    recommendation_id: Optional[str] = None,
) -> HiringRecommendation:
    """Assemble an advisory recommendation. Forces NOT_ELIGIBLE on gate failure;
    never reads the Overall Fit Index."""
    confidence = compute_confidence(dimension_assessments)
    lineage = tuple(e.lineage_node_id for e in admitted_evidence if e.admitted)

    if eligibility.status is not EligibilityStatus.ELIGIBLE:
        disposition = RecommendationDisposition.NOT_ELIGIBLE
        proposed_action = None
        summary = (
            f"Not eligible: {eligibility.status.value} "
            f"(blocking gates: {list(eligibility.blocking_gate_ids)})"
        )
    else:
        disposition = _advisory_disposition(dimension_assessments, confidence)
        if disposition is RecommendationDisposition.ADVANCE and proposed_action is not None:
            if action_constraints is not None:
                violation = _action_within_constraints(proposed_action, action_constraints)
                if violation is not None:
                    raise DomainValidationError(
                        f"proposed_action breaches contract constraints: {violation}"
                    )
        else:
            proposed_action = None
        summary = f"Eligible; advisory disposition {disposition.value} from dimension evidence + confidence"

    reason_tree = (
        ReasonNode(
            claim=f"eligibility={eligibility.status.value}",
            basis=tuple(g.gate_id for g in gate_results),
        ),
        *(
            ReasonNode(
                claim=f"{a.dimension}={a.outcome.value}"
                + (f" score={a.score:g}" if a.score is not None else ""),
                basis=a.evidence_refs,
            )
            for a in dimension_assessments
        ),
    )

    return HiringRecommendation(
        recommendation_id=recommendation_id or new_id("hrec"),
        candidate_id=candidate_id,
        role_id=role_id,
        contract_ref=contract_ref,
        compatibility_assessment=dimension_assessments,
        mandatory_gate_results=gate_results,
        eligibility=eligibility,
        confidence=confidence,
        evidence_lineage=lineage,
        proposed_action=proposed_action,
        recommendation=disposition,
        explanation=Explanation(summary=summary, reason_tree=reason_tree),
    )
