"""Context-aware duplicate-semantics tests."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.errors import DuplicateEvidenceError
from ugence_ai_hiring.policies.duplicate_policy import DuplicateClassification

from .conftest import text_sub


def _ingest(platform, sub, **kw):
    return platform.evidence_ingestion_service.ingest(sub, **kw)


def test_exact_same_upload_same_context_blocks(platform):
    _ingest(platform, text_sub("same body", tenant_id="t1", candidate_id="c1"))
    with pytest.raises(DuplicateEvidenceError):
        _ingest(platform, text_sub("same body", tenant_id="t1", candidate_id="c1"))


def test_same_bytes_across_candidates_never_merges(platform):
    a = _ingest(platform, text_sub("shared", tenant_id="t1", candidate_id="cand-A"))
    b = _ingest(platform, text_sub("shared", tenant_id="t1", candidate_id="cand-B"))
    assert a.evidence_id != b.evidence_id
    assert b.normalized_evidence.candidate_id == "cand-B"
    assert b.duplicate_classification == DuplicateClassification.CROSS_CANDIDATE_DUPLICATE.value


def test_normalized_duplicate_different_raw_preserved(platform):
    # different raw bytes (extra spaces) but identical normalized prose content
    a = _ingest(platform, text_sub("hello world", tenant_id="t1", candidate_id="c1",
                                   assessment_item_id="a1"))
    b = _ingest(platform, text_sub("hello    world", tenant_id="t1", candidate_id="c1",
                                   assessment_item_id="a1"))
    assert a.evidence_id != b.evidence_id
    assert a.raw_hash != b.raw_hash
    assert a.normalized_hash == b.normalized_hash
    assert b.duplicate_classification == DuplicateClassification.NORMALIZED_CONTENT_DUPLICATE.value


def test_declared_revision_creates_new_version(platform):
    a = _ingest(platform, text_sub("draft 1", tenant_id="t1", candidate_id="c1"))
    b = _ingest(platform, text_sub("draft 2", tenant_id="t1", candidate_id="c1"),
                parent_evidence_id=a.evidence_id)
    assert b.evidence_id == a.evidence_id and b.version == 2
    assert b.duplicate_classification == DuplicateClassification.NEW_VERSION.value


def test_reuse_across_assessments(platform):
    a = _ingest(platform, text_sub("portfolio piece", tenant_id="t1", candidate_id="c1",
                                   assessment_item_id="asm-1"))
    b = _ingest(platform, text_sub("portfolio piece", tenant_id="t1", candidate_id="c1",
                                   assessment_item_id="asm-2"))
    assert a.evidence_id != b.evidence_id
    assert b.duplicate_classification == DuplicateClassification.CROSS_CONTEXT_REUSE.value


def test_cross_tenant_duplicate_no_information_leak(platform):
    a = _ingest(platform, text_sub("secret content", tenant_id="tenant-A", candidate_id="c1"))
    # same bytes in a different tenant: succeeds, and reveals nothing about tenant-A
    b = _ingest(platform, text_sub("secret content", tenant_id="tenant-B", candidate_id="c1"))
    assert a.evidence_id != b.evidence_id
    # cross-tenant match is never disclosed as a duplicate
    assert b.duplicate_classification not in (
        DuplicateClassification.EXACT_BINARY_DUPLICATE.value,
        DuplicateClassification.CROSS_TENANT_DUPLICATE.value,
    )
    assert b.duplicate_classification == DuplicateClassification.NOT_DUPLICATE.value


def test_policy_cross_tenant_not_disclosed():
    from ugence_ai_hiring.policies.duplicate_policy import (
        DEFAULT_DUPLICATE_POLICY,
        DuplicateMatch,
        EvidenceContext,
    )

    other = DuplicateMatch(
        context=EvidenceContext(tenant_id="t-other", candidate_id="c1"),
        raw_hash="h", normalized_hash="n", evidence_id="ev-other")
    decision = DEFAULT_DUPLICATE_POLICY.classify(
        new_context=EvidenceContext(tenant_id="t-mine", candidate_id="c1"),
        new_raw_hash="h", new_normalized_hash="n", is_revision=False, match=other)
    assert decision.classification == DuplicateClassification.CROSS_TENANT_DUPLICATE
    assert decision.disclose is False
    assert decision.matched_evidence_id is None
