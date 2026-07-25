"""Search / access authorization tests."""

from __future__ import annotations

import pytest

from ai_hiring.domain.enums import AuditEventType
from ai_hiring.errors import EvidenceAccessDeniedError
from ai_hiring.index.interfaces import SearchQuery
from ai_hiring.policies.evidence_access_policy import AccessGrant, Permission

from .conftest import struct_sub, text_sub


def _grant(platform, principal, tenant, perms, candidates=frozenset()):
    platform.access_grants.add(AccessGrant(
        principal_id=principal, tenant_id=tenant, permissions=frozenset(perms),
        candidate_ids=candidates))


def test_authorized_tenant_search(platform):
    platform.evidence_ingestion_service.ingest(text_sub("hello", tenant_id="t1"))
    _grant(platform, "hm-alex", "t1", {Permission.EVIDENCE_SEARCH})
    assert platform.evidence_access_service.search(
        principal_id="hm-alex", tenant_id="t1", query=SearchQuery(keyword="hello"))


def test_missing_permission_denied(platform):
    platform.evidence_ingestion_service.ingest(text_sub("hello", tenant_id="t1"))
    _grant(platform, "hm-alex", "t1", {Permission.EVIDENCE_READ})  # not SEARCH
    with pytest.raises(EvidenceAccessDeniedError):
        platform.evidence_access_service.search(
            principal_id="hm-alex", tenant_id="t1", query=SearchQuery())


def test_unauthenticated_principal_denied(platform):
    platform.evidence_ingestion_service.ingest(text_sub("hello", tenant_id="t1"))
    _grant(platform, "ghost", "t1", {Permission.EVIDENCE_SEARCH})  # not in identity provider
    with pytest.raises(EvidenceAccessDeniedError):
        platform.evidence_access_service.search(
            principal_id="ghost", tenant_id="t1", query=SearchQuery())


def test_ordinary_reader_cannot_read_quarantine(platform):
    ing = platform.evidence_ingestion_service.ingest(
        struct_sub({"answer": "ok", "gender": "x"}, tenant_id="t1"))
    _grant(platform, "hm-alex", "t1", {Permission.EVIDENCE_READ, Permission.EVIDENCE_SEARCH})
    with pytest.raises(EvidenceAccessDeniedError):
        platform.evidence_access_service.get_quarantine(
            principal_id="hm-alex", tenant_id="t1", evidence_id=ing.evidence_id,
            version=ing.version)


def test_quarantine_reader_permission_allows_access(platform):
    ing = platform.evidence_ingestion_service.ingest(
        struct_sub({"answer": "ok", "gender": "x"}, tenant_id="t1"))
    _grant(platform, "hr-partner-1", "t1", {Permission.QUARANTINE_READ})
    record = platform.evidence_access_service.get_quarantine(
        principal_id="hr-partner-1", tenant_id="t1", evidence_id=ing.evidence_id,
        version=ing.version)
    assert record is not None
    assert any(f.field_name == "gender" for f in record.fields)


def test_access_to_one_candidate_does_not_imply_another(platform):
    platform.evidence_ingestion_service.ingest(
        text_sub("a", tenant_id="t1", candidate_id="cand-A", assessment_item_id="x"))
    platform.evidence_ingestion_service.ingest(
        text_sub("b", tenant_id="t1", candidate_id="cand-B", assessment_item_id="y"))
    _grant(platform, "hm-alex", "t1", {Permission.EVIDENCE_SEARCH},
           candidates=frozenset({"cand-A"}))
    with pytest.raises(EvidenceAccessDeniedError):
        platform.evidence_access_service.search(
            principal_id="hm-alex", tenant_id="t1", candidate_id="cand-B", query=SearchQuery())


def test_denial_is_audited(platform):
    _grant(platform, "hm-alex", "t1", {Permission.EVIDENCE_READ})
    with pytest.raises(EvidenceAccessDeniedError):
        platform.evidence_access_service.search(
            principal_id="hm-alex", tenant_id="t1", query=SearchQuery())
    assert any(e.event_type is AuditEventType.EVIDENCE_ACCESS_DENIED
               for e in platform.audit_repo.all())
