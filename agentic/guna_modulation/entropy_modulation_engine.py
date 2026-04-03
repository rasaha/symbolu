"""
Guna Entropy Modulation Engine
==============================

Symbol-U v2.6 - Deterministic, Zero-Parameter, Non-Learning System

This module implements the Guna-aware entropy modulation engine.
It operates after truth is computed, controlling only delivery intensity, not meaning.

CANONICAL OUTPUT EQUATION (MANDATORY):
    OUTPUT_intensity = BASE_intensity * E

ENTROPY MODULATION FACTOR (MANDATORY):
    E = G * P * T

Where:
    G = w_S * S + w_R * R + w_T * T  (Guna coefficient)
    P = clamp(1 - r_risk - r_escalation, 0, 1)  (Policy scalar)
    T = tier_scalar  (Tier scalar: 1.0, 0.9, or 0.85)

PLACEMENT IN PIPELINE:
    Input
     -> STL (10D symbolic reasoning)
     -> Canonical Matching (C x R x S)
     -> Tier Routing
     -> AGI Augmentation (optional)
     -> Guna Derivation (FORMULAS ABOVE)
     -> Entropy Modulation <-- THIS ENGINE
     -> Renderer
     -> Output

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
It controls how strongly the system speaks, not what it says.

LAYMAN EXPLANATION:
    "The system already knows the answer.
     This layer only controls how strongly it speaks, using fixed mathematical
     knobs - like a volume control, not thinking."

Version: 2.6.0
Date: 2025-12-22
"""

from typing import Tuple, Optional

from agentic.guna_modulation.types import (
    EPSILON,
    GunaVector,
    GunaWeights,
    PolicyConfig,
    PipelineInputs,
    ModulationTier,
    TierModulationConfig,
    ModulationTraceEntry,
    ModulationResult,
)
from agentic.guna_modulation.guna_derivation import derive_guna_vector
from agentic.guna_modulation.config import (
    get_tier_modulation_config,
    get_tier_scalar,
    TIER_1_MODULATION_CONFIG,
)


# =============================================================================
# Guna Coefficient Computation
# =============================================================================

def compute_guna_coefficient(
    guna_vector: GunaVector,
    weights: GunaWeights,
) -> Tuple[float, ModulationTraceEntry]:
    """
    Compute the Guna coefficient G.

    MANDATORY FORMULA:
        G = w_S * S + w_R * R + w_T * T

    This is a linear scalar projection of the Guna vector
    onto the operator-configured weight vector.

    Args:
        guna_vector: Derived Guna vector [S, R, T]
        weights: Operator-configured weights [w_S, w_R, w_T]

    Returns:
        Tuple of (G, trace_entry)

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    S, R, T = guna_vector.sattva, guna_vector.rajas, guna_vector.tamas
    w_S, w_R, w_T = weights.w_S, weights.w_R, weights.w_T

    G = w_S * S + w_R * R + w_T * T

    trace = ModulationTraceEntry(
        step_name="guna_coefficient",
        inputs=(
            ("S", S), ("R", R), ("T", T),
            ("w_S", w_S), ("w_R", w_R), ("w_T", w_T),
        ),
        output=G,
        formula="G = w_S * S + w_R * R + w_T * T",
    )

    return (G, trace)


# =============================================================================
# Policy Scalar Computation
# =============================================================================

def compute_policy_scalar(
    policy_config: PolicyConfig,
) -> Tuple[float, ModulationTraceEntry]:
    """
    Compute the Policy scalar P.

    MANDATORY FORMULA:
        P = clamp(1 - r_risk - r_escalation, 0, 1)

    No interpretation or judgment is allowed.
    This is pure mathematical computation.

    Args:
        policy_config: Operator-supplied policy constants

    Returns:
        Tuple of (P, trace_entry)

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    r_risk = policy_config.r_risk
    r_escalation = policy_config.r_escalation

    # Compute unclamped value
    P_unclamped = 1.0 - r_risk - r_escalation

    # Clamp to [0, 1]
    P = max(0.0, min(1.0, P_unclamped))

    trace = ModulationTraceEntry(
        step_name="policy_scalar",
        inputs=(("r_risk", r_risk), ("r_escalation", r_escalation)),
        output=P,
        formula="P = clamp(1 - r_risk - r_escalation, 0, 1)",
    )

    return (P, trace)


# =============================================================================
# Entropy Modulation Factor Computation
# =============================================================================

