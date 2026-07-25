"""DecisionCaseService — creates cases, links records, orchestrates lifecycle.

This service owns the aggregate's structure and lifecycle: it creates and versions
cases, links finalized assessments, assigns and completes review tasks, drives
legal status transitions, and emits audit events. It never generates
recommendations, never records decisions, and never executes actions — those live
in the sibling services (and, for execution, in later phases that do not exist
here).
"""

from __future__ import annotations

from typing import Optional

from ..common import Clock, IdFactory, new_id, utc_now
from ..decision_cases.case import DecisionCase
from ..decision_cases.lifecycle import is_legal_transition
from ..decision_cases.review import ReviewTask
from ..decision_cases.status import (
    CaseStatus,
    OperatingMode,
    ReviewTaskStatus,
    ReviewTaskType,
    TERMINAL_CASE_STATUSES,
)
from ..decision_cases.subject import SubjectRef, VersionedRef
from ..decision_cases.validation import DecisionReadinessResult
from ..domain.enums import ActorType, AuditEventType
from ..errors import (
    AssessmentNotLinkableError,
    CaseFinalizedError,
    InvalidCaseTransitionError,
    ReviewTaskNotFoundError,
)
from ..policies.decision_boundary import IdentityProvider
from ..policies.evidence_access_policy import EvidenceAccessPolicy, Permission
from ..repositories.decision_case_repository import DecisionCaseRepository
from .audit_service import AuditService
from .case_validation_service import CaseValidationService
from ._case_authz import authorize_case_action


