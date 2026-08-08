"""HiringDecisionCase — the package aggregate root for one candidate-role lifecycle.

Links admitted evidence, dimension assessments, gate results, eligibility, the
advisory recommendation, an (externally authorized) binding decision, and
post-hire reviews — without collapsing them into one another. The case is
immutable; every ``record_*`` method returns a new case with an appended history
entry.

Authority boundary: a binding decision can be recorded **only** from a
:class:`DecisionAuthorityOutcome` that is ``binding`` and carries HUMAN authority.
An AI/service principal cannot construct one (``BindingDecision.actor_type`` is
pinned to HUMAN), and :meth:`record_decision` refuses a non-binding outcome.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field, model_validator

from ..common import new_id
from ..domain.base import DomainModel
from ..errors import BoundaryViolationError, DomainValidationError
from .assessment import DimensionAssessment
from .eligibility import Eligibility
from .enums import CaseStatus, DecisionDisposition
from .evidence import AdmittedEvidence
from .gates import GateResult
from .ports import DecisionAuthorityOutcome
from .recommendation import HiringRecommendation
from .refs import ContractRef
from .reviews import ReviewRecord


class BindingDecision(DomainModel):
    """A binding employment decision. Only a HUMAN authority can author one."""

    decision_id: str = Field(default_factory=lambda: new_id("hdec"))
    recommendation_id: str
    disposition: DecisionDisposition
    decided_by: str
    actor_type: Literal["HUMAN"] = "HUMAN"
    authority_id: str
    rationale_job_related: str = ""
    override_reason: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "BindingDecision":
        if not self.decided_by.strip():
            raise DomainValidationError("decided_by is required")
        return self


class HiringDecisionCase(DomainModel):
    """Immutable aggregate root; ``record_*`` methods return updated copies."""

    case_id: str = Field(default_factory=lambda: new_id("hcase"))
    candidate_id: str
    role_id: str
    contract_ref: ContractRef
    status: CaseStatus = CaseStatus.OPEN
    admitted_evidence: tuple[AdmittedEvidence, ...] = ()
    dimension_assessments: tuple[DimensionAssessment, ...] = ()
    gate_results: tuple[GateResult, ...] = ()
    eligibility: Optional[Eligibility] = None
    recommendation: Optional[HiringRecommendation] = None
    decision: Optional[BindingDecision] = None
    reviews: tuple[ReviewRecord, ...] = ()
    history: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> "HiringDecisionCase":
        if not self.candidate_id.strip() or not self.role_id.strip():
            raise DomainValidationError("candidate_id and role_id are required")
        return self

    # -- append-only transitions ------------------------------------------
    def _with(self, event: str, **update) -> "HiringDecisionCase":
        update["history"] = self.history + (event,)
        return self.model_copy(update=update)

    def record_evidence(self, evidence: tuple[AdmittedEvidence, ...]) -> "HiringDecisionCase":
        admitted = sum(1 for e in evidence if e.admitted)
        return self._with(
            f"evidence_admitted:{admitted}/{len(evidence)}",
            admitted_evidence=evidence,
            status=CaseStatus.EVIDENCE_ADMITTED,
        )

    def record_assessments(
        self, assessments: tuple[DimensionAssessment, ...]
    ) -> "HiringDecisionCase":
        return self._with(
            f"assessed:{len(assessments)}",
            dimension_assessments=assessments,
            status=CaseStatus.ASSESSED,
        )

    def record_gate_results(
        self, gate_results: tuple[GateResult, ...], eligibility: Eligibility
    ) -> "HiringDecisionCase":
        return self._with(
            f"authority_evaluated:eligibility={eligibility.status.value}",
            gate_results=gate_results,
            eligibility=eligibility,
            status=CaseStatus.AUTHORITY_EVALUATED,
        )

    def record_recommendation(
        self, recommendation: HiringRecommendation
    ) -> "HiringDecisionCase":
        if recommendation.binding is not False:
            raise BoundaryViolationError("a recommendation is advisory and cannot be binding")
        return self._with(
            f"recommended:{recommendation.recommendation.value}",
            recommendation=recommendation,
            status=CaseStatus.RECOMMENDED,
        )

    def record_decision(self, outcome: DecisionAuthorityOutcome) -> "HiringDecisionCase":
        """Record a binding decision from a Decision Authority outcome.

        Refuses to bind unless the shared Decision Authority marked the outcome
        binding; the ``BindingDecision`` it constructs is HUMAN-authored by
        construction.
        """
        if self.recommendation is None:
            raise DomainValidationError("cannot record a decision before a recommendation")
        if outcome.recommendation_id != self.recommendation.recommendation_id:
            raise DomainValidationError("decision outcome does not reference this case's recommendation")
        if not outcome.binding:
            raise BoundaryViolationError(
                "Decision Authority did not make this outcome binding; the recommendation "
                "stays advisory"
            )
        decision = BindingDecision(
            recommendation_id=outcome.recommendation_id,
            disposition=outcome.disposition,
            decided_by=outcome.authority_id,
            authority_id=outcome.authority_id,
            rationale_job_related=outcome.rationale_job_related,
            override_reason=outcome.override_reason,
        )
        return self._with(
            f"decided:{decision.disposition.value}",
            decision=decision,
            status=CaseStatus.DECIDED,
        )

    def record_review(self, review: ReviewRecord) -> "HiringDecisionCase":
        return self._with(
            f"review:{review.checkpoint.value}:{review.trajectory.value}",
            reviews=self.reviews + (review,),
            status=CaseStatus.IN_LIFECYCLE_REVIEW,
        )
