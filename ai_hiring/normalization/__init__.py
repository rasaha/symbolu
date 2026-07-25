"""Evidence normalization subsystem (Phase 2).

Pure, deterministic building blocks for turning a raw candidate submission into
immutable, normalized, chunked, quarantined evidence with full provenance and
lineage. No scoring, embedding, or interpretation lives here.
"""

from __future__ import annotations

from .chunking import ChunkConfig, chunk_text, reconstruct
from .cleaners import NormalizationProfile, normalize_text
from .lineage import LineageGraph
from .models import (
    EvidenceChunk,
    EvidenceFormat,
    IngestedEvidence,
    IngestionStage,
    LineageNode,
    Provenance,
    QuarantineCategory,
    QuarantinedField,
    QuarantineRecord,
    RawSubmission,
    RelevanceClass,
    StageResult,
    TransformationStep,
)
from .pipeline import PipelineOutput, run_pipeline
from .quarantine import DEFAULT_POLICY, QuarantineEngine, QuarantinePolicy

__all__ = [
    "EvidenceFormat",
    "RawSubmission",
    "Provenance",
    "TransformationStep",
    "EvidenceChunk",
    "QuarantinedField",
    "QuarantineRecord",
    "QuarantineCategory",
    "RelevanceClass",
    "LineageNode",
    "IngestionStage",
    "StageResult",
    "IngestedEvidence",
    "NormalizationProfile",
    "normalize_text",
    "ChunkConfig",
    "chunk_text",
    "reconstruct",
    "QuarantineEngine",
    "QuarantinePolicy",
    "DEFAULT_POLICY",
    "LineageGraph",
    "PipelineOutput",
    "run_pipeline",
]
