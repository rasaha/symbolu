"""Context-aware duplicate classification.

A matching hash never automatically means "the same evidence record". Identity
includes the full context (tenant, candidate, application, role, assessment,
uploader), so the same bytes in a different context are a *different* artifact
and ownership/provenance is never merged. Cross-tenant matches are never
disclosed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DuplicateClassification(str, Enum):
    EXACT_BINARY_DUPLICATE = "EXACT_BINARY_DUPLICATE"
    NORMALIZED_CONTENT_DUPLICATE = "NORMALIZED_CONTENT_DUPLICATE"
    NEW_VERSION = "NEW_VERSION"
    CROSS_CONTEXT_REUSE = "CROSS_CONTEXT_REUSE"
    CROSS_CANDIDATE_DUPLICATE = "CROSS_CANDIDATE_DUPLICATE"
    CROSS_TENANT_DUPLICATE = "CROSS_TENANT_DUPLICATE"
    NOT_DUPLICATE = "NOT_DUPLICATE"


@dataclass(frozen=True)
class EvidenceContext:
    tenant_id: str = ""
    candidate_id: str = ""
    application_id: str = ""
    role_id: str = ""
    assessment_id: str = ""
    uploader: str = ""

    def same_stage(self, other: "EvidenceContext") -> bool:
        return (
            self.tenant_id == other.tenant_id
            and self.candidate_id == other.candidate_id
            and self.assessment_id == other.assessment_id
        )


@dataclass(frozen=True)
class DuplicateMatch:
    """A candidate prior artifact to compare against."""

    context: EvidenceContext
    raw_hash: str
    normalized_hash: str
    evidence_id: str


@dataclass(frozen=True)
class DuplicateDecision:
    classification: DuplicateClassification
    matched_evidence_id: Optional[str] = None
    # Whether the caller should be told a match exists (never across tenants).
    disclose: bool = True
    block: bool = False  # block ingestion (idempotency) vs. allow a new record


class DuplicatePolicy:
    """Classifies a new submission against an optional prior match."""

    def classify(
        self,
        *,
        new_context: EvidenceContext,
        new_raw_hash: str,
        new_normalized_hash: str,
        is_revision: bool,
        match: Optional[DuplicateMatch],
    ) -> DuplicateDecision:
        if is_revision:
            return DuplicateDecision(DuplicateClassification.NEW_VERSION, block=False)

        if match is None:
            return DuplicateDecision(DuplicateClassification.NOT_DUPLICATE, block=False)

        # Cross-tenant: never disclose that a duplicate exists elsewhere.
        if match.context.tenant_id != new_context.tenant_id:
            return DuplicateDecision(
                DuplicateClassification.CROSS_TENANT_DUPLICATE,
                matched_evidence_id=None, disclose=False, block=False,
            )

        # Same tenant, different candidate: never merge ownership.
        if match.context.candidate_id != new_context.candidate_id:
            return DuplicateDecision(
                DuplicateClassification.CROSS_CANDIDATE_DUPLICATE,
                matched_evidence_id=match.evidence_id, disclose=True, block=False,
            )

        # Same candidate, different assessment: intentional reuse.
        if match.context.assessment_id != new_context.assessment_id:
            return DuplicateDecision(
                DuplicateClassification.CROSS_CONTEXT_REUSE,
                matched_evidence_id=match.evidence_id, disclose=True, block=False,
            )

        # Same stage: exact bytes → block (idempotency); normalized-only → allow new raw.
        if match.raw_hash == new_raw_hash:
            return DuplicateDecision(
                DuplicateClassification.EXACT_BINARY_DUPLICATE,
                matched_evidence_id=match.evidence_id, disclose=True, block=True,
            )
        if match.normalized_hash == new_normalized_hash:
            return DuplicateDecision(
                DuplicateClassification.NORMALIZED_CONTENT_DUPLICATE,
                matched_evidence_id=match.evidence_id, disclose=True, block=False,
            )
        return DuplicateDecision(DuplicateClassification.NOT_DUPLICATE, block=False)


DEFAULT_DUPLICATE_POLICY = DuplicatePolicy()
