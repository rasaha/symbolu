"""
Data model for the Relationship Claim Validation layer.

Stdlib-only, deterministic, frozen dataclasses. Every proposed relationship becomes
an explicit *claim* (a factual hypothesis) that must be grounded in document
evidence before it is retained.

Nothing here reads a resolver, governance engine, or any other track.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Optional, Tuple


# --- statuses & actions ------------------------------------------------------

class ClaimStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNSUPPORTED = "UNSUPPORTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNKNOWN = "UNKNOWN"


class RecommendedAction(str, Enum):
    RETAIN = "retain"          # SUPPORTED
    NARROW = "narrow"          # PARTIALLY_SUPPORTED
    REMOVE = "remove"          # CONTRADICTED / UNSUPPORTED
    ABSTAIN = "abstain"        # INSUFFICIENT_EVIDENCE
    MANUAL_REVIEW = "manual_review"  # UNKNOWN


# Frozen status -> action map (CLAIM_STATUS_SPEC.md).
STATUS_ACTION: Mapping[ClaimStatus, RecommendedAction] = {
    ClaimStatus.SUPPORTED: RecommendedAction.RETAIN,
    ClaimStatus.PARTIALLY_SUPPORTED: RecommendedAction.NARROW,
    ClaimStatus.CONTRADICTED: RecommendedAction.REMOVE,
    ClaimStatus.UNSUPPORTED: RecommendedAction.REMOVE,
    ClaimStatus.INSUFFICIENT_EVIDENCE: RecommendedAction.ABSTAIN,
    ClaimStatus.UNKNOWN: RecommendedAction.MANUAL_REVIEW,
}

# A relationship is "kept in the graph handed to governance" iff its action is
# retain or narrow. remove/abstain/manual_review drop it from the retained set.
RETAINED_ACTIONS = frozenset({RecommendedAction.RETAIN, RecommendedAction.NARROW})


# --- validation predicates ---------------------------------------------------

class PredicateName(str, Enum):
    ENTITY_CORRECTNESS = "entity_correctness"
    RELATIONSHIP_WORDING = "relationship_wording"
    DIRECTION = "direction"
    SCOPE = "scope"
    TEMPORAL_APPLICABILITY = "temporal_applicability"
    AUTHORITY_APPLICABILITY = "authority_applicability"
    DOCUMENT_PROVENANCE = "document_provenance"
    SUPPORT_COMPLETENESS = "support_completeness"
    CONTRADICTION = "contradiction"
    MISSING_EVIDENCE = "missing_evidence"


class PredicateVerdict(str, Enum):
    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"
    CONTRADICTED = "contradicted"
    NOT_APPLICABLE = "not_applicable"


# Predicates that must be affirmatively supported for a claim to be SUPPORTED.
CORE_PREDICATES: Tuple[PredicateName, ...] = (
    PredicateName.ENTITY_CORRECTNESS,
    PredicateName.RELATIONSHIP_WORDING,
    PredicateName.DIRECTION,
    PredicateName.DOCUMENT_PROVENANCE,
)

# Predicates whose absence *narrows* (PARTIALLY_SUPPORTED) rather than kills.
NARROWING_PREDICATES: Tuple[PredicateName, ...] = (
    PredicateName.SCOPE,
    PredicateName.TEMPORAL_APPLICABILITY,
    PredicateName.AUTHORITY_APPLICABILITY,
)


# --- documents & spans -------------------------------------------------------

@dataclass(frozen=True)
class Span:
    """One citable unit of document evidence.

    ``assertions`` is a small structured, deterministic description of what the
    span states. The judges reason over these fields; they never read gold.
    Recognized keys (all optional):
      source, target      : entities the span talks about
      relation            : relationship type the span asserts (source->target)
      negates             : True if the span denies the relation
      scope               : scope token the relation is restricted to (or None)
      temporal            : {"from": int|None, "to": int|None}
      authority           : authority-domain token
    """
    span_id: str
    text: str
    assertions: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Document:
    doc_id: str
    spans: Tuple[Span, ...] = ()

    def span(self, span_id: str) -> Optional[Span]:
        for s in self.spans:
            if s.span_id == span_id:
                return s
        return None


# --- the claim ---------------------------------------------------------------

@dataclass(frozen=True)
class RelationshipClaim:
    """A proposed relationship, treated as a factual hypothesis."""
    relationship_id: str
    relationship_type: str          # e.g. SUPERSEDES, EXEMPTS, REQUIRES, ...
    source_node: str
    target_node: str
    cited_document_ids: Tuple[str, ...] = ()
    cited_span_ids: Tuple[str, ...] = ()
    claimed_scope: Optional[str] = None
    claimed_temporal: Optional[Tuple[Optional[int], Optional[int]]] = None
    claimed_authority: Optional[str] = None


# --- evidence record (validator output per claim) ----------------------------

@dataclass(frozen=True)
class ConfidenceVector:
    """Per-predicate deterministic confidence in [0,1]. No randomness."""
    per_predicate: Mapping[str, float]

    def overall(self) -> float:
        if not self.per_predicate:
            return 0.0
        return round(sum(self.per_predicate.values()) / len(self.per_predicate), 4)


@dataclass(frozen=True)
class EvidenceRecord:
    relationship_id: str
    relationship_type: str
    source_node: str
    target_node: str
    supporting_document_ids: Tuple[str, ...]
    supporting_spans: Tuple[str, ...]
    contradicting_spans: Tuple[str, ...]
    missing_predicates: Tuple[str, ...]
    confidence_vector: ConfidenceVector
    validation_status: ClaimStatus
    recommended_action: RecommendedAction
    predicate_verdicts: Mapping[str, str]
    adjudicated: bool = False          # True iff Judge C ran
    deterministic_removed: bool = False  # True iff killed pre-judge

    def to_public_dict(self) -> Dict[str, object]:
        """Executable/consumer-facing projection (no author or gold fields)."""
        return {
            "relationship_id": self.relationship_id,
            "relationship_type": self.relationship_type,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "supporting_document_ids": list(self.supporting_document_ids),
            "supporting_spans": list(self.supporting_spans),
            "contradicting_spans": list(self.contradicting_spans),
            "missing_predicates": list(self.missing_predicates),
            "confidence_vector": dict(self.confidence_vector.per_predicate),
            "validation_status": self.validation_status.value,
            "recommended_action": self.recommended_action.value,
            "predicate_verdicts": dict(self.predicate_verdicts),
        }


# --- gold label (kept OUT of the public projection) --------------------------

@dataclass(frozen=True)
class GoldLabel:
    """Author-assigned ground truth for a synthetic claim. Never visible to
    judges or the public loader; used only for offline scoring."""
    relationship_id: str
    gold_status: ClaimStatus
    rationale: str
    difficulty: int                 # 1..5, deterministic (see DIFFICULTY note)
    family: str                     # scenario family tag (documentation only)

    @property
    def gold_action(self) -> RecommendedAction:
        return STATUS_ACTION[self.gold_status]

    @property
    def gold_retained(self) -> bool:
        return self.gold_action in RETAINED_ACTIONS


# --- deterministic hashing helper (for the hidden lock) ----------------------

def stable_hash(obj: object) -> str:
    """Deterministic content hash for lock/manifest use."""
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                         default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
