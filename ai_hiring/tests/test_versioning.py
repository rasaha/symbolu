"""Immutable evidence versioning tests."""

from __future__ import annotations

import pytest

from ai_hiring.errors import RecordNotFoundError, VersionConflictError
from ai_hiring.normalization.models import EvidenceFormat, RawSubmission

SERVICE_ID = "svc-ats"


def _sub(text: str, **kw) -> RawSubmission:
    base = dict(
        candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.TEXT, uploader=SERVICE_ID,
    )
    base.update(kw)
    return RawSubmission.from_text(text, **base)


def test_revision_creates_new_version(platform):
    svc = platform.evidence_ingestion_service
    v1 = svc.ingest(_sub("draft one"))
    v2 = svc.ingest(_sub("draft two"), parent_evidence_id=v1.evidence_id)
    assert v2.evidence_id == v1.evidence_id
    assert (v1.version, v2.version) == (1, 2)


def test_parent_linkage_recorded(platform):
    svc = platform.evidence_ingestion_service
    v1 = svc.ingest(_sub("draft one"))
    v2 = svc.ingest(_sub("draft two"), parent_evidence_id=v1.evidence_id)
    assert v2.provenance.parent_version == 1
    assert v2.provenance.created_from == v1.evidence_id
    assert v2.provenance.ancestor_version == 1


def test_no_overwrite_of_prior_version(platform):
    svc = platform.evidence_ingestion_service
    v1 = svc.ingest(_sub("original"))
    svc.ingest(_sub("revised"), parent_evidence_id=v1.evidence_id)
    # the original version is still retrievable, unchanged
    stored_v1 = platform.evidence_repo.get_version(v1.evidence_id, 1)
    assert stored_v1.content_hash == v1.normalized_evidence.content_hash
    # latest is version 2
    assert platform.evidence_repo.get(v1.evidence_id).version == 2


def test_immutable_records_cannot_be_re_added(platform):
    svc = platform.evidence_ingestion_service
    v1 = svc.ingest(_sub("original"))
    # re-adding the same provenance version is a conflict (immutability)
    with pytest.raises(VersionConflictError):
        platform.provenance_repo.add(v1.provenance)


def test_version_graph_grows(platform):
    svc = platform.evidence_ingestion_service
    v1 = svc.ingest(_sub("one"))
    svc.ingest(_sub("two"), parent_evidence_id=v1.evidence_id)
    svc.ingest(_sub("three"), parent_evidence_id=v1.evidence_id)
    ancestry = platform.provenance_service.ancestry(v1.evidence_id)
    assert ancestry == (1, 2, 3)


def test_revision_of_unknown_evidence_fails(platform):
    with pytest.raises(RecordNotFoundError):
        platform.evidence_ingestion_service.ingest(
            _sub("x"), parent_evidence_id="ev-nope"
        )


def test_normalized_evidence_is_immutable(platform):
    from pydantic import ValidationError

    v1 = platform.evidence_ingestion_service.ingest(_sub("frozen"))
    with pytest.raises(ValidationError):
        v1.normalized_evidence.version = 99  # frozen
