"""Explicit extraction-outcome tests."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.errors import (
    ContentExtractionError,
    EmptyExtractionError,
    EncryptedContentError,
    IngestionError,
    ManualReviewRequiredError,
    TextLimitError,
)
from ugence_ai_hiring.normalization.extraction_status import (
    ExtractionResult,
    ExtractionStatus,
)
from ugence_ai_hiring.normalization.models import EvidenceFormat, RawSubmission

from .conftest import (
    PDF_EMPTY,
    PDF_ENCRYPTED,
    PDF_FLATE,
    PDF_NATIVE,
    SVC,
    docx_bytes,
    text_sub,
)


def _sub(content: bytes, fmt: EvidenceFormat, **kw) -> RawSubmission:
    base = dict(candidate_id="c1", role_id="r1", assessment_item_id="a1",
                declared_format=fmt, uploader=SVC)
    base.update(kw)
    return RawSubmission(content=content, **base)


def _ingest(platform, sub):
    return platform.evidence_ingestion_service.ingest(sub)


# --- PDF outcomes ----------------------------------------------------------
def test_valid_native_text_pdf(platform):
    ing = _ingest(platform, _sub(PDF_NATIVE, EvidenceFormat.PDF))
    assert ing.extraction_result.status is ExtractionStatus.SUCCEEDED
    assert ing.extraction_result.evaluation_eligible
    assert "native text" in ing.normalized_text


def test_empty_pdf_fails_closed(platform):
    with pytest.raises(EmptyExtractionError):
        _ingest(platform, _sub(PDF_EMPTY, EvidenceFormat.PDF))


def test_malformed_pdf_fails_closed(platform):
    with pytest.raises((EmptyExtractionError, IngestionError)):
        _ingest(platform, _sub(b"total garbage not a pdf", EvidenceFormat.PDF))


def test_encrypted_pdf_detected(platform):
    with pytest.raises(EncryptedContentError):
        _ingest(platform, _sub(PDF_ENCRYPTED, EvidenceFormat.PDF))


def test_unsupported_compressed_pdf_routed_to_manual_review(platform):
    with pytest.raises(ManualReviewRequiredError):
        _ingest(platform, _sub(PDF_FLATE, EvidenceFormat.PDF))


# --- DOCX outcomes ---------------------------------------------------------
def test_empty_docx_fails_closed(platform):
    with pytest.raises(EmptyExtractionError):
        _ingest(platform, _sub(docx_bytes(""), EvidenceFormat.DOCX))


def test_malformed_docx_fails_closed(platform):
    with pytest.raises(ContentExtractionError):
        _ingest(platform, _sub(b"not a zip at all", EvidenceFormat.DOCX))


# --- text outcomes ---------------------------------------------------------
def test_invalid_utf_succeeds_with_warnings(platform):
    ing = _ingest(platform, _sub(b"ok \xff\xfe done", EvidenceFormat.TEXT))
    assert ing.extraction_result.status is ExtractionStatus.SUCCEEDED_WITH_WARNINGS
    assert "INVALID_UTF_REPLACED" in ing.extraction_result.warnings


def test_binary_content_labeled_as_text_is_rejected(platform):
    with pytest.raises(TextLimitError):
        _ingest(platform, _sub(b"A\x00\x00\x00\x00B binary payload", EvidenceFormat.TEXT))


# --- ExtractionResult contract --------------------------------------------
def test_extraction_result_success_never_inferred_from_string():
    # a status of EMPTY may never be evaluation_eligible
    with pytest.raises(Exception):
        ExtractionResult(status=ExtractionStatus.EMPTY, format="TEXT",
                         extractor_name="x", characters_extracted=0,
                         evaluation_eligible=True)


def test_extraction_result_failure_requires_code():
    with pytest.raises(Exception):
        ExtractionResult(status=ExtractionStatus.MALFORMED, format="PDF",
                         extractor_name="x")  # no failure_code
