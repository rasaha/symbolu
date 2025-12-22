"""
Guna Entropy Modulation - Configuration
========================================

Symbol-U v2.6 - Deterministic, Zero-Parameter, Non-Learning System

Pre-defined tier configurations for the Guna-aware entropy modulation layer.

All configurations are operator-supplied constants.
No values imply good/bad or carry moral meaning.
No inference or judgment is performed.

EXPLICIT NON-CAPABILITIES:
    - No learning
    - No adaptation
    - No state memory
    - No evaluation of "better" or "worse"
    - No psychology
    - No morality
    - No feedback loops
    - No preference formation

Version: 2.6.0
Date: 2025-12-22
"""

from typing import Dict

from symbolu.guna_modulation.types import (
    ModulationTier,
    TierModulationConfig,
    GunaWeights,
    PolicyConfig,
)


# =============================================================================
# Tier Scalar Constants (MANDATORY - Fixed System Constants)
# =============================================================================

TIER_SCALARS: Dict[ModulationTier, float] = {
    ModulationTier.ENTERPRISE_TIER_1: 1.0,
    ModulationTier.ENTERPRISE_TIER_2: 0.9,
    ModulationTier.CONSUMER: 0.85,
}
"""
Fixed tier intensity scalars.

These are system constants with no evaluative meaning:
    - Enterprise Tier 1: 1.0 (full intensity)
    - Enterprise Tier 2: 0.9 (reduced intensity)
    - Consumer: 0.85 (conservative intensity)
"""


# =============================================================================
# Default Guna Weights (Illustrative - Operator Configurable)
# =============================================================================

DEFAULT_GUNA_WEIGHTS = GunaWeights(
    w_S=0.9,
    w_R=1.05,
    w_T=0.6,
)
"""
Default Guna weights (illustrative only).

These are operator-configurable constants:
    - w_S = 0.9 (Sattva weight)
    - w_R = 1.05 (Rajas weight)
    - w_T = 0.6 (Tamas weight)

No defaults imply good/bad.
Operators may override these values.
"""

NEUTRAL_GUNA_WEIGHTS = GunaWeights(
    w_S=1.0,
    w_R=1.0,
    w_T=1.0,
)
"""
Neutral Guna weights (disable modulation effect).

When all weights are 1.0, G equals (S + R + T) = 1.0,
resulting in no modulation effect from Guna components.
"""


# =============================================================================
# Default Policy Configuration
# =============================================================================

DEFAULT_POLICY_CONFIG = PolicyConfig(
    r_risk=0.0,
    r_escalation=0.0,
)
"""
Default policy configuration (no risk/escalation adjustment).

When r_risk = r_escalation = 0, P = 1.0 (no policy modulation).
"""


# =============================================================================
# Tier Configurations
# =============================================================================

TIER_1_MODULATION_CONFIG = TierModulationConfig(
    tier=ModulationTier.ENTERPRISE_TIER_1,
    tier_scalar=TIER_SCALARS[ModulationTier.ENTERPRISE_TIER_1],
    guna_weights=DEFAULT_GUNA_WEIGHTS,
    policy_config=DEFAULT_POLICY_CONFIG,
)
"""
Enterprise Tier 1 Configuration.

Full intensity tier with default modulation parameters.
T = 1.0 (maximum tier scalar)
"""

TIER_2_MODULATION_CONFIG = TierModulationConfig(
    tier=ModulationTier.ENTERPRISE_TIER_2,
    tier_scalar=TIER_SCALARS[ModulationTier.ENTERPRISE_TIER_2],
    guna_weights=DEFAULT_GUNA_WEIGHTS,
    policy_config=DEFAULT_POLICY_CONFIG,
)
"""
Enterprise Tier 2 Configuration.

Reduced intensity tier with default modulation parameters.
T = 0.9 (reduced tier scalar)
"""

TIER_3_MODULATION_CONFIG = TierModulationConfig(
    tier=ModulationTier.CONSUMER,
    tier_scalar=TIER_SCALARS[ModulationTier.CONSUMER],
    guna_weights=DEFAULT_GUNA_WEIGHTS,
    policy_config=DEFAULT_POLICY_CONFIG,
)
"""
Consumer Tier Configuration.

Conservative intensity tier with default modulation parameters.
T = 0.85 (conservative tier scalar)
"""


# =============================================================================
# Configuration Registry
# =============================================================================

TIER_MODULATION_CONFIGS: Dict[ModulationTier, TierModulationConfig] = {
    ModulationTier.ENTERPRISE_TIER_1: TIER_1_MODULATION_CONFIG,
    ModulationTier.ENTERPRISE_TIER_2: TIER_2_MODULATION_CONFIG,
    ModulationTier.CONSUMER: TIER_3_MODULATION_CONFIG,
}

