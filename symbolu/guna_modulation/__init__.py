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

SIGNAL WIRING (v2.6.1):
    H is computed from operator-selectable entropy sources:
        - GUNA: H = H_G / ln(3)  [DEFAULT]
        - DIMENSIONAL: H = H_D / ln(10)
        - KOSHA: H = H_K / ln(5)

    M is computed from operator-selectable motion modes:
        - SEMANTIC: M = delta_sem  [DEFAULT]
        - STRUCTURAL: M = delta_str_norm
        - EXPERIENTIAL: M = delta_exp
        - COMPOSITE: M = weighted average of all deltas

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

    # Using pipeline integration with signal wiring
    from symbolu.guna_modulation import (
        PipelineModulationEngine,
        EntropyMode,
        MotionMode,
        SignalWiringConfig,
    )

    engine = PipelineModulationEngine(
        wiring_config=SignalWiringConfig(
            entropy_mode=EntropyMode.GUNA,  # H = H_G / ln(3)
            motion_mode=MotionMode.SEMANTIC,  # M = delta_sem
        ),
    )
    result = engine.modulate_from_pipeline(
        base_intensity=0.8,
        C_s=0.7,
        H_G=0.5, H_D=1.0, H_K=0.3,
        candidate_aspect_vector={"clarity": 0.8},
        context_aspect_vector={"clarity": 0.7},
        domain_jump_count=1,
        intent="informative",
    )

Version: 2.6.1
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

# Signal wiring (v2.6.1)
from symbolu.guna_modulation.signal_wiring import (
    # Constants
    LN_3,
    LN_5,
    LN_10,
    MAX_STRUCTURAL_JUMPS,
    EXPERIENTIAL_MOTION_INTENTS,
    # Enums (operator-selectable modes)
    EntropyMode,
    MotionMode,
    # Audit types
    EntropyWiringAudit,
    MotionWiringAudit,
    SignalWiringAudit,
    WiredSignals,
    # Configuration
    SignalWiringConfig,
    DEFAULT_WIRING_CONFIG,
    # Entropy computation
    compute_H,
    # Motion delta computation
    compute_semantic_delta,
    compute_structural_delta,
    compute_experiential_delta,
    # Motion computation
    compute_M,
    compute_M_from_raw,
    # Full signal wiring
    wire_signals,
    wire_signals_simple,
)

# Pipeline integration (v2.6.1)
from symbolu.guna_modulation.pipeline_integration import (
    # Result type
    IntegratedModulationResult,
    # Pipeline engine
    PipelineModulationEngine,
    # Factory functions
    create_pipeline_engine,
    create_default_pipeline_engine,
    # Standalone function
    modulate_from_pipeline,
)

# Pipeline signal adapter (v2.6.1) - wires to existing pipeline signals
from symbolu.guna_modulation.pipeline_signal_adapter import (
    # Intent mapping
    EXPERIENTIAL_INTENT_TYPES,
    intent_to_experiential_delta,
    # Delta computations from pipeline signals
    compute_semantic_delta_from_vectors,
    compute_structural_delta_from_stitching,
    # Entropy extraction
    extract_entropy_from_router_context,
    # Context aggregation
    PipelineSignalContext,
    # Adapter functions
    wire_from_pipeline_context,
    wire_signals_from_router_context,
    modulate_from_pipeline_context,
)

# =============================================================================
# v2.7 State Evolution (Deterministic Evaluation Layer)
# =============================================================================

from symbolu.guna_modulation.state_types import (
    # Constants
    DEFAULT_ALPHA,
    POLICY_BIAS_MAX,
    # State bounds
    StateBounds,
    DEFAULT_BOUNDS,
    # State register
    StateRegister,
    DEFAULT_STATE,
    # State delta
    StateDelta,
    # Utility functions
    normalize_weights,
    softmax_3,
)

from symbolu.guna_modulation.observables import (
    # Observables container
    Observables,
    # Factory functions
    observables_from_v26_pipeline,
    # Entropy computation
    compute_guna_entropy,
)

from symbolu.guna_modulation.utility import (
    # Constants
    LAMBDA_H,
    LAMBDA_C,
    LAMBDA_F,
    # Audit types
    UtilityAudit,
    TargetStateAudit,
    # Utility computation
    compute_utility,
    # Target computation
    compute_target_tau_768,
    compute_target_tau_175,
    compute_target_w_tone,
    compute_target_state,
)

# v2.7 Configuration (Fix #1-5: Operator-configurable coefficients)
from symbolu.guna_modulation.v27_config import (
    # Tier identifiers
    TIER_ENTERPRISE_1,
    TIER_ENTERPRISE_2,
    TIER_CONSUMER,
    # Fix #1: Utility coefficients (operator-configurable signs)
    UtilityCoefficients,
    DEFAULT_UTILITY_COEFFICIENTS,
    NEUTRAL_UTILITY_COEFFICIENTS,
    # Fix #2: Alpha configuration (tier-specific with half-life)
    AlphaConfig,
    ALPHA_ENTERPRISE_T1,
    ALPHA_ENTERPRISE_T2,
    ALPHA_CONSUMER,
    DEFAULT_ALPHA_CONFIG,
    get_alpha_for_tier,
    # Fix #3: Tone logit configuration (named, bounded)
    ToneLogitConfig,
    DEFAULT_TONE_CONFIG,
    # Fix #4: State persistence configuration
    StatePersistenceConfig,
    PERSISTENCE_GLOBAL,
    PERSISTENCE_TENANT,
    PERSISTENCE_USER,
    PERSISTENCE_SESSION,
    DEFAULT_PERSISTENCE_CONFIG,
    # Master v2.7 configuration
    V27Config,
    DEFAULT_V27_CONFIG,
    ENABLED_V27_CONFIG,
    ENTERPRISE_T1_CONFIG,
    ENTERPRISE_T2_CONFIG,
    CONSUMER_CONFIG,
)

