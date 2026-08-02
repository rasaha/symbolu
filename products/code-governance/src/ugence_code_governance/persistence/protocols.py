"""Narrow repository protocols for product records.

These are deliberately small, tenant-scoped ports. MVP 1A ships in-memory
reference implementations (and no production database). Every operation is
tenant-bound; cross-tenant reads are refused. Historical records are immutable —
a repository never overwrites an existing revision.

Persistence lives ONLY in the product boundary. It is never placed inside TAP,
Decision Authority, ActionGate, or Action Clearance.
"""
from __future__ import annotations

from typing import Optional, Protocol, Tuple, runtime_checkable

from ..claims.manifest import ClaimManifest
from ..evidence.records import EvidenceRecord
from ..governance.prepared_action import PreparedMergeAction
from ..governance.recommendation import GovernanceRecommendation


@runtime_checkable
class EvidenceRepository(Protocol):
    def put(self, record: EvidenceRecord) -> None: ...
    def get(self, tenant_id: str, evidence_id: str) -> Optional[EvidenceRecord]: ...
    def list_for_head(
        self, tenant_id: str, repository: str, head_sha: str
    ) -> Tuple[EvidenceRecord, ...]: ...


@runtime_checkable
class ClaimManifestRepository(Protocol):
    def put(self, manifest: ClaimManifest) -> None: ...
    def get(self, tenant_id: str, manifest_id: str) -> Optional[ClaimManifest]: ...


@runtime_checkable
class RecommendationRepository(Protocol):
    def put(self, recommendation: GovernanceRecommendation) -> None: ...
    def get(self, tenant_id: str, recommendation_id: str) -> Optional[GovernanceRecommendation]: ...


@runtime_checkable
class PreparedActionRepository(Protocol):
    def put(self, tenant_id: str, action: PreparedMergeAction) -> None: ...
    def get(self, tenant_id: str, fingerprint: str) -> Optional[PreparedMergeAction]: ...


@runtime_checkable
class WorkflowRepository(Protocol):
    def put(self, revision) -> None: ...
    def get(self, tenant_id: str, revision_id: str) -> Optional[object]: ...
    def revisions_for(self, tenant_id: str, workflow_id: str) -> Tuple[object, ...]: ...


@runtime_checkable
class GovernanceChainRepository(Protocol):
    def put(self, chain) -> None: ...
    def get(self, tenant_id: str, chain_id: str) -> Optional[object]: ...


__all__ = [
    "EvidenceRepository",
    "ClaimManifestRepository",
    "RecommendationRepository",
    "PreparedActionRepository",
    "WorkflowRepository",
    "GovernanceChainRepository",
]