def compute_entropy_modulation_factor(
    G: float,
    P: float,
    T: float,
) -> Tuple[float, ModulationTraceEntry]:
    """
    Compute the Entropy Modulation Factor E.

    MANDATORY FORMULA:
        E = G * P * T

    No additional terms are permitted.

    Args:
        G: Guna coefficient
        P: Policy scalar
        T: Tier scalar

    Returns:
        Tuple of (E, trace_entry)

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    E = G * P * T

    trace = ModulationTraceEntry(
        step_name="entropy_modulation_factor",
        inputs=(("G", G), ("P", P), ("T", T)),
        output=E,
        formula="E = G * P * T",
    )

    return (E, trace)


# =============================================================================
# Output Intensity Computation
# =============================================================================

def compute_output_intensity(
    base_intensity: float,
    E: float,
) -> Tuple[float, ModulationTraceEntry]:
    """
    Compute the final output intensity.

    MANDATORY FORMULA:
        OUTPUT_intensity = BASE_intensity * E

    BASE_intensity MUST NOT be altered (only scaled).

    Args:
        base_intensity: Already computed by STL + routing + AGI
        E: Entropy modulation factor

    Returns:
        Tuple of (output_intensity, trace_entry)

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    output_intensity = base_intensity * E

    trace = ModulationTraceEntry(
        step_name="output_intensity",
        inputs=(("BASE_intensity", base_intensity), ("E", E)),
        output=output_intensity,
        formula="OUTPUT_intensity = BASE_intensity * E",
    )

    return (output_intensity, trace)


# =============================================================================
# Main Entropy Modulation Engine
# =============================================================================

class EntropyModulationEngine:
    """
    Guna-aware Entropy Modulation Engine.

    This engine operates after truth is computed, controlling only
    delivery intensity, not meaning.

    The engine is purely mathematical, deterministic, and v2.6-safe.

    EXPLICIT NON-CAPABILITIES:
        - No learning
        - No adaptation
        - No state memory
        - No evaluation of "better" or "worse"
        - No psychology
        - No morality
        - No feedback loops
        - No preference formation

    This layer is scalar modulation only.

    Example:
        engine = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)
        result = engine.modulate(
            base_intensity=0.8,
            C_s=0.7,  # Structural coherence
            M=0.5,    # Motion magnitude
            H=0.3,    # Entropy
        )
        print(result.output_intensity)
    """

    def __init__(
        self,
        config: TierModulationConfig,
    ) -> None:
        """
        Initialize the engine with tier configuration.

        Args:
            config: Tier-specific modulation configuration.
        """
        self._config = config
        self._tier = config.tier
        self._tier_scalar = config.tier_scalar
        self._guna_weights = config.guna_weights
        self._policy_config = config.policy_config

    @property
    def config(self) -> TierModulationConfig:
        """Get the current configuration."""
        return self._config

    @property
    def tier(self) -> ModulationTier:
        """Get the current tier."""
        return self._tier

    def modulate(
        self,
        base_intensity: float,
        C_s: float,
        M: float,
        H: float,
        *,
        guna_weights_override: Optional[GunaWeights] = None,
        policy_config_override: Optional[PolicyConfig] = None,
    ) -> ModulationResult:
        """
        Perform entropy modulation on base intensity.

        This is the main entry point for modulation.

        PIPELINE PLACEMENT:
            Input -> STL -> Matching -> Routing -> AGI -> [THIS] -> Renderer -> Output

        FORMULAS APPLIED:
            1. Guna Derivation:
               S_raw = C_s * (1 - H)
               R_raw = M * (1 - |H - H_mid|)
               T_raw = H * (1 - C_s)
               [S, R, T] = normalize([S_raw, R_raw, T_raw])

            2. Guna Coefficient:
               G = w_S * S + w_R * R + w_T * T

            3. Policy Scalar:
               P = clamp(1 - r_risk - r_escalation, 0, 1)

            4. Tier Scalar:
               T = tier_scalar (fixed: 1.0, 0.9, or 0.85)

            5. Entropy Modulation Factor:
               E = G * P * T

            6. Output Intensity:
               OUTPUT_intensity = BASE_intensity * E

        Args:
            base_intensity: Input intensity from upstream pipeline
            C_s: Structural coherence [0.0, 1.0]
            M: Motion / transformation magnitude [0.0, 1.0]
            H: Entropy [0.0, 1.0]
            guna_weights_override: Optional override for Guna weights
            policy_config_override: Optional override for policy config

        Returns:
            ModulationResult with complete audit trail

        Determinism Guarantee:
            Same inputs always produce same outputs.

        Disable Proof:
            If w_S = w_R = w_T = 1 and P = T = 1, then E = 1
            and OUTPUT_intensity = BASE_intensity (unchanged).
        """
        # Use overrides or defaults
        weights = guna_weights_override or self._guna_weights
        policy = policy_config_override or self._policy_config
        tier_scalar = self._tier_scalar

        # Build trace
        trace_entries = []

        # Step 1: Derive Guna vector
        inputs = PipelineInputs(C_s=C_s, M=M, H=H)
        guna_vector, guna_trace = derive_guna_vector(inputs)
        trace_entries.extend(guna_trace)

        # Step 2: Compute Guna coefficient
        G, g_trace = compute_guna_coefficient(guna_vector, weights)
        trace_entries.append(g_trace)

        # Step 3: Compute Policy scalar
        P, p_trace = compute_policy_scalar(policy)
        trace_entries.append(p_trace)

        # Step 4: Get Tier scalar (already known)
        tier_trace = ModulationTraceEntry(
            step_name="tier_scalar",
            inputs=(("tier", self._tier.value),),
            output=tier_scalar,
            formula="T = tier_scalar (fixed constant)",
        )
        trace_entries.append(tier_trace)

        # Step 5: Compute Entropy Modulation Factor
        E, e_trace = compute_entropy_modulation_factor(G, P, tier_scalar)
        trace_entries.append(e_trace)

        # Step 6: Compute Output Intensity
        output_intensity, out_trace = compute_output_intensity(base_intensity, E)
        trace_entries.append(out_trace)

        # Build result
        return ModulationResult(
            guna_vector=guna_vector,
            G=G,
            P=P,
            T=tier_scalar,
            E=E,
            base_intensity=base_intensity,
            output_intensity=output_intensity,
            trace=tuple(trace_entries),
        )

    def modulate_from_inputs(
        self,
        base_intensity: float,
        inputs: PipelineInputs,
        *,
        guna_weights_override: Optional[GunaWeights] = None,
        policy_config_override: Optional[PolicyConfig] = None,
    ) -> ModulationResult:
        """
        Perform entropy modulation using PipelineInputs.

        Convenience method that accepts PipelineInputs instead of
        individual C_s, M, H values.

        Args:
            base_intensity: Input intensity from upstream pipeline
            inputs: Pipeline inputs (C_s, M, H)
            guna_weights_override: Optional override for Guna weights
            policy_config_override: Optional override for policy config

        Returns:
            ModulationResult with complete audit trail
        """
        return self.modulate(
            base_intensity=base_intensity,
            C_s=inputs.C_s,
            M=inputs.M,
            H=inputs.H,
            guna_weights_override=guna_weights_override,
            policy_config_override=policy_config_override,
        )


