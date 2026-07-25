"""Deterministic structural validation for the DecisionCase aggregate.

Every method returns a *typed result*, never a bare boolean. Validation checks
references, versions, tenant consistency, assessment finalization, authority
shape, required reviews, and lifecycle legality. It never reinterprets assessment
content and never judges candidate quality.
"""

from __future__ import annotations

from typing import Optional

from ..assessments.status import AssessmentStatus, CompletenessStatus
from ..decision_cases.authority import AuthorityContext
from ..decision_cases.case import DecisionCase
from ..decision_cases.review import ReviewTask
from ..decision_cases.status import (
    AuthorityType,
    GeneratorType,
    HUMAN_AUTHORITIES,
    ReviewTaskStatus,
)
from ..decision_cases.validation import (
    CaseValidationIssue,
    CaseValidationResult,
    DecisionReadinessResult,
)
from ..domain.enums import ActorType
from ..ontology.taxonomy import ReasonCode, is_known_reason_code
from ..repositories.assessment_repository import AssessmentRepository

#: Review tasks that must be COMPLETED before a decision may be recorded.
_BLOCKING_REVIEW_STATUSES = frozenset(
    {ReviewTaskStatus.PENDING})


class CaseValidationService:
    def __init__(self, assessment_repository: AssessmentRepository) -> None:
        self._assessments = assessment_repository

    # --- assessment linkage ----------------------------------------------
    def validate_assessment_link(
        self, case: DecisionCase, *, assessment_id: str, version: int
    ) -> CaseValidationResult:
        errors: list[CaseValidationIssue] = []

        def err(code: str, msg: str) -> None:
            errors.append(CaseValidationIssue(code=code, message=msg, ref_id=assessment_id))

        try:
            assessment = self._assessments.get_assessment(assessment_id)
        except Exception:  # noqa: BLE001 - missing == not linkable
            err("ASSESSMENT_NOT_FOUND", f"assessment '{assessment_id}' does not exist")
            return CaseValidationResult(valid=False, errors=tuple(errors),
                                        blocking_conditions=tuple(i.code for i in errors))
        if assessment.version != version:
            err("ASSESSMENT_VERSION_MISMATCH",
                f"assessment '{assessment_id}' is at version {assessment.version}, "
                f"not {version}")
        if assessment.tenant_id != case.tenant_id:
            err("CROSS_TENANT_ASSESSMENT",
                "assessment belongs to a different tenant")
        subjects = {s.subject_id for s in case.subject_refs}
        if assessment.subject_id not in subjects:
            err("ASSESSMENT_SUBJECT_MISMATCH",
                "assessment subject is not a subject of this case")
        if assessment.status is not AssessmentStatus.FINALIZED_ADVISORY:
            err("ASSESSMENT_NOT_FINALIZED",
                "only a finalized advisory assessment may be linked")
        return CaseValidationResult(
            valid=not errors, errors=tuple(errors),
            blocking_conditions=tuple(i.code for i in errors),
            referenced_versions=(f"assessment:{assessment_id}:{version}",))

    # --- recommendation ---------------------------------------------------
    def validate_recommendation(
        self, case: DecisionCase, *, assessment_ref_ids: tuple[str, ...],
        reason_codes: tuple[ReasonCode, ...], generator_type: GeneratorType,
        model_provenance: Optional[str],
    ) -> CaseValidationResult:
        errors: list[CaseValidationIssue] = []
        linked = {r.ref_id for r in case.assessment_refs}
        for aid in assessment_ref_ids:
            if aid not in linked:
                errors.append(CaseValidationIssue(
                    code="RECOMMENDATION_ASSESSMENT_NOT_LINKED",
                    message=f"assessment '{aid}' is not linked to this case",
                    ref_id=aid))
        for rc in reason_codes:
            if not is_known_reason_code(rc.value):
                errors.append(CaseValidationIssue(
                    code="REASON_CODE_UNKNOWN",
                    message=f"reason code '{rc}' is not in the approved catalog"))
        if generator_type is GeneratorType.AI_ASSISTED and not (model_provenance or "").strip():
            errors.append(CaseValidationIssue(
                code="MISSING_MODEL_PROVENANCE",
                message="AI-assisted recommendations require model provenance"))
        return CaseValidationResult(
            valid=not errors, errors=tuple(errors),
            blocking_conditions=tuple(i.code for i in errors))

    # --- authority --------------------------------------------------------
    def validate_authority(
        self, case: DecisionCase, authority: AuthorityContext, *,
        actor_type: ActorType, decided_by: str,
        recommendation_authors: frozenset[str] = frozenset(),
    ) -> CaseValidationResult:
        """Validate that the recorded authority may bind a decision on this case."""
        errors: list[CaseValidationIssue] = []

        def err(code: str, msg: str) -> None:
            errors.append(CaseValidationIssue(code=code, message=msg))

        # An AI principal may never be the binding authority (belt and braces:
        # AuthorityType has no AI member, and the actor itself must not be AI).
        if actor_type is ActorType.AI:
            err("AI_CANNOT_DECIDE", "an AI principal may not author a binding decision")

        if authority.authority_type in HUMAN_AUTHORITIES and actor_type is not ActorType.HUMAN:
            err("HUMAN_AUTHORITY_REQUIRES_HUMAN",
                f"{authority.authority_type.value} requires an authenticated human actor")

        if authority.authority_type is AuthorityType.DELEGATED_POLICY:
            if authority.granting_policy_ref is None:
                err("DELEGATED_POLICY_UNBOUNDED",
                    "delegated policy authority requires a granting policy reference")
            if not authority.decision_scope.strip() and not authority.limits:
                err("DELEGATED_POLICY_NO_SCOPE",
                    "delegated policy authority requires explicit scope or limits")
            if actor_type is ActorType.AI:
                err("DELEGATED_POLICY_NOT_AI",
                    "delegated policy must be a deterministic policy, not AI discretion")

        # Segregation of duties: an actor who authored a recommendation cannot be
        # the sole decision authority when SoD is required.
        if authority.segregation_of_duties and decided_by in recommendation_authors:
            err("SEGREGATION_OF_DUTIES",
                "the decision authority may not also be the recommendation author")

        return CaseValidationResult(
            valid=not errors, errors=tuple(errors),
            blocking_conditions=tuple(i.code for i in errors))

    # --- decision readiness ----------------------------------------------
    def evaluate_decision_readiness(
        self, case: DecisionCase, *, review_tasks: tuple[ReviewTask, ...],
    ) -> DecisionReadinessResult:
        """Structural readiness only — never a judgement of candidate quality."""
        blockers: list[CaseValidationIssue] = []
        warnings: list[CaseValidationIssue] = []
        outstanding: list[str] = []

        for task in review_tasks:
            if task.status in _BLOCKING_REVIEW_STATUSES:
                outstanding.append(task.task_id)
                blockers.append(CaseValidationIssue(
                    code="REQUIRED_REVIEW_OUTSTANDING",
                    message=f"review task '{task.task_id}' ({task.task_type.value}) "
                            "is not complete", ref_id=task.task_id))

        # A finalized assessment whose completeness is BLOCKED must never gate a
        # decision as "ready" (defensive; finalize already forbids this state).
        for ref in case.assessment_refs:
            try:
                assessment = self._assessments.get_assessment(ref.ref_id)
            except Exception:  # noqa: BLE001
                continue
            if assessment.completeness.status is CompletenessStatus.BLOCKED:
                blockers.append(CaseValidationIssue(
                    code="BLOCKING_ASSESSMENT_CONDITION",
                    message=f"assessment '{ref.ref_id}' has a blocking condition",
                    ref_id=ref.ref_id))

        if case.require_recommendation and not case.recommendation_refs:
            blockers.append(CaseValidationIssue(
                code="RECOMMENDATION_REQUIRED",
                message="policy requires a recommendation before a decision"))

        return DecisionReadinessResult(
            ready=not blockers, blockers=tuple(blockers), warnings=tuple(warnings),
            required_reviews_outstanding=tuple(outstanding))
