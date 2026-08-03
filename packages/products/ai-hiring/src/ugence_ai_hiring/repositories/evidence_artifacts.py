"""Repositories for Phase-2 evidence artifacts.

Ports + in-memory adapters for provenance, chunks, quarantine, and lineage.
Consistent with the Phase-1 repository pattern (uniqueness + immutability;
no update/delete of stored records). No production database in this phase.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..errors import RecordNotFoundError, VersionConflictError
from ..normalization.models import (
    EvidenceChunk,
    LineageNode,
    Provenance,
    QuarantineRecord,
)


# --- ports -----------------------------------------------------------------
@runtime_checkable
class ProvenanceRepository(Protocol):
    def add(self, record: Provenance) -> Provenance: ...
    def get(self, provenance_id: str) -> Provenance: ...
    def versions_of(self, evidence_id: str) -> tuple[Provenance, ...]: ...
    def latest_version(self, evidence_id: str) -> Optional[Provenance]: ...
    def find_duplicate(
        self, candidate_id: str, assessment_item_id: str, raw_hash: str
    ) -> Optional[Provenance]: ...
    def find_same_stage_raw(
        self, tenant_id: str, candidate_id: str, assessment_item_id: str, raw_hash: str
    ) -> Optional[Provenance]: ...
    def find_same_stage_normalized(
        self, tenant_id: str, candidate_id: str, assessment_item_id: str, normalized_hash: str
    ) -> Optional[Provenance]: ...
    def find_tenant_hash(
        self, tenant_id: str, raw_hash: str, normalized_hash: str
    ) -> Optional[Provenance]: ...


@runtime_checkable
class ChunkRepository(Protocol):
    def add(self, record: EvidenceChunk) -> EvidenceChunk: ...
    def for_evidence(self, evidence_id: str, version: int) -> tuple[EvidenceChunk, ...]: ...
    def get(self, chunk_id: str) -> EvidenceChunk: ...


@runtime_checkable
class QuarantineRepository(Protocol):
    def add(self, record: QuarantineRecord) -> QuarantineRecord: ...
    def for_evidence(self, evidence_id: str, version: int) -> Optional[QuarantineRecord]: ...


@runtime_checkable
class LineageRepository(Protocol):
    def add(self, node: LineageNode) -> LineageNode: ...
    def for_evidence(self, evidence_id: str) -> tuple[LineageNode, ...]: ...
    def get(self, node_id: str) -> LineageNode: ...


# --- in-memory adapters ----------------------------------------------------
class InMemoryProvenanceRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, Provenance] = {}
        self._by_evidence: dict[str, dict[int, Provenance]] = {}

    def add(self, record: Provenance) -> Provenance:
        if record.provenance_id in self._by_id:
            raise VersionConflictError(f"provenance '{record.provenance_id}' already exists")
        versions = self._by_evidence.setdefault(record.evidence_id, {})
        if record.version in versions:
            raise VersionConflictError(
                f"provenance for evidence '{record.evidence_id}' version "
                f"{record.version} already exists; immutable records are not overwritten"
            )
        self._by_id[record.provenance_id] = record
        versions[record.version] = record
        return record

    def get(self, provenance_id: str) -> Provenance:
        record = self._by_id.get(provenance_id)
        if record is None:
            raise RecordNotFoundError(f"provenance '{provenance_id}' not found")
        return record

    def versions_of(self, evidence_id: str) -> tuple[Provenance, ...]:
        versions = self._by_evidence.get(evidence_id, {})
        return tuple(versions[v] for v in sorted(versions))

    def latest_version(self, evidence_id: str) -> Optional[Provenance]:
        versions = self._by_evidence.get(evidence_id)
        if not versions:
            return None
        return versions[max(versions)]

    def find_duplicate(
        self, candidate_id: str, assessment_item_id: str, raw_hash: str
    ) -> Optional[Provenance]:
        """Return an existing provenance with identical raw content for the same
        candidate + assessment stage, or None. Deterministic (lowest version)."""
        matches = [
            p for p in self._by_id.values()
            if p.candidate_id == candidate_id
            and p.assessment_item_id == assessment_item_id
            and p.raw_hash == raw_hash
        ]
        if not matches:
            return None
        return sorted(matches, key=lambda p: (p.evidence_id, p.version))[0]

    def _scan(self, predicate) -> Optional[Provenance]:
        matches = [p for p in self._by_id.values() if predicate(p)]
        if not matches:
            return None
        return sorted(matches, key=lambda p: (p.evidence_id, p.version))[0]

    def find_same_stage_raw(
        self, tenant_id: str, candidate_id: str, assessment_item_id: str, raw_hash: str
    ) -> Optional[Provenance]:
        return self._scan(
            lambda p: p.tenant_id == tenant_id and p.candidate_id == candidate_id
            and p.assessment_item_id == assessment_item_id and p.raw_hash == raw_hash
        )

    def find_same_stage_normalized(
        self, tenant_id: str, candidate_id: str, assessment_item_id: str, normalized_hash: str
    ) -> Optional[Provenance]:
        return self._scan(
            lambda p: p.tenant_id == tenant_id and p.candidate_id == candidate_id
            and p.assessment_item_id == assessment_item_id
            and p.normalized_hash == normalized_hash
        )

    def find_tenant_hash(
        self, tenant_id: str, raw_hash: str, normalized_hash: str
    ) -> Optional[Provenance]:
        """Same-tenant match by raw or normalized hash (cross-candidate/context)."""
        return self._scan(
            lambda p: p.tenant_id == tenant_id
            and (p.raw_hash == raw_hash or p.normalized_hash == normalized_hash)
        )


class InMemoryChunkRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, EvidenceChunk] = {}
        self._by_evidence: dict[tuple[str, int], list[EvidenceChunk]] = {}

    def add(self, record: EvidenceChunk) -> EvidenceChunk:
        if record.chunk_id in self._by_id:
            raise VersionConflictError(f"chunk '{record.chunk_id}' already exists")
        self._by_id[record.chunk_id] = record
        self._by_evidence.setdefault((record.evidence_id, record.version), []).append(record)
        return record

    def for_evidence(self, evidence_id: str, version: int) -> tuple[EvidenceChunk, ...]:
        chunks = self._by_evidence.get((evidence_id, version), [])
        return tuple(sorted(chunks, key=lambda c: c.index))

    def get(self, chunk_id: str) -> EvidenceChunk:
        record = self._by_id.get(chunk_id)
        if record is None:
            raise RecordNotFoundError(f"chunk '{chunk_id}' not found")
        return record


class InMemoryQuarantineRepository:
    def __init__(self) -> None:
        self._by_evidence: dict[tuple[str, int], QuarantineRecord] = {}

    def add(self, record: QuarantineRecord) -> QuarantineRecord:
        key = (record.evidence_id, record.version)
        if key in self._by_evidence:
            raise VersionConflictError(
                f"quarantine record for evidence '{record.evidence_id}' version "
                f"{record.version} already exists"
            )
        self._by_evidence[key] = record
        return record

    def for_evidence(self, evidence_id: str, version: int) -> Optional[QuarantineRecord]:
        return self._by_evidence.get((evidence_id, version))


class InMemoryLineageRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, LineageNode] = {}
        self._by_evidence: dict[str, list[LineageNode]] = {}

    def add(self, node: LineageNode) -> LineageNode:
        if node.node_id in self._by_id:
            raise VersionConflictError(f"lineage node '{node.node_id}' already exists")
        self._by_id[node.node_id] = node
        self._by_evidence.setdefault(node.evidence_id, []).append(node)
        return node

    def for_evidence(self, evidence_id: str) -> tuple[LineageNode, ...]:
        return tuple(
            sorted(self._by_evidence.get(evidence_id, []), key=lambda n: n.timestamp)
        )

    def get(self, node_id: str) -> LineageNode:
        node = self._by_id.get(node_id)
        if node is None:
            raise RecordNotFoundError(f"lineage node '{node_id}' not found")
        return node
