"""Criterion-specific evidence bindings and exclusions (immutable).

A binding attaches an eligible evidence artifact to a specific rubric criterion
(capability) with a *declared* evidence type and a deterministic admissibility
outcome. The evidence type is supplied by an authorized source or a deterministic
rule — it is never inferred from content. Evidence admissible for one criterion
is not automatically admissible for another.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from ..ontology.taxonomy import EvidenceType, ReasonCode
from ..rubrics.evidence_rules import EvidenceAdmissibility
from .status import BindingProvenance


class EvidenceBinding(DomainModel):
    """An admissible evidence artifact bound to one criterion."""

    binding_id: str
    workspace_id: str
    criterion_id: str
    capability_id: str
    capability_version: int
    evidence_id: str
    evidence_version: int
    evidence_type: EvidenceType
    admissibility_outcome: EvidenceAdmissibility
    admissibility_reason_codes: tuple[ReasonCode, ...] = ()
    policy_reference: str = ""
    provenance: BindingProvenance = BindingProvenance.MANUAL_AUTHORIZED
    bound_by: str
    bound_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate(self) -> "EvidenceBinding":
        for req in ("binding_id", "workspace_id", "criterion_id", "capability_id",
                    "evidence_id", "bound_by"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        # An eligible binding must be ADMISSIBLE; anything else is an exclusion.
        if self.admissibility_outcome is not EvidenceAdmissibility.ADMISSIBLE:
            raise DomainValidationError(
                "EvidenceBinding requires an ADMISSIBLE outcome; use "
                "ExcludedEvidenceRecord for non-admissible evidence")
        return self


class ExcludedEvidenceRecord(DomainModel):
    """A non-admissible evidence artifact, recorded (never silently dropped)."""

    record_id: str
    workspace_id: str
    criterion_id: str
    capability_id: str
    capability_version: int
    evidence_id: str
    evidence_type: EvidenceType
    admissibility_outcome: EvidenceAdmissibility
    reason_codes: tuple[ReasonCode, ...] = ()
    excluded_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate(self) -> "ExcludedEvidenceRecord":
        if self.admissibility_outcome is EvidenceAdmissibility.ADMISSIBLE:
            raise DomainValidationError(
                "ExcludedEvidenceRecord must carry a non-admissible outcome")
        return self