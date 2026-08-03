"""Quarantine non-leakage tests."""

from __future__ import annotations

from ugence_ai_hiring.index.interfaces import SearchQuery
from ugence_ai_hiring.policies.evidence_access_policy import AccessGrant, Permission

from .conftest import struct_sub

SECRET = "SENSITIVE_PROTECTED_VALUE_XYZ"


def _ingest(platform):
    return platform.evidence_ingestion_service.ingest(
        struct_sub({"answer": "used a heap", "gender": SECRET, "age": "SECRET_AGE_42"},
                   tenant_id="t1"))


def test_not_in_normalized_evidence(platform):
    ing = _ingest(platform)
    assert SECRET not in ing.normalized_text
    assert "SECRET_AGE_42" not in ing.normalized_text
    assert "answer=used a heap" in ing.normalized_text


def test_not_in_chunks(platform):
    ing = _ingest(platform)
    for chunk in ing.chunks:
        assert SECRET not in chunk.text


def test_not_in_index(platform):
    ing = _ingest(platform)
    for entry in platform.search_service.by_evidence(ing.evidence_id):
        assert SECRET not in entry.text
        assert SECRET.lower() not in entry.keywords
    # keyword search for the secret returns nothing
    assert platform.search_service.keyword(SECRET) == ()


def test_not_in_audit_payloads(platform):
    ing = _ingest(platform)
    import json

    for event in platform.audit_repo.all():
        blob = json.dumps(event.metadata, default=str)
        assert SECRET not in blob
        assert SECRET not in (event.new_state or "")


def test_safe_quarantine_count_is_auditable(platform):
    ing = _ingest(platform)
    from ugence_ai_hiring.domain.enums import AuditEventType

    quar_events = [e for e in platform.audit_service.history(ing.evidence_id)
                   if e.event_type is AuditEventType.EVIDENCE_PII_QUARANTINED]
    assert quar_events  # the fact of quarantine is recorded (safe identifiers only)


def test_value_only_via_quarantine_permission(platform):
    ing = _ingest(platform)
    platform.access_grants.add(AccessGrant(
        principal_id="hr-partner-1", tenant_id="t1",
        permissions=frozenset({Permission.QUARANTINE_READ})))
    record = platform.evidence_access_service.get_quarantine(
        principal_id="hr-partner-1", tenant_id="t1", evidence_id=ing.evidence_id,
        version=ing.version)
    # the raw value is preserved (never deleted) but only reachable here
    values = {f.value for f in record.fields}
    assert SECRET in values


def test_not_in_error_messages(platform):
    # a malformed structured payload error must not echo protected values
    from ugence_ai_hiring.errors import ContentExtractionError
    from ugence_ai_hiring.normalization.models import EvidenceFormat, RawSubmission

    sub = RawSubmission(content=b'{"gender": "' + SECRET.encode() + b'" bad json',
                        candidate_id="c1", role_id="r1", assessment_item_id="a1",
                        declared_format=EvidenceFormat.JSON, uploader="svc-ats", tenant_id="t1")
    try:
        platform.evidence_ingestion_service.ingest(sub)
    except ContentExtractionError as exc:
        assert SECRET not in str(exc)
