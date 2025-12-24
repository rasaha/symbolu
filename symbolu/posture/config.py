"""
Posture Configuration Presets
=============================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                    PRE-DEFINED POSTURE PROFILES                                ║
║                                                                                ║
║  Enterprise-ready configurations for common deployment scenarios.              ║
║  All profiles respect hard safety constraints.                                 ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Available Presets:
    - BALANCED_DEFAULT: Equal weighting, neutral behavior
    - CONSERVATIVE_ENTERPRISE: Cautious, minimal risk
    - EXPLORATORY_RESEARCH: Adaptive, learning-oriented
    - HIGH_COHERENCE: Thorough explanations, audit-focused
    - HIGH_CONSTRAINT: Maximum caution, strict refusal

Version: 1.0
Date: 2025-12-22
"""

from typing import Dict, Optional
from symbolu.posture.types import (
    DecisionPostureProfile,
    PostureConfig,
    PostureTier,
)


# =============================================================================
# Preset Profiles
# =============================================================================

BALANCED_DEFAULT = DecisionPostureProfile(
    coherence_bias=0.34,
    exploration_bias=0.33,
    constraint_bias=0.33,
)
"""
Balanced Default Profile

The recommended starting point for most deployments.
Equal weighting across all biases ensures neutral behavior.

Use when:
    - Starting a new deployment
    - No specific behavioral requirements
    - Default fallback needed

Characteristics:
    - Neutral routing sensitivity
    - Balanced response depth
    - Standard conservatism
"""


CONSERVATIVE_ENTERPRISE = DecisionPostureProfile(
    coherence_bias=0.35,
    exploration_bias=0.15,
    constraint_bias=0.50,
)
"""
Conservative Enterprise Profile

Designed for risk-averse enterprise deployments where caution is paramount.

Use when:
    - Financial or healthcare domains
    - High regulatory scrutiny
    - Customer-facing critical systems
    - Zero tolerance for unexpected behavior

Characteristics:
    - Higher routing thresholds (careful escalation)
    - Reduced exploration (stable behavior)
    - Strict conservatism (prefer refusal over risk)
    - Slower feedback loop activation
"""


EXPLORATORY_RESEARCH = DecisionPostureProfile(
    coherence_bias=0.30,
    exploration_bias=0.50,
    constraint_bias=0.20,
)
"""
Exploratory Research Profile

Designed for research and development environments where
learning and adaptation are priorities.

Use when:
    - Internal R&D testing
    - Training data collection
    - Feature exploration
    - Non-production environments

Characteristics:
    - Lower routing thresholds (aggressive cascade)
    - High exploration (try more variations)
    - Relaxed conservatism (fewer refusals)
    - Active feedback loops
"""


HIGH_COHERENCE = DecisionPostureProfile(
    coherence_bias=0.55,
    exploration_bias=0.25,
    constraint_bias=0.20,
)
"""
High Coherence Profile

Designed for deployments requiring detailed explanations and audit trails.

Use when:
    - Compliance-heavy environments
    - Decision audit requirements
    - Customer explanation needs
    - Quality over speed priority

Characteristics:
    - Deep response explanations
    - Thorough routing decisions
    - Balanced conservatism
    - Clear audit trails
"""


HIGH_CONSTRAINT = DecisionPostureProfile(
    coherence_bias=0.25,
    exploration_bias=0.10,
    constraint_bias=0.65,
)
"""
High Constraint Profile

Maximum caution mode for highly sensitive deployments.

Use when:
    - Legal/regulatory uncertainty
    - Temporary lockdown needed
    - Unknown edge case handling
    - Defensive posture required

Characteristics:
    - Strict refusal thresholds
    - Minimal exploration
    - Conservative routing
    - Frequent escalation to human review
"""


# =============================================================================
# Profile Registry
# =============================================================================

