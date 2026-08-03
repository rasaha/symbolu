"""Fail-closed behavior: failed/uncertain extraction never becomes usable."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.domain.enums import AuditEventType
from ugence_ai_hiring.errors import EmptyExtractionError
from ugence_ai_hiring.index.interfaces import SearchQuery
from ugence_ai_hiring.normalization.eligibility import EligibilityReason
from ugence_ai_hiring.normalization.models import EvidenceFormat, RawSubmission

from .conftest import PDF_EMPTY, SVC, struct_sub


def _pdf(content: bytes):
    return RawSubmission(content=content, candidate_id="c1", role_id="r1",
                         assessment_item_id="a1", declared_format=EvidenceFormat.PDF,
                         uploader=SVC)


def test_empty_extraction_not_searchable(platform):
    with pytest.raises(EmptyExtractionError):
        platform.evidence_ingestion_service.ingest(_pdf(PDF_EMPTY))
    # nothing became searchable as completed evidence
    assert platform.search_service.search(SearchQuery(candidate_id="c1")) == ()


def test_empty_extraction_no_completed_or_indexed_audit(platform):
    with pytest.raises(EmptyExtractionError):
        platform.evidence_ingestion_service.ingest(_pdf(PDF_EMPTY))
    types = {e.event_type for e in platform.audit_repo.all()}
    assert AuditEventType.EVIDENCE_EXTRACTION_EMPTY in types
    assert AuditEventType.EVIDENCE_ELIGIBILITY_BLOCKED in types
    assert AuditEventType.EVIDENCE_INDEXED not in types
    assert AuditEventType.EVIDENCE_INGESTION_COMPLETED not in types


def test_all_quarantined_structured_fails_closed(platform):
    # every field prohibited -> empty clean content -> fail closed
    with pytest.raises(EmptyExtractionError):
        platform.evidence_ingestion_service.ingest(struct_sub({"age": "40", "gender": "x"}))


def test_eligibility_policy_blocks_on_empty():
    from ugence_ai_hiring.normalization.eligibility import (
        DEFAULT_ELIGIBILITY_POLICY,
        EligibilityInput,
    )
    from ugence_ai_hiring.normalization.extraction_status import ExtractionStatus

    facts = EligibilityInput(extraction_status=ExtractionStatus.EMPTY)
    result = DEFAULT_ELIGIBILITY_POLICY.evaluate(facts)
    assert not result.eligible
    assert EligibilityReason.EXTRACTION_EMPTY in result.reasons


def test_eligibility_requires_every_condition():
    from ugence_ai_hiring.normalization.eligibility import (
        DEFAULT_ELIGIBILITY_POLICY,
        EligibilityInput,
    )
    from ugence_ai_hiring.normalization.extraction_status import ExtractionStatus

    # all good -> eligible
    ok = EligibilityInput(
        extraction_status=ExtractionStatus.SUCCEEDED, normalized_non_empty=True,
        provenance_complete=True, hashes_valid=True, lineage_valid=True,
        not_quarantined=True, authorized=True, tenant_consistent=True)
    assert DEFAULT_ELIGIBILITY_POLICY.evaluate(ok).eligible
    # drop authorization -> blocked with ACCESS_DENIED
    denied = DEFAULT_ELIGIBILITY_POLICY.evaluate(
        EligibilityInput(extraction_status=ExtractionStatus.SUCCEEDED,
                         normalized_non_empty=True, provenance_complete=True,
                         hashes_valid=True, lineage_valid=True, authorized=False,
                         tenant_consistent=True))
    assert not denied.eligible
    assert EligibilityReason.ACCESS_DENIED in denied.reasons


def test_successful_evidence_is_eligible_via_validation_service(platform):
    ing = platform.evidence_ingestion_service.ingest(struct_sub({"answer": "recursion"}))
    result = platform.evidence_validation_service.evaluate_eligibility(
        ing.evidence_id, tenant_id="", authorized=True)
    assert result.eligible, result.reason_codes


def test_tenant_mismatch_blocks_eligibility(platform):
    ing = platform.evidence_ingestion_service.ingest(
        struct_sub({"answer": "ok"}, tenant_id="tenant-A"))
    result = platform.evidence_validation_service.evaluate_eligibility(
        ing.evidence_id, tenant_id="tenant-B", authorized=True)
    assert not result.eligible
    assert EligibilityReason.TENANT_MISMATCH in result.reasons
