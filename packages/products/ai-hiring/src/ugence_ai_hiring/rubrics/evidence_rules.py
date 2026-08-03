"""Evidence admissibility rules and the missing-evidence vocabulary.

Defines which evidence a capability accepts/requires/forbids and a deterministic
admissibility policy over *descriptors* (not candidate data — descriptors are
hypothetical evidence shapes used to test the contract). No scoring occurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from pydantic import model_validator

from ..domain.base import DomainModel
from ..errors import DomainValidationError
from ..ontology.taxonomy import EvidenceType


class EvidenceAdmissibility(str, Enum):
    ADMISSIBLE = "ADMISSIBLE"
    INSUFFICIENT = "INSUFFICIENT"
    PROHIBITED = "PROHIBITED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class MissingEvidenceStatus(str, Enum):
    """Explicit representation of *why* evidence is absent — never inferred."""

    NOT_SUBMITTED = "NOT_SUBMITTED"
    NOT_REQUIRED = "NOT_REQUIRED"
    REDACTED = "REDACTED"
    QUARANTINED = "QUARANTINED"
    UNAVAILABLE = "UNAVAILABLE"
    INSUFFICIENT = "INSUFFICIENT"


class EvidenceRule(DomainModel):
    """The admissibility rule for one capability."""

    capability_id: str
    allowed_types: tuple[EvidenceType, ...] = ()
    required_types: tuple[EvidenceType, ...] = ()
    prohibited_types: tuple[EvidenceType, ...] = ()
    minimum_count: int = 0
    maximum_count: Optional[int] = None
    freshness_days: Optional[int] = None

    @model_validator(mode="after")
    def _validate(self) -> "EvidenceRule":
        if self.minimum_count < 0:
            raise DomainValidationError("minimum_count must be >= 0")
        if self.maximum_count is not None and self.maximum_count < self.minimum_count:
            raise DomainValidationError("maximum_count must be >= minimum_count")
        allowed = set(self.allowed_types)
        if self.allowed_types:
            missing = [t for t in self.required_types if t not in allowed]
            if missing:
                raise DomainValidationError(f"required types not allowed: {missing}")
        overlap = set(self.prohibited_types) & (allowed | set(self.required_types))
        if overlap:
            raise DomainValidationError(f"types both allowed and prohibited: {overlap}")
        if self.freshness_days is not None and self.freshness_days < 0:
            raise DomainValidationError("freshness_days must be >= 0")
        return self


@dataclass(frozen=True)
class EvidenceDescriptor:
    """A hypothetical evidence item (type + optional age). Not candidate data."""

    evidence_type: EvidenceType
    age_days: int = 0


class AdmissibilityPolicy:
    """Deterministic admissibility classification. No scoring."""

    def classify_item(
        self, rule: EvidenceRule, descriptor: EvidenceDescriptor
    ) -> EvidenceAdmissibility:
        if descriptor.evidence_type in rule.prohibited_types:
            return EvidenceAdmissibility.PROHIBITED
        if rule.allowed_types and descriptor.evidence_type not in rule.allowed_types:
            return EvidenceAdmissibility.UNKNOWN
        if (rule.freshness_days is not None
                and descriptor.age_days > rule.freshness_days):
            return EvidenceAdmissibility.STALE
        return EvidenceAdmissibility.ADMISSIBLE

    def classify_set(
        self, rule: EvidenceRule, descriptors: tuple[EvidenceDescriptor, ...]
    ) -> EvidenceAdmissibility:
        """Overall admissibility of a set against a rule (deterministic order)."""
        per_item = [self.classify_item(rule, d) for d in descriptors]
        if EvidenceAdmissibility.PROHIBITED in per_item:
            return EvidenceAdmissibility.PROHIBITED
        admissible = sum(1 for a in per_item if a is EvidenceAdmissibility.ADMISSIBLE)
        if admissible < rule.minimum_count:
            return EvidenceAdmissibility.INSUFFICIENT
        if per_item and all(a is EvidenceAdmissibility.STALE for a in per_item):
            return EvidenceAdmissibility.STALE
        if any(a is EvidenceAdmissibility.UNKNOWN for a in per_item) and admissible == 0:
            return EvidenceAdmissibility.UNKNOWN
        return EvidenceAdmissibility.ADMISSIBLE


DEFAULT_ADMISSIBILITY_POLICY = AdmissibilityPolicy()
