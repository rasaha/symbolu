"""Evidence ingestion tests: multi-format, duplicates, encoding, size, audit."""

from __future__ import annotations

import io
import zipfile

import pytest

from ai_hiring.domain.enums import AuditEventType
from ai_hiring.errors import (
    ContentExtractionError,
    DuplicateEvidenceError,
    IntegrityValidationError,
)
from ai_hiring.normalization.chunking import reconstruct
from ai_hiring.normalization.models import EvidenceFormat, RawSubmission
from ai_hiring.normalization.pipeline import run_pipeline

SERVICE_ID = "svc-ats"


def _text_submission(text: str, **kw) -> RawSubmission:
    base = dict(
        candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.TEXT, uploader=SERVICE_ID,
        filename="note.txt", assessment_type="WORK_SAMPLE",
    )
    base.update(kw)
    return RawSubmission.from_text(text, **base)


def _make_docx(text: str) -> bytes:
    doc = (
        '<?xml version="1.0"?><w:document xmlns:w="x"><w:body>'
        + "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in text.split("\n"))
        + "</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", doc)
    return buf.getvalue()


# --- valid ingestion, multiple formats ------------------------------------
def test_valid_text_upload(platform):
    ing = platform.evidence_ingestion_service.ingest(_text_submission("Hello world"))
    assert ing.version == 1
    assert ing.normalized_evidence.job_relevant is True
    assert ing.normalized_evidence.content_hash  # normalized hash present
    assert reconstruct(ing.chunks) == "Hello world"


def test_valid_docx_upload(platform):
    sub = RawSubmission(
        candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.DOCX, uploader=SERVICE_ID,
        filename="cv.docx", content=_make_docx("First line\nSecond line"),
    )
    ing = platform.evidence_ingestion_service.ingest(sub)
    assert "First line" in ing.normalized_text
    assert "Second line" in ing.normalized_text


def test_valid_json_structured_upload(platform):
    sub = RawSubmission(
        candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.JSON, uploader=SERVICE_ID, filename="resp.json",
        content=b'{"answer": "used a hash map", "complexity": "O(n)"}',
    )
    ing = platform.evidence_ingestion_service.ingest(sub)
    assert "answer=used a hash map" in ing.normalized_text


@pytest.mark.parametrize(
    "fmt",
    [
        EvidenceFormat.TEXT, EvidenceFormat.MARKDOWN, EvidenceFormat.SOURCE_CODE,
        EvidenceFormat.INTERVIEW_TRANSCRIPT, EvidenceFormat.WORK_SAMPLE,
        EvidenceFormat.PORTFOLIO_ARTIFACT,
    ],
)
def test_all_text_formats_ingest(platform, fmt):
    sub = RawSubmission.from_text(
        "content body", candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=fmt, uploader=SERVICE_ID,
    )
    ing = platform.evidence_ingestion_service.ingest(sub)
    assert ing.normalized_evidence.format == fmt.value


# --- duplicates ------------------------------------------------------------
def test_duplicate_upload_is_detected(platform):
    platform.evidence_ingestion_service.ingest(_text_submission("same content"))
    with pytest.raises(DuplicateEvidenceError):
        platform.evidence_ingestion_service.ingest(_text_submission("same content"))
    # the duplicate attempt is audited
    dups = [
        e for e in platform.audit_repo.all()
        if e.event_type is AuditEventType.EVIDENCE_DUPLICATE_DETECTED
    ]
    assert dups


def test_duplicate_allowed_when_opted_in(platform):
    platform.evidence_ingestion_service.ingest(_text_submission("dup ok"))
    ing2 = platform.evidence_ingestion_service.ingest(
        _text_submission("dup ok"), allow_duplicate=True
    )
    assert ing2.version == 1  # a separate evidence object


# --- invalid encoding (resilient, not a crash) ----------------------------
def test_invalid_encoding_is_handled_gracefully(platform):
    sub = RawSubmission(
        candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.TEXT, uploader=SERVICE_ID,
        content=b"valid \xff\xfe invalid bytes",
    )
    ing = platform.evidence_ingestion_service.ingest(sub)
    assert "valid" in ing.normalized_text  # decoded with replacement, no crash


def test_malformed_json_raises_typed_error(platform):
    sub = RawSubmission(
        candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.JSON, uploader=SERVICE_ID,
        content=b"{not valid json",
    )
    with pytest.raises(ContentExtractionError):
        platform.evidence_ingestion_service.ingest(sub)


def test_malformed_docx_raises_typed_error(platform):
    sub = RawSubmission(
        candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.DOCX, uploader=SERVICE_ID,
        content=b"this is not a zip",
    )
    with pytest.raises(ContentExtractionError):
        platform.evidence_ingestion_service.ingest(sub)


# --- large document --------------------------------------------------------
def test_large_document_over_ceiling_is_rejected():
    sub = RawSubmission.from_text(
        "x" * 100, candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.TEXT, uploader=SERVICE_ID,
    )
    with pytest.raises(IntegrityValidationError):
        run_pipeline(sub, max_content_bytes=10)


def test_large_document_under_ceiling_chunks(platform):
    ing = platform.evidence_ingestion_service.ingest(_text_submission("A" * 2500))
    assert len(ing.chunks) == 3  # default 1000-char windows
    assert reconstruct(ing.chunks) == "A" * 2500


# --- audit: every stage logged, ordered, immutable ------------------------
def test_every_pipeline_stage_is_audited_in_order(platform):
    ing = platform.evidence_ingestion_service.ingest(_text_submission("audit me"))
    events = platform.audit_service.history(ing.evidence_id)
    types = [e.event_type for e in events]
    expected_prefix = [
        AuditEventType.EVIDENCE_UPLOAD_RECEIVED,
        AuditEventType.EVIDENCE_INTEGRITY_VALIDATED,
        AuditEventType.EVIDENCE_PROVENANCE_CAPTURED,
        AuditEventType.EVIDENCE_CONTENT_HASHED,
        AuditEventType.EVIDENCE_CONTENT_EXTRACTED,
        AuditEventType.EVIDENCE_NORMALIZED,
        AuditEventType.EVIDENCE_PII_QUARANTINED,
        AuditEventType.EVIDENCE_CHUNK_CREATED,
        AuditEventType.EVIDENCE_VERSION_CREATED,
        AuditEventType.EVIDENCE_INDEXED,
    ]
    assert types == expected_prefix
    # timestamps are non-decreasing (correct ordering)
    ts = [e.timestamp for e in events]
    assert ts == sorted(ts)


def test_audit_events_are_causally_chained(platform):
    ing = platform.evidence_ingestion_service.ingest(_text_submission("chain"))
    events = platform.audit_service.history(ing.evidence_id)
    for prev, nxt in zip(events, events[1:]):
        assert nxt.causation_id == prev.event_id
