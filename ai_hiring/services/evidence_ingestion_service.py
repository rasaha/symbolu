"""Evidence ingestion service (Phase 2.5 hardened).

Runs the pure pipeline, then **fails closed**: only successfully extracted,
integrity-verified, non-empty, provenance-linked evidence is persisted, indexed,
and marked COMPLETED. Any failure leaves no searchable/completed evidence and no
evaluation-eligible artifact.

Two audit streams share one correlation id:
* the pipeline stage events remain keyed to ``evidence_id`` (unchanged 10-event
  success history — Phase-2 compatible);
* the ingestion *lifecycle* events (received, extraction outcome, reconstruction,
  lineage, completed/failed) are keyed to ``ingestion_id`` so the failure path
  has a coherent trail even when no evidence is ever created.

No scoring, ranking, embeddings, OCR, or inference is performed here.
"""

from __future__ import annotations

import hmac
from typing import Optional

from ..common import Clock, IdFactory, new_id, utc_now
from ..domain.enums import ActorType, AuditEventType
from ..errors import (
    ArchiveSafetyError,
    ContentExtractionError,
    DuplicateEvidenceError,
    EmptyExtractionError,
    EncryptedContentError,
    HashMismatchError,
    IngestionError,
    IntegrityValidationError,
    ManualReviewRequiredError,
    ReconstructionError,
    RecordNotFoundError,
    ResourceLimitError,
    UnsupportedFormatError,
)
from ..index.interfaces import IndexEntry
from ..index.search import tokenize
from ..normalization.chunking import ChunkConfig
from ..normalization.extraction_status import ExtractionStatus
from ..normalization.hashing import normalized_hash as hash_normalized
from ..normalization.hashing import raw_hash as compute_raw_hash
from ..normalization.lineage import LineageGraph
from ..normalization.limits import DEFAULT_LIMITS, EvidenceLimits
from ..normalization.models import (
    IngestedEvidence,
    IngestionStage,
    IngestionState,
    LineageNode,
    QuarantineRecord,
    RawSubmission,
)
from ..normalization.pipeline import PipelineOutput, run_pipeline
from ..normalization.quarantine import QuarantineEngine
from ..normalization.reconstruction import verify_reconstruction
from ..policies import lineage_integrity_policy as lineage_policy
from ..policies.duplicate_policy import (
    DEFAULT_DUPLICATE_POLICY,
    DuplicateClassification,
    DuplicateMatch,
    DuplicatePolicy,
    EvidenceContext,
)
from ..repositories.evidence_artifacts import (
    ChunkRepository,
    LineageRepository,
    ProvenanceRepository,
    QuarantineRepository,
)
from ..repositories.evidence_index_repository import EvidenceIndexRepository
from ..repositories.interfaces import EvidenceRepository
from .audit_service import AuditService

# Pipeline stage -> audit event type (keyed to evidence_id; Phase-2 compatible).
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

