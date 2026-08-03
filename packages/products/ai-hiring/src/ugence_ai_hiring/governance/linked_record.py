"""LinkedRecordPort adapter over hiring recommendations (H3).

The DGM ``CaseValidationService`` sees a linked assessment only through the neutral
kernel ``LinkedRecordPort``. This adapter projects an H2 hiring recommendation onto
a ``LinkedRecordSnapshot`` so the kernel can validate the case→assessment link
without ever importing hiring vocabulary. A recommendation that has been generated
and is review-bound projects as FINALIZED; anything not review-bound projects as
PENDING (the kernel fails closed).
"""

from __future__ import annotations

from typing import Optional

from ugence_decision_authority.api.ports import FINALIZED_STATUS, LinkedRecordSnapshot

from ..recommendations.status import RecommendationStatus

_REVIEW_BOUND = frozenset(
    {RecommendationStatus.READY_FOR_HUMAN_REVIEW, RecommendationStatus.ASSERTION_REVIEW_REQUIRED})


class HiringRecommendationLinkedRecordAdapter:
    """Resolve a hiring recommendation id into a neutral linked-record snapshot."""

    def __init__(self, recommendation_repository) -> None:
        self._recs = recommendation_repository

    def get_record(
        self, *, tenant_id: str, record_type: str, record_id: str, version: Optional[int] = None,
    ) -> Optional[LinkedRecordSnapshot]:
        if not self._recs.exists(record_id):
            return None
        rec = self._recs.get(record_id)
        if rec.tenant_id != tenant_id:
            return None
        finalized = rec.status in _REVIEW_BOUND
        return LinkedRecordSnapshot(
            record_type=record_type or "assessment", record_id=record_id, version=version or 1,
            tenant_id=rec.tenant_id,
            status=FINALIZED_STATUS if finalized else "PENDING",
            subject_ref=rec.candidate_subject_ref, content_hash=rec.provenance_id,
            metadata={"hiring_recommendation_status": rec.status.value,
                      "evidence_coverage": f"{rec.confidence:.2f}"})