PRESET_PROFILES: Dict[str, DecisionPostureProfile] = {
    "balanced": BALANCED_DEFAULT,
    "balanced_default": BALANCED_DEFAULT,
    "default": BALANCED_DEFAULT,
    "conservative": CONSERVATIVE_ENTERPRISE,
    "conservative_enterprise": CONSERVATIVE_ENTERPRISE,
    "enterprise": CONSERVATIVE_ENTERPRISE,
    "exploratory": EXPLORATORY_RESEARCH,
    "exploratory_research": EXPLORATORY_RESEARCH,
    "research": EXPLORATORY_RESEARCH,
    "coherence": HIGH_COHERENCE,
    "high_coherence": HIGH_COHERENCE,
    "audit": HIGH_COHERENCE,
    "constraint": HIGH_CONSTRAINT,
    "high_constraint": HIGH_CONSTRAINT,
    "lockdown": HIGH_CONSTRAINT,
}


def get_preset_profile(name: str) -> DecisionPostureProfile:
    """
    Get a preset profile by name.

    Args:
        name: One of the registered preset names (case-insensitive)

    Returns:
        DecisionPostureProfile for the requested preset

    Raises:
        ValueError: If the preset name is not recognized
    """
    key = name.lower().strip()
    if key not in PRESET_PROFILES:
        valid = sorted(set(PRESET_PROFILES.keys()))
        raise ValueError(f"Unknown preset: '{name}'. Valid options: {valid}")
    return PRESET_PROFILES[key]


def list_presets() -> list:
    """List all available preset names."""
    return ["balanced", "conservative", "exploratory", "coherence", "constraint"]


# =============================================================================
# Default Configurations by Tier
# =============================================================================

TIER_DEFAULT_CONFIGS: Dict[PostureTier, PostureConfig] = {
    PostureTier.TIER_1: PostureConfig(
        default_profile=BALANCED_DEFAULT,
        allow_request_override=False,  # No posture influence in Tier 1
        max_adjustment_magnitude=0.0,   # Zero adjustment
        enable_audit_logging=True,
    ),
    PostureTier.TIER_2: PostureConfig(
        default_profile=CONSERVATIVE_ENTERPRISE,  # Enterprise default
        allow_request_override=True,
        max_adjustment_magnitude=0.08,  # Limited adjustment
        enable_audit_logging=True,
    ),
    PostureTier.TIER_3: PostureConfig(
        default_profile=BALANCED_DEFAULT,
        allow_request_override=True,
        max_adjustment_magnitude=0.10,  # Full adjustment range
        enable_audit_logging=True,
    ),
}


def get_tier_default_config(tier: PostureTier) -> PostureConfig:
    """Get the default configuration for a tier."""
    return TIER_DEFAULT_CONFIGS.get(tier, TIER_DEFAULT_CONFIGS[PostureTier.TIER_3])


# =============================================================================
# Profile Builder
# =============================================================================

def create_custom_profile(
    coherence: float = 0.34,
    exploration: float = 0.33,
    constraint: float = 0.33,
    normalize: bool = True,
) -> DecisionPostureProfile:
    """
    Create a custom posture profile.

    Args:
        coherence: Coherence bias weight [0.0-1.0]
        exploration: Exploration bias weight [0.0-1.0]
        constraint: Constraint bias weight [0.0-1.0]
        normalize: Whether to normalize weights to sum to 1.0

    Returns:
        DecisionPostureProfile with specified weights
    """
    profile = DecisionPostureProfile(
        coherence_bias=coherence,
        exploration_bias=exploration,
        constraint_bias=constraint,
    )
    if normalize:
        return profile.normalize()
    return profile


def create_config(
    profile: Optional[DecisionPostureProfile] = None,
    allow_override: bool = True,
    max_adjustment: float = 0.10,
    enable_logging: bool = True,
) -> PostureConfig:
    """
    Create a custom posture configuration.

    Args:
        profile: Default profile (uses BALANCED_DEFAULT if None)
        allow_override: Whether per-request overrides are allowed
        max_adjustment: Maximum adjustment magnitude [0.0-0.20]
        enable_logging: Whether to log posture applications

    Returns:
        PostureConfig with specified settings
    """
    return PostureConfig(
        default_profile=profile or BALANCED_DEFAULT,
        allow_request_override=allow_override,
        max_adjustment_magnitude=max_adjustment,
        enable_audit_logging=enable_logging,
    )