class DecisionCaseService:
    def __init__(
        self,
        case_repository: DecisionCaseRepository,
        validation_service: CaseValidationService,
        audit_service: AuditService,
        identity_provider: IdentityProvider,
        access_policy: EvidenceAccessPolicy,
        *,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._repo = case_repository
        self._validation = validation_service
        self._audit = audit_service
        self._identity = identity_provider
        self._policy = access_policy
        self._new_id = id_factory
        self._clock = clock

    # --- helpers ----------------------------------------------------------
    def _authorize(self, actor: str, permission: Permission, tenant_id: str,
                   subject_id: Optional[str], correlation_id: str,
                   entity_id: str) -> ActorType:
        return authorize_case_action(
            self._identity, self._policy, self._audit, actor=actor,
            permission=permission, tenant_id=tenant_id, subject_id=subject_id,
            correlation_id=correlation_id, entity_id=entity_id)

    def _emit(self, event_type, entity_id, actor, actor_type, corr, payload):
        self._audit.record(
            event_type=event_type, entity_type="decision_case", entity_id=entity_id,
            actor_type=actor_type, actor_id=actor, correlation_id=corr, payload=payload)

    def _require_mutable(self, case: DecisionCase) -> None:
        if case.status in TERMINAL_CASE_STATUSES:
            raise CaseFinalizedError(
                f"case '{case.decision_case_id}' is {case.status.value} and immutable")

    def _transition(self, case: DecisionCase, target: CaseStatus,
                    **changes) -> DecisionCase:
        if not is_legal_transition(case.status, target):
            raise InvalidCaseTransitionError(
                f"illegal transition {case.status.value} -> {target.value}")
        evolved = case.evolve(case_version_id=self._new_id("cv"),
                              status=target, **changes)
        return self._repo.save_case_version(evolved)

    # --- lifecycle --------------------------------------------------------
    def create_case(self, *, tenant_id: str, decision_type: str,
                    subject_ids: tuple[str, ...], created_by: str,
                    policy_refs: tuple[VersionedRef, ...] = (),
                    operating_mode: OperatingMode = OperatingMode.DELIBERATIVE,
                    require_recommendation: bool = False,
                    correlation_id: Optional[str] = None) -> DecisionCase:
        corr = correlation_id or self._new_id("corr")
        case_id = self._new_id("case")
        actor_type = self._authorize(created_by, Permission.CREATE_DECISION_CASE,
                                     tenant_id, subject_ids[0] if subject_ids else None,
                                     corr, case_id)
        case = DecisionCase(
            decision_case_id=case_id, tenant_id=tenant_id, decision_type=decision_type,
            subject_refs=tuple(SubjectRef(subject_id=s) for s in subject_ids),
            policy_refs=policy_refs, operating_mode=operating_mode,
            require_recommendation=require_recommendation, status=CaseStatus.CREATED,
            version=1, case_version_id=self._new_id("cv"), created_by=created_by,
            created_at=self._clock(), correlation_id=corr)
        self._repo.create_case(case)
        self._emit(AuditEventType.DECISION_CASE_CREATED, case_id, created_by, actor_type,
                   corr, {"decision_type": decision_type,
                          "subjects": list(subject_ids),
                          "operating_mode": operating_mode.value})
        return case

    def link_assessment(self, *, case_id: str, assessment_id: str, version: int,
                        actor: str) -> DecisionCase:
        case = self._repo.get_case(case_id)
        self._require_mutable(case)
        actor_type = self._authorize(actor, Permission.LINK_ASSESSMENT, case.tenant_id,
                                     None, case.correlation_id, case_id)
        result = self._validation.validate_assessment_link(
            case, assessment_id=assessment_id, version=version)
        if not result.valid:
            raise AssessmentNotLinkableError(
                f"assessment '{assessment_id}' not linkable: {result.error_codes}")
        ref = VersionedRef(ref_id=assessment_id, version=version, kind="assessment")
        # Advance from CREATED/EVIDENCE_ASSEMBLY toward assessment-in-progress.
        target = (CaseStatus.ASSESSMENT_IN_PROGRESS
                  if case.status in (CaseStatus.CREATED, CaseStatus.EVIDENCE_ASSEMBLY)
                  else case.status)
        evolved = case.evolve(case_version_id=self._new_id("cv"), status=target,
                              assessment_refs=case.assessment_refs + (ref,))
        self._repo.save_case_version(evolved)
        self._emit(AuditEventType.DECISION_CASE_ASSESSMENT_LINKED, case_id, actor,
                   actor_type, case.correlation_id,
                   {"assessment_id": assessment_id, "version": version})
        return evolved

    def mark_ready_for_recommendation(self, *, case_id: str, actor: str) -> DecisionCase:
        case = self._repo.get_case(case_id)
        self._require_mutable(case)
        actor_type = self._authorize(actor, Permission.LINK_ASSESSMENT, case.tenant_id,
                                     None, case.correlation_id, case_id)
        evolved = self._transition(case, CaseStatus.READY_FOR_RECOMMENDATION)
        self._emit(AuditEventType.DECISION_CASE_ASSESSMENT_LINKED, case_id, actor,
                   actor_type, case.correlation_id, {"status": evolved.status.value})
        return evolved

    def assign_review(self, *, case_id: str, task_type: ReviewTaskType,
                      assigned_to: Optional[str], required_role: str = "",
                      actor: str) -> ReviewTask:
        case = self._repo.get_case(case_id)
        self._require_mutable(case)
        actor_type = self._authorize(actor, Permission.ASSIGN_REVIEW, case.tenant_id,
                                     None, case.correlation_id, case_id)
        task = ReviewTask(
            task_id=self._new_id("rev"), decision_case_id=case_id,
            tenant_id=case.tenant_id, task_type=task_type, assigned_to=assigned_to,
            required_role=required_role, status=ReviewTaskStatus.PENDING,
            created_at=self._clock())
        self._repo.add_review_task(task)
        target = (CaseStatus.UNDER_REVIEW
                  if is_legal_transition(case.status, CaseStatus.UNDER_REVIEW)
                  else case.status)
        if target is not case.status:
            case = self._repo.save_case_version(
                case.evolve(case_version_id=self._new_id("cv"),
                            status=target, review_tasks=case.review_tasks + (task.task_id,)))
        else:
            case = self._repo.save_case_version(
                case.evolve(case_version_id=self._new_id("cv"),
                            review_tasks=case.review_tasks + (task.task_id,)))
        self._emit(AuditEventType.DECISION_CASE_REVIEW_ASSIGNED, case_id, actor,
                   actor_type, case.correlation_id,
                   {"task_id": task.task_id, "task_type": task_type.value})
        return task

    def complete_review(self, *, case_id: str, task_id: str, actor: str) -> ReviewTask:
        case = self._repo.get_case(case_id)
        actor_type = self._authorize(actor, Permission.COMPLETE_REVIEW, case.tenant_id,
                                     None, case.correlation_id, case_id)
        task = self._repo.get_review_task(task_id)
        if task.decision_case_id != case_id:
            raise ReviewTaskNotFoundError(
                f"task '{task_id}' does not belong to case '{case_id}'")
        completed = task.completed(by=actor, at=self._clock())
        self._repo.save_review_task(completed)
        self._emit(AuditEventType.DECISION_CASE_REVIEW_COMPLETED, case_id, actor,
                   actor_type, case.correlation_id,
                   {"task_id": task_id, "task_type": task.task_type.value})
        return completed

    def validate_decision_readiness(self, *, case_id: str,
                                    actor: str) -> DecisionReadinessResult:
        case = self._repo.get_case(case_id)
        actor_type = self._authorize(actor, Permission.VIEW_DECISION_CASE, case.tenant_id,
                                     None, case.correlation_id, case_id)
        result = self._validation.evaluate_decision_readiness(
            case, review_tasks=self._repo.list_review_tasks(case_id))
        if result.ready and is_legal_transition(case.status, CaseStatus.READY_FOR_DECISION):
            case = self._repo.save_case_version(
                case.evolve(case_version_id=self._new_id("cv"),
                            status=CaseStatus.READY_FOR_DECISION))
            self._emit(AuditEventType.DECISION_CASE_READY_FOR_DECISION, case_id, actor,
                       actor_type, case.correlation_id, {"ready": True})
        return result

    def supersede_case(self, *, case_id: str, actor: str) -> DecisionCase:
        """Reopen a DECIDED case for a superseding revision (append-only)."""
        case = self._repo.get_case(case_id)
        actor_type = self._authorize(actor, Permission.SUPERSEDE_DECISION_CASE,
                                     case.tenant_id, None, case.correlation_id, case_id)
        if case.status is not CaseStatus.DECIDED:
            raise InvalidCaseTransitionError("only a DECIDED case can be superseded")
        # Mark the current snapshot superseded, then append a reopened version.
        superseded = self._repo.save_case_version(
            case.evolve(case_version_id=self._new_id("cv"), status=CaseStatus.SUPERSEDED))
        reopened = self._repo.save_case_version(
            superseded.evolve(case_version_id=self._new_id("cv"),
                              status=CaseStatus.READY_FOR_DECISION))
        self._emit(AuditEventType.DECISION_CASE_SUPERSEDED, case_id, actor, actor_type,
                   case.correlation_id, {"reopened_version": reopened.version})
        return reopened

    def cancel_case(self, *, case_id: str, actor: str) -> DecisionCase:
        case = self._repo.get_case(case_id)
        actor_type = self._authorize(actor, Permission.CANCEL_DECISION_CASE,
                                     case.tenant_id, None, case.correlation_id, case_id)
        self._require_mutable(case)
        evolved = self._repo.save_case_version(
            case.evolve(case_version_id=self._new_id("cv"), status=CaseStatus.CANCELLED))
        self._emit(AuditEventType.DECISION_CASE_CANCELLED, case_id, actor, actor_type,
                   case.correlation_id, {})
        return evolved

    def close_case(self, *, case_id: str, actor: str) -> DecisionCase:
        case = self._repo.get_case(case_id)
        actor_type = self._authorize(actor, Permission.CLOSE_DECISION_CASE,
                                     case.tenant_id, None, case.correlation_id, case_id)
        if not is_legal_transition(case.status, CaseStatus.CLOSED):
            raise InvalidCaseTransitionError(
                f"cannot close a case in status {case.status.value}")
        evolved = self._repo.save_case_version(
            case.evolve(case_version_id=self._new_id("cv"), status=CaseStatus.CLOSED))
        self._emit(AuditEventType.DECISION_CASE_CLOSED, case_id, actor, actor_type,
                   case.correlation_id, {})
        return evolved

    # --- reads ------------------------------------------------------------
    def get_case(self, case_id: str) -> DecisionCase:
        return self._repo.get_case(case_id)

    def get_case_history(self, case_id: str) -> tuple[DecisionCase, ...]:
        return self._repo.get_case_history(case_id)
