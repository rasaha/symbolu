"""
PO1 — Observer–Observed Grounding Module
(Implemented as phase_minus_one for backward compatibility)

Pre-pipeline grounding analysis to establish observer-observed relationships
before any semantic or discourse processing occurs.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Components:
- PO1.0: Observer-Observed Grounding (OOG)
- PO1.1: Ambiguity Resolver (ARL)
- PO1.2: Conservative Clause Splitter (CSL)
- PO1.F: Fuzzy Query Classifier (FQC) - fuzzy logic for disambiguation
- PO1.S: Session Context Tracker (SCT) - session-level context accumulation
- PhaseMinusOnePipeline: Orchestrates all PO1 stages

Session Context (PO1.S) enables:
- Domain accumulation: Tracks topics/domains explored in session
- Event history: Conversation events and emotional arcs
- User persona signals: Communication patterns observed
- Prior query projections: Previous grounding decisions for inference

Authority flows downward, information flows upward.
"""

from .phase_minus_one_schema import (
    # Enums
    ObservedEntity,
    ObservationMode,
    ProjectionRisk,
    GroundingStatus,
    ResolutionPolicy,
    LinkageHint,
    OverallPolicy,
    # Dataclasses
    GroundingCandidate,
    ClauseGroundingResult,
    PhaseMinusOneEnvelope,
)
from .phase_minus_one_grounding import ObserverObservedGrounding
from .phase_minus_one_ambiguity import AmbiguityResolver, AmbiguityResolution
from .phase_minus_one_clause_splitter import ConservativeClauseSplitter
from .phase_minus_one_pipeline import PhaseMinusOnePipeline
from .phase_minus_one_fuzzy import (
    FuzzyQueryClassifier,
    FuzzyQuerySignals,
    QueryIntentHint,
    TemporalOrientation,
)
from .phase_minus_one_session import (
    # Configuration
    SESSION_INFLUENCE_WINDOW,
    DECAY_HALF_LIFE,
    CONTRADICTION_THRESHOLD,
    MAX_RESOLUTION_BIAS,
    # Enums
    SessionNonPermission,
    DomainCategory,
    EventType,
    ResolutionSource,
    # Core classes
    SessionContext,
    SessionEvent,
    DomainAccumulator,
    PersonaSignals,
    PriorGroundingProjection,
    # Constraint narrowing
    SessionConstraintEffect,
    # Projection layer
    SessionProjection,
    # Audit
    SessionAuditEntry,
    SessionSummary,
    # Session-aware signals
    SessionAwareFuzzySignals,
)

__all__ = [
    # Enums
    "ObservedEntity",
    "ObservationMode",
    "ProjectionRisk",
    "GroundingStatus",
    "ResolutionPolicy",
    "LinkageHint",
    "OverallPolicy",
    "QueryIntentHint",
    "TemporalOrientation",
    "EventType",
    "DomainCategory",
    "ResolutionSource",
    "SessionNonPermission",
    # Dataclasses
    "GroundingCandidate",
    "ClauseGroundingResult",
    "PhaseMinusOneEnvelope",
    "AmbiguityResolution",
    "FuzzyQuerySignals",
    "SessionContext",
    "SessionEvent",
    "DomainAccumulator",
    "PersonaSignals",
    "PriorGroundingProjection",
    "SessionAwareFuzzySignals",
    "SessionConstraintEffect",
    "SessionProjection",
    "SessionAuditEntry",
    "SessionSummary",
    # Components
    "ObserverObservedGrounding",
    "AmbiguityResolver",
    "ConservativeClauseSplitter",
    "PhaseMinusOnePipeline",
    "FuzzyQueryClassifier",
    # Configuration
    "SESSION_INFLUENCE_WINDOW",
    "DECAY_HALF_LIFE",
    "CONTRADICTION_THRESHOLD",
    "MAX_RESOLUTION_BIAS",
]
