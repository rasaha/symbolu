"""Authorization-aware, tenant-scoped evidence access.

The single public entry point for reading and searching evidence. It
authenticates the principal (Phase-1 identity provider), consults the
:class:`EvidenceAccessPolicy`, and scopes every read/search to the caller's
tenant. Repositories never decide authorization; results are filtered *before*
return so unauthorized matches never affect counts. Quarantine access requires a
separate permission. Denials are audited.
"""

from __future__ import annotations

from typing import Optional

from ..common import new_id
from ..domain.enums import ActorType, AuditEventType
from ..errors import EvidenceAccessDeniedError, TenantMismatchError
from ..index.interfaces import IndexEntry, SearchQuery
from ..normalization.lineage import LineageGraph
from ..normalization.models import Provenance, QuarantineRecord
from decision_governance.identity import IdentityProvider
from decision_governance.policy import (
    AccessRequest,
    EvidenceAccessPolicy,
    Permission,
)
from ..repositories.evidence_artifacts import (
    LineageRepository,
    ProvenanceRepository,
    QuarantineRepository,
)
from ..repositories.evidence_index_repository import EvidenceIndexRepository
from ..repositories.interfaces import EvidenceRepository
from .audit_service import AuditService


class EvidenceAccessService:
    def __init__(
        self,
        evidence_repository: EvidenceRepository,
        provenance_repository: ProvenanceRepository,
        lineage_repository: LineageRepository,
        quarantine_repository: QuarantineRepository,
        index_repository: EvidenceIndexRepository,
        identity_provider: IdentityProvider,
        access_policy: EvidenceAccessPolicy,
        audit_service: AuditService,
    ) -> None:
        self._evidence = evidence_repository
        self._prov = provenance_repository
        self._lineage = lineage_repository
        self._quarantine = quarantine_repository
        self._index = index_repository
        self._identity = identity_provider
        self._policy = access_policy
        self._audit = audit_service

    # --- authorization -----------------------------------------------------
    def _authorize(self, request: AccessRequest, *, correlation_id: str) -> None:
        identity = self._identity.authenticate(request.principal_id)
        denied_reason: Optional[str] = None
        if not identity.authenticated:
            denied_reason = "unauthenticated"
        else:
            decision = self._policy.authorize(request)
            if not decision.allowed:
                denied_reason = decision.reason
        if denied_reason is not None:
            self._audit.record(
                event_type=AuditEventType.EVIDENCE_ACCESS_DENIED, entity_type="access",
                entity_id=request.tenant_id or "unknown", actor_type=ActorType.HUMAN,
                actor_id=request.principal_id, correlation_id=correlation_id,
                payload={"operation": request.operation.value, "reason": denied_reason})
            raise EvidenceAccessDeniedError(
                f"access denied for {request.operation.value}: {denied_reason}")

    # --- search ------------------------------------------------------------
    def search(
        self,
        *,
        principal_id: str,
        tenant_id: str,
        query: SearchQuery,
        candidate_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> tuple[IndexEntry, ...]:
        corr = correlation_id or new_id("corr")
        self._authorize(AccessRequest(
            principal_id=principal_id, tenant_id=tenant_id,
            operation=Permission.EVIDENCE_SEARCH, candidate_id=candidate_id), correlation_id=corr)
        # Force tenant scope (and candidate scope if requested) before search so
        # cross-tenant / cross-candidate matches never affect results or counts.
        scoped = SearchQuery(
            candidate_id=candidate_id or query.candidate_id, role_id=query.role_id,
            assessment_item_id=query.assessment_item_id, assessment_type=query.assessment_type,
            document_type=query.document_type, evidence_id=query.evidence_id,
            chunk_id=query.chunk_id, filename=query.filename, keyword=query.keyword,
            tenant_id=tenant_id, application_id=query.application_id, metadata=query.metadata)
        return self._index.search(scoped)

    # --- reads (tenant-scoped) --------------------------------------------
    def get_evidence(self, *, principal_id: str, tenant_id: str, evidence_id: str,
                     correlation_id: Optional[str] = None):
        corr = correlation_id or new_id("corr")
        self._authorize(AccessRequest(
            principal_id=principal_id, tenant_id=tenant_id,
            operation=Permission.EVIDENCE_READ), correlation_id=corr)
        evidence = self._evidence.get(evidence_id)
        self._require_tenant(evidence.tenant_id, tenant_id, evidence_id, principal_id, corr)
        return evidence

    def get_lineage(self, *, principal_id: str, tenant_id: str, evidence_id: str,
                    correlation_id: Optional[str] = None) -> LineageGraph:
        corr = correlation_id or new_id("corr")
        self._authorize(AccessRequest(
            principal_id=principal_id, tenant_id=tenant_id,
            operation=Permission.EVIDENCE_LINEAGE_READ), correlation_id=corr)
        nodes = self._lineage.for_evidence(evidence_id)
        for node in nodes:
            self._require_tenant(node.tenant_id, tenant_id, evidence_id, principal_id, corr)
        return LineageGraph(nodes=nodes)

    def get_versions(self, *, principal_id: str, tenant_id: str, evidence_id: str,
                     correlation_id: Optional[str] = None) -> tuple[Provenance, ...]:
        corr = correlation_id or new_id("corr")
        self._authorize(AccessRequest(
            principal_id=principal_id, tenant_id=tenant_id,
            operation=Permission.EVIDENCE_VERSION_READ), correlation_id=corr)
        versions = self._prov.versions_of(evidence_id)
        for prov in versions:
            self._require_tenant(prov.tenant_id, tenant_id, evidence_id, principal_id, corr)
        return versions

    def get_quarantine(self, *, principal_id: str, tenant_id: str, evidence_id: str,
                       version: int, correlation_id: Optional[str] = None
                       ) -> Optional[QuarantineRecord]:
        """Requires a separate quarantine permission; not part of ordinary reads."""
        corr = correlation_id or new_id("corr")
        self._authorize(AccessRequest(
            principal_id=principal_id, tenant_id=tenant_id,
            operation=Permission.QUARANTINE_READ, include_quarantine=True), correlation_id=corr)
        record = self._quarantine.for_evidence(evidence_id, version)
        if record is not None:
            self._require_tenant(record.tenant_id, tenant_id, evidence_id, principal_id, corr)
        return record

    def _require_tenant(self, resource_tenant, tenant_id, evidence_id, principal_id, corr):
        if resource_tenant != tenant_id:
            self._audit.record(
                event_type=AuditEventType.EVIDENCE_ACCESS_DENIED, entity_type="access",
                entity_id=evidence_id, actor_type=ActorType.HUMAN, actor_id=principal_id,
                correlation_id=corr, payload={"reason": "tenant mismatch"})
            raise TenantMismatchError(
                f"evidence '{evidence_id}' is outside tenant '{tenant_id}'")
