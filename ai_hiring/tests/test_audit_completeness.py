"""Audit-completeness tests for success and failure outcomes."""

from __future__ import annotations

import pytest

from ai_hiring.domain.enums import AuditEventType as E
from ai_hiring.errors import ContentExtractionError, EmptyExtractionError
from ai_hiring.normalization.models import EvidenceFormat, RawSubmission

from .conftest import PDF_EMPTY, SVC, text_sub

REQUIRED_SUCCESS = [
    E.EVIDENCE_UPLOAD_RECEIVED, E.EVIDENCE_INTEGRITY_VALIDATED,
    E.EVIDENCE_PROVENANCE_CAPTURED, E.EVIDENCE_CONTENT_HASHED,
    E.EVIDENCE_CONTENT_EXTRACTED, E.EVIDENCE_NORMALIZED,
    E.EVIDENCE_PII_QUARANTINED, E.EVIDENCE_CHUNK_CREATED,
    E.EVIDENCE_VERSION_CREATED, E.EVIDENCE_INDEXED,
]


def test_success_has_all_stage_events_in_order(platform):
    ing = platform.evidence_ingestion_service.ingest(
        text_sub("audit body"), correlation_id="corr-s")
    # the evidence-keyed pipeline stream is exactly the 10 stage events (Phase-2 compatible)
    types = [e.event_type for e in platform.audit_service.history(ing.evidence_id)]
    assert types == REQUIRED_SUCCESS


def test_success_lifecycle_completes(platform):
    ing = platform.evidence_ingestion_service.ingest(
        text_sub("audit body"), correlation_id="corr-s")
    life = [e.event_type for e in platform.audit_service.history(ing.ingestion_id)]
    assert E.EVIDENCE_INGESTION_RECEIVED == life[0]
    assert E.EVIDENCE_EXTRACTION_SUCCEEDED in life
    assert E.EVIDENCE_RECONSTRUCTION_VALIDATED in life
    assert E.EVIDENCE_LINEAGE_VALIDATED in life
    assert E.EVIDENCE_INGESTION_COMPLETED in life


def test_success_correlation_contains_indexed_and_completed(platform):
    platform.evidence_ingestion_service.ingest(text_sub("body"), correlation_id="corr-s")
    chain = {e.event_type for e in platform.audit_service.by_correlation("corr-s")}
    assert E.EVIDENCE_INDEXED in chain
    assert E.EVIDENCE_INGESTION_COMPLETED in chain


def test_failed_empty_extraction_audit_sequence(platform):
    sub = RawSubmission(content=PDF_EMPTY, candidate_id="c1", role_id="r1",
                        assessment_item_id="a1", declared_format=EvidenceFormat.PDF,
                        uploader=SVC)
    with pytest.raises(EmptyExtractionError):
        platform.evidence_ingestion_service.ingest(sub, correlation_id="corr-f")
    chain = [e.event_type for e in platform.audit_service.by_correlation("corr-f")]
    for required in (E.EVIDENCE_UPLOAD_RECEIVED, E.EVIDENCE_INTEGRITY_VALIDATED,
                     E.EVIDENCE_PROVENANCE_CAPTURED, E.EVIDENCE_CONTENT_HASHED,
                     E.EVIDENCE_EXTRACTION_EMPTY, E.EVIDENCE_ELIGIBILITY_BLOCKED,
                     E.EVIDENCE_INGESTION_FAILED):
        assert required in chain, required
    # must NOT look completed / indexed
    assert E.EVIDENCE_INDEXED not in chain
    assert E.EVIDENCE_INGESTION_COMPLETED not in chain


def test_failed_malformed_extraction_audit_sequence(platform):
    sub = RawSubmission(content=b"{bad json", candidate_id="c1", role_id="r1",
                        assessment_item_id="a1", declared_format=EvidenceFormat.JSON,
                        uploader=SVC)
    with pytest.raises(ContentExtractionError):
        platform.evidence_ingestion_service.ingest(sub, correlation_id="corr-m")
    chain = [e.event_type for e in platform.audit_service.by_correlation("corr-m")]
    assert E.EVIDENCE_EXTRACTION_MALFORMED in chain
    assert E.EVIDENCE_ELIGIBILITY_BLOCKED in chain
    assert E.EVIDENCE_INGESTION_FAILED in chain
    assert E.EVIDENCE_INDEXED not in chain
    assert E.EVIDENCE_INGESTION_COMPLETED not in chain


def test_correlation_ids_coherent(platform):
    ing = platform.evidence_ingestion_service.ingest(
        text_sub("body"), correlation_id="corr-x")
    all_evt = platform.audit_service.by_correlation("corr-x")
    assert all_evt
    assert all(e.correlation_id == "corr-x" for e in all_evt)


def test_ingestion_completed_state_recorded(platform):
    ing = platform.evidence_ingestion_service.ingest(text_sub("body"))
    from ai_hiring.normalization.models import IngestionState

    assert ing.ingestion_state is IngestionState.COMPLETED
