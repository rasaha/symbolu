"""
Stitching Module - Cross-Domain Reasoning via Constrained Optimization
=======================================================================

This module implements the Stitching Encoder for Symbol-U, providing:
- Cross-domain reasoning with controlled analogies
- Relevance scoring using domain-agnostic aspects
- Redundancy and domain-jump penalties
- Constraint enforcement and audit trails

Specification Reference:
    Project_documentation/repository/docs/architecture/STITCHING_FUSION_SPECIFICATION.md

Patent Reference:
    Claim [2]  - Relevance scoring with resonance coupling
    Claim [12] - Resonance modulation coefficient λres
    Claim [13] - Governance gates including cross-domain entropy gate
"""

from symbolu.core.stitching.stitching_engine import (
    StitchingEngine,
    StitchingConfig,
    StitchingResult,
    QueryContext,
    create_stitching_engine,
    create_query_context,
)
from symbolu.core.stitching.penalties import (
    PenaltyCalculator,
    PenaltyConfig,
    ScoredCandidate,
    StitchingConstraints,
)
from symbolu.core.stitching.domain_distance import (
    get_domain_distance,
    get_aspect_overlap,
    is_cross_domain,
    DOMAIN_DISTANCE_MATRIX,
    UNIVERSAL_ASPECTS,
)
from symbolu.core.stitching.objective import StitchingObjective

# New contracts per spec v1.1
from symbolu.core.stitching.contracts import (
    RejectionReason,
    CandidateDecision,
    StitchingDecision,
)
from symbolu.core.stitching.handoff import (
    StitchingToFusionHandoff,
    create_handoff,
)

__all__ = [
    # Engine
    "StitchingEngine",
    "StitchingConfig",
    "StitchingResult",
    "QueryContext",
    "create_stitching_engine",
    "create_query_context",
    # Penalties
    "PenaltyCalculator",
    "PenaltyConfig",
    "ScoredCandidate",
    "StitchingConstraints",
    # Domain Distance
    "get_domain_distance",
    "get_aspect_overlap",
    "is_cross_domain",
    "DOMAIN_DISTANCE_MATRIX",
    "UNIVERSAL_ASPECTS",
    # Objective (legacy compatibility)
    "StitchingObjective",
    # Contracts (spec v1.1)
    "RejectionReason",
    "CandidateDecision",
    "StitchingDecision",
    # Handoff (spec v1.1)
    "StitchingToFusionHandoff",
    "create_handoff",
]
