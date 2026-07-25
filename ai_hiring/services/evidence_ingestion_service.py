"""Evidence ingestion service.

Orchestrates the full pipeline with side effects: runs the pure normalization
pipeline, persists every artifact (provenance, immutable evidence, chunks,
quarantine), builds the lineage DAG, indexes chunks for deterministic search,
and emits one append-only audit event per pipeline stage. Returns the immutable
:class:`IngestedEvidence` aggregate.

No scoring, ranking, extraction-of-meaning, or inference occurs here.
"""

from __future__ import annotations

from typing import Optional

from ..common import Clock, IdFactory, new_id, utc_now
from ..domain.enums import ActorType, AuditEventType
from ..index.interfaces import IndexEntry
from ..index.search import tokenize
from ..normalization.chunking import ChunkConfig
from ..normalization.hashing import raw_hash as compute_raw_hash
from ..normalization.lineage import LineageGraph
from ..normalization.models import (
    IngestedEvidence,
    IngestionStage,
    LineageNode,
    QuarantineRecord,
    RawSubmission,
)
from ..normalization.pipeline import PipelineOutput, run_pipeline
from ..normalization.quarantine import QuarantineEngine
from ..errors import DuplicateEvidenceError, RecordNotFoundError
from ..repositories.interfaces import EvidenceRepository
from ..repositories.evidence_artifacts import (
    ChunkRepository,
    LineageRepository,
    ProvenanceRepository,
    QuarantineRepository,
)
from ..repositories.evidence_index_repository import EvidenceIndexRepository
from .audit_service import AuditService

# Pipeline stage -> audit event type.
_STAGE_EVENT = {
    IngestionStage.UPLOAD_RECEIVED: AuditEventType.EVIDENCE_UPLOAD_RECEIVED,
    IngestionStage.INTEGRITY_VALIDATED: AuditEventType.EVIDENCE_INTEGRITY_VALIDATED,
    IngestionStage.PROVENANCE_CAPTURED: AuditEventType.EVIDENCE_PROVENANCE_CAPTURED,
    IngestionStage.CONTENT_HASHED: AuditEventType.EVIDENCE_CONTENT_HASHED,
    IngestionStage.CONTENT_EXTRACTED: AuditEventType.EVIDENCE_CONTENT_EXTRACTED,
    IngestionStage.NORMALIZED: AuditEventType.EVIDENCE_NORMALIZED,
    IngestionStage.QUARANTINED: AuditEventType.EVIDENCE_PII_QUARANTINED,
    IngestionStage.CHUNKED: AuditEventType.EVIDENCE_CHUNK_CREATED,
    IngestionStage.FINALIZED: AuditEventType.EVIDENCE_VERSION_CREATED,
}


