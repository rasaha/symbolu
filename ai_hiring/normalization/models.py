"""Phase 2 domain models — the immutable evidence substrate.

These models extend the Phase-1 contracts *without modifying them*. The Phase-1
``NormalizedEvidence`` remains the canonical unit that downstream AI modules
consume; the models here carry the richer ingestion metadata (provenance,
chunks, quarantine, lineage) alongside it, keyed by ``evidence_id`` + ``version``.

All models are frozen (immutable). No scoring, embedding, or interpretation
concept appears anywhere in this module.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Mapping, Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..domain.evidence import NormalizedEvidence
from ..errors import DomainValidationError


class EvidenceFormat(str, Enum):
    """Supported evidence formats. Video/audio are not parsed — only transcripts."""

    TEXT = "TEXT"
    PDF = "PDF"
    DOCX = "DOCX"
    MARKDOWN = "MARKDOWN"
    SOURCE_CODE = "SOURCE_CODE"
    JSON = "JSON"
    CSV = "CSV"
    INTERVIEW_TRANSCRIPT = "INTERVIEW_TRANSCRIPT"
    WORK_SAMPLE = "WORK_SAMPLE"
    PORTFOLIO_ARTIFACT = "PORTFOLIO_ARTIFACT"
    STRUCTURED_RESPONSE = "STRUCTURED_RESPONSE"


# Formats whose content is a set of named fields (subject to field quarantine).
STRUCTURED_FORMATS = frozenset(
    {EvidenceFormat.JSON, EvidenceFormat.CSV, EvidenceFormat.STRUCTURED_RESPONSE}
)
# Binary formats requiring text extraction.
BINARY_FORMATS = frozenset({EvidenceFormat.PDF, EvidenceFormat.DOCX})
# Formats whose whitespace is semantically significant (use the code-safe profile).
WHITESPACE_SENSITIVE_FORMATS = frozenset(
    {EvidenceFormat.SOURCE_CODE, EvidenceFormat.JSON, EvidenceFormat.CSV}
)


class RelevanceClass(str, Enum):
    JOB_RELEVANT = "JOB_RELEVANT"
    NON_JOB_RELEVANT = "NON_JOB_RELEVANT"
    UNKNOWN = "UNKNOWN"


class QuarantineCategory(str, Enum):
    PROHIBITED = "PROHIBITED"
    NON_JOB_RELEVANT = "NON_JOB_RELEVANT"
    UNKNOWN = "UNKNOWN"


class IngestionStage(str, Enum):
    """The ordered pipeline stages, each of which emits its own audit event."""

    UPLOAD_RECEIVED = "UPLOAD_RECEIVED"
    INTEGRITY_VALIDATED = "INTEGRITY_VALIDATED"
    PROVENANCE_CAPTURED = "PROVENANCE_CAPTURED"
    CONTENT_HASHED = "CONTENT_HASHED"
    CONTENT_EXTRACTED = "CONTENT_EXTRACTED"
    NORMALIZED = "NORMALIZED"
    QUARANTINED = "QUARANTINED"
    CHUNKED = "CHUNKED"
    FINALIZED = "FINALIZED"
    INDEXED = "INDEXED"


class RawSubmission(DomainModel):
    """An immutable raw candidate submission entering the pipeline.

    ``content`` holds the raw bytes. For structured formats a caller may instead
    (or additionally) provide ``fields`` directly; otherwise fields are parsed
    from ``content``.
    """

    candidate_id: str
    role_id: str
    assessment_item_id: str = ""
    declared_format: EvidenceFormat
    filename: str = ""
    uploader: str
    source_uri: str = ""
    assessment_type: str = ""
    content: bytes = b""
    fields: Optional[Mapping[str, str]] = None
    metadata: Mapping[str, str] = Field(default_factory=dict)
    submitted_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate(self) -> "RawSubmission":
        if not self.candidate_id.strip():
            raise DomainValidationError("candidate_id is required")
        if not self.role_id.strip():
            raise DomainValidationError("role_id is required")
        if not self.uploader.strip():
            raise DomainValidationError("uploader is required")
        if not self.content and not self.fields:
            raise DomainValidationError("a submission must carry content or fields")
        return self

    @classmethod
    def from_text(cls, text: str, **kwargs: object) -> "RawSubmission":
        return cls(content=text.encode("utf-8"), **kwargs)  # type: ignore[arg-type]


class TransformationStep(DomainModel):
    """One recorded, provenance-preserving transformation in the pipeline."""

    operation: str
    actor: str
    timestamp: datetime = Field(default_factory=utc_now)
    detail: str = ""


class Provenance(DomainModel):
    """The complete, immutable provenance of one evidence version.

    No pipeline stage may destroy provenance; each stage appends a
    :class:`TransformationStep` to ``transformation_history``.
    """

    provenance_id: str
    evidence_id: str
    version: int
    candidate_id: str
    role_id: str
    assessment_item_id: str = ""
    original_filename: str = ""
    uploader: str
    upload_timestamp: datetime
    original_format: EvidenceFormat
    raw_hash: str
    normalized_hash: str
    content_length: int
    source_uri: str = ""
    parent_version: Optional[int] = None
    ancestor_version: int = 1
    created_from: Optional[str] = None
    transformation_history: tuple[TransformationStep, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate(self) -> "Provenance":
        for req in ("provenance_id", "evidence_id", "candidate_id", "role_id",
                    "uploader", "raw_hash", "normalized_hash"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required in provenance")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        if self.content_length < 0:
            raise DomainValidationError("content_length must be >= 0")
        return self


class EvidenceChunk(DomainModel):
    """A contiguous, immutable chunk of normalized evidence text.

    Concatenating a version's chunks in ``index`` order reproduces the
    normalized content exactly.
    """

    chunk_id: str
    evidence_id: str
    version: int
    index: int
    offset: int
    length: int
    hash: str
    chunk_type: str
    text: str

    @model_validator(mode="after")
    def _validate(self) -> "EvidenceChunk":
        if self.offset < 0 or self.length < 0:
            raise DomainValidationError("offset and length must be >= 0")
        if self.length != len(self.text):
            raise DomainValidationError("chunk length must equal len(text)")
        return self


class QuarantinedField(DomainModel):
    """A field withheld from evaluation. Never deleted; never exposed downstream."""

    field_name: str
    category: QuarantineCategory
    reason: str = ""
    value: str = ""  # preserved only inside the quarantine store


class QuarantineRecord(DomainModel):
    """The set of fields quarantined for one evidence version."""

    record_id: str
    evidence_id: str
    version: int
    fields: tuple[QuarantinedField, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)

    @property
    def prohibited(self) -> tuple[QuarantinedField, ...]:
        return tuple(f for f in self.fields if f.category is QuarantineCategory.PROHIBITED)


class LineageNode(DomainModel):
    """One node in the evidence lineage DAG.

    Children are derived at read time (a node's children are the nodes that name
    it as a parent), so nodes stay immutable.
    """

    node_id: str
    evidence_id: str
    version: int
    operation: str
    actor: str
    timestamp: datetime = Field(default_factory=utc_now)
    parent_ids: tuple[str, ...] = ()


class StageResult(DomainModel):
    """The outcome of one pipeline stage (for per-stage auditing)."""

    stage: IngestionStage
    ok: bool = True
    summary_hash: str = ""
    detail: str = ""


class IngestedEvidence(DomainModel):
    """The aggregate result of a successful ingestion.

    ``normalized_evidence`` is the Phase-1 contract downstream modules consume;
    everything else is the supporting substrate produced this phase.
    """

    normalized_evidence: NormalizedEvidence
    provenance: Provenance
    chunks: tuple[EvidenceChunk, ...]
    quarantine: Optional[QuarantineRecord] = None
    lineage_node_ids: tuple[str, ...] = ()
    stage_results: tuple[StageResult, ...] = ()
    duplicate_of: Optional[str] = None

    @property
    def evidence_id(self) -> str:
        return self.normalized_evidence.evidence_id

    @property
    def version(self) -> int:
        return self.normalized_evidence.version

    @property
    def raw_hash(self) -> str:
        return self.provenance.raw_hash

    @property
    def normalized_hash(self) -> str:
        return self.provenance.normalized_hash

    @property
    def normalized_text(self) -> str:
        """Reconstruct the normalized text from the chunks (exact)."""
        return "".join(c.text for c in sorted(self.chunks, key=lambda c: c.index))
