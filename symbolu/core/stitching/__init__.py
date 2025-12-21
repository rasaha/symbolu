"""
Stitching Module - Cross-Domain Reasoning via Constrained Optimization
=======================================================================

This module implements the Stitching Encoder for Symbol-U, providing:
- Cross-domain reasoning with controlled analogies
- Relevance scoring using domain-agnostic aspects
- Redundancy and domain-jump penalties
- Constraint enforcement and audit trails

Patent Reference:
    Claim [2]  - Relevance scoring with resonance coupling
    Claim [12] - Resonance modulation coefficient λres
    Claim [13] - Governance gates including cross-domain entropy gate
"""

from symbolu.core.stitching.stitching_engine import (
    StitchingEngine,
    StitchingConfig,
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

__all__ = [
    # Engine
    "StitchingEngine",
    "StitchingConfig",
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
]
