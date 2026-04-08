"""
Entropy Engine Configuration
=============================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                         TIER CONFIGURATIONS                                    ║
║                                                                                ║
║  Pre-defined configurations for each tier.                                     ║
║  One engine, three configurations.                                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝

The same Entropy Engine code runs everywhere - only configuration differs.
This preserves: one mental model, one math, one truth.

Authority scales by tier:
    Tier 1 (Enterprise Search): DIAGNOSTIC_ONLY - no behavioral impact
    Tier 2 (Enterprise Chat):   MODULATION_ONLY - advisory only
    Tier 3 (Consumer):          FULL_GATING - expression gate only

Version: 1.0
Date: 2025-12-21
"""

from agentic.entropy.types import TierConfig, EntropyMode


# =============================================================================
# Tier 1 — Enterprise Search (Pure STL)
# =============================================================================

TIER_1_CONFIG = TierConfig(
    tier_name="enterprise_search",
    mode=EntropyMode.DIAGNOSTIC_ONLY,
    modulation_threshold=0.5,   # Not used in this tier
    block_threshold=0.85,       # Not used in this tier
    guna_weight=0.30,
    kosha_weight=0.30,
    cross_domain_weight=0.40,
)
"""
Tier 1 — Enterprise Search (Pure STL)

Status: ACTIVE (DIAGNOSTIC ONLY)

What it does:
    - Computes Guna entropy and Kosha entropy
    - Logs entropy metrics
    - Produces no modulation
    - Produces no gating

Why:
    - Tier 1 is substrate-level
    - No generation, no expression layer
    - Entropy here is telemetry only

Authority: NONE
Cannot block or alter anything.
"""


# =============================================================================
# Tier 2 — Enterprise Chat (STL + 7B)
# =============================================================================

TIER_2_CONFIG = TierConfig(
    tier_name="enterprise_chat",
    mode=EntropyMode.MODULATION_ONLY,
    modulation_threshold=0.5,   # Above this: suggest modulation
    block_threshold=0.85,       # Not used in this tier
    guna_weight=0.30,
    kosha_weight=0.30,
    cross_domain_weight=0.40,
)
"""
Tier 2 — Enterprise Chat (STL + 7B)

Status: ACTIVE (MODULATION ONLY)

What it does:
    - Computes entropy
    - Applies tone / verbosity modulation
    - Cannot block output
    - Cannot change meaning

Why:
    - Enterprise chat must remain predictable
    - Customers expect answers, not refusal
    - Regulation must be soft

Allowed actions:
    - Soften tone
    - Reduce verbosity
    - Increase abstraction

Disallowed:
    - Hard blocking
    - Semantic rewriting

Authority: LOW–MEDIUM (advisory)
"""


# =============================================================================
# Tier 3 — Consumer (STL + 768D + Cascade)
# =============================================================================

TIER_3_CONFIG = TierConfig(
    tier_name="consumer",
    mode=EntropyMode.FULL_GATING,
    modulation_threshold=0.5,   # Above this: apply modulation
    block_threshold=0.85,       # Above this: block (rare)
    guna_weight=0.30,
    kosha_weight=0.30,
    cross_domain_weight=0.40,
)
"""
Tier 3 — Consumer (STL + 768D + Cascade)

Status: ACTIVE (FULL GATING ENABLED)

What it does:
    - Computes entropy
    - Applies modulation
    - Can gate expression when entropy is extreme

Why:
    - Consumer tier includes:
        - Ambiguous queries
        - Emotional content
        - Cross-domain synthesis
    - Requires final expression safety

Gate outcomes:
    - ALLOW
    - ALLOW_WITH_MODULATION
    - BLOCK (rare, structural incoherence only)

Important:
    - Blocking is based on entropy, not policy
    - No content rules
    - No ethical judgments

Authority: MEDIUM (expression gate only)
"""


# =============================================================================
# Configuration Registry
# =============================================================================

TIER_CONFIGS = {
    "enterprise_search": TIER_1_CONFIG,
    "enterprise_chat": TIER_2_CONFIG,
    "consumer": TIER_3_CONFIG,
    # Aliases
    "tier_1": TIER_1_CONFIG,
    "tier_2": TIER_2_CONFIG,
    "tier_3": TIER_3_CONFIG,
    "search": TIER_1_CONFIG,
    "chat": TIER_2_CONFIG,
}


def get_tier_config(tier_name: str) -> TierConfig:
    """
    Get the configuration for a named tier.

    Args:
        tier_name: One of:
            - "enterprise_search", "tier_1", "search"
            - "enterprise_chat", "tier_2", "chat"
            - "consumer", "tier_3"

    Returns:
        TierConfig for the specified tier

    Raises:
        ValueError: If tier_name is unknown
    """
    tier_key = tier_name.lower().strip()
    if tier_key not in TIER_CONFIGS:
        valid_keys = sorted(set(TIER_CONFIGS.keys()))
        raise ValueError(
            f"Unknown tier: '{tier_name}'. Valid options: {valid_keys}"
        )
    return TIER_CONFIGS[tier_key]


def list_tiers() -> list:
    """List all available tier names."""
    return ["enterprise_search", "enterprise_chat", "consumer"]


# =============================================================================
# Custom Configuration Builder
# =============================================================================

def create_custom_config(
    tier_name: str,
    mode: EntropyMode,
    *,
    modulation_threshold: float = 0.5,
    block_threshold: float = 0.85,
    guna_weight: float = 0.30,
    kosha_weight: float = 0.30,
    cross_domain_weight: float = 0.40,
) -> TierConfig:
    """
    Create a custom tier configuration.

    Use this for testing or experimental configurations.
    Production should use the pre-defined TIER_*_CONFIG constants.

    Args:
        tier_name: Custom tier identifier
        mode: Operating mode (DIAGNOSTIC_ONLY, MODULATION_ONLY, FULL_GATING)
        modulation_threshold: Entropy level to trigger modulation
        block_threshold: Entropy level to trigger block
        guna_weight: Weight for guna entropy (must sum to 1.0 with others)
        kosha_weight: Weight for kosha entropy
        cross_domain_weight: Weight for cross-domain entropy

    Returns:
        Custom TierConfig

    Raises:
        ValueError: If weights don't sum to 1.0 or thresholds are invalid
    """
    return TierConfig(
        tier_name=tier_name,
        mode=mode,
        modulation_threshold=modulation_threshold,
        block_threshold=block_threshold,
        guna_weight=guna_weight,
        kosha_weight=kosha_weight,
        cross_domain_weight=cross_domain_weight,
    )