from symbolu.guna_modulation.state_evolution_engine import (
    # Audit types
    RuleFired,
    StateUpdateAudit,
    # Engine
    StateEvolutionEngine,
    # Factory functions
    create_evolution_engine,
    create_v26_engine,
    create_v27_engine,
    create_state_engine_for_tier,
    # Standalone function
    update_state,
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
    # =========================================================================
    # Signal Wiring (v2.6.1)
    # =========================================================================
    # Constants
    "LN_3",
    "LN_5",
    "LN_10",
    "MAX_STRUCTURAL_JUMPS",
    "EXPERIENTIAL_MOTION_INTENTS",
    # Enums (operator-selectable modes)
    "EntropyMode",
    "MotionMode",
    # Audit types
    "EntropyWiringAudit",
    "MotionWiringAudit",
    "SignalWiringAudit",
    "WiredSignals",
    # Configuration
    "SignalWiringConfig",
    "DEFAULT_WIRING_CONFIG",
    # Entropy computation
    "compute_H",
    # Motion delta computation
    "compute_semantic_delta",
    "compute_structural_delta",
    "compute_experiential_delta",
    # Motion computation
    "compute_M",
    "compute_M_from_raw",
    # Full signal wiring
    "wire_signals",
    "wire_signals_simple",
    # =========================================================================
    # Pipeline Integration (v2.6.1)
    # =========================================================================
    # Result type
    "IntegratedModulationResult",
    # Pipeline engine
    "PipelineModulationEngine",
    # Factory functions
    "create_pipeline_engine",
    "create_default_pipeline_engine",
    # Standalone function
    "modulate_from_pipeline",
    # =========================================================================
    # Pipeline Signal Adapter (v2.6.1)
    # =========================================================================
    # Intent mapping
    "EXPERIENTIAL_INTENT_TYPES",
    "intent_to_experiential_delta",
    # Delta computations from pipeline signals
    "compute_semantic_delta_from_vectors",
    "compute_structural_delta_from_stitching",
    # Entropy extraction
    "extract_entropy_from_router_context",
    # Context aggregation
    "PipelineSignalContext",
    # Adapter functions
    "wire_from_pipeline_context",
    "wire_signals_from_router_context",
    "modulate_from_pipeline_context",
    # =========================================================================
    # v2.7 State Evolution
    # =========================================================================
    # Constants
    "DEFAULT_ALPHA",
    "POLICY_BIAS_MAX",
    "LAMBDA_H",
    "LAMBDA_C",
    "LAMBDA_F",
    # State types
    "StateBounds",
    "DEFAULT_BOUNDS",
    "StateRegister",
    "DEFAULT_STATE",
    "StateDelta",
    # Observables
    "Observables",
    "observables_from_v26_pipeline",
    "compute_guna_entropy",
    # Utility computation
    "UtilityAudit",
    "TargetStateAudit",
    "compute_utility",
    "compute_target_tau_768",
    "compute_target_tau_175",
    "compute_target_w_tone",
    "compute_target_state",
    # =========================================================================
    # v2.7 Configuration (Fix #1-5)
    # =========================================================================
    # Tier identifiers
    "TIER_ENTERPRISE_1",
    "TIER_ENTERPRISE_2",
    "TIER_CONSUMER",
    # Fix #1: Utility coefficients
    "UtilityCoefficients",
    "DEFAULT_UTILITY_COEFFICIENTS",
    "NEUTRAL_UTILITY_COEFFICIENTS",
    # Fix #2: Alpha configuration
    "AlphaConfig",
    "ALPHA_ENTERPRISE_T1",
    "ALPHA_ENTERPRISE_T2",
    "ALPHA_CONSUMER",
    "DEFAULT_ALPHA_CONFIG",
    "get_alpha_for_tier",
    # Fix #3: Tone logit configuration
    "ToneLogitConfig",
    "DEFAULT_TONE_CONFIG",
    # Fix #4: State persistence configuration
    "StatePersistenceConfig",
    "PERSISTENCE_GLOBAL",
    "PERSISTENCE_TENANT",
    "PERSISTENCE_USER",
    "PERSISTENCE_SESSION",
    "DEFAULT_PERSISTENCE_CONFIG",
    # Master v2.7 configuration
    "V27Config",
    "DEFAULT_V27_CONFIG",
    "ENABLED_V27_CONFIG",
    "ENTERPRISE_T1_CONFIG",
    "ENTERPRISE_T2_CONFIG",
    "CONSUMER_CONFIG",
    # Audit types
    "RuleFired",
    "StateUpdateAudit",
    # Engine
    "StateEvolutionEngine",
    # Factory functions
    "create_evolution_engine",
    "create_v26_engine",
    "create_v27_engine",
    "create_state_engine_for_tier",
    # Standalone function
    "update_state",
    # Helper functions
    "normalize_weights",
    "softmax_3",
]


# =============================================================================
# Module-level convenience aliases
# =============================================================================

# Primary entry point
Engine = EntropyModulationEngine

# Quick modulation
modulate = modulate_intensity

# Pipeline integration entry point
PipelineEngine = PipelineModulationEngine

# v2.7 State Evolution entry point
EvolutionEngine = StateEvolutionEngine
