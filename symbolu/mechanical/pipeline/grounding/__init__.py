"""
Symbol-U Phase −1 Grounding Module

Pre-pipeline grounding analysis to establish observer-observed relationships
before any semantic or discourse processing occurs.

Components:
- Phase −1.0: Observer-Observed Grounding (OOG)
- Phase −1.1: Ambiguity Resolver (ARL)
- Phase −1.2: Conservative Clause Splitter (CSL)
- PhaseMinusOnePipeline: Orchestrates all Phase −1 stages

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
from .phase_minus_one_ambiguity import AmbiguityResolver
from .phase_minus_one_clause_splitter import ConservativeClauseSplitter
from .phase_minus_one_pipeline import PhaseMinusOnePipeline

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
    # Components
    "ObserverObservedGrounding",
    "AmbiguityResolver",
    "ConservativeClauseSplitter",
    "PhaseMinusOnePipeline",
]
