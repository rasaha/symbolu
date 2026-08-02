"""The DecisionCase aggregate root — a governed container, not a god object.

A ``DecisionCase`` links subjects, policies, assessments, recommendations, and
decisions **by versioned reference**. It never embeds those records and never
carries execution state. The aggregate is immutable and versioned: every material
change appends a new snapshot (``version`` + a fresh ``case_version_id``) that
points back at the prior snapshot via ``supersedes_case_version_id``. The latest
version never overwrites a prior one.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..base import DomainModel
from ..errors import DomainValidationError
from .authority import AuthorityContext
from .status import CaseStatus, OperatingMode
from .subject import SubjectRef, VersionedRef


class DecisionCase(DomainModel):
    """An immutable snapshot of a governed decision case."""

    decision_case_id: str
    tenant_id: str
    decision_type: str
    subject_refs: tuple[SubjectRef, ...]
    policy_refs: tuple[VersionedRef, ...] = ()
    assessment_refs: tuple[VersionedRef, ...] = ()
    recommendation_refs: tuple[VersionedRef, ...] = ()
    decision_refs: tuple[VersionedRef, ...] = ()
    review_tasks: tuple[str, ...] = ()
    authority_context: Optional[AuthorityContext] = None
    operating_mode: OperatingMode = OperatingMode.DELIBERATIVE
    require_recommendation: bool = False
    status: CaseStatus = CaseStatus.CREATED
    version: int = 1
    case_version_id: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    correlation_id: str = ""
    supersedes_case_version_id: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "DecisionCase":
        for req in ("decision_case_id", "tenant_id", "decision_type", "created_by"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        if not self.subject_refs:
            raise DomainValidationError("a decision case requires at least one subject")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    # --- immutable evolution -------------------------------------------------
    def evolve(self, *, case_version_id: str, **changes: object) -> "DecisionCase":
        """Return a new, higher-version snapshot that supersedes this one.

        The prior snapshot is never mutated; the returned snapshot records its
        predecessor in ``supersedes_case_version_id``.
        """
        data = self.model_dump()
        data.update(changes)
        data.update(
            version=self.version + 1,
            case_version_id=case_version_id,
            supersedes_case_version_id=self.case_version_id or None,
        )
        return DecisionCase(**data)

    def with_added_ref(self, field: str, ref: VersionedRef, *,
                       case_version_id: str, **changes: object) -> "DecisionCase":
        """Append a versioned reference to one of the ref tuples (immutably)."""
        current = getattr(self, field)
        changes[field] = current + (ref,)
        return self.evolve(case_version_id=case_version_id, **changes)
