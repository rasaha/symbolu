"""Hiring adapter implementing the kernel ``LinkedRecordPort`` over assessments.

Maps a finalized hiring ``Assessment`` onto the kernel's neutral
``LinkedRecordSnapshot`` — projecting only governance-relevant fields (identity,
tenant, version, a neutral finalized status, subject, and a blocked flag). No
evidence or assessment content crosses the boundary.
"""

from __future__ import annotations

from typing import Optional

from decision_governance.ports.linked_record import (
    BLOCKED_METADATA_KEY,
    FINALIZED_STATUS,
    LinkedRecordSnapshot,
)

from ..assessments.status import AssessmentStatus, CompletenessStatus
from ..repositories.assessment_repository import AssessmentRepository


class HiringAssessmentLinkedRecordAdapter:
    """Resolves hiring assessment records into neutral governance snapshots."""

    def __init__(self, assessment_repository: AssessmentRepository) -> None:
        self._assessments = assessment_repository

    def get_record(
        self,
        *,
        tenant_id: str,
        record_type: str,
        record_id: str,
        version: Optional[int] = None,
    ) -> Optional[LinkedRecordSnapshot]:
        try:
            assessment = self._assessments.get_assessment(record_id)
        except Exception:  # noqa: BLE001 - missing record == not linkable
            return None
        status = (FINALIZED_STATUS
                  if assessment.status is AssessmentStatus.FINALIZED_ADVISORY
                  else assessment.status.value)
        metadata = {}
        if assessment.completeness.status is CompletenessStatus.BLOCKED:
            metadata[BLOCKED_METADATA_KEY] = "true"
        return LinkedRecordSnapshot(
            record_type=record_type, record_id=record_id,
            version=assessment.version, tenant_id=assessment.tenant_id,
            status=status, subject_ref=assessment.subject_id,
            created_at=assessment.created_at, metadata=metadata)
