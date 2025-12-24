"""
Pipeline Integration for Guna Entropy Modulation
=================================================

Symbol-U v2.6 - Deterministic, Zero-Parameter, Non-Learning System

This module provides the integration layer that connects the signal wiring
to the entropy modulation engine, completing the pipeline circuit.

PIPELINE PLACEMENT (MANDATORY):
    STL -> C x R x S -> Routing -> (optional AGI)
    -> Signal Wiring (compute H, M)
    -> [THIS INTEGRATION]
    -> Entropy Modulation Engine
    -> Renderer

This layer ONLY modulates delivery intensity.
It does NOT:
    - Change STL
    - Change Stitching
    - Change Fusion
    - Influence candidate selection
    - Override truth

EXPLICIT NON-CAPABILITIES (MANDATORY):
    - No learning
    - No feedback loops
    - No preference updates
    - No moral reasoning
    - No user psychology inference
    - No policy evaluation
    - No AGI claims

Version: 2.6.0
Date: 2025-12-22
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from symbolu.guna_modulation.types import (
    ModulationTier,
    ModulationResult,
    GunaWeights,
    PolicyConfig,
    TierModulationConfig,
)
from symbolu.guna_modulation.config import (
    get_tier_modulation_config,
    TIER_1_MODULATION_CONFIG,
)
from symbolu.guna_modulation.entropy_modulation_engine import (
    EntropyModulationEngine,
    create_engine_for_tier,
)
from symbolu.guna_modulation.signal_wiring import (
    EntropyMode,
    MotionMode,
    SignalWiringConfig,
    WiredSignals,
    SignalWiringAudit,
    compute_H,
    compute_M,
    compute_M_from_raw,
    compute_semantic_delta,
    compute_structural_delta,
    compute_experiential_delta,
    wire_signals,
    wire_signals_simple,
    DEFAULT_WIRING_CONFIG,
)


# =============================================================================
# Integrated Modulation Result
# =============================================================================

@dataclass(frozen=True)
class IntegratedModulationResult:
    """
    Complete result from integrated pipeline modulation.

    Contains:
        - Signal wiring audit (H, M derivation)
        - Modulation result (Guna derivation, E computation)
        - Complete traceability chain

    This is the primary output type for pipeline integration.
    """
    wired_signals: WiredSignals
    modulation_result: ModulationResult
    C_s: float  # Structural coherence (passed through)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "wired_signals": self.wired_signals.to_dict(),
            "modulation_result": self.modulation_result.to_dict(),
            "C_s": self.C_s,
        }

    @property
    def output_intensity(self) -> float:
        """Get the final output intensity."""
        return self.modulation_result.output_intensity

    @property
    def E(self) -> float:
        """Get the entropy modulation factor."""
        return self.modulation_result.E

    @property
    def H(self) -> float:
        """Get the wired entropy value."""
        return self.wired_signals.H

    @property
    def M(self) -> float:
        """Get the wired motion value."""
        return self.wired_signals.M


# =============================================================================
# Pipeline Integration Engine
# =============================================================================

class PipelineModulationEngine:
    """
    Integrated engine for pipeline signal wiring and modulation.

    This engine:
        1. Wires pipeline signals (H_G, H_D, H_K, aspect_vectors, etc.)
        2. Computes C_s from coherence signals
        3. Feeds wired H, M, C_s to modulation engine
        4. Produces complete audit trail

    EXPLICIT NON-CAPABILITIES:
        - No learning
        - No adaptation
        - No state memory
        - No evaluation of "better" or "worse"
        - No psychology
        - No morality
        - No feedback loops
        - No preference formation

    Example:
        engine = PipelineModulationEngine(
            tier=ModulationTier.ENTERPRISE_TIER_1,
            wiring_config=SignalWiringConfig(
                entropy_mode=EntropyMode.GUNA,
                motion_mode=MotionMode.SEMANTIC,
            ),
        )
        result = engine.modulate_from_pipeline(
            base_intensity=0.8,
            C_s=0.7,
            H_G=0.5,
            H_D=1.0,
            H_K=0.3,
            candidate_aspect_vector={"clarity": 0.8, "depth": 0.6},
            context_aspect_vector={"clarity": 0.7, "depth": 0.7},
            domain_jump_count=1,
            intent="informative",
        )
    """

    def __init__(
        self,
        tier: ModulationTier = ModulationTier.ENTERPRISE_TIER_1,
        wiring_config: SignalWiringConfig = DEFAULT_WIRING_CONFIG,
        guna_weights_override: Optional[GunaWeights] = None,
        policy_config_override: Optional[PolicyConfig] = None,
    ) -> None:
        """
        Initialize the pipeline modulation engine.

        Args:
            tier: System tier for modulation
            wiring_config: Signal wiring configuration
            guna_weights_override: Optional Guna weights override
            policy_config_override: Optional policy config override
        """
        self._tier = tier
        self._wiring_config = wiring_config
        self._guna_weights_override = guna_weights_override
        self._policy_config_override = policy_config_override
        self._modulation_engine = create_engine_for_tier(tier)

    @property
    def tier(self) -> ModulationTier:
        """Get the current tier."""
        return self._tier

    @property
    def wiring_config(self) -> SignalWiringConfig:
        """Get the wiring configuration."""
        return self._wiring_config

    def modulate_from_pipeline(
        self,
        base_intensity: float,
        # Coherence input (C_s)
        C_s: float,
        # Entropy inputs (from TTOR)
        H_G: float,
        H_D: float,
        H_K: float,
        # Motion inputs (from pipeline)
        candidate_aspect_vector: Dict[str, float],
        context_aspect_vector: Dict[str, float],
        domain_jump_count: int,
        intent: str,
        # Optional inputs
        layer_transition_count: int = 0,
    ) -> IntegratedModulationResult:
        """
        Perform complete pipeline modulation.

        This is the main entry point for pipeline integration.

        PIPELINE FLOW:
            1. Wire H from H_G/H_D/H_K based on entropy_mode
            2. Compute delta components from pipeline signals
            3. Wire M from deltas based on motion_mode
            4. Feed C_s, M, H to modulation engine
            5. Apply Guna derivation and intensity modulation
            6. Return complete result with audit trail

        Args:
            base_intensity: Input intensity from upstream pipeline
            C_s: Structural coherence [0.0, 1.0]
            H_G: Guna entropy [0, ln(3)]
            H_D: Dimensional entropy [0, ln(10)]
            H_K: Kosha entropy [0, ln(5)]
            candidate_aspect_vector: Aspect vector from candidate
            context_aspect_vector: Aspect vector from context
            domain_jump_count: Number of domain jumps
            intent: Intent string from fusion context
            layer_transition_count: Number of layer transitions

        Returns:
            IntegratedModulationResult with complete audit trail

        Determinism Guarantee:
            Same inputs always produce same outputs.
        """
        # Step 1: Wire signals
        wired = wire_signals(
            H_G=H_G,
            H_D=H_D,
            H_K=H_K,
            candidate_aspect_vector=candidate_aspect_vector,
            context_aspect_vector=context_aspect_vector,
            domain_jump_count=domain_jump_count,
            intent=intent,
            layer_transition_count=layer_transition_count,
            config=self._wiring_config,
        )

        # Step 2: Feed to modulation engine
        modulation_result = self._modulation_engine.modulate(
            base_intensity=base_intensity,
            C_s=C_s,
            M=wired.M,
            H=wired.H,
            guna_weights_override=self._guna_weights_override,
            policy_config_override=self._policy_config_override,
        )

        return IntegratedModulationResult(
            wired_signals=wired,
            modulation_result=modulation_result,
            C_s=C_s,
        )

    def modulate_with_precomputed_deltas(
        self,
        base_intensity: float,
        # Coherence input
        C_s: float,
        # Pre-computed entropy
        H_raw: float,
        # Pre-computed motion deltas
        delta_sem: float,
        delta_str_norm: float,
        delta_exp: float,
    ) -> IntegratedModulationResult:
        """
        Perform modulation with pre-computed delta values.

        Simplified version for when delta components are already computed.

        Args:
            base_intensity: Input intensity from upstream pipeline
            C_s: Structural coherence [0.0, 1.0]
            H_raw: Raw entropy in source's native range
            delta_sem: Pre-computed semantic delta
            delta_str_norm: Pre-computed structural delta
            delta_exp: Pre-computed experiential delta

        Returns:
            IntegratedModulationResult with complete audit trail
        """
        # Wire using pre-computed values
        wired = wire_signals_simple(
            H_raw=H_raw,
            entropy_mode=self._wiring_config.entropy_mode,
            delta_sem=delta_sem,
            delta_str_norm=delta_str_norm,
            delta_exp=delta_exp,
            motion_mode=self._wiring_config.motion_mode,
            weights=self._wiring_config.composite_weights,
        )

        # Feed to modulation engine
        modulation_result = self._modulation_engine.modulate(
            base_intensity=base_intensity,
            C_s=C_s,
            M=wired.M,
            H=wired.H,
            guna_weights_override=self._guna_weights_override,
            policy_config_override=self._policy_config_override,
        )

        return IntegratedModulationResult(
            wired_signals=wired,
            modulation_result=modulation_result,
            C_s=C_s,
        )


# =============================================================================
# Factory Functions
# =============================================================================

def create_pipeline_engine(
    tier: ModulationTier = ModulationTier.ENTERPRISE_TIER_1,
    entropy_mode: EntropyMode = EntropyMode.GUNA,
    motion_mode: MotionMode = MotionMode.SEMANTIC,
    composite_weights: Optional[Tuple[float, float, float]] = None,
) -> PipelineModulationEngine:
    """
    Create a pipeline modulation engine with specified configuration.

    Args:
        tier: System tier for modulation
        entropy_mode: Entropy source selection (default: GUNA)
        motion_mode: Motion computation mode (default: SEMANTIC)
        composite_weights: Optional weights for COMPOSITE motion mode

    Returns:
        PipelineModulationEngine instance
    """
    wiring_config = SignalWiringConfig(
        entropy_mode=entropy_mode,
        motion_mode=motion_mode,
        composite_weights=composite_weights,
    )
    return PipelineModulationEngine(tier=tier, wiring_config=wiring_config)


def create_default_pipeline_engine() -> PipelineModulationEngine:
    """
    Create a pipeline engine with default configuration.

    Defaults:
        - Tier: ENTERPRISE_TIER_1
        - Entropy Mode: GUNA (H = H_G / ln(3))
        - Motion Mode: SEMANTIC (M = delta_sem)

    Returns:
        PipelineModulationEngine instance
    """
    return PipelineModulationEngine()


# =============================================================================
# Standalone Integration Function
# =============================================================================

def modulate_from_pipeline(
    base_intensity: float,
    # Coherence input
    C_s: float,
    # Entropy inputs
    H_G: float,
    H_D: float,
    H_K: float,
    # Motion inputs
    candidate_aspect_vector: Dict[str, float],
    context_aspect_vector: Dict[str, float],
    domain_jump_count: int,
    intent: str,
    # Configuration
    tier: ModulationTier = ModulationTier.ENTERPRISE_TIER_1,
    entropy_mode: EntropyMode = EntropyMode.GUNA,
    motion_mode: MotionMode = MotionMode.SEMANTIC,
    composite_weights: Optional[Tuple[float, float, float]] = None,
    layer_transition_count: int = 0,
    guna_weights_override: Optional[GunaWeights] = None,
    policy_config_override: Optional[PolicyConfig] = None,
) -> IntegratedModulationResult:
    """
    Standalone function for complete pipeline modulation.

    Convenience function for one-off modulation without creating an engine.

    PIPELINE PLACEMENT:
        STL -> C x R x S -> Routing -> (optional AGI)
        -> [THIS FUNCTION]
        -> Renderer

    Args:
        base_intensity: Input intensity from upstream pipeline
        C_s: Structural coherence [0.0, 1.0]
        H_G: Guna entropy [0, ln(3)]
        H_D: Dimensional entropy [0, ln(10)]
        H_K: Kosha entropy [0, ln(5)]
        candidate_aspect_vector: Aspect vector from candidate
        context_aspect_vector: Aspect vector from context
        domain_jump_count: Number of domain jumps
        intent: Intent string from fusion context
        tier: System tier for modulation
        entropy_mode: Entropy source selection
        motion_mode: Motion computation mode
        composite_weights: Optional weights for COMPOSITE motion mode
        layer_transition_count: Number of layer transitions
        guna_weights_override: Optional Guna weights override
        policy_config_override: Optional policy config override

    Returns:
        IntegratedModulationResult with complete audit trail

    Example:
        result = modulate_from_pipeline(
            base_intensity=0.8,
            C_s=0.7,
            H_G=0.5,
            H_D=1.0,
            H_K=0.3,
            candidate_aspect_vector={"clarity": 0.8},
            context_aspect_vector={"clarity": 0.7},
            domain_jump_count=1,
            intent="informative",
        )
        print(f"Output: {result.output_intensity}")
    """
    wiring_config = SignalWiringConfig(
        entropy_mode=entropy_mode,
        motion_mode=motion_mode,
        composite_weights=composite_weights,
    )

    engine = PipelineModulationEngine(
        tier=tier,
        wiring_config=wiring_config,
        guna_weights_override=guna_weights_override,
        policy_config_override=policy_config_override,
    )

    return engine.modulate_from_pipeline(
        base_intensity=base_intensity,
        C_s=C_s,
        H_G=H_G,
        H_D=H_D,
        H_K=H_K,
        candidate_aspect_vector=candidate_aspect_vector,
        context_aspect_vector=context_aspect_vector,
        domain_jump_count=domain_jump_count,
        intent=intent,
        layer_transition_count=layer_transition_count,
    )
