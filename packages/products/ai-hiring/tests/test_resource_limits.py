"""Resource-limit tests (input size + text/source shape)."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.errors import IntegrityValidationError, TextLimitError
from ugence_ai_hiring.normalization.limits import (
    DEFAULT_LIMITS,
    EvidenceLimits,
    check_input_size,
    check_text_limits,
)
from ugence_ai_hiring.normalization.models import EvidenceFormat, RawSubmission
from ugence_ai_hiring.normalization.pipeline import run_pipeline

from .conftest import SVC, text_sub


def test_input_size_limit():
    with pytest.raises(TextLimitError):
        check_input_size(100, EvidenceLimits(max_input_bytes=10))


def test_pipeline_enforces_input_ceiling():
    sub = text_sub("x" * 100)
    with pytest.raises(IntegrityValidationError):
        run_pipeline(sub, max_content_bytes=10)


def test_max_characters():
    with pytest.raises(TextLimitError):
        check_text_limits(b"", "a" * 100, EvidenceLimits(max_characters=10))


def test_max_line_length():
    with pytest.raises(TextLimitError):
        check_text_limits(b"", "a" * 50, EvidenceLimits(max_line_length=10))


def test_max_lines():
    text = "\n".join(str(i) for i in range(50))
    with pytest.raises(TextLimitError):
        check_text_limits(b"", text, EvidenceLimits(max_lines=10))


def test_null_bytes_rejected_as_binary():
    with pytest.raises(TextLimitError):
        check_text_limits(b"a\x00b", "a\x00b", DEFAULT_LIMITS)


def test_excessive_invalid_utf_rejected_as_binary():
    raw = b"\xff\xff\xff\xff\xff"
    text = raw.decode("utf-8", errors="replace")  # all replacement chars
    with pytest.raises(TextLimitError):
        check_text_limits(raw, text, DEFAULT_LIMITS)


def test_invalid_utf_within_ratio_warns_not_rejects():
    warnings = check_text_limits(b"", "ok � done and more text here", DEFAULT_LIMITS)
    assert "INVALID_UTF_REPLACED" in warnings


def test_line_length_limit_via_service(platform):
    # a single very long line trips the default is fine; use a tight custom svc
    from ugence_ai_hiring.services import EvidenceIngestionService

    svc = EvidenceIngestionService(
        platform.evidence_repo, platform.provenance_repo, platform.chunk_repo,
        platform.quarantine_repo, platform.lineage_repo, platform.evidence_index_repo,
        platform.audit_service, limits=EvidenceLimits(max_line_length=5))
    with pytest.raises(TextLimitError):
        svc.ingest(text_sub("this line is definitely longer than five characters"))
