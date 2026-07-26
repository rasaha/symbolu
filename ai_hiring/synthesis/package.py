"""Bounded evidence-synthesis package (H2).

The immutable, versioned output of evidence synthesis: the exact, bounded set of
evidence used to generate a recommendation, with direct-vs-derived provenance and
explicit detection of missing / quarantined / stale / duplicated / conflicting
evidence. Adverse (contradicting) evidence is carried explicitly and is **never**
silently omitted. A deterministic fingerprint pins the package content.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field, model_validator

from decision_governance.api.common import canonical_hash

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError


class EvidenceKind(str, Enum):
    DIRECT = "DIRECT"          # a collected evidence item
    DERIVED = "DERIVED"        # a derived summary over collected evidence


class EvidencePackageItem(DomainModel):
    evidence_ref: str
    evidence_type: str
    content_hash: str
    kind: EvidenceKind = EvidenceKind.DIRECT
    provenance_source: str = ""
    collected_by: str = ""
    adverse: bool = False      # contradicting/adverse — preserved, never omitted

    @model_validator(mode="after")
    def _validate(self) -> "EvidencePackageItem":
        for req in ("evidence_ref", "evidence_type", "content_hash"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"EvidencePackageItem.{req} is required")
        return self


class EvidencePackage(DomainModel):
    synthesis_package_id: str
    tenant_id: str
    application_id: str
    candidate_subject_ref: str
    requisition_id: str
    job_definition_id: str
    job_definition_version: int
    rubric_id: str
    rubric_version: int
    items: tuple[EvidencePackageItem, ...] = ()
    missing_evidence_types: tuple[str, ...] = ()
    quarantined_refs: tuple[str, ...] = ()
    stale_refs: tuple[str, ...] = ()
    duplicate_refs: tuple[str, ...] = ()
    conflicting_evidence_types: tuple[str, ...] = ()
    item_limit: int = 0                       # 0 = unbounded (bounded when > 0)
    minimization_applied: bool = False
    excluded_fields: tuple[str, ...] = ()
    prohibited_attributes_checked: tuple[str, ...] = ()
    policy_refs: tuple[str, ...] = ()
    provenance_id: str = ""
    correlation_id: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    version: int = 1

    @model_validator(mode="after")
    def _validate(self) -> "EvidencePackage":
        for req in ("synthesis_package_id", "tenant_id", "application_id",
                    "candidate_subject_ref", "requisition_id", "job_definition_id", "rubric_id"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"EvidencePackage.{req} is required")
        refs = [i.evidence_ref for i in self.items]
        if len(set(refs)) != len(refs):
            raise DomainValidationError("duplicate evidence_ref within package items")
        return self

    @property
    def evidence_refs(self) -> tuple[str, ...]:
        """The exact evidence set used (deterministic, sorted)."""
        return tuple(sorted(i.evidence_ref for i in self.items))

    @property
    def included_count(self) -> int:
        return len(self.items)

    @property
    def has_adverse_evidence(self) -> bool:
        return any(i.adverse for i in self.items)

    def covered_evidence_types(self, *, include_quarantined: bool = False) -> frozenset[str]:
        q = set(self.quarantined_refs)
        return frozenset(
            i.evidence_type for i in self.items
            if include_quarantined or i.evidence_ref not in q)

    @property
    def fingerprint(self) -> str:
        """Deterministic content hash — identical inputs → identical fingerprint."""
        return canonical_hash({
            "application_id": self.application_id,
            "job_definition_version": self.job_definition_version,
            "rubric_version": self.rubric_version,
            "items": [
                {"ref": i.evidence_ref, "type": i.evidence_type, "hash": i.content_hash,
                 "kind": i.kind.value, "adverse": i.adverse}
                for i in sorted(self.items, key=lambda x: x.evidence_ref)
            ],
            "missing": sorted(self.missing_evidence_types),
            "quarantined": sorted(self.quarantined_refs),
            "stale": sorted(self.stale_refs),
            "duplicate": sorted(self.duplicate_refs),
            "conflicting": sorted(self.conflicting_evidence_types),
            "excluded_fields": sorted(self.excluded_fields),
        })
