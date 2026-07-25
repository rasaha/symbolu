"""The assessment workspace — the governed context for supplying observations.

A workspace pins *exact published versions* of the rubric and its capabilities at
creation and never references mutable "latest" versions thereafter. Each rubric
capability becomes one criterion (criterion_id == capability_id in Phase 3B).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from ..ontology.taxonomy import ReasonCode
from ..rubrics.evidence_rules import EvidenceRule
from ..rubrics.uncertainty import UncertaintyRule
from .status import WorkspaceStatus


class CapabilityBinding(DomainModel):
    """A pinned criterion within a workspace (one per rubric capability)."""

    criterion_id: str
    capability_id: str
    capability_version: int
    scoring_scale_id: str
    evidence_rule: EvidenceRule
    allowed_reason_codes: tuple[ReasonCode, ...] = ()
    required: bool = False

    @model_validator(mode="after")
    def _validate(self) -> "CapabilityBinding":
        if self.capability_version < 1:
            raise DomainValidationError("capability_version must be >= 1")
        return self


class AssessmentWorkspace(DomainModel):
    """Immutable, versioned governed context for one subject + rubric version."""

    workspace_id: str
    tenant_id: str
    subject_id: str
    decision_type: str
    rubric_id: str
    rubric_version: int
    capability_bindings: tuple[CapabilityBinding, ...]
    uncertainty_rules: tuple[UncertaintyRule, ...] = ()
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    status: WorkspaceStatus = WorkspaceStatus.CREATED
    version: int = 1
    correlation_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "AssessmentWorkspace":
        for req in ("workspace_id", "tenant_id", "subject_id", "rubric_id",
                    "created_by"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        if not self.capability_bindings:
            raise DomainValidationError("a workspace requires at least one criterion")
        ids = [b.criterion_id for b in self.capability_bindings]
        if len(set(ids)) != len(ids):
            raise DomainValidationError("duplicate criterion in workspace")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    def uncertainty_rule_for(self, criterion_id: str) -> Optional[UncertaintyRule]:
        for r in self.uncertainty_rules:
            if r.capability_id == criterion_id:
                return r
        return None

    def binding_for(self, criterion_id: str) -> Optional[CapabilityBinding]:
        for b in self.capability_bindings:
            if b.criterion_id == criterion_id:
                return b
        return None

    def with_status(self, status: WorkspaceStatus) -> "AssessmentWorkspace":
        """Return a new, higher-versioned workspace snapshot in ``status``."""
        data = self.model_dump()
        data["status"] = status
        data["version"] = self.version + 1
        return AssessmentWorkspace(**data)