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
- PhaseMinusOnePipeline: Orchestrates all PO1 stages

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
    # Dataclasses
    "GroundingCandidate",
    "ClauseGroundingResult",
    "PhaseMinusOneEnvelope",
    "AmbiguityResolution",
    "FuzzyQuerySignals",
    # Components
    "ObserverObservedGrounding",
    "AmbiguityResolver",
    "ConservativeClauseSplitter",
    "PhaseMinusOnePipeline",
    "FuzzyQueryClassifier",
]
