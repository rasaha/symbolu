"""Deterministic in-memory reference repositories (tenant-isolated, immutable).

These are the MVP 1A reference stores. They are **not** the production durable
store — no database is introduced in this phase (see SHADOW_LIMITATIONS). They
enforce two invariants the design requires:

* **tenant isolation** — every read is keyed by ``(tenant_id, id)``; a lookup
  with the wrong tenant returns ``None`` (never another tenant's record);
* **immutability of history** — re-``put`` of an existing ``(tenant, id)`` with a
  *different* value raises ``ImmutableRecordError``; an identical re-``put`` is an
  idempotent no-op.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from ..errors import ImmutableRecordError
from ..claims.manifest import ClaimManifest
from ..evidence.records import EvidenceRecord
from ..governance.prepared_action import PreparedMergeAction
from ..governance.recommendation import GovernanceRecommendation


class _ImmutableStore:
    """Base tenant-keyed immutable store."""

    def __init__(self) -> None:
        self._items: Dict[Tuple[str, str], object] = {}

    def _put(self, tenant_id: str, key: str, value: object) -> None:
        existing = self._items.get((tenant_id, key))
        if existing is not None and existing != value:
            raise ImmutableRecordError(
                f"refusing to overwrite immutable record {key!r} for tenant {tenant_id!r}")
        self._items[(tenant_id, key)] = value

    def _get(self, tenant_id: str, key: str) -> Optional[object]:
        return self._items.get((tenant_id, key))


class InMemoryEvidenceRepository(_ImmutableStore):
    def put(self, record: EvidenceRecord) -> None:
        self._put(record.tenant_id, record.evidence_id, record)

    def get(self, tenant_id: str, evidence_id: str) -> Optional[EvidenceRecord]:
        return self._get(tenant_id, evidence_id)  # type: ignore[return-value]

    def list_for_head(
        self, tenant_id: str, repository: str, head_sha: str
    ) -> Tuple[EvidenceRecord, ...]:
        out = []
        for (tid, _eid), rec in self._items.items():
            if tid != tenant_id:
                continue
            assert isinstance(rec, EvidenceRecord)
            if rec.repository == repository and rec.head_sha == head_sha:
                out.append(rec)
        return tuple(sorted(out, key=lambda r: r.evidence_id))


class InMemoryClaimManifestRepository(_ImmutableStore):
    def put(self, manifest: ClaimManifest) -> None:
        self._put(manifest.tenant_id, manifest.manifest_id, manifest)

    def get(self, tenant_id: str, manifest_id: str) -> Optional[ClaimManifest]:
        return self._get(tenant_id, manifest_id)  # type: ignore[return-value]


class InMemoryRecommendationRepository(_ImmutableStore):
    def put(self, recommendation: GovernanceRecommendation) -> None:
        self._put(recommendation.tenant_id, recommendation.recommendation_id, recommendation)

    def get(self, tenant_id: str, recommendation_id: str) -> Optional[GovernanceRecommendation]:
        return self._get(tenant_id, recommendation_id)  # type: ignore[return-value]


class InMemoryPreparedActionRepository(_ImmutableStore):
    def put(self, tenant_id: str, action: PreparedMergeAction) -> None:
        self._put(tenant_id, action.fingerprint, action)

    def get(self, tenant_id: str, fingerprint: str) -> Optional[PreparedMergeAction]:
        return self._get(tenant_id, fingerprint)  # type: ignore[return-value]


class InMemoryWorkflowRepository(_ImmutableStore):
    def put(self, revision) -> None:
        self._put(revision.tenant_id, revision.revision_id, revision)

    def get(self, tenant_id: str, revision_id: str):
        return self._get(tenant_id, revision_id)

    def revisions_for(self, tenant_id: str, workflow_id: str) -> Tuple[object, ...]:
        out = [
            rec for (tid, _rid), rec in self._items.items()
            if tid == tenant_id and getattr(rec, "workflow_id", None) == workflow_id
        ]
        return tuple(sorted(out, key=lambda r: r.created_at))


class InMemoryGovernanceChainRepository(_ImmutableStore):
    def put(self, chain) -> None:
        self._put(chain.tenant_id, chain.chain_id, chain)

    def get(self, tenant_id: str, chain_id: str):
        return self._get(tenant_id, chain_id)


__all__ = [
    "InMemoryEvidenceRepository",
    "InMemoryClaimManifestRepository",
    "InMemoryRecommendationRepository",
    "InMemoryPreparedActionRepository",
    "InMemoryWorkflowRepository",
    "InMemoryGovernanceChainRepository",
]