# Aliases for string-based lookup
TIER_CONFIG_ALIASES: Dict[str, ModulationTier] = {
    "enterprise_tier_1": ModulationTier.ENTERPRISE_TIER_1,
    "enterprise_tier_2": ModulationTier.ENTERPRISE_TIER_2,
    "consumer": ModulationTier.CONSUMER,
    "tier_1": ModulationTier.ENTERPRISE_TIER_1,
    "tier_2": ModulationTier.ENTERPRISE_TIER_2,
    "tier_3": ModulationTier.CONSUMER,
    "enterprise_1": ModulationTier.ENTERPRISE_TIER_1,
    "enterprise_2": ModulationTier.ENTERPRISE_TIER_2,
}


# =============================================================================
# Configuration Access Functions
# =============================================================================

def get_tier_modulation_config(
    tier: ModulationTier,
) -> TierModulationConfig:
    """
    Get the modulation configuration for a tier.

    Args:
        tier: The tier enum value.

    Returns:
        TierModulationConfig for the specified tier.

    Raises:
        KeyError: If tier is not found.
    """
    return TIER_MODULATION_CONFIGS[tier]


def get_tier_modulation_config_by_name(
    tier_name: str,
) -> TierModulationConfig:
    """
    Get the modulation configuration for a tier by name.

    Args:
        tier_name: String name for the tier.
            Valid names: "enterprise_tier_1", "tier_1", "enterprise_1",
                        "enterprise_tier_2", "tier_2", "enterprise_2",
                        "consumer", "tier_3"

    Returns:
        TierModulationConfig for the specified tier.

    Raises:
        ValueError: If tier_name is unknown.
    """
    tier_key = tier_name.lower().strip()
    if tier_key not in TIER_CONFIG_ALIASES:
        valid_keys = sorted(set(TIER_CONFIG_ALIASES.keys()))
        raise ValueError(
            f"Unknown tier: '{tier_name}'. Valid options: {valid_keys}"
        )
    tier = TIER_CONFIG_ALIASES[tier_key]
    return TIER_MODULATION_CONFIGS[tier]


def get_tier_scalar(tier: ModulationTier) -> float:
    """
    Get the tier scalar constant for a tier.

    Args:
        tier: The tier enum value.

    Returns:
        Tier scalar (1.0, 0.9, or 0.85).
    """
    return TIER_SCALARS[tier]


def list_tiers() -> list:
    """List all available tier names."""
    return ["enterprise_tier_1", "enterprise_tier_2", "consumer"]


# =============================================================================
# Custom Configuration Builder
# =============================================================================

def create_custom_config(
    tier: ModulationTier,
    *,
    w_S: float = 0.9,
    w_R: float = 1.05,
    w_T: float = 0.6,
    r_risk: float = 0.0,
    r_escalation: float = 0.0,
    tier_scalar_override: float = None,
) -> TierModulationConfig:
    """
    Create a custom tier modulation configuration.

    Use this for testing or specialized configurations.
    Production should use the pre-defined TIER_*_MODULATION_CONFIG constants.

    Args:
        tier: The tier enum value.
        w_S: Sattva weight (default: 0.9)
        w_R: Rajas weight (default: 1.05)
        w_T: Tamas weight (default: 0.6)
        r_risk: Risk factor (default: 0.0)
        r_escalation: Escalation factor (default: 0.0)
        tier_scalar_override: Override tier scalar (default: use tier default)

    Returns:
        Custom TierModulationConfig.
    """
    tier_scalar = (
        tier_scalar_override
        if tier_scalar_override is not None
        else TIER_SCALARS[tier]
    )

    return TierModulationConfig(
        tier=tier,
        tier_scalar=tier_scalar,
        guna_weights=GunaWeights(w_S=w_S, w_R=w_R, w_T=w_T),
        policy_config=PolicyConfig(r_risk=r_risk, r_escalation=r_escalation),
    )


def create_disabled_config(tier: ModulationTier) -> TierModulationConfig:
    """
    Create a configuration that disables modulation.

    When w_S = w_R = w_T = 1.0 and r_risk = r_escalation = 0,
    the entropy modulation factor E = 1.0 and OUTPUT_intensity = BASE_intensity.

    This satisfies the disable proof requirement.

    Args:
        tier: The tier enum value.

    Returns:
        TierModulationConfig with disabled modulation.
    """
    return TierModulationConfig(
        tier=tier,
        tier_scalar=1.0,  # Override to 1.0 for full disable
        guna_weights=NEUTRAL_GUNA_WEIGHTS,
        policy_config=PolicyConfig(r_risk=0.0, r_escalation=0.0),
    )