class EvidenceIngestionService:
    def __init__(
        self,
        evidence_repository: EvidenceRepository,
        provenance_repository: ProvenanceRepository,
        chunk_repository: ChunkRepository,
        quarantine_repository: QuarantineRepository,
        lineage_repository: LineageRepository,
        index_repository: EvidenceIndexRepository,
        audit_service: AuditService,
        *,
        quarantine_engine: Optional[QuarantineEngine] = None,
        chunk_config: ChunkConfig = ChunkConfig(),
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._evidence = evidence_repository
        self._prov = provenance_repository
        self._chunks = chunk_repository
        self._quarantine = quarantine_repository
        self._lineage = lineage_repository
        self._index = index_repository
        self._audit = audit_service
        self._engine = quarantine_engine or QuarantineEngine()
        self._chunk_config = chunk_config
        self._new_id = id_factory
        self._clock = clock

    def ingest(
        self,
        submission: RawSubmission,
        *,
        correlation_id: Optional[str] = None,
        parent_evidence_id: Optional[str] = None,
        allow_duplicate: bool = False,
    ) -> IngestedEvidence:
        """Ingest a raw submission into immutable, indexed, audited evidence."""
        corr = correlation_id or self._new_id("corr")
        actor_id = submission.uploader

        # Resolve version lineage.
        if parent_evidence_id is not None:
            latest = self._prov.latest_version(parent_evidence_id)
            if latest is None:
                raise RecordNotFoundError(
                    f"cannot revise unknown evidence '{parent_evidence_id}'"
                )
            evidence_id = parent_evidence_id
            version = latest.version + 1
            parent_version: Optional[int] = latest.version
            ancestor_version = latest.ancestor_version
            created_from: Optional[str] = parent_evidence_id
        else:
            evidence_id = self._new_id("ev")
            version, parent_version, ancestor_version, created_from = 1, None, 1, None

        # Duplicate detection (new uploads only) on raw content.
        if parent_evidence_id is None and not allow_duplicate:
            raw_h = compute_raw_hash(submission.content)
            dup = self._prov.find_duplicate(
                submission.candidate_id, submission.assessment_item_id, raw_h
            )
            if dup is not None:
                self._audit.record(
                    event_type=AuditEventType.EVIDENCE_DUPLICATE_DETECTED,
                    entity_type="evidence",
                    entity_id=dup.evidence_id,
                    actor_type=ActorType.SYSTEM,
                    actor_id=actor_id,
                    correlation_id=corr,
                    payload={"raw_hash": raw_h, "candidate_id": submission.candidate_id},
                )
                raise DuplicateEvidenceError(
                    f"identical content already ingested as evidence "
                    f"'{dup.evidence_id}' v{dup.version}"
                )

        # Run the pure pipeline.
        output = run_pipeline(
            submission,
            evidence_id=evidence_id,
            version=version,
            parent_version=parent_version,
            ancestor_version=ancestor_version,
            created_from=created_from,
            quarantine_engine=self._engine,
            chunk_config=self._chunk_config,
            id_factory=self._new_id,
            clock=self._clock,
            actor=actor_id,
        )

        # Persist artifacts.
        self._prov.add(output.provenance)
        self._evidence.add(output.normalized_evidence)
        for chunk in output.chunks:
            self._chunks.add(chunk)

        quarantine_record: Optional[QuarantineRecord] = None
        if output.quarantined:
            quarantine_record = QuarantineRecord(
                record_id=self._new_id("quar"),
                evidence_id=evidence_id,
                version=version,
                fields=output.quarantined,
                created_at=self._clock(),
            )
            self._quarantine.add(quarantine_record)

        # Audit one event per stage, chained by causation.
        prev_event_id = self._audit_stages(output, evidence_id, actor_id, corr)

        # Lineage DAG (per stage + chunks + evidence + index).
        node_ids = self._build_lineage(output, evidence_id, version, actor_id)

        # Index chunks for deterministic search.
        self._index_chunks(submission, output)
        index_event = self._audit.record(
            event_type=AuditEventType.EVIDENCE_INDEXED,
            entity_type="evidence",
            entity_id=evidence_id,
            actor_type=ActorType.SYSTEM,
            actor_id=actor_id,
            correlation_id=corr,
            causation_id=prev_event_id,
            new_state=IngestionStage.INDEXED.value,
            payload={"chunks_indexed": len(output.chunks)},
        )
        _ = index_event

        return IngestedEvidence(
            normalized_evidence=output.normalized_evidence,
            provenance=output.provenance,
            chunks=output.chunks,
            quarantine=quarantine_record,
            lineage_node_ids=node_ids,
            stage_results=output.stage_results,
        )

    # --- helpers -----------------------------------------------------------
    def _audit_stages(
        self, output: PipelineOutput, evidence_id: str, actor_id: str, corr: str
    ) -> Optional[str]:
        prev_event_id: Optional[str] = None
        for stage in output.stage_results:
            event_type = _STAGE_EVENT.get(stage.stage)
            if event_type is None:
                continue
            event = self._audit.record(
                event_type=event_type,
                entity_type="evidence",
                entity_id=evidence_id,
                actor_type=ActorType.SYSTEM,
                actor_id=actor_id,
                correlation_id=corr,
                causation_id=prev_event_id,
                new_state=stage.stage.value,
                payload={"stage": stage.stage.value, "summary_hash": stage.summary_hash},
            )
            prev_event_id = event.event_id
        return prev_event_id

    def _build_lineage(
        self, output: PipelineOutput, evidence_id: str, version: int, actor_id: str
    ) -> tuple[str, ...]:
        node_ids: list[str] = []
        prev_id: Optional[str] = None
        chunked_node_id: Optional[str] = None
        for stage in output.stage_results:
            node = LineageNode(
                node_id=self._new_id("lin"),
                evidence_id=evidence_id,
                version=version,
                operation=stage.stage.value,
                actor=actor_id,
                timestamp=self._clock(),
                parent_ids=(prev_id,) if prev_id else (),
            )
            self._lineage.add(node)
            node_ids.append(node.node_id)
            if stage.stage is IngestionStage.CHUNKED:
                chunked_node_id = node.node_id
            prev_id = node.node_id

        # Chunk nodes fan out from the CHUNKED operation node.
        for chunk in output.chunks:
            cnode = LineageNode(
                node_id=self._new_id("lin"),
                evidence_id=evidence_id,
                version=version,
                operation=f"CHUNK[{chunk.index}]",
                actor=actor_id,
                timestamp=self._clock(),
                parent_ids=(chunked_node_id,) if chunked_node_id else (),
            )
            self._lineage.add(cnode)
            node_ids.append(cnode.node_id)
        return tuple(node_ids)

    def _index_chunks(self, submission: RawSubmission, output: PipelineOutput) -> None:
        ne = output.normalized_evidence
        for chunk in output.chunks:
            entry = IndexEntry(
                evidence_id=ne.evidence_id,
                version=ne.version,
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.index,
                candidate_id=ne.candidate_id,
                role_id=ne.role_id,
                assessment_item_id=submission.assessment_item_id,
                assessment_type=submission.assessment_type,
                document_type=submission.declared_format.value,
                filename=submission.filename,
                keywords=tokenize(chunk.text),
                metadata=dict(submission.metadata),
                text=chunk.text,
            )
            self._index.index(entry)

    # --- reads -------------------------------------------------------------
    def get_evidence(self, evidence_id: str):
        return self._evidence.get(evidence_id)

    def lineage_graph(self, evidence_id: str) -> LineageGraph:
        return LineageGraph(nodes=self._lineage.for_evidence(evidence_id))
