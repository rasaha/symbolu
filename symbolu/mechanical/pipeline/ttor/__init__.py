"""
TTOR v1.4 - Two-Tier Ontology Router

The cognitive bridge between the symbolic aspect engine (v2.6) and
the MLCR/Fusion/DHA engines (v2.7/v3.0) in the SOULPI pipeline.

This module provides deterministic, auditable routing based on:
- Symbolic Aspects (Execution → Universal)
- Experiential Anchors (Needs → Collective)
- Entropy Measures (Dimensional, Guna, Kosha)
- Domain Context & Risk Level
- Long-Arc Tension (future LAM integration)

Usage:
    from mechanical.pipeline.ttor import TTORRouter, RouterContext

    context = RouterContext(
        aspect_probs={"Execution": 0.8, "Cognition": 0.6},
        H_D=1.5,
        H_G=0.5,
        anchor_scores={"Needs": 0.7, "Exchange": 0.4},
        domain="task",
        risk_level="low",
    )

    router = TTORRouter()
    plan = router.route(context)

    print(plan.tier)        # Tier.LOWER
    print(plan.flow_mode)   # FlowMode.OUTER_ONLY
    print(plan.debug)       # Full audit trail
"""

from .constants import (
    ALL_ANCHORS,
    ALL_ASPECTS,
    ENTROPY_THRESHOLD,
    H_D_MAX,
    H_G_MAX,
    H_K_MAX,
    LOWER_ANCHORS,
    LOWER_ASPECTS,
    REGULATED_DOMAINS,
    REFLECTIVE_DOMAINS,
    TASK_DOMAINS,
    TENSION_THRESHOLD,
    TIER_THRESHOLD,
    UPPER_ANCHORS,
    UPPER_ASPECTS,
)
from .formulas import (
    anchor_boosts,
    aspect_base_scores,
    compute_conflict_score,
    compute_entropy_boosts,
    domain_modulation,
    entropy_mix,
    final_scores,
    normalize_to_unit_interval,
)
from .models import (
    FlowMode,
    RouterContext,
    RouterContextValidationError,
    RoutingPlan,
    Tier,
)
from .router import TTORRouter

__version__ = "1.4.0"

__all__ = [
    # Main classes
    "TTORRouter",
    "RouterContext",
    "RoutingPlan",
    # Enums
    "Tier",
    "FlowMode",
    # Exceptions
    "RouterContextValidationError",
    # Constants
    "LOWER_ASPECTS",
    "UPPER_ASPECTS",
    "ALL_ASPECTS",
    "LOWER_ANCHORS",
    "UPPER_ANCHORS",
    "ALL_ANCHORS",
    "TIER_THRESHOLD",
    "ENTROPY_THRESHOLD",
    "TENSION_THRESHOLD",
    "H_D_MAX",
    "H_G_MAX",
    "H_K_MAX",
    "TASK_DOMAINS",
    "REFLECTIVE_DOMAINS",
    "REGULATED_DOMAINS",
    # Formulas (for advanced usage)
    "aspect_base_scores",
    "anchor_boosts",
    "entropy_mix",
    "domain_modulation",
    "final_scores",
    "compute_entropy_boosts",
    "compute_conflict_score",
    "normalize_to_unit_interval",
]
