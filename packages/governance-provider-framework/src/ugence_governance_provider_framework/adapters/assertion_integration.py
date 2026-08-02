"""Assertion-governance integration (NOT a forced kernel port).

Assertion governance evaluates whether an assertion is supported by evidence.
That is **not** external execution, and it is not forced through an unrelated
kernel port. Instead this module provides an *application-level* integration that
turns an assertion evaluation into inputs for the assessment / recommendation
workflow, plus an **optional** projection onto the kernel ``LinkedRecordPort``
where that is semantically sufficient.

Optional ``LinkedRecordPort`` projection — what is preserved vs. lost:

* **Preserved:** record identity (type/id/version/tenant), a neutral finalized
  status (``SUPPORTED`` → FINALIZED), a blocked flag (``CONSTRAINED`` →
  blocked), the subject reference, and (as opaque metadata strings) the evidence
  coverage ratio and provider trace id.
* **Lost / not projected:** the structured evidence breakdown — covered vs.
  unsupported elements, omitted qualifiers, and explanation references. Those
  remain on the :class:`AssertionAssessment` for the recommendation to cite; the
  kernel never sees them. ``UNSUPPORTED`` / ``INDETERMINATE`` map to a
  non-finalized status so the kernel fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from decision_governance.api.ports import (
    BLOCKED_METADATA_KEY,
    FINALIZED_STATUS,
    LinkedRecordSnapshot,
)

from ..contracts import AssertionGovernanceRequest, AssertionGovernanceResult
from ..contracts.assertion import AssertionCoverage, AssertionGovernanceProvider


@dataclass(frozen=True)
class AssertionAssessment:
    """A neutral assessment record derived from an assertion evaluation.

    Suitable as a recommendation's cited evidence; richer than a kernel snapshot.
    """

    assertion: str
    assertion_type: str
    coverage: AssertionCoverage
    finalized: bool
    blocked: bool
    evidence_coverage: float
    covered_evidence_refs: tuple[str, ...]
    unsupported_elements: tuple[str, ...]
    explanation_refs: tuple[str, ...]
    provider_trace_id: str
    fingerprint: str


class AssertionAssessmentIntegration:
    """Evaluates an assertion and produces assessment/recommendation inputs."""

    def __init__(self, provider: AssertionGovernanceProvider) -> None:
        self._provider = provider

    def assess(self, request: AssertionGovernanceRequest) -> AssertionAssessment:
        result: AssertionGovernanceResult = self._provider.evaluate(request)
        finalized = result.coverage in (AssertionCoverage.SUPPORTED, AssertionCoverage.CONSTRAINED)
        blocked = result.coverage is AssertionCoverage.CONSTRAINED
        return AssertionAssessment(
            assertion=request.assertion, assertion_type=request.assertion_type,
            coverage=result.coverage, finalized=finalized, blocked=blocked,
            evidence_coverage=result.evidence_coverage,
            covered_evidence_refs=result.covered_evidence_refs,
            unsupported_elements=result.unsupported_elements,
            explanation_refs=result.explanation_refs,
            provider_trace_id=result.provider_trace_id, fingerprint=result.fingerprint)

    @staticmethod
    def to_linked_record_snapshot(
        assessment: AssertionAssessment, *, tenant_id: str, record_type: str,
        record_id: str, subject_ref: str, version: int = 1,
    ) -> LinkedRecordSnapshot:
        metadata: dict[str, str] = {
            "evidence_coverage": f"{assessment.evidence_coverage:.2f}",
            "assertion_trace": assessment.provider_trace_id,
        }
        if assessment.blocked:
            metadata[BLOCKED_METADATA_KEY] = "true"
        return LinkedRecordSnapshot(
            record_type=record_type, record_id=record_id, version=version,
            tenant_id=tenant_id,
            status=FINALIZED_STATUS if assessment.finalized else "PENDING",
            subject_ref=subject_ref, content_hash=assessment.fingerprint, metadata=metadata)


class AssertionLinkedRecordAdapter:
    """Optional ``LinkedRecordPort`` over precomputed assertion snapshots.

    Provided for the case where a finalized assertion is semantically sufficient
    as a linked governance record. Records are registered explicitly; missing
    ids resolve to ``None`` (the kernel fails closed).
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, LinkedRecordSnapshot] = {}

    def register(self, record_id: str, snapshot: LinkedRecordSnapshot) -> None:
        self._snapshots[record_id] = snapshot

    def get_record(self, *, tenant_id: str, record_type: str, record_id: str,
                   version: Optional[int] = None) -> Optional[LinkedRecordSnapshot]:
        return self._snapshots.get(record_id)
