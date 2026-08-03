"""The evidence normalization pipeline (pure transformation).

Runs exactly the specified stage order and returns all artifacts, with **no
side effects** — persistence, auditing, indexing, and lineage are the
:class:`~ugence_ai_hiring.services.evidence_ingestion_service.EvidenceIngestionService`'s
job. Keeping the pipeline pure makes it deterministic and unit-testable.

Pipeline order::

    Raw Submission -> Integrity Validation -> Provenance Capture -> Hash
    Generation -> Content Extraction -> Normalization -> PII / Non-job-relevant
    Quarantine -> Evidence Chunking -> Immutable NormalizedEvidence

(The Search Index and final Audit stage are applied by the service.)

No scoring, embedding, or interpretation occurs anywhere in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..common import Clock, IdFactory, canonical_hash, new_id, utc_now
from ..domain.evidence import NormalizedEvidence
from ..errors import IntegrityValidationError
from . import parsers, provenance as prov
from .chunking import ChunkConfig, chunk_text
from .cleaners import NormalizationProfile, normalize_text
from .extraction_status import ELIGIBLE_STATUSES, ExtractionResult, ExtractionStatus
from .hashing import normalized_hash as hash_normalized
from .hashing import raw_hash as hash_raw
from .limits import DEFAULT_LIMITS, EvidenceLimits, check_input_size
from .models import (
    WHITESPACE_SENSITIVE_FORMATS,
    EvidenceChunk,
    EvidenceFormat,
    IngestionStage,
    Provenance,
    QuarantinedField,
    RawSubmission,
    StageResult,
)
from .quarantine import QuarantineEngine

MAX_CONTENT_BYTES = 25 * 1024 * 1024  # 25 MiB integrity ceiling


def _profile_for(fmt: EvidenceFormat) -> NormalizationProfile:
    if fmt in WHITESPACE_SENSITIVE_FORMATS:
        return NormalizationProfile.CODE_SAFE
    return NormalizationProfile.PROSE


def _serialize_fields(fields: dict[str, str]) -> str:
    """Deterministic canonical text for a set of clean structured fields."""
    return "\n".join(f"{k}={fields[k]}" for k in sorted(fields))


@dataclass(frozen=True)
class PipelineOutput:
    normalized_evidence: NormalizedEvidence
    provenance: Provenance
    chunks: tuple[EvidenceChunk, ...]
    quarantined: tuple[QuarantinedField, ...]
    raw_hash: str
    normalized_hash: str
    normalized_text: str
    stage_results: tuple[StageResult, ...]
    extraction_result: ExtractionResult


def run_pipeline(
    submission: RawSubmission,
    *,
    evidence_id: Optional[str] = None,
    version: int = 1,
    parent_version: Optional[int] = None,
    ancestor_version: int = 1,
    created_from: Optional[str] = None,
    quarantine_engine: Optional[QuarantineEngine] = None,
    chunk_config: ChunkConfig = ChunkConfig(),
    max_content_bytes: int = MAX_CONTENT_BYTES,
    limits: EvidenceLimits = DEFAULT_LIMITS,
    id_factory: IdFactory = new_id,
    clock: Clock = utc_now,
    actor: str = "system:ingestion",
) -> PipelineOutput:
    """Run the full normalization pipeline and return its artifacts."""
    engine = quarantine_engine or QuarantineEngine()
    evidence_id = evidence_id or id_factory("ev")
    stages: list[StageResult] = []

    def record(stage: IngestionStage, summary: object, detail: str = "") -> None:
        stages.append(
            StageResult(stage=stage, summary_hash=canonical_hash({"s": summary}), detail=detail)
        )

    # 1. Upload received.
    record(IngestionStage.UPLOAD_RECEIVED, submission.filename or submission.candidate_id,
           f"format={submission.declared_format.value}")

    # 2. Integrity validation.
    if len(submission.content) > max_content_bytes:
        raise IntegrityValidationError(
            f"submission exceeds {max_content_bytes} byte integrity ceiling"
        )
    check_input_size(len(submission.content), limits)
    if not submission.content and not submission.fields:
        raise IntegrityValidationError("empty submission")
    record(IngestionStage.INTEGRITY_VALIDATED, len(submission.content), "size + non-empty ok")

    # 3. Provenance capture (source metadata; hashes appended as computed).
    record(IngestionStage.PROVENANCE_CAPTURED, submission.uploader, "source metadata captured")

    # 4. Hash generation (raw).
    raw_h = hash_raw(submission.content)
    record(IngestionStage.CONTENT_HASHED, raw_h, "raw_hash")

    # 5. Content extraction.
    extracted = parsers.extract(
        submission.declared_format,
        submission.content,
        dict(submission.fields) if submission.fields else None,
        limits,
    )
    record(IngestionStage.CONTENT_EXTRACTED, extracted.is_structured,
           "structured" if extracted.is_structured else "unstructured")

    profile = _profile_for(submission.declared_format)

    # 6. Normalization + 7. Quarantine.
    if extracted.is_structured:
        normalized_fields = {
            k: normalize_text(v, NormalizationProfile.CODE_SAFE)
            for k, v in extracted.fields.items()
        }
        record(IngestionStage.NORMALIZED, sorted(normalized_fields), "fields normalized")
        q = engine.apply(normalized_fields)
        normalized_text = _serialize_fields(q.clean_fields)
        quarantined = q.quarantined
    else:
        normalized_text = normalize_text(extracted.text, profile)
        record(IngestionStage.NORMALIZED, len(normalized_text), f"profile={profile.value}")
        quarantined = ()
    record(IngestionStage.QUARANTINED, [f.field_name for f in quarantined],
           f"{len(quarantined)} field(s) quarantined")

    norm_h = hash_normalized(normalized_text)

    # Build immutable provenance with a transformation step per completed stage.
    provenance = prov.build_provenance(
        submission,
        evidence_id=evidence_id,
        version=version,
        raw_hash=raw_h,
        normalized_hash=norm_h,
        content_length=len(normalized_text),
        parent_version=parent_version,
        ancestor_version=ancestor_version,
        created_from=created_from,
        id_factory=id_factory,
        clock=clock,
    )
    for stage in stages:
        provenance = prov.append_step(
            provenance, operation=stage.stage.value, actor=actor,
            detail=stage.detail, timestamp=clock(),
        )

    # 8. Chunking.
    chunks = chunk_text(
        normalized_text, evidence_id, version, config=chunk_config, id_factory=id_factory,
        tenant_id=submission.tenant_id, candidate_id=submission.candidate_id,
    )
    record(IngestionStage.CHUNKED, len(chunks), f"{len(chunks)} chunk(s)")
    provenance = prov.append_step(
        provenance, operation=IngestionStage.CHUNKED.value, actor=actor,
        detail=f"{len(chunks)} chunk(s)", timestamp=clock(),
    )

    # 9. Immutable NormalizedEvidence (the Phase-1 contract downstream consumes).
    normalized_evidence = NormalizedEvidence(
        evidence_id=evidence_id,
        candidate_id=submission.candidate_id,
        role_id=submission.role_id,
        assessment_item_id=submission.assessment_item_id or None,
        content_hash=norm_h,
        source_ref=submission.source_uri or submission.filename,
        index_ref=f"{evidence_id}:{version}",
        job_relevant=True,
        format=submission.declared_format.value,
        provenance=provenance.provenance_id,
        tenant_id=submission.tenant_id,
        application_id=submission.application_id,
        created_at=clock(),
        version=version,
    )
    record(IngestionStage.FINALIZED, normalized_evidence.evidence_id,
           f"version={version}")

    # Explicit extraction outcome — success is never inferred from a string.
    warnings = extracted.warnings
    if not normalized_text:
        status = ExtractionStatus.EMPTY
    elif warnings:
        status = ExtractionStatus.SUCCEEDED_WITH_WARNINGS
    else:
        status = ExtractionStatus.SUCCEEDED
    extraction_result = ExtractionResult(
        status=status,
        format=submission.declared_format.value,
        extractor_name=f"parser:{submission.declared_format.value}",
        characters_extracted=len(normalized_text),
        bytes_received=len(submission.content),
        warnings=warnings,
        failure_code=None if status in ELIGIBLE_STATUSES else "EXTRACTION_EMPTY",
        failure_detail="" if normalized_text else "no content after normalization/quarantine",
        evaluation_eligible=bool(normalized_text) and status in ELIGIBLE_STATUSES,
    )

    return PipelineOutput(
        normalized_evidence=normalized_evidence,
        provenance=provenance,
        chunks=chunks,
        quarantined=quarantined,
        raw_hash=raw_h,
        normalized_hash=norm_h,
        normalized_text=normalized_text,
        stage_results=tuple(stages),
        extraction_result=extraction_result,
    )
