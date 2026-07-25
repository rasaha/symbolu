"""Procurement adapter implementing the kernel ``LinkedRecordPort``.

Maps a finalized procurement :class:`PolicyAssessment` onto the kernel's neutral
:class:`LinkedRecordSnapshot`, projecting only governance-relevant fields
(identity, tenant, version, a neutral finalized status, subject, blocked flag).
No purchase-request or assessment content crosses the boundary — this is the
exact same seam the hiring domain uses, exercised by a structurally different
domain record.
"""

from __future__ import annotations

from typing import Optional

from decision_governance.ports.linked_record import (
    BLOCKED_METADATA_KEY,
    FINALIZED_STATUS,
    LinkedRecordSnapshot,
)

from ..policies.assessment import (
    AssessmentStatus,
    InMemoryProcurementAssessmentRepository,
)


class ProcurementAssessmentLinkedRecordAdapter:
    """Resolves procurement policy-assessment records into neutral snapshots."""

    def __init__(self, assessment_repository: InMemoryProcurementAssessmentRepository) -> None:
        self._assessments = assessment_repository

    def get_record(
        self,
        *,
        tenant_id: str,
        record_type: str,
        record_id: str,
        version: Optional[int] = None,
    ) -> Optional[LinkedRecordSnapshot]:
        assessment = self._assessments.get(record_id)
        if assessment is None:
            return None
        status = (FINALIZED_STATUS
                  if assessment.status is AssessmentStatus.FINALIZED
                  else assessment.status.value)
        metadata = {}
        if assessment.blocked:
            metadata[BLOCKED_METADATA_KEY] = "true"
        return LinkedRecordSnapshot(
            record_type=record_type, record_id=record_id,
            version=assessment.version, tenant_id=assessment.tenant_id,
            status=status, subject_ref=assessment.subject_ref,
            created_at=assessment.created_at, metadata=metadata)
