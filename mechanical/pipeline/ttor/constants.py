"""
TTOR v1.4 Constants Module

Defines all constant values for the Two-Tier Ontology Router including:
- Aspect groups (Lower/Upper tier classification)
- Anchor groups (Experiential anchors by tier)
- Thresholds for routing decisions
- Domain classifications

All values are immutable and form the foundation of deterministic routing.
"""

from typing import Final, FrozenSet, Tuple

# =============================================================================
# ASPECT GROUPS
# =============================================================================
# Lower-tier aspects: operational, concrete, identity-focused
LOWER_ASPECTS: Final[Tuple[str, ...]] = (
    "Execution",
    "Identity",
    "Form",
    "Cognition",
)

# Upper-tier aspects: abstract, meaning-focused, transcendent
UPPER_ASPECTS: Final[Tuple[str, ...]] = (
    "Agency",
    "Reasoning",
    "Purpose",
    "Observation",
    "Core",
    "Universal",
)

# Complete set of valid aspect keys for validation
ALL_ASPECTS: Final[FrozenSet[str]] = frozenset(LOWER_ASPECTS + UPPER_ASPECTS)

# =============================================================================
# EXPERIENTIAL ANCHOR GROUPS
# =============================================================================
# Lower-tier anchors: survival, exchange, challenge-focused
LOWER_ANCHORS: Final[Tuple[str, ...]] = (
    "Needs",
    "Exchange",
    "Challenge",
)

# Upper-tier anchors: connection, meaning, collective-focused
UPPER_ANCHORS: Final[Tuple[str, ...]] = (
    "Belonging",
    "Relation",
    "Change",
    "Meaning",
    "Role",
    "Collective",
)

# Complete set of valid anchor keys for validation
ALL_ANCHORS: Final[FrozenSet[str]] = frozenset(LOWER_ANCHORS + UPPER_ANCHORS)

# =============================================================================
# ROUTING THRESHOLDS
# =============================================================================
# Threshold for tier determination (difference between lower/upper scores)
TIER_THRESHOLD: Final[float] = 0.15

# Entropy threshold for flow mode selection
ENTROPY_THRESHOLD: Final[float] = 0.6

# Long-arc tension threshold for LAM activation
TENSION_THRESHOLD: Final[float] = 0.5

# =============================================================================
# ENTROPY BOUNDS
# =============================================================================
# Dimensional entropy maximum: ln(10) ≈ 2.303
H_D_MAX: Final[float] = 2.302585093  # ln(10)

# Guna entropy maximum: ln(3) ≈ 1.099
H_G_MAX: Final[float] = 1.098612289  # ln(3)

# Kosha entropy maximum: ln(5) ≈ 1.609
H_K_MAX: Final[float] = 1.609437912  # ln(5)

# =============================================================================
# DOMAIN CLASSIFICATIONS
# =============================================================================
# Task-oriented domains: favor lower tier, outer flow
TASK_DOMAINS: Final[Tuple[str, ...]] = (
    "task",
    "code",
    "math",
    "lookup",
)

# Reflective domains: favor upper tier, inner flow
REFLECTIVE_DOMAINS: Final[Tuple[str, ...]] = (
    "therapy",
    "philosophy",
    "spiritual",
    "identity",
)

# Regulated domains: require safety overrides
REGULATED_DOMAINS: Final[Tuple[str, ...]] = (
    "health",
    "finance",
    "legal",
)

# Complete set of all recognized domains
ALL_DOMAINS: Final[FrozenSet[str]] = frozenset(
    TASK_DOMAINS + REFLECTIVE_DOMAINS + REGULATED_DOMAINS + ("generic",)
)

# =============================================================================
# RISK LEVELS
# =============================================================================
VALID_RISK_LEVELS: Final[Tuple[str, ...]] = (
    "low",
    "medium",
    "high",
    "critical",
)

# =============================================================================
# ENGINE FAMILIES
# =============================================================================
ENGINE_FAMILY_PERSONA: Final[str] = "persona"
ENGINE_FAMILY_FUSION: Final[str] = "fusion"
ENGINE_FAMILY_DHA: Final[str] = "dha"
ENGINE_FAMILY_RENDERER_ONLY: Final[str] = "renderer_only"

# =============================================================================
# FORMULA WEIGHTS (for aspect and anchor scoring)
# =============================================================================
# Weights for combining aspect and anchor contributions
ASPECT_WEIGHT: Final[float] = 0.5
ANCHOR_WEIGHT: Final[float] = 0.3
ENTROPY_WEIGHT: Final[float] = 0.2

# Domain modulation factors
TASK_DOMAIN_LOWER_BOOST: Final[float] = 0.1
REFLECTIVE_DOMAIN_UPPER_BOOST: Final[float] = 0.1