# =============================================================================
# Factory Functions
# =============================================================================

def create_engine(config: TierModulationConfig) -> EntropyModulationEngine:
    """
    Create an entropy modulation engine with the given configuration.

    Args:
        config: Tier-specific modulation configuration

    Returns:
        EntropyModulationEngine instance
    """
    return EntropyModulationEngine(config)


def create_engine_for_tier(tier: ModulationTier) -> EntropyModulationEngine:
    """
    Create an entropy modulation engine for the specified tier.

    Uses the default configuration for the tier.

    Args:
        tier: The tier enum value

    Returns:
        EntropyModulationEngine instance
    """
    config = get_tier_modulation_config(tier)
    return EntropyModulationEngine(config)


def create_engine_for_tier_name(tier_name: str) -> EntropyModulationEngine:
    """
    Create an entropy modulation engine for the specified tier name.

    Args:
        tier_name: String name for the tier

    Returns:
        EntropyModulationEngine instance
    """
    from agentic.guna_modulation.config import get_tier_modulation_config_by_name
    config = get_tier_modulation_config_by_name(tier_name)
    return EntropyModulationEngine(config)


# =============================================================================
# Standalone Modulation Function
# =============================================================================

def modulate_intensity(
    base_intensity: float,
    C_s: float,
    M: float,
    H: float,
    *,
    tier: ModulationTier = ModulationTier.ENTERPRISE_TIER_1,
    guna_weights: Optional[GunaWeights] = None,
    policy_config: Optional[PolicyConfig] = None,
) -> ModulationResult:
    """
    Standalone function to perform entropy modulation.

    Convenience function for one-off modulation without creating an engine.

    Args:
        base_intensity: Input intensity from upstream pipeline
        C_s: Structural coherence [0.0, 1.0]
        M: Motion / transformation magnitude [0.0, 1.0]
        H: Entropy [0.0, 1.0]
        tier: The tier to use (default: ENTERPRISE_TIER_1)
        guna_weights: Optional Guna weights override
        policy_config: Optional policy config override

    Returns:
        ModulationResult with complete audit trail

    Example:
        result = modulate_intensity(
            base_intensity=0.8,
            C_s=0.7,
            M=0.5,
            H=0.3,
        )
        print(f"Output: {result.output_intensity}")
    """
    engine = create_engine_for_tier(tier)
    return engine.modulate(
        base_intensity=base_intensity,
        C_s=C_s,
        M=M,
        H=H,
        guna_weights_override=guna_weights,
        policy_config_override=policy_config,
    )
