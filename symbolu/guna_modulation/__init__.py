"""
Guna Entropy Modulation Module
==============================

Symbol-U v2.6 - Deterministic, Zero-Parameter, Non-Learning System

This module implements a Guna-aware entropy modulation layer that operates
after truth is computed, controlling only delivery intensity, not meaning.

The layer is purely mathematical, deterministic, and v2.6-safe.

CANONICAL OUTPUT EQUATION (MANDATORY):
    OUTPUT_intensity = BASE_intensity * E

ENTROPY MODULATION FACTOR (MANDATORY):
    E = G * P * T

Where:
    - G = w_S * S + w_R * R + w_T * T  (Guna coefficient)
    - P = clamp(1 - r_risk - r_escalation, 0, 1)  (Policy scalar)
    - T = tier_scalar  (Tier scalar: 1.0, 0.9, or 0.85)

GUNA DERIVATION (EXCLUSIVE):
    S_raw = C_s * (1 - H)
    R_raw = M * (1 - |H - H_mid|)
    T_raw = H * (1 - C_s)
    [S, R, T] = normalize([S_raw, R_raw, T_raw])

Where:
    - C_s: Structural coherence [0,1]
    - M: Motion / transformation magnitude [0,1]
    - H: Entropy [0,1]
    - H_mid = 0.5
    - epsilon = 10^-9

EXPLICIT NON-CAPABILITIES (MANDATORY):
    - No learning
    - No adaptation
    - No state memory
    - No evaluation of "better" or "worse"
    - No psychology
    - No morality
    - No feedback loops
    - No preference formation

This layer is scalar modulation only.

LAYMAN EXPLANATION:
    "The system already knows the answer.
     This layer only controls how strongly it speaks, using fixed mathematical
     knobs - like a volume control, not thinking."

CLASSIFICATION:
    - SymbolU v2.6
    - Deterministic
    - Non-normative
    - Enterprise-safe
    - Patent-aligned

Usage:
    from symbolu.guna_modulation import (
        EntropyModulationEngine,
        modulate_intensity,
        TIER_1_MODULATION_CONFIG,
    )

    # Using the engine
    engine = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)
    result = engine.modulate(
        base_intensity=0.8,
        C_s=0.7,  # Structural coherence
        M=0.5,    # Motion magnitude
        H=0.3,    # Entropy
    )
    print(result.output_intensity)

    # Using the standalone function
    result = modulate_intensity(
        base_intensity=0.8,
        C_s=0.7,
        M=0.5,
        H=0.3,
    )

Version: 2.6.0
Date: 2025-12-22
"""

# Types
from symbolu.guna_modulation.types import (
    # Constants
    H_MID,
    EPSILON,
    # Enums
    ModulationTier,
    # Core types
    GunaVector,
    PipelineInputs,
    GunaWeights,
    PolicyConfig,
    ModulationTraceEntry,
    ModulationResult,
    TierModulationConfig,
)

# Configuration
from symbolu.guna_modulation.config import (
    # Tier scalars
    TIER_SCALARS,
    # Default weights
    DEFAULT_GUNA_WEIGHTS,
    NEUTRAL_GUNA_WEIGHTS,
    # Default policy
    DEFAULT_POLICY_CONFIG,
    # Tier configs
    TIER_1_MODULATION_CONFIG,
    TIER_2_MODULATION_CONFIG,
    TIER_3_MODULATION_CONFIG,
    TIER_MODULATION_CONFIGS,
    # Access functions
    get_tier_modulation_config,
    get_tier_modulation_config_by_name,
    get_tier_scalar,
    list_tiers,
    # Custom config
    create_custom_config,
    create_disabled_config,
)

# Guna derivation
from symbolu.guna_modulation.guna_derivation import (
    # Raw component computation
    compute_sattva_raw,
    compute_rajas_raw,
    compute_tamas_raw,
    # Normalization
    normalize_guna_components,
    # Main derivation
    derive_guna_vector,
    derive_guna_from_values,
    derive_guna_with_trace,
)

# Engine and modulation
from symbolu.guna_modulation.entropy_modulation_engine import (
    # Computation functions
    compute_guna_coefficient,
    compute_policy_scalar,
    compute_entropy_modulation_factor,
    compute_output_intensity,
    # Engine
    EntropyModulationEngine,
    # Factory functions
    create_engine,
    create_engine_for_tier,
    create_engine_for_tier_name,
    # Standalone function
    modulate_intensity,
)


__all__ = [
    # Constants
    "H_MID",
    "EPSILON",
    # Enums
    "ModulationTier",
    # Core types
    "GunaVector",
    "PipelineInputs",
    "GunaWeights",
    "PolicyConfig",
    "ModulationTraceEntry",
    "ModulationResult",
    "TierModulationConfig",
    # Tier scalars
    "TIER_SCALARS",
    # Default weights
    "DEFAULT_GUNA_WEIGHTS",
    "NEUTRAL_GUNA_WEIGHTS",
    # Default policy
    "DEFAULT_POLICY_CONFIG",
    # Tier configs
    "TIER_1_MODULATION_CONFIG",
    "TIER_2_MODULATION_CONFIG",
    "TIER_3_MODULATION_CONFIG",
    "TIER_MODULATION_CONFIGS",
    # Config access functions
    "get_tier_modulation_config",
    "get_tier_modulation_config_by_name",
    "get_tier_scalar",
    "list_tiers",
    "create_custom_config",
    "create_disabled_config",
    # Raw component computation
    "compute_sattva_raw",
    "compute_rajas_raw",
    "compute_tamas_raw",
    # Normalization
    "normalize_guna_components",
    # Guna derivation
    "derive_guna_vector",
    "derive_guna_from_values",
    "derive_guna_with_trace",
    # Computation functions
    "compute_guna_coefficient",
    "compute_policy_scalar",
    "compute_entropy_modulation_factor",
    "compute_output_intensity",
    # Engine
    "EntropyModulationEngine",
    # Factory functions
    "create_engine",
    "create_engine_for_tier",
    "create_engine_for_tier_name",
    # Standalone function
    "modulate_intensity",
]


# =============================================================================
# Module-level convenience aliases
# =============================================================================

# Primary entry point
Engine = EntropyModulationEngine

# Quick modulation
modulate = modulate_intensity
