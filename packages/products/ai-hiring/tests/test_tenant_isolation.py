"""Tenant/candidate/application isolation tests."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.errors import EvidenceAccessDeniedError, TenantMismatchError
from ugence_ai_hiring.index.interfaces import SearchQuery
from ugence_ai_hiring.policies.evidence_access_policy import AccessGrant, Permission

from .conftest import text_sub

ALL_READ = frozenset({Permission.EVIDENCE_SEARCH, Permission.EVIDENCE_READ,
                      Permission.EVIDENCE_LINEAGE_READ, Permission.EVIDENCE_VERSION_READ})


def _grant(platform, principal, tenant, perms=ALL_READ, candidates=frozenset()):
    platform.access_grants.add(AccessGrant(
        principal_id=principal, tenant_id=tenant, permissions=perms, candidate_ids=candidates))


def _seed_two_tenants(platform):
    a = platform.evidence_ingestion_service.ingest(
        text_sub("shared filename body", tenant_id="tenant-A", candidate_id="c1",
                 filename="resume.txt"))
    b = platform.evidence_ingestion_service.ingest(
        text_sub("shared filename body", tenant_id="tenant-B", candidate_id="c1",
                 filename="resume.txt"))
    return a, b


def test_search_is_tenant_scoped(platform):
    a, b = _seed_two_tenants(platform)
    _grant(platform, "hm-alex", "tenant-A")
    results = platform.evidence_access_service.search(
        principal_id="hm-alex", tenant_id="tenant-A",
        query=SearchQuery(filename="resume.txt"))
    assert results and all(r.tenant_id == "tenant-A" for r in results)
    # identical filename/keyword in tenant-B never leaks into tenant-A results
    assert all(r.evidence_id == a.evidence_id for r in results)


def test_cross_tenant_search_denied(platform):
    _seed_two_tenants(platform)
    _grant(platform, "hm-alex", "tenant-A")
    with pytest.raises(EvidenceAccessDeniedError):
        platform.evidence_access_service.search(
            principal_id="hm-alex", tenant_id="tenant-B", query=SearchQuery())


def test_result_counts_do_not_leak_other_tenant(platform):
    a, b = _seed_two_tenants(platform)
    _grant(platform, "hm-alex", "tenant-A")
    # keyword present in BOTH tenants; A-scoped principal sees only A's chunks
    results = platform.evidence_access_service.search(
        principal_id="hm-alex", tenant_id="tenant-A", query=SearchQuery(keyword="shared"))
    assert len(results) == len(a.chunks)


def test_get_evidence_cross_tenant_denied(platform):
    a, b = _seed_two_tenants(platform)
    _grant(platform, "hm-alex", "tenant-A")
    # authorized in tenant-A but the target belongs to tenant-B -> mismatch
    with pytest.raises(TenantMismatchError):
        platform.evidence_access_service.get_evidence(
            principal_id="hm-alex", tenant_id="tenant-A", evidence_id=b.evidence_id)


def test_candidate_scope_within_tenant(platform):
    platform.evidence_ingestion_service.ingest(
        text_sub("alpha", tenant_id="t1", candidate_id="cand-A", assessment_item_id="x"))
    platform.evidence_ingestion_service.ingest(
        text_sub("beta", tenant_id="t1", candidate_id="cand-B", assessment_item_id="y"))
    # principal scoped to cand-A only
    _grant(platform, "hm-alex", "t1", candidates=frozenset({"cand-A"}))
    ok = platform.evidence_access_service.search(
        principal_id="hm-alex", tenant_id="t1", candidate_id="cand-A", query=SearchQuery())
    assert ok and all(r.candidate_id == "cand-A" for r in ok)
    with pytest.raises(EvidenceAccessDeniedError):
        platform.evidence_access_service.search(
            principal_id="hm-alex", tenant_id="t1", candidate_id="cand-B", query=SearchQuery())


def test_denied_access_is_audited(platform):
    _seed_two_tenants(platform)
    with pytest.raises(EvidenceAccessDeniedError):
        platform.evidence_access_service.search(
            principal_id="hm-alex", tenant_id="tenant-A", query=SearchQuery())
    from ugence_ai_hiring.domain.enums import AuditEventType

    assert any(e.event_type is AuditEventType.EVIDENCE_ACCESS_DENIED
               for e in platform.audit_repo.all())
