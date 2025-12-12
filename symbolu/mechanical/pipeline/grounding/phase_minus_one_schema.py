"""
Phase −1 Schema Definitions

Stable envelope objects for Observer-Observed grounding analysis.

All schemas are designed to be:
- Deterministic (no probabilistic sampling)
- Serializable (can be logged/traced)
- Immutable-friendly (dataclasses with frozen=False for practicality)

Authority Model:
- Phase −1 establishes WHO is being observed (SELF/OTHER/PHENOMENON)
- Phase −1 establishes HOW they are being observed (REFLEXIVE/RELATIONAL/DETACHED)
- Downstream stages MUST respect these constraints
- Authority flows downward; information flows upward
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ============================================================================
# ENUMS - Stable string constants for type safety
# ============================================================================


class ObservedEntity(str, Enum):
    """
    WHO is being observed in the utterance.

    SELF: The speaker/user themselves (first-person perspective)
    OTHER: Another person or entity being referenced
    PHENOMENON: An abstract concept, event, or general truth
    """
    SELF = "SELF"
    OTHER = "OTHER"
    PHENOMENON = "PHENOMENON"


class ObservationMode(str, Enum):
    """
    HOW the observation is framed.

    REFLEXIVE: Self-directed observation (I observe myself)
    RELATIONAL: Observation about another in relation to self/context
    DETACHED: Objective/abstract observation (no personal stake)
    """
    REFLEXIVE = "REFLEXIVE"
    RELATIONAL = "RELATIONAL"
    DETACHED = "DETACHED"


class ProjectionRisk(str, Enum):
    """
    Risk level of unintentionally projecting observer's framework onto observed.

    LOW: Safe to analyze without projection risk
    MEDIUM: Some projection risk; proceed with care
    HIGH: High risk of projection; restrict analytical operations
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class GroundingStatus(str, Enum):
    """
    Result of grounding resolution.

    CONFIDENT: Clear grounding established (top candidate above threshold)
    AMBIGUOUS: Multiple plausible groundings (requires clarification or safe default)
    CONFLICTED: Contradictory signals (may indicate genuine complexity)
    """
    CONFIDENT = "CONFIDENT"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICTED = "CONFLICTED"


class ResolutionPolicy(str, Enum):
    """
    Policy for handling ambiguous grounding.

    NONE: No special handling needed (confident grounding)
    ASK_CLARIFY: Request clarification from user before proceeding
    SAFE_DEFAULT: Use conservative default without asking
    """
    NONE = "NONE"
    ASK_CLARIFY = "ASK_CLARIFY"
    SAFE_DEFAULT = "SAFE_DEFAULT"


class LinkageHint(str, Enum):
    """
    Semantic relationship hint when clause is split.

    CAUSAL: Second clause explains/causes first (because, since)
    CONTRAST: Clauses are in tension (but, however)
    ADDITIVE: Clauses add information (and)
    NONE: No special linkage detected
    """
    CAUSAL = "CAUSAL"
    CONTRAST = "CONTRAST"
    ADDITIVE = "ADDITIVE"
    NONE = "NONE"


class OverallPolicy(str, Enum):
    """
    Overall pipeline policy based on Phase −1 analysis.

    SINGLE_CONTEXT: Single coherent grounding context
    MULTI_CONTEXT: Multiple clause contexts (requires per-clause handling)
    BLOCKED: Cannot proceed without clarification
    """
    SINGLE_CONTEXT = "SINGLE_CONTEXT"
    MULTI_CONTEXT = "MULTI_CONTEXT"
    BLOCKED = "BLOCKED"


# ============================================================================
# DATACLASSES - Core envelope objects
# ============================================================================


@dataclass
class GroundingCandidate:
    """
    A single grounding hypothesis for a clause or utterance.

    Represents one possible interpretation of WHO is being observed
    and HOW the observation is framed.

    Attributes:
        observed: WHO is being observed (SELF/OTHER/PHENOMENON)
        mode: HOW observation is framed (REFLEXIVE/RELATIONAL/DETACHED)
        projection_risk: Risk of observer projecting onto observed
        analysis_allowed: Whether analytical operations are permitted
        confidence: Confidence score in [0.0, 1.0]
        evidence: List of evidence strings supporting this candidate
    """
    observed: ObservedEntity
    mode: ObservationMode
    projection_risk: ProjectionRisk
    analysis_allowed: bool
    confidence: float
    evidence: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate confidence bounds."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "observed": self.observed.value,
            "mode": self.mode.value,
            "projection_risk": self.projection_risk.value,
            "analysis_allowed": self.analysis_allowed,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


