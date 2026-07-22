"""
Versioned, serializable EvidencePacket schema for TAP-E5.

The EvidencePacket is the sole output of the Evidence Assembly layer: one deterministic,
immutable, provenance-preserving, dependency-preserving object that packages what the
upstream TAP layers discovered (intent, evidence, relationships, governance) into the
minimal complete set required by downstream claim validation (TAP-E6).

E5 assembles; it does not reason. The packet never invents, summarizes, rewrites, or merges
evidence, never resolves a conflict, and never fills a gap. Every object preserves
provenance; no object is orphaned.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Optional, Tuple

SCHEMA_VERSION = "tap-e5-evidence-packet/1.0.0"


class ObjectKind(str, Enum):
    INTENT = "intent"
    EVIDENCE = "evidence"
    RELATIONSHIP = "relationship"
    GOVERNANCE = "governance"


class EdgeType(str, Enum):
    ANSWERS_INTENT = "answers_intent"              # governance -> intent
    SUPPORTED_BY_RELATIONSHIP = "supported_by_relationship"  # governance -> relationship
    SUPPORTED_BY_EVIDENCE = "supported_by_evidence"          # relationship -> evidence


@dataclass(frozen=True)
class PacketIntent:
    request_id: str
    primary_objective: str
    task_type: str

    def to_dict(self) -> Dict[str, object]:
        return {"request_id": self.request_id, "primary_objective": self.primary_objective,
                "task_type": self.task_type}


@dataclass(frozen=True)
class PacketEvidence:
    unit_id: str
    source_id: str
    source_location: str
    doc_type: str
    authority_level: str
    retrieval_rank: int
    retrieval_method: str
    retrieval_score: float
    extraction_method: str
    confidence: float

    def to_dict(self) -> Dict[str, object]:
        return {"unit_id": self.unit_id, "source_id": self.source_id,
                "source_location": self.source_location, "doc_type": self.doc_type,
                "authority_level": self.authority_level, "retrieval_rank": self.retrieval_rank,
                "retrieval_method": self.retrieval_method,
                "retrieval_score": round(self.retrieval_score, 6),
                "extraction_method": self.extraction_method,
                "confidence": round(self.confidence, 6)}


@dataclass(frozen=True)
class PacketRelationship:
    assertion_id: str
    relationship_type: str
    direction: str
    polarity: str
    modality: str
    temporality: str
    valid_from: Optional[str]
    valid_until: Optional[str]
    scope: Mapping[str, str]
    evidence_unit_ids: Tuple[str, ...]
    confidence_band: str
    status: str

    def to_dict(self) -> Dict[str, object]:
        return {"assertion_id": self.assertion_id, "relationship_type": self.relationship_type,
                "direction": self.direction, "polarity": self.polarity,
                "modality": self.modality, "temporality": self.temporality,
                "valid_from": self.valid_from, "valid_until": self.valid_until,
                "scope": dict(self.scope), "evidence_unit_ids": list(self.evidence_unit_ids),
                "confidence_band": self.confidence_band, "status": self.status}


@dataclass(frozen=True)
class PacketRejectedAuthority:
    authority_name: str
    tier: str
    reason: str
    relationship_id: Optional[str] = None      # link to the minority relationship, if present

    def to_dict(self) -> Dict[str, object]:
        return {"authority_name": self.authority_name, "tier": self.tier,
                "reason": self.reason, "relationship_id": self.relationship_id}


@dataclass(frozen=True)
class PacketGovernance:
    decision_id: str
    selected_authority: Optional[str]
    tier: str
    status: str
    precedence_chain: Tuple[str, ...]
    rejected_authorities: Tuple[PacketRejectedAuthority, ...]
    exception_basis: Tuple[str, ...]
    temporal_basis: Mapping[str, str]
    jurisdiction: Mapping[str, str]
    scope: Mapping[str, str]
    supporting_relationships: Tuple[str, ...]
    confidence: Mapping[str, float]
    governance_record_id: str

    def to_dict(self) -> Dict[str, object]:
        return {"decision_id": self.decision_id, "selected_authority": self.selected_authority,
                "tier": self.tier, "status": self.status,
                "precedence_chain": list(self.precedence_chain),
                "rejected_authorities": [r.to_dict() for r in self.rejected_authorities],
                "exception_basis": list(self.exception_basis),
                "temporal_basis": dict(self.temporal_basis),
                "jurisdiction": dict(self.jurisdiction), "scope": dict(self.scope),
                "supporting_relationships": list(self.supporting_relationships),
                "confidence": {k: round(v, 6) for k, v in self.confidence.items()},
                "governance_record_id": self.governance_record_id}


@dataclass(frozen=True)
class PacketConflict:
    conflict_id: str
    origin: str                       # "E3" or "E4"
    conflict_type: str
    member_ids: Tuple[str, ...]
    explanation: str
    status: str

    def to_dict(self) -> Dict[str, object]:
        return {"conflict_id": self.conflict_id, "origin": self.origin,
                "conflict_type": self.conflict_type, "member_ids": list(self.member_ids),
                "explanation": self.explanation, "status": self.status}


@dataclass(frozen=True)
class PacketGap:
    gap_id: str
    origin: str                       # "E2" | "E3" | "E4"
    gap_code: str
    description: str
    detail: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {"gap_id": self.gap_id, "origin": self.origin, "gap_code": self.gap_code,
                "description": self.description, "detail": dict(self.detail)}


@dataclass(frozen=True)
class DependencyEdge:
    src_id: str
    src_kind: ObjectKind
    dst_id: str
    dst_kind: ObjectKind
    edge_type: EdgeType

    def key(self) -> Tuple[str, str, str]:
        return (self.src_id, self.dst_id, self.edge_type.value)

    def to_dict(self) -> Dict[str, object]:
        return {"src_id": self.src_id, "src_kind": self.src_kind.value,
                "dst_id": self.dst_id, "dst_kind": self.dst_kind.value,
                "edge_type": self.edge_type.value}


@dataclass(frozen=True)
class EvidencePacket:
    schema_version: str
    packet_id: str
    intent: PacketIntent
    intent_record_id: str
    retrieval_record_id: str
    relationship_record_id: str
    governance_record_id: str
    evidence_units: Tuple[PacketEvidence, ...]
    relationships: Tuple[PacketRelationship, ...]
    governance_decisions: Tuple[PacketGovernance, ...]
    conflicts: Tuple[PacketConflict, ...]
    gaps: Tuple[PacketGap, ...]
    dependency_edges: Tuple[DependencyEdge, ...]
    confidence_summary: Mapping[str, object]
    provenance_index: Mapping[str, Mapping[str, object]]
    processing_trace: Tuple[str, ...]

    def object_ids(self) -> Tuple[str, ...]:
        ids = [self.intent.request_id]
        ids += [e.unit_id for e in self.evidence_units]
        ids += [r.assertion_id for r in self.relationships]
        ids += [g.decision_id for g in self.governance_decisions]
        return tuple(ids)

    def to_dict(self) -> Dict[str, object]:
        return {"schema_version": self.schema_version, "packet_id": self.packet_id,
                "intent": self.intent.to_dict(), "intent_record_id": self.intent_record_id,
                "retrieval_record_id": self.retrieval_record_id,
                "relationship_record_id": self.relationship_record_id,
                "governance_record_id": self.governance_record_id,
                "evidence_units": [e.to_dict() for e in self.evidence_units],
                "relationships": [r.to_dict() for r in self.relationships],
                "governance_decisions": [g.to_dict() for g in self.governance_decisions],
                "conflicts": [c.to_dict() for c in self.conflicts],
                "gaps": [g.to_dict() for g in self.gaps],
                "dependency_edges": [e.to_dict() for e in self.dependency_edges],
                "confidence_summary": dict(self.confidence_summary),
                "provenance_index": {k: dict(v) for k, v in self.provenance_index.items()},
                "processing_trace": list(self.processing_trace)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