# Exception type -> (failure audit event, extraction status, terminal state).
_FAILURE_MAP = [
    (EncryptedContentError, AuditEventType.EVIDENCE_EXTRACTION_ENCRYPTED,
     ExtractionStatus.ENCRYPTED, IngestionState.FAILED),
    (ManualReviewRequiredError, AuditEventType.EVIDENCE_MANUAL_REVIEW_REQUIRED,
     ExtractionStatus.MANUAL_REVIEW_REQUIRED, IngestionState.REVIEW_REQUIRED),
    (UnsupportedFormatError, AuditEventType.EVIDENCE_EXTRACTION_UNSUPPORTED,
     ExtractionStatus.UNSUPPORTED, IngestionState.FAILED),
    (ArchiveSafetyError, AuditEventType.EVIDENCE_RESOURCE_LIMIT_EXCEEDED,
     ExtractionStatus.RESOURCE_LIMIT_EXCEEDED, IngestionState.FAILED),
    (ResourceLimitError, AuditEventType.EVIDENCE_RESOURCE_LIMIT_EXCEEDED,
     ExtractionStatus.RESOURCE_LIMIT_EXCEEDED, IngestionState.FAILED),
    (IntegrityValidationError, AuditEventType.EVIDENCE_RESOURCE_LIMIT_EXCEEDED,
     ExtractionStatus.RESOURCE_LIMIT_EXCEEDED, IngestionState.FAILED),
    (ContentExtractionError, AuditEventType.EVIDENCE_EXTRACTION_MALFORMED,
     ExtractionStatus.MALFORMED, IngestionState.FAILED),
    (IngestionError, AuditEventType.EVIDENCE_EXTRACTION_MALFORMED,
     ExtractionStatus.MALFORMED, IngestionState.FAILED),
]


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
        limits: EvidenceLimits = DEFAULT_LIMITS,
        duplicate_policy: DuplicatePolicy = DEFAULT_DUPLICATE_POLICY,
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
        self._limits = limits
        self._dup_policy = duplicate_policy
        self._new_id = id_factory
        self._clock = clock

    # --- lifecycle audit (keyed to ingestion_id) ---------------------------
    def _life(self, event_type, ingestion_id, corr, actor, prev, *,
              new_state=None, payload=None, entity_id=None):
        return self._audit.record(
            event_type=event_type, entity_type="ingestion",
            entity_id=entity_id or ingestion_id, actor_type=ActorType.SYSTEM,
            actor_id=actor, correlation_id=corr, causation_id=prev,
            new_state=new_state, payload=payload or {},
        )

    def ingest(
        self,
        submission: RawSubmission,
        *,
        correlation_id: Optional[str] = None,
        parent_evidence_id: Optional[str] = None,
        allow_duplicate: bool = False,
    ) -> IngestedEvidence:
        """Ingest a submission into immutable, verified, indexed evidence (fail-closed)."""
        corr = correlation_id or self._new_id("corr")
        ingestion_id = self._new_id("ing")
        actor = submission.uploader
        is_revision = parent_evidence_id is not None

        # Lifecycle: RECEIVED -> VALIDATING -> HASHED (present on success and failure).
        ev = self._life(AuditEventType.EVIDENCE_INGESTION_RECEIVED, ingestion_id, corr,
                        actor, None, new_state=IngestionState.RECEIVED.value,
                        payload={"format": submission.declared_format.value})
        ev = self._life(AuditEventType.EVIDENCE_UPLOAD_RECEIVED, ingestion_id, corr, actor,
                        ev.event_id, new_state=IngestionState.RECEIVED.value)
        ev = self._life(AuditEventType.EVIDENCE_INTEGRITY_VALIDATED, ingestion_id, corr,
                        actor, ev.event_id, new_state=IngestionState.VALIDATING.value)
        ev = self._life(AuditEventType.EVIDENCE_PROVENANCE_CAPTURED, ingestion_id, corr,
                        actor, ev.event_id)

        # Resolve version lineage.
        if is_revision:
            latest = self._prov.latest_version(parent_evidence_id)
            if latest is None:
                self._fail(ingestion_id, corr, actor, ev.event_id,
                           AuditEventType.EVIDENCE_INGESTION_FAILED, "unknown parent")
                raise RecordNotFoundError(f"cannot revise unknown evidence '{parent_evidence_id}'")
            evidence_id = parent_evidence_id
            version, parent_version, ancestor_version, created_from = (
                latest.version + 1, latest.version, latest.ancestor_version, parent_evidence_id)
        else:
            evidence_id = self._new_id("ev")
            version, parent_version, ancestor_version, created_from = 1, None, 1, None

        raw_h = compute_raw_hash(submission.content)
        ev = self._life(AuditEventType.EVIDENCE_CONTENT_HASHED, ingestion_id, corr, actor,
                        ev.event_id, payload={"raw_hash": raw_h})

        # Exact same-context binary duplicate -> block (idempotency).
        if not is_revision and not allow_duplicate:
            exact = self._prov.find_same_stage_raw(
                submission.tenant_id, submission.candidate_id,
                submission.assessment_item_id, raw_h)
            if exact is not None:
                self._audit.record(
                    event_type=AuditEventType.EVIDENCE_DUPLICATE_DETECTED,
                    entity_type="evidence", entity_id=exact.evidence_id,
                    actor_type=ActorType.SYSTEM, actor_id=actor, correlation_id=corr,
                    causation_id=ev.event_id,
                    payload={"classification": DuplicateClassification.EXACT_BINARY_DUPLICATE.value})
                self._fail(ingestion_id, corr, actor, ev.event_id,
                           AuditEventType.EVIDENCE_INGESTION_FAILED, "exact duplicate")
                raise DuplicateEvidenceError(
                    f"identical content already ingested as evidence '{exact.evidence_id}'")

        # Run the pure pipeline; classify any failure and fail closed.
        try:
            output = run_pipeline(
                submission, evidence_id=evidence_id, version=version,
                parent_version=parent_version, ancestor_version=ancestor_version,
                created_from=created_from, quarantine_engine=self._engine,
                chunk_config=self._chunk_config, limits=self._limits,
                id_factory=self._new_id, clock=self._clock, actor=actor)
        except Exception as exc:  # noqa: BLE001 - classified + re-raised
            self._classify_and_fail(exc, ingestion_id, corr, actor, ev.event_id)
            raise

        # Empty extraction fails closed — never accepted as evidence.
        if output.extraction_result.status is ExtractionStatus.EMPTY:
            self._life(AuditEventType.EVIDENCE_EXTRACTION_EMPTY, ingestion_id, corr, actor,
                       ev.event_id)
            self._fail(ingestion_id, corr, actor, ev.event_id,
                       AuditEventType.EVIDENCE_INGESTION_FAILED, "empty extraction")
            raise EmptyExtractionError(
                "extraction produced no content after normalization/quarantine")

        # Integrity: reconstruction + hash checks BEFORE any persistence.
        recon = verify_reconstruction(
            output.chunks, expected_normalized_hash=output.normalized_hash,
            evidence_id=evidence_id, version=version)
        if not recon.ok:
            self._life(AuditEventType.EVIDENCE_RECONSTRUCTION_FAILED, ingestion_id, corr,
                       actor, ev.event_id, payload={"reason": recon.reason_code})
            self._fail(ingestion_id, corr, actor, ev.event_id,
                       AuditEventType.EVIDENCE_INTEGRITY_FAILED, recon.reason_code)
            raise ReconstructionError(recon.reason_code)

        if not (hmac.compare_digest(output.raw_hash, output.provenance.raw_hash)
                and hmac.compare_digest(
                    hash_normalized(output.normalized_text), output.provenance.normalized_hash)):
            self._life(AuditEventType.EVIDENCE_INTEGRITY_FAILED, ingestion_id, corr, actor,
                       ev.event_id)
            self._fail(ingestion_id, corr, actor, ev.event_id,
                       AuditEventType.EVIDENCE_INGESTION_FAILED, "hash mismatch")
            raise HashMismatchError("raw/normalized hash mismatch at ingestion")

        # Classify duplicates against *prior* evidence (before persisting this one).
        dup_class = self._classify_duplicate(submission, output, is_revision)

        # --- all checks passed: persist atomically, then index -------------
        self._prov.add(output.provenance)
        self._evidence.add(output.normalized_evidence)
        for chunk in output.chunks:
            self._chunks.add(chunk)
        quarantine_record: Optional[QuarantineRecord] = None
        if output.quarantined:
            quarantine_record = QuarantineRecord(
                record_id=self._new_id("quar"), evidence_id=evidence_id, version=version,
                tenant_id=submission.tenant_id, fields=output.quarantined,
                created_at=self._clock())
            self._quarantine.add(quarantine_record)

        # Pipeline stage events keyed to evidence_id (unchanged 10-event history).
        prev_stage = self._audit_stages(output, evidence_id, actor, corr)

        node_ids = self._build_lineage(output, submission, evidence_id, version)
        self._life(AuditEventType.EVIDENCE_LINEAGE_VALIDATED, ingestion_id, corr, actor,
                   ev.event_id, payload={"nodes": len(node_ids)})

        self._index_chunks(submission, output)
        self._audit.record(
            event_type=AuditEventType.EVIDENCE_INDEXED, entity_type="evidence",
            entity_id=evidence_id, actor_type=ActorType.SYSTEM, actor_id=actor,
            correlation_id=corr, causation_id=prev_stage,
            new_state=IngestionStage.INDEXED.value,
            payload={"chunks_indexed": len(output.chunks)})

        # Duplicate classification audit (non-blocking; safe identifiers only).
        if dup_class not in (DuplicateClassification.NOT_DUPLICATE,
                             DuplicateClassification.NEW_VERSION):
            self._life(AuditEventType.EVIDENCE_DUPLICATE_CLASSIFIED, ingestion_id, corr,
                       actor, ev.event_id, payload={"classification": dup_class.value})

        # Success lifecycle: extraction outcome, reconstruction, completed.
        succ_event = (AuditEventType.EVIDENCE_EXTRACTION_WARNING
                      if output.extraction_result.status
                      is ExtractionStatus.SUCCEEDED_WITH_WARNINGS
                      else AuditEventType.EVIDENCE_EXTRACTION_SUCCEEDED)
        self._life(succ_event, ingestion_id, corr, actor, ev.event_id,
                   payload={"warnings": list(output.extraction_result.warnings)})
        self._life(AuditEventType.EVIDENCE_RECONSTRUCTION_VALIDATED, ingestion_id, corr,
                   actor, ev.event_id)
        self._life(AuditEventType.EVIDENCE_INGESTION_COMPLETED, ingestion_id, corr, actor,
                   ev.event_id, new_state=IngestionState.COMPLETED.value)

        return IngestedEvidence(
            normalized_evidence=output.normalized_evidence, provenance=output.provenance,
            chunks=output.chunks, quarantine=quarantine_record, lineage_node_ids=node_ids,
            stage_results=output.stage_results, extraction_result=output.extraction_result,
            ingestion_state=IngestionState.COMPLETED,
            duplicate_classification=dup_class.value, ingestion_id=ingestion_id)

    # --- failure helpers ---------------------------------------------------
    def _fail(self, ingestion_id, corr, actor, prev, event_type, reason):
        self._life(AuditEventType.EVIDENCE_ELIGIBILITY_BLOCKED, ingestion_id, corr, actor,
                   prev, payload={"reason": reason})
        self._life(event_type, ingestion_id, corr, actor, prev,
                   new_state=IngestionState.FAILED.value, payload={"reason": reason})

    def _classify_and_fail(self, exc, ingestion_id, corr, actor, prev):
        for exc_type, event_type, status, state in _FAILURE_MAP:
            if isinstance(exc, exc_type):
                self._life(event_type, ingestion_id, corr, actor, prev,
                           new_state=state.value, payload={"status": status.value})
                self._life(AuditEventType.EVIDENCE_ELIGIBILITY_BLOCKED, ingestion_id, corr,
                           actor, prev, payload={"status": status.value})
                final = (AuditEventType.EVIDENCE_MANUAL_REVIEW_REQUIRED
                         if state is IngestionState.REVIEW_REQUIRED
                         else AuditEventType.EVIDENCE_INGESTION_FAILED)
                self._life(final, ingestion_id, corr, actor, prev, new_state=state.value)
                return
        # Unknown -> generic failure (still fail closed).
        self._life(AuditEventType.EVIDENCE_INGESTION_FAILED, ingestion_id, corr, actor, prev,
                   new_state=IngestionState.FAILED.value)

    # --- helpers -----------------------------------------------------------
    def _audit_stages(self, output: PipelineOutput, evidence_id, actor, corr):
        prev: Optional[str] = None
        for stage in output.stage_results:
            event_type = _STAGE_EVENT.get(stage.stage)
            if event_type is None:
                continue
            event = self._audit.record(
                event_type=event_type, entity_type="evidence", entity_id=evidence_id,
                actor_type=ActorType.SYSTEM, actor_id=actor, correlation_id=corr,
                causation_id=prev, new_state=stage.stage.value,
                payload={"stage": stage.stage.value, "summary_hash": stage.summary_hash})
            prev = event.event_id
        return prev

    def _build_lineage(self, output, submission, evidence_id, version):
        node_ids: list[str] = []
        existing: list[LineageNode] = list(self._lineage.for_evidence(evidence_id))
        prev_id: Optional[str] = existing[-1].node_id if existing else None
        chunked_id: Optional[str] = None
        for stage in output.stage_results:
            node = LineageNode(
                node_id=self._new_id("lin"), evidence_id=evidence_id, version=version,
                operation=stage.stage.value, actor=submission.uploader,
                timestamp=self._clock(), parent_ids=(prev_id,) if prev_id else (),
                tenant_id=submission.tenant_id, candidate_id=submission.candidate_id,
                application_id=submission.application_id)
            lineage_policy.validate_new_node(node, tuple(existing))
            self._lineage.add(node)
            existing.append(node)
            node_ids.append(node.node_id)
            if stage.stage is IngestionStage.CHUNKED:
                chunked_id = node.node_id
            prev_id = node.node_id
        for chunk in output.chunks:
            cnode = LineageNode(
                node_id=self._new_id("lin"), evidence_id=evidence_id, version=version,
                operation=f"CHUNK[{chunk.index}]", actor=submission.uploader,
                timestamp=self._clock(), parent_ids=(chunked_id,) if chunked_id else (),
                tenant_id=submission.tenant_id, candidate_id=submission.candidate_id,
                application_id=submission.application_id)
            lineage_policy.validate_new_node(cnode, tuple(existing))
            self._lineage.add(cnode)
            existing.append(cnode)
            node_ids.append(cnode.node_id)
        return tuple(node_ids)

    def _index_chunks(self, submission, output: PipelineOutput):
        ne = output.normalized_evidence
        for chunk in output.chunks:
            self._index.index(IndexEntry(
                evidence_id=ne.evidence_id, version=ne.version, chunk_id=chunk.chunk_id,
                chunk_index=chunk.index, candidate_id=ne.candidate_id, role_id=ne.role_id,
                assessment_item_id=submission.assessment_item_id,
                assessment_type=submission.assessment_type,
                document_type=submission.declared_format.value, filename=submission.filename,
                keywords=tokenize(chunk.text), metadata=dict(submission.metadata),
                text=chunk.text, tenant_id=ne.tenant_id, application_id=ne.application_id))

    def _classify_duplicate(self, submission, output, is_revision) -> DuplicateClassification:
        ctx = EvidenceContext(
            tenant_id=submission.tenant_id, candidate_id=submission.candidate_id,
            application_id=submission.application_id, role_id=submission.role_id,
            assessment_id=submission.assessment_item_id, uploader=submission.uploader)
        prior = self._prov.find_tenant_hash(
            submission.tenant_id, output.raw_hash, output.normalized_hash)
        match = None
        if prior is not None and prior.evidence_id != output.normalized_evidence.evidence_id:
            match = DuplicateMatch(
                context=EvidenceContext(
                    tenant_id=prior.tenant_id, candidate_id=prior.candidate_id,
                    application_id=prior.application_id, role_id=prior.role_id,
                    assessment_id=prior.assessment_item_id, uploader=prior.uploader),
                raw_hash=prior.raw_hash, normalized_hash=prior.normalized_hash,
                evidence_id=prior.evidence_id)
        decision = self._dup_policy.classify(
            new_context=ctx, new_raw_hash=output.raw_hash,
            new_normalized_hash=output.normalized_hash, is_revision=is_revision, match=match)
        return decision.classification

    # --- reads -------------------------------------------------------------
    def get_evidence(self, evidence_id: str):
        return self._evidence.get(evidence_id)

    def lineage_graph(self, evidence_id: str) -> LineageGraph:
        return LineageGraph(nodes=self._lineage.for_evidence(evidence_id))
