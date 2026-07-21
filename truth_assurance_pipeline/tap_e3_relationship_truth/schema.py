"""
Versioned, serializable RelationshipRecord schema for TAP-E3.

The RelationshipRecord is the sole output of the Relationship Truth layer: a structured,
provenance-preserving representation of the relationships the retrieved evidence
*asserts, qualifies, negates, alleges, conditions, or contradicts*. It does NOT decide
final claim truth, governance applicability, or authorization, and never answers the
user (see ARCHITECTURE / boundary section).

Every dimension (direction, polarity, modality, temporality, explicitness, scope,
conditions, exceptions) is represented SEPARATELY — never collapsed into a binary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Optional, Tuple

from truth_assurance_pipeline.tap_e3_relationship_truth.ontology import (
    ONTOLOGY_VERSION, RelationshipType,
)

SCHEMA_VERSION = "tap-e3-relationship/1.0.0"


# --- dimension enums --------------------------------------------------------

class Direction(str, Enum):
    SUBJECT_TO_OBJECT = "subject_to_object"
    OBJECT_TO_SUBJECT = "object_to_subject"
    UNDIRECTED = "undirected"
    UNCLEAR = "unclear"


class Polarity(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATED = "NEGATED"
    UNKNOWN = "UNKNOWN"


class Modality(str, Enum):
    ASSERTED = "ASSERTED"
    REQUIRED = "REQUIRED"
    PERMITTED = "PERMITTED"
    RECOMMENDED = "RECOMMENDED"
    POSSIBLE = "POSSIBLE"
    CONDITIONAL = "CONDITIONAL"
    ALLEGED = "ALLEGED"
    UNKNOWN = "UNKNOWN"


class Temporality(str, Enum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"
    FUTURE = "FUTURE"
    SUPERSEDED = "SUPERSEDED"
    CONDITIONAL_TIME = "CONDITIONAL_TIME"
    UNRESOLVED = "UNRESOLVED"


class Explicitness(str, Enum):
    EXPLICIT = "EXPLICIT"
    STRUCTURALLY_INFERRED = "STRUCTURALLY_INFERRED"
    LINGUISTICALLY_INFERRED = "LINGUISTICALLY_INFERRED"
    UNSUPPORTED_INFERENCE = "UNSUPPORTED_INFERENCE"


class AssertionStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNRESOLVED = "UNRESOLVED"


class EvidenceRole(str, Enum):
    PRIMARY_SUPPORT = "PRIMARY_SUPPORT"
    QUALIFIER = "QUALIFIER"
    EXCEPTION = "EXCEPTION"
    TEMPORAL_CONTEXT = "TEMPORAL_CONTEXT"
    CONTRADICTION = "CONTRADICTION"


class ConflictType(str, Enum):
    POLARITY_CONFLICT = "POLARITY_CONFLICT"
    MODALITY_CONFLICT = "MODALITY_CONFLICT"
    VALUE_CONFLICT = "VALUE_CONFLICT"
    TEMPORAL_CONFLICT = "TEMPORAL_CONFLICT"
    DIRECTION_CONFLICT = "DIRECTION_CONFLICT"
    ONTOLOGY_CONFLICT = "ONTOLOGY_CONFLICT"
    SCOPE_CONFLICT = "SCOPE_CONFLICT"


class GapCode(str, Enum):
    NO_RELATIONSHIP_ESTABLISHED = "NO_RELATIONSHIP_ESTABLISHED"
    AMBIGUOUS_PREDICATE = "AMBIGUOUS_PREDICATE"
    AMBIGUOUS_DIRECTION = "AMBIGUOUS_DIRECTION"
    UNRESOLVED_SUBJECT = "UNRESOLVED_SUBJECT"
    UNRESOLVED_OBJECT = "UNRESOLVED_OBJECT"
    NEGATION_SCOPE_UNCLEAR = "NEGATION_SCOPE_UNCLEAR"
    TEMPORAL_SCOPE_UNCLEAR = "TEMPORAL_SCOPE_UNCLEAR"
    CONDITION_SCOPE_UNCLEAR = "CONDITION_SCOPE_UNCLEAR"
    CONFLICTING_RELATIONSHIPS = "CONFLICTING_RELATIONSHIPS"
    INSUFFICIENT_RETRIEVAL_EVIDENCE = "INSUFFICIENT_RETRIEVAL_EVIDENCE"
    UNSUPPORTED_INFERENCE = "UNSUPPORTED_INFERENCE"


# --- sub-structures ---------------------------------------------------------

@dataclass(frozen=True)
class SourceProvenance:
    """Mandatory per-assertion provenance back to a TAP-E2 evidence unit."""
    evidence_unit_id: str
    source_id: str
    source_location: str
    retrieval_record_id: str
    retrieval_rank: int
    retrieval_method: str
    extraction_span: Tuple[int, int]
    extraction_method: str
    role: EvidenceRole = EvidenceRole.PRIMARY_SUPPORT

    def is_complete(self) -> bool:
        return bool(self.evidence_unit_id and self.source_id and self.source_location
                    and self.retrieval_record_id and self.extraction_method)

    def to_dict(self) -> Dict[str, object]:
        return {"evidence_unit_id": self.evidence_unit_id, "source_id": self.source_id,
                "source_location": self.source_location,
                "retrieval_record_id": self.retrieval_record_id,
                "retrieval_rank": self.retrieval_rank,
                "retrieval_method": self.retrieval_method,
                "extraction_span": list(self.extraction_span),
                "extraction_method": self.extraction_method, "role": self.role.value}


@dataclass(frozen=True)
class RelationshipConfidence:
    subject_resolution: float
    object_resolution: float
    predicate_resolution: float
    direction_confidence: float
    polarity_confidence: float
    modality_confidence: float
    temporal_confidence: float
    scope_confidence: float
    condition_confidence: float
    provenance_completeness: float
    cross_evidence_consistency: float

    def band(self) -> str:
        vals = list(self.to_dict().values())
        m = min(vals)                     # a low component must not be hidden
        avg = sum(vals) / len(vals)
        if m < 0.34:
            return "UNRESOLVED" if m < 0.15 else "LOW"
        if avg >= 0.8 and m >= 0.6:
            return "HIGH"
        if avg >= 0.6:
            return "MEDIUM"
        return "LOW"

    def to_dict(self) -> Dict[str, float]:
        return {"subject_resolution": round(self.subject_resolution, 4),
                "object_resolution": round(self.object_resolution, 4),
                "predicate_resolution": round(self.predicate_resolution, 4),
                "direction_confidence": round(self.direction_confidence, 4),
                "polarity_confidence": round(self.polarity_confidence, 4),
                "modality_confidence": round(self.modality_confidence, 4),
                "temporal_confidence": round(self.temporal_confidence, 4),
                "scope_confidence": round(self.scope_confidence, 4),
                "condition_confidence": round(self.condition_confidence, 4),
                "provenance_completeness": round(self.provenance_completeness, 4),
                "cross_evidence_consistency": round(self.cross_evidence_consistency, 4)}


@dataclass(frozen=True)
class RelationshipAssertion:
    assertion_id: str
    subject: str
    predicate: str
    object: str
    normalized_subject: str
    normalized_predicate: RelationshipType
    normalized_object: str
    relationship_type: RelationshipType
    direction: Direction
    polarity: Polarity
    modality: Modality
    temporality: Temporality
    scope: Mapping[str, str]
    conditions: Tuple[str, ...]
    exceptions: Tuple[str, ...]
    explicitness: Explicitness
    evidence_unit_ids: Tuple[str, ...]
    source_provenance: Tuple[SourceProvenance, ...]
    extraction_method: str
    confidence_vector: RelationshipConfidence
    ambiguities: Tuple[str, ...]
    conflicts: Tuple[str, ...]
    status: AssertionStatus
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None

    def triple(self) -> Tuple[str, str, str]:
        return (self.normalized_subject, self.normalized_predicate.value,
                self.normalized_object)

    def to_dict(self) -> Dict[str, object]:
        return {
            "assertion_id": self.assertion_id, "subject": self.subject,
            "predicate": self.predicate, "object": self.object,
            "normalized_subject": self.normalized_subject,
            "normalized_predicate": self.normalized_predicate.value,
            "normalized_object": self.normalized_object,
            "relationship_type": self.relationship_type.value,
            "direction": self.direction.value, "polarity": self.polarity.value,
            "modality": self.modality.value, "temporality": self.temporality.value,
            "scope": dict(self.scope), "conditions": list(self.conditions),
            "exceptions": list(self.exceptions), "explicitness": self.explicitness.value,
            "evidence_unit_ids": list(self.evidence_unit_ids),
            "source_provenance": [p.to_dict() for p in self.source_provenance],
            "extraction_method": self.extraction_method,
            "confidence_vector": self.confidence_vector.to_dict(),
            "confidence_band": self.confidence_vector.band(),
            "ambiguities": list(self.ambiguities), "conflicts": list(self.conflicts),
            "status": self.status.value,
            "valid_from": self.valid_from, "valid_until": self.valid_until,
        }


@dataclass(frozen=True)
class RelationshipConflict:
    conflict_id: str
    assertion_ids: Tuple[str, ...]
    conflict_type: ConflictType
    scope_overlap: bool
    temporal_overlap: bool
    severity: str
    explanation: str
    status: str = "OPEN"

    def to_dict(self) -> Dict[str, object]:
        return {"conflict_id": self.conflict_id,
                "assertion_ids": list(self.assertion_ids),
                "conflict_type": self.conflict_type.value,
                "scope_overlap": self.scope_overlap,
                "temporal_overlap": self.temporal_overlap,
                "severity": self.severity, "explanation": self.explanation,
                "status": self.status}


@dataclass(frozen=True)
class RelationshipGap:
    gap_code: GapCode
    description: str
    detail: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {"gap_code": self.gap_code.value, "description": self.description,
                "detail": dict(self.detail)}


@dataclass(frozen=True)
class RelationshipRecord:
    schema_version: str
    ontology_version: str
    relationship_record_id: str
    intent_record_id: str
    retrieval_record_id: str
    created_at: str
    relationship_assertions: Tuple[RelationshipAssertion, ...]
    relationship_conflicts: Tuple[RelationshipConflict, ...]
    unresolved_relationship_gaps: Tuple[RelationshipGap, ...]
    provenance_summary: Mapping[str, object]
    confidence_summary: Mapping[str, object]
    processing_trace: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "ontology_version": self.ontology_version,
            "relationship_record_id": self.relationship_record_id,
            "intent_record_id": self.intent_record_id,
            "retrieval_record_id": self.retrieval_record_id,
            "created_at": self.created_at,
            "relationship_assertions": [a.to_dict() for a in self.relationship_assertions],
            "relationship_conflicts": [c.to_dict() for c in self.relationship_conflicts],
            "unresolved_relationship_gaps": [g.to_dict()
                                             for g in self.unresolved_relationship_gaps],
            "provenance_summary": dict(self.provenance_summary),
            "confidence_summary": dict(self.confidence_summary),
            "processing_trace": list(self.processing_trace),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def validate_record(rec: RelationshipRecord) -> Tuple[bool, Tuple[str, ...]]:
    problems: List[str] = []
    if rec.schema_version != SCHEMA_VERSION:
        problems.append("schema_version mismatch")
    if rec.ontology_version != ONTOLOGY_VERSION:
        problems.append("ontology_version mismatch")
    if not rec.relationship_record_id:
        problems.append("empty relationship_record_id")
    for a in rec.relationship_assertions:
        if not a.source_provenance:
            problems.append(f"assertion {a.assertion_id} has no provenance")
        for p in a.source_provenance:
            if not p.is_complete():
                problems.append(f"assertion {a.assertion_id} incomplete provenance")
        if not a.evidence_unit_ids:
            problems.append(f"assertion {a.assertion_id} has no evidence_unit_ids")
    try:
        if json.loads(rec.to_json())["relationship_record_id"] != rec.relationship_record_id:
            problems.append("round-trip mismatch")
    except Exception as exc:  # pragma: no cover
        problems.append(f"round-trip raised {exc!r}")
    return (not problems, tuple(problems))
