"""Fail-closed evaluation-eligibility policy.

The single authority that decides whether normalized evidence may become
evaluation-eligible for a *future* evaluation engine. It returns a typed result
with reason codes, never a bare boolean, and defaults to **ineligible** — a
future evaluation service must call this and must never bypass it by reading a
repository directly.

No scoring, extraction-of-meaning, or inference occurs here; this only checks
the boundary conditions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .extraction_status import ELIGIBLE_STATUSES, ExtractionStatus


class EligibilityReason(str, Enum):
    EXTRACTION_EMPTY = "EXTRACTION_EMPTY"
    FORMAT_UNSUPPORTED = "FORMAT_UNSUPPORTED"
    DOCUMENT_MALFORMED = "DOCUMENT_MALFORMED"
    DOCUMENT_ENCRYPTED = "DOCUMENT_ENCRYPTED"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    PROVENANCE_INCOMPLETE = "PROVENANCE_INCOMPLETE"
    HASH_MISMATCH = "HASH_MISMATCH"
    LINEAGE_INVALID = "LINEAGE_INVALID"
    QUARANTINED_CONTENT = "QUARANTINED_CONTENT"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    APPLICATION_MISMATCH = "APPLICATION_MISMATCH"
    ACCESS_DENIED = "ACCESS_DENIED"


_STATUS_REASON = {
    ExtractionStatus.EMPTY: EligibilityReason.EXTRACTION_EMPTY,
    ExtractionStatus.UNSUPPORTED: EligibilityReason.FORMAT_UNSUPPORTED,
    ExtractionStatus.MALFORMED: EligibilityReason.DOCUMENT_MALFORMED,
    ExtractionStatus.ENCRYPTED: EligibilityReason.DOCUMENT_ENCRYPTED,
    ExtractionStatus.RESOURCE_LIMIT_EXCEEDED: EligibilityReason.RESOURCE_LIMIT_EXCEEDED,
    ExtractionStatus.MANUAL_REVIEW_REQUIRED: EligibilityReason.MANUAL_REVIEW_REQUIRED,
}


@dataclass(frozen=True)
class EligibilityInput:
    """The facts the policy evaluates. Booleans default to the unsafe side."""

    extraction_status: ExtractionStatus
    normalized_non_empty: bool = False
    provenance_complete: bool = False
    hashes_valid: bool = False
    lineage_valid: bool = False
    not_quarantined: bool = True
    authorized: bool = False
    tenant_consistent: bool = False
    application_consistent: bool = True


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    reasons: tuple[EligibilityReason, ...] = field(default_factory=tuple)

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return tuple(r.value for r in self.reasons)


class EvaluationEligibilityPolicy:
    """Fail-closed: eligible only when *every* condition holds."""

    def evaluate(self, facts: EligibilityInput) -> EligibilityResult:
        reasons: list[EligibilityReason] = []

        if facts.extraction_status not in ELIGIBLE_STATUSES:
            reasons.append(_STATUS_REASON.get(
                facts.extraction_status, EligibilityReason.DOCUMENT_MALFORMED))
        if not facts.normalized_non_empty:
            _add(reasons, EligibilityReason.EXTRACTION_EMPTY)
        if not facts.provenance_complete:
            reasons.append(EligibilityReason.PROVENANCE_INCOMPLETE)
        if not facts.hashes_valid:
            reasons.append(EligibilityReason.HASH_MISMATCH)
        if not facts.lineage_valid:
            reasons.append(EligibilityReason.LINEAGE_INVALID)
        if not facts.not_quarantined:
            reasons.append(EligibilityReason.QUARANTINED_CONTENT)
        if not facts.tenant_consistent:
            reasons.append(EligibilityReason.TENANT_MISMATCH)
        if not facts.application_consistent:
            reasons.append(EligibilityReason.APPLICATION_MISMATCH)
        if not facts.authorized:
            reasons.append(EligibilityReason.ACCESS_DENIED)

        return EligibilityResult(eligible=not reasons, reasons=tuple(reasons))


def _add(reasons: list, reason) -> None:
    if reason not in reasons:
        reasons.append(reason)


DEFAULT_ELIGIBILITY_POLICY = EvaluationEligibilityPolicy()
