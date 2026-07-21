"""
Versioned, serializable RetrievalRecord schema for TAP-E2.

The RetrievalRecord is the sole output of the Trusted Retrieval Layer. It selects
candidate evidence; it does NOT judge factual correctness, policy applicability,
relationship validity, authorization, claim truth, or response quality, and it does
NOT answer the user.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Optional, Tuple

from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import (
    EvidenceProvenance, EvidenceUnit, stable_hash,
)

SCHEMA_VERSION = "tap-e2-retrieval/1.0.0"


class GapType(str, Enum):
    NO_AUTHORITATIVE_SOURCE = "no_authoritative_source"
    CONFLICTING_SOURCES = "conflicting_sources"
    OUTDATED_SOURCES = "outdated_sources"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    MISSING_ENTITY = "missing_entity"
    UNRESOLVED_TEMPORAL_SCOPE = "unresolved_temporal_scope"


@dataclass(frozen=True)
class RetrievalQuery:
    """Structured query derived from an IntentRecord (query-generation stage)."""
    terms: Tuple[str, ...]
    concepts: Tuple[str, ...]
    entities: Tuple[str, ...]
    temporal_scope: Optional[int]           # year, if any
    required_authority: bool                # does the objective demand an authoritative source?

    def to_dict(self) -> Dict[str, object]:
        return {"terms": list(self.terms), "concepts": list(self.concepts),
                "entities": list(self.entities), "temporal_scope": self.temporal_scope,
                "required_authority": self.required_authority}


@dataclass(frozen=True)
class RankingSignals:
    """Interpretable per-candidate ranking signals (no opaque single score)."""
    lexical: float
    semantic: float
    authority: float
    freshness: float
    provenance_completeness: float
    specificity: float
    redundancy_penalty: float

    def to_dict(self) -> Dict[str, float]:
        return {k: round(v, 6) for k, v in {
            "lexical": self.lexical, "semantic": self.semantic,
            "authority": self.authority, "freshness": self.freshness,
            "provenance_completeness": self.provenance_completeness,
            "specificity": self.specificity, "redundancy_penalty": self.redundancy_penalty,
        }.items()}


@dataclass(frozen=True)
class RankedCandidate:
    unit: EvidenceUnit
    provenance: EvidenceProvenance
    signals: RankingSignals
    score: float                            # final combined score (interpretable weights)

    def to_public_dict(self) -> Dict[str, object]:
        return {
            "unit": self.unit.to_public_dict(),
            "provenance": self.provenance.to_dict(),
            "signals": self.signals.to_dict(),
            "score": round(self.score, 6),
        }


@dataclass(frozen=True)
class RetrievalConfidence:
    """Multidimensional confidence — never collapsed into one scalar."""
    entity_match: float
    semantic_relevance: float
    temporal_relevance: float
    source_completeness: float
    provenance_quality: float
    retrieval_coverage: float

    def to_dict(self) -> Dict[str, float]:
        return {"entity_match": round(self.entity_match, 4),
                "semantic_relevance": round(self.semantic_relevance, 4),
                "temporal_relevance": round(self.temporal_relevance, 4),
                "source_completeness": round(self.source_completeness, 4),
                "provenance_quality": round(self.provenance_quality, 4),
                "retrieval_coverage": round(self.retrieval_coverage, 4)}


@dataclass(frozen=True)
class RetrievalGap:
    gap_type: GapType
    description: str
    detail: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {"gap_type": self.gap_type.value, "description": self.description,
                "detail": dict(self.detail)}


@dataclass(frozen=True)
class RetrievalRecord:
    schema_version: str
    retrieval_id: str
    intent_ref: str                         # originating IntentRecord (request_id / hash)
    intent_objective: str
    query: RetrievalQuery
    candidates: Tuple[RankedCandidate, ...]
    confidence: RetrievalConfidence
    gaps: Tuple[RetrievalGap, ...]
    latency_ms: float

    @property
    def unit_ids(self) -> Tuple[str, ...]:
        return tuple(c.unit.unit_id for c in self.candidates)

    def to_dict(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "retrieval_id": self.retrieval_id,
            "intent_ref": self.intent_ref,
            "intent_objective": self.intent_objective,
            "query": self.query.to_dict(),
            "candidates": [c.to_public_dict() for c in self.candidates],
            "confidence": self.confidence.to_dict(),
            "gaps": [g.to_dict() for g in self.gaps],
            "latency_ms": round(self.latency_ms, 4),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def validate_record(rec: RetrievalRecord) -> Tuple[bool, Tuple[str, ...]]:
    problems: List[str] = []
    if rec.schema_version != SCHEMA_VERSION:
        problems.append("schema_version mismatch")
    if not rec.retrieval_id:
        problems.append("empty retrieval_id")
    for c in rec.candidates:
        # provenance must be ATTACHED to every candidate (source + method + path +
        # extraction). Completeness (an in-document location) is a quality signal the
        # provenance-filter stage enforces from baseline D onward; a pre-filter
        # baseline may legitimately surface an unsourced unit, but never one with no
        # provenance object at all.
        p = c.provenance
        if not (p.source_id and p.retrieval_path and p.retrieval_method
                and p.extraction_method):
            problems.append(f"candidate {c.unit.unit_id} missing provenance")
    # round-trip
    try:
        if json.loads(rec.to_json())["retrieval_id"] != rec.retrieval_id:
            problems.append("round-trip mismatch")
    except Exception as exc:  # pragma: no cover
        problems.append(f"round-trip raised {exc!r}")
    return (not problems, tuple(problems))