@dataclass
class ClauseGroundingResult:
    """
    Grounding result for a single clause.

    Contains all candidate groundings, the selected grounding (if any),
    and resolution metadata.

    Attributes:
        clause_text: The text of this clause
        candidates: All grounding candidates generated for this clause
        selected: The selected grounding candidate (may be None if ambiguous)
        grounding_status: Result status (CONFIDENT/AMBIGUOUS/CONFLICTED)
        resolution_policy: How to handle ambiguity (NONE/ASK_CLARIFY/SAFE_DEFAULT)
        linkage_hint: Semantic relationship to previous clause
        clause_index: Position in the original utterance (0-indexed)
    """
    clause_text: str
    candidates: List[GroundingCandidate] = field(default_factory=list)
    selected: Optional[GroundingCandidate] = None
    grounding_status: GroundingStatus = GroundingStatus.AMBIGUOUS
    resolution_policy: ResolutionPolicy = ResolutionPolicy.ASK_CLARIFY
    linkage_hint: LinkageHint = LinkageHint.NONE
    clause_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "clause_text": self.clause_text,
            "candidates": [c.to_dict() for c in self.candidates],
            "selected": self.selected.to_dict() if self.selected else None,
            "grounding_status": self.grounding_status.value,
            "resolution_policy": self.resolution_policy.value,
            "linkage_hint": self.linkage_hint.value,
            "clause_index": self.clause_index,
        }


@dataclass
class PhaseMinusOneEnvelope:
    """
    Complete Phase −1 analysis result.

    This envelope is attached to PipelineContext and carries all grounding
    constraints that downstream stages must respect.

    Invariants:
    - Authority flows downward: Phase −1 constraints are binding on all later phases
    - Information flows upward: Later phases can report violations but cannot override
    - If overall_policy == BLOCKED, pipeline must request clarification

    Attributes:
        overall_policy: Pipeline-level policy (SINGLE_CONTEXT/MULTI_CONTEXT/BLOCKED)
        clauses: List of clause grounding results
        selected_primary: Primary grounding for simple queries (may be None)
        original_text: The original input text before any splitting
        was_split: Whether the text was split into multiple clauses
        debug: Debug/trace information for diagnostics
        run_id: Unique identifier for this analysis run
    """
    overall_policy: OverallPolicy
    clauses: List[ClauseGroundingResult]
    selected_primary: Optional[GroundingCandidate] = None
    original_text: str = ""
    was_split: bool = False
    debug: Dict[str, Any] = field(default_factory=dict)
    run_id: str = ""

    def is_blocked(self) -> bool:
        """Check if pipeline should block and request clarification."""
        return self.overall_policy == OverallPolicy.BLOCKED

    def has_multi_context(self) -> bool:
        """Check if multiple grounding contexts exist."""
        return self.overall_policy == OverallPolicy.MULTI_CONTEXT

    def get_mode_distribution(self) -> Dict[str, int]:
        """Get distribution of observation modes across clauses."""
        dist: Dict[str, int] = {}
        for clause in self.clauses:
            if clause.selected:
                mode = clause.selected.mode.value
                dist[mode] = dist.get(mode, 0) + 1
        return dist

    def get_risk_distribution(self) -> Dict[str, int]:
        """Get distribution of projection risks across clauses."""
        dist: Dict[str, int] = {}
        for clause in self.clauses:
            if clause.selected:
                risk = clause.selected.projection_risk.value
                dist[risk] = dist.get(risk, 0) + 1
        return dist

    def get_confidence_stats(self) -> Dict[str, float]:
        """Get confidence statistics across clauses."""
        confidences = [
            c.selected.confidence
            for c in self.clauses
            if c.selected is not None
        ]
        if not confidences:
            return {"min": 0.0, "max": 0.0, "mean": 0.0}
        return {
            "min": min(confidences),
            "max": max(confidences),
            "mean": sum(confidences) / len(confidences),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "overall_policy": self.overall_policy.value,
            "clauses": [c.to_dict() for c in self.clauses],
            "selected_primary": self.selected_primary.to_dict() if self.selected_primary else None,
            "original_text": self.original_text,
            "was_split": self.was_split,
            "debug": self.debug,
            "run_id": self.run_id,
            "mode_distribution": self.get_mode_distribution(),
            "risk_distribution": self.get_risk_distribution(),
            "confidence_stats": self.get_confidence_stats(),
        }


# Public exports
__all__ = [
    # Enums
    "ObservedEntity",
    "ObservationMode",
    "ProjectionRisk",
    "GroundingStatus",
    "ResolutionPolicy",
    "LinkageHint",
    "OverallPolicy",
    # Dataclasses
    "GroundingCandidate",
    "ClauseGroundingResult",
    "PhaseMinusOneEnvelope",
]
