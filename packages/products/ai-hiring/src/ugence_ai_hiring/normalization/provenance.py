"""Provenance construction helpers.

Provenance is immutable; these helpers build a new :class:`Provenance` and append
:class:`TransformationStep` entries (returning new instances — nothing mutates).
No stage may destroy provenance, so every transformation is additive.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..common import Clock, IdFactory, new_id, utc_now
from .models import (
    EvidenceFormat,
    Provenance,
    RawSubmission,
    TransformationStep,
)


def build_provenance(
    submission: RawSubmission,
    *,
    evidence_id: str,
    version: int,
    raw_hash: str,
    normalized_hash: str,
    content_length: int,
    parent_version: Optional[int] = None,
    ancestor_version: int = 1,
    created_from: Optional[str] = None,
    id_factory: IdFactory = new_id,
    clock: Clock = utc_now,
) -> Provenance:
    """Assemble the full provenance for one evidence version."""
    return Provenance(
        provenance_id=id_factory("prov"),
        evidence_id=evidence_id,
        version=version,
        candidate_id=submission.candidate_id,
        role_id=submission.role_id,
        assessment_item_id=submission.assessment_item_id,
        tenant_id=submission.tenant_id,
        application_id=submission.application_id,
        original_filename=submission.filename,
        uploader=submission.uploader,
        upload_timestamp=submission.submitted_at,
        original_format=submission.declared_format,
        raw_hash=raw_hash,
        normalized_hash=normalized_hash,
        content_length=content_length,
        source_uri=submission.source_uri,
        parent_version=parent_version,
        ancestor_version=ancestor_version,
        created_from=created_from,
        transformation_history=(),
        created_at=clock(),
    )


def append_step(
    provenance: Provenance,
    *,
    operation: str,
    actor: str,
    detail: str = "",
    timestamp: Optional[datetime] = None,
) -> Provenance:
    """Return a new provenance with an additional transformation step."""
    step = TransformationStep(
        operation=operation,
        actor=actor,
        detail=detail,
        timestamp=timestamp or utc_now(),
    )
    data = provenance.model_dump()
    data["transformation_history"] = provenance.transformation_history + (step,)
    return Provenance(**data)
