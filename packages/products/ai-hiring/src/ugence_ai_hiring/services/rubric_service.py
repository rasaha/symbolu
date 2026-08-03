"""Rubric service — authoring, approval workflow, and publication.

Drives the Author → Reviewer → Approver → Publisher lifecycle with append-only
snapshots, enforces segregation of duties (approver ≠ author), and requires a
valid contract before publication. Only PUBLISHED rubrics may later be used for
evaluation. No candidate data or scoring is involved.
"""

from __future__ import annotations

from typing import Optional

from ..common import new_id
from ..domain.enums import ActorType, AuditEventType
from ..errors import ApprovalError, RubricValidationError
from ..rubrics.approval import (
    ApprovalAction,
    ApprovalRecord,
    ApprovalRole,
    RubricStatus,
    role_for_target,
    validate_transition,
)
from ..rubrics.rubric import Rubric
from ..repositories.rubric_repository import RubricRepository
from .audit_service import AuditService
from .rubric_validation_service import RubricValidationService


class RubricService:
    def __init__(
        self,
        repository: RubricRepository,
        validation_service: RubricValidationService,
        audit_service: AuditService,
    ) -> None:
        self._repo = repository
        self._validation = validation_service
        self._audit = audit_service

    # --- helpers -----------------------------------------------------------
    @staticmethod
    def _author_of(rubric: Rubric) -> Optional[str]:
        for record in rubric.approvals:
            if record.action is ApprovalAction.CREATE:
                return record.actor_id
        return None

    def _audit_evt(self, event_type, rubric, actor_id, corr, **payload):
        self._audit.record(
            event_type=event_type, entity_type="rubric", entity_id=rubric.rubric_id,
            actor_type=ActorType.HUMAN, actor_id=actor_id,
            correlation_id=corr or new_id("corr"), new_state=rubric.status.value,
            payload={"version": rubric.version, **payload})

    def _transition(self, rubric_id, target, actor_id, role, action, corr, **audit_kw):
        current = self._repo.current(rubric_id)
        validate_transition(current.status, target)
        record = ApprovalRecord(actor_id=actor_id, role=role, action=action)
        updated = current.with_status(target, approval=record)
        self._repo.append(updated)
        return updated

    # --- lifecycle ---------------------------------------------------------
    def create(self, rubric: Rubric, *, author_id: str,
               correlation_id: Optional[str] = None) -> Rubric:
        draft = Rubric(**{**rubric.model_dump(), "status": RubricStatus.DRAFT,
                          "approvals": (ApprovalRecord(
                              actor_id=author_id, role=ApprovalRole.AUTHOR,
                              action=ApprovalAction.CREATE).model_dump(),)})
        self._repo.append(draft)
        self._audit_evt(AuditEventType.RUBRIC_CREATED, draft, author_id, correlation_id)
        return draft

    def submit(self, rubric_id: str, *, author_id: str,
               correlation_id: Optional[str] = None) -> Rubric:
        updated = self._transition(rubric_id, RubricStatus.UNDER_REVIEW, author_id,
                                   ApprovalRole.AUTHOR, ApprovalAction.SUBMIT, correlation_id)
        self._audit_evt(AuditEventType.RUBRIC_SUBMITTED, updated, author_id, correlation_id)
        return updated

    def approve(self, rubric_id: str, *, approver_id: str,
                correlation_id: Optional[str] = None) -> Rubric:
        current = self._repo.current(rubric_id)
        author = self._author_of(current)
        if author is not None and approver_id == author:
            raise ApprovalError("segregation of duties: approver must differ from author")
        updated = self._transition(rubric_id, RubricStatus.APPROVED, approver_id,
                                   ApprovalRole.APPROVER, ApprovalAction.APPROVE, correlation_id)
        self._audit_evt(AuditEventType.RUBRIC_APPROVED, updated, approver_id, correlation_id)
        return updated

    def reject(self, rubric_id: str, *, reviewer_id: str, note: str = "",
               correlation_id: Optional[str] = None) -> Rubric:
        current = self._repo.current(rubric_id)
        validate_transition(current.status, RubricStatus.DRAFT)
        record = ApprovalRecord(actor_id=reviewer_id, role=ApprovalRole.REVIEWER,
                                action=ApprovalAction.REJECT, note=note)
        updated = current.with_status(RubricStatus.DRAFT, approval=record)
        self._repo.append(updated)
        self._audit_evt(AuditEventType.RUBRIC_REJECTED, updated, reviewer_id, correlation_id)
        return updated

    def publish(self, rubric_id: str, *, publisher_id: str,
                correlation_id: Optional[str] = None) -> Rubric:
        corr = correlation_id or new_id("corr")
        current = self._repo.current(rubric_id)
        validate_transition(current.status, RubricStatus.PUBLISHED)
        author = self._author_of(current)
        if author is not None and publisher_id == author:
            raise ApprovalError("segregation of duties: publisher must differ from author")
        result = self._validation.validate(current)
        if not result.valid:
            self._audit.record(
                event_type=AuditEventType.RUBRIC_VALIDATION_FAILED, entity_type="rubric",
                entity_id=rubric_id, actor_type=ActorType.HUMAN, actor_id=publisher_id,
                correlation_id=corr, payload={"issues": list(result.issue_codes)})
            raise RubricValidationError(
                f"rubric '{rubric_id}' failed validation: {result.issue_codes}")
        record = ApprovalRecord(actor_id=publisher_id, role=ApprovalRole.PUBLISHER,
                                action=ApprovalAction.PUBLISH)
        published = current.with_status(RubricStatus.PUBLISHED, approval=record)
        self._repo.append(published)
        self._audit_evt(AuditEventType.RUBRIC_PUBLISHED, published, publisher_id, corr)
        return published

    def deprecate(self, rubric_id: str, *, publisher_id: str,
                  correlation_id: Optional[str] = None) -> Rubric:
        updated = self._transition(rubric_id, RubricStatus.DEPRECATED, publisher_id,
                                   ApprovalRole.PUBLISHER, ApprovalAction.DEPRECATE,
                                   correlation_id)
        self._audit_evt(AuditEventType.RUBRIC_DEPRECATED, updated, publisher_id, correlation_id)
        return updated

    def retire(self, rubric_id: str, *, publisher_id: str,
               correlation_id: Optional[str] = None) -> Rubric:
        updated = self._transition(rubric_id, RubricStatus.RETIRED, publisher_id,
                                   ApprovalRole.PUBLISHER, ApprovalAction.RETIRE,
                                   correlation_id)
        self._audit_evt(AuditEventType.RUBRIC_RETIRED, updated, publisher_id, correlation_id)
        return updated

    def create_revision(self, rubric_id: str, revised: Rubric, *, author_id: str,
                        correlation_id: Optional[str] = None) -> Rubric:
        """Create a new DRAFT version from an existing (typically published) rubric."""
        current = self._repo.current(rubric_id)
        new_draft = current.as_new_version(
            capabilities=revised.capabilities,
            default_scoring_scale_id=revised.default_scoring_scale_id,
            allowed_reason_codes=revised.allowed_reason_codes,
            custom_scales=revised.custom_scales,
            recognized_conflict_severities=revised.recognized_conflict_severities,
        )
        new_draft = Rubric(**{**new_draft.model_dump(), "approvals": (ApprovalRecord(
            actor_id=author_id, role=ApprovalRole.AUTHOR,
            action=ApprovalAction.CREATE).model_dump(),)})
        self._repo.append(new_draft)
        self._audit_evt(AuditEventType.RUBRIC_REVISION_CREATED, new_draft, author_id,
                        correlation_id)
        return new_draft

    # --- reads -------------------------------------------------------------
    def validate(self, rubric: Rubric):
        return self._validation.validate(rubric)

    def get_current(self, rubric_id: str) -> Rubric:
        return self._repo.current(rubric_id)

    def get_published(self, rubric_id: str) -> Optional[Rubric]:
        return self._repo.published(rubric_id)

    def history(self, rubric_id: str) -> tuple[Rubric, ...]:
        return self._repo.history(rubric_id)
