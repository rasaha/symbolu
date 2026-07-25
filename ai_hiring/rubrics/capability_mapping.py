"""How a rubric maps a capability into a scored dimension (contract only).

A ``RubricCapability`` binds an ontology capability into a rubric with a weight,
a scoring scale, its per-capability evidence rule, the reason codes it may emit,
and its uncertainty rule. It defines *how the capability will be assessed* — it
holds no score.
"""

from __future__ import annotations

from typing import Optional

from pydantic import model_validator

from ..domain.base import DomainModel
from ..errors import DomainValidationError
from ..ontology.taxonomy import ReasonCode
from .evidence_rules import EvidenceRule
from .uncertainty import UncertaintyRule


class RubricCapability(DomainModel):
    """A capability bound into a rubric with weight, scale, and evidence rule."""

    capability_id: str
    capability_version: int
    weight: float
    scoring_scale_id: str
    evidence_rule: EvidenceRule
    allowed_reason_codes: tuple[ReasonCode, ...] = ()
    uncertainty_rule: Optional[UncertaintyRule] = None

    @model_validator(mode="after")
    def _validate(self) -> "RubricCapability":
        if not self.capability_id.strip():
            raise DomainValidationError("capability_id is required")
        if self.capability_version < 1:
            raise DomainValidationError("capability_version must be >= 1")
        if not (0.0 <= self.weight <= 1.0):
            raise DomainValidationError("weight must be within [0, 1]")
        if not self.scoring_scale_id.strip():
            raise DomainValidationError("scoring_scale_id is required")
        if self.evidence_rule.capability_id != self.capability_id:
            raise DomainValidationError(
                "evidence_rule.capability_id must match this capability")
        if (self.uncertainty_rule is not None
                and self.uncertainty_rule.capability_id != self.capability_id):
            raise DomainValidationError(
                "uncertainty_rule.capability_id must match this capability")
        return self
