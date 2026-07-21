"""
Versioned, serializable GovernanceRecord schema for TAP-E4.

The GovernanceRecord is the sole output of the Governance Truth layer: a deterministic,
provenance-preserving selection and justification of which documented authority governs a
situation. It does NOT determine factual truth, claim truth, response correctness, or
execution authorization, and never answers the user (see ARCHITECTURE).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Optional, Tuple

from truth_assurance_pipeline.tap_e4_governance_truth.authority import (
    AUTHORITY_MODEL_VERSION, AuthorityTier,
)

SCHEMA_VERSION = "tap-e4-governance/1.0.0"


class GovStatus(str, Enum):
    GOVERNING = "GOVERNING"                 # a single controlling authority resolved
    GOVERNING_WITH_EXCEPTION = "GOVERNING_WITH_EXCEPTION"
    CONFLICTED = "CONFLICTED"               # >1 authority survives with no resolver
    NO_GOVERNING_AUTHORITY = "NO_GOVERNING_AUTHORITY"
    INSUFFICIENT_BASIS = "INSUFFICIENT_BASIS"
    UNRESOLVED = "UNRESOLVED"


class GovConflictType(str, Enum):
    AUTHORITY_CONFLICT = "AUTHORITY_CONFLICT"
    JURISDICTION_CONFLICT = "JURISDICTION_CONFLICT"
    CONTRACT_POLICY_CONFLICT = "CONTRACT_POLICY_CONFLICT"
    EXCEPTION_CONFLICT = "EXCEPTION_CONFLICT"
    VERSION_CONFLICT = "VERSION_CONFLICT"


class GovGapCode(str, Enum):
    NO_GOVERNING_POLICY = "NO_GOVERNING_POLICY"
    CONFLICTING_AUTHORITIES = "CONFLICTING_AUTHORITIES"
    AMBIGUOUS_JURISDICTION = "AMBIGUOUS_JURISDICTION"
    MISSING_VERSION = "MISSING_VERSION"
    UNRESOLVED_SCOPE = "UNRESOLVED_SCOPE"
    UNRESOLVED_EXCEPTION = "UNRESOLVED_EXCEPTION"
    EXPIRED_AUTHORITY = "EXPIRED_AUTHORITY"
    MISSING_TEMPORAL_BASIS = "MISSING_TEMPORAL_BASIS"
    INSUFFICIENT_UPSTREAM_RELATIONSHIPS = "INSUFFICIENT_UPSTREAM_RELATIONSHIPS"


@dataclass(frozen=True)
class GovProvenance:
    """Provenance back to the TAP-E3 assertion and its TAP-E2 evidence unit."""
    authority_name: str
    relationship_assertion_id: str
    evidence_unit_id: str
    source_id: str
    source_location: str
    relationship_record_id: str

    def is_complete(self) -> bool:
        return bool(self.authority_name and self.relationship_assertion_id
                    and self.evidence_unit_id and self.source_id
                    and self.relationship_record_id)

    def to_dict(self) -> Dict[str, object]:
        return {"authority_name": self.authority_name,
                "relationship_assertion_id": self.relationship_assertion_id,
                "evidence_unit_id": self.evidence_unit_id, "source_id": self.source_id,
                "source_location": self.source_location,
                "relationship_record_id": self.relationship_record_id}


@dataclass(frozen=True)
class RejectedAuthority:
    authority_name: str
    tier: AuthorityTier
    reason: str

    def to_dict(self) -> Dict[str, object]:
        return {"authority_name": self.authority_name, "tier": self.tier.value,
                "reason": self.reason}


@dataclass(frozen=True)
class GovernanceConfidence:
    authority_confidence: float
    jurisdiction_confidence: float
    scope_confidence: float
    temporal_confidence: float
    exception_confidence: float
    precedence_confidence: float
    conflict_confidence: float
    provenance_completeness: float

    def band(self) -> str:
        vals = list(self.to_dict().values())
        m, avg = min(vals), sum(vals) / len(vals)
        if m < 0.34:
            return "UNRESOLVED" if m < 0.15 else "LOW"
        if avg >= 0.8 and m >= 0.6:
            return "HIGH"
        return "MEDIUM" if avg >= 0.6 else "LOW"

    def to_dict(self) -> Dict[str, float]:
        return {"authority_confidence": round(self.authority_confidence, 4),
                "jurisdiction_confidence": round(self.jurisdiction_confidence, 4),
                "scope_confidence": round(self.scope_confidence, 4),
                "temporal_confidence": round(self.temporal_confidence, 4),
                "exception_confidence": round(self.exception_confidence, 4),
                "precedence_confidence": round(self.precedence_confidence, 4),
                "conflict_confidence": round(self.conflict_confidence, 4),
                "provenance_completeness": round(self.provenance_completeness, 4)}


@dataclass(frozen=True)
class GoverningDecision:
    decision_id: str
    selected_authority: Optional[str]
    tier: AuthorityTier
    selection_reason: str
    supporting_relationships: Tuple[str, ...]
    rejected_relationships: Tuple[RejectedAuthority, ...]
    precedence_chain: Tuple[str, ...]
    jurisdiction: Mapping[str, str]
    scope: Mapping[str, str]
    temporal_basis: Mapping[str, str]
    exception_basis: Tuple[str, ...]
    provenance: Tuple[GovProvenance, ...]
    confidence: GovernanceConfidence
    status: GovStatus

    def to_dict(self) -> Dict[str, object]:
        return {"decision_id": self.decision_id,
                "selected_authority": self.selected_authority,
                "tier": self.tier.value, "selection_reason": self.selection_reason,
                "supporting_relationships": list(self.supporting_relationships),
                "rejected_relationships": [r.to_dict() for r in self.rejected_relationships],
                "precedence_chain": list(self.precedence_chain),
                "jurisdiction": dict(self.jurisdiction), "scope": dict(self.scope),
                "temporal_basis": dict(self.temporal_basis),
                "exception_basis": list(self.exception_basis),
                "provenance": [p.to_dict() for p in self.provenance],
                "confidence": self.confidence.to_dict(),
                "confidence_band": self.confidence.band(),
                "status": self.status.value}


@dataclass(frozen=True)
class GovernanceConflict:
    conflict_id: str
    conflict_type: GovConflictType
    authority_names: Tuple[str, ...]
    explanation: str
    status: str = "OPEN"

    def to_dict(self) -> Dict[str, object]:
        return {"conflict_id": self.conflict_id, "conflict_type": self.conflict_type.value,
                "authority_names": list(self.authority_names),
                "explanation": self.explanation, "status": self.status}


@dataclass(frozen=True)
class GovernanceGap:
    gap_code: GovGapCode
    description: str
    detail: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {"gap_code": self.gap_code.value, "description": self.description,
                "detail": dict(self.detail)}


@dataclass(frozen=True)
class GovernanceRecord:
    schema_version: str
    authority_model_version: str
    governance_record_id: str
    intent_record_id: str
    retrieval_record_id: str
    relationship_record_id: str
    created_at: str
    governing_authorities: Tuple[GoverningDecision, ...]
    governing_relationships: Tuple[str, ...]
    governance_conflicts: Tuple[GovernanceConflict, ...]
    governance_gaps: Tuple[GovernanceGap, ...]
    confidence_vector: GovernanceConfidence
    processing_trace: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        return {"schema_version": self.schema_version,
                "authority_model_version": self.authority_model_version,
                "governance_record_id": self.governance_record_id,
                "intent_record_id": self.intent_record_id,
                "retrieval_record_id": self.retrieval_record_id,
                "relationship_record_id": self.relationship_record_id,
                "created_at": self.created_at,
                "governing_authorities": [d.to_dict() for d in self.governing_authorities],
                "governing_relationships": list(self.governing_relationships),
                "governance_conflicts": [c.to_dict() for c in self.governance_conflicts],
                "governance_gaps": [g.to_dict() for g in self.governance_gaps],
                "confidence_vector": self.confidence_vector.to_dict(),
                "processing_trace": list(self.processing_trace)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def validate_record(rec: GovernanceRecord) -> Tuple[bool, Tuple[str, ...]]:
    problems: List[str] = []
    if rec.schema_version != SCHEMA_VERSION:
        problems.append("schema_version mismatch")
    if rec.authority_model_version != AUTHORITY_MODEL_VERSION:
        problems.append("authority_model_version mismatch")
    if not rec.governance_record_id:
        problems.append("empty governance_record_id")
    for d in rec.governing_authorities:
        if d.selected_authority and not d.provenance:
            problems.append(f"decision {d.decision_id} selects an authority without provenance")
        for p in d.provenance:
            if not p.is_complete():
                problems.append(f"decision {d.decision_id} incomplete provenance")
    try:
        if json.loads(rec.to_json())["governance_record_id"] != rec.governance_record_id:
            problems.append("round-trip mismatch")
    except Exception as exc:  # pragma: no cover
        problems.append(f"round-trip raised {exc!r}")
    return (not problems, tuple(problems))
