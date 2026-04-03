"""
Pipeline Signal Adapter for Guna Entropy Modulation
====================================================

Symbol-U v2.6.1 - Deterministic Signal Wiring to Existing Pipeline

This module provides adapters that wire the Guna entropy modulation layer
to EXISTING signals in the SymbolU pipeline, rather than recomputing them.

SIGNAL SOURCE MAPPING:
    H_G    ← RouterContext.H_G (from TTOR)
    H_D    ← RouterContext.H_D (from TTOR)
    H_K    ← RouterContext.H_K (from TTOR)
    Δ_sem  ← cosine_similarity() from similarity.py
    Δ_str  ← StitchingDecision.diagnostics["cross_domain_count"]
    Δ_exp  ← IntentType from ActivationPlan.intent

PIPELINE PLACEMENT:
    STL → C×R×S → Routing → Stitching → Fusion
    → [THIS ADAPTER] ← reads existing signals
    → Guna Modulation
    → Renderer

EXPLICIT NON-CAPABILITIES (MANDATORY):
    - No learning
    - No feedback loops
    - No preference updates
    - No moral reasoning
    - No user psychology inference
    - No policy evaluation
    - No AGI claims

Version: 2.6.1
Date: 2025-12-22
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

from agentic.guna_modulation.signal_wiring import (
    EntropyMode,
    MotionMode,
    LN_3,
    LN_5,
    LN_10,
    MAX_STRUCTURAL_JUMPS,
    EntropyWiringAudit,
    MotionWiringAudit,
    SignalWiringAudit,
    WiredSignals,
    SignalWiringConfig,
    compute_M,
)

if TYPE_CHECKING:
    from symbolu_core.mechanical.pipeline.ttor.models import RouterContext
    from symbolu_core.mechanical.mlcr.activation_plan import ActivationPlan, IntentType
    from agentic.core.stitching.contracts import StitchingDecision


# =============================================================================
# Intent Type Mapping to Experiential Motion
# =============================================================================

# Map existing IntentType enum values to experiential motion triggers
# These are the intents that represent "transformative" delivery postures
EXPERIENTIAL_INTENT_TYPES: frozenset = frozenset({
    "COMMAND",      # Directive - direct action requests
    "SHOULD",       # Decision support - guidance that may alter course
    "REFLECTION",   # Self-reflection - introspective shifts
})
"""
IntentType values that trigger experiential motion (Δ_exp = 1).

Mapping rationale:
    COMMAND → directive (transforms user state through action)
    SHOULD → corrective (guidance that may alter user's course)
    REFLECTION → inverse_jolt (introspective transformation)
"""


def intent_to_experiential_delta(intent_type: str) -> float:
    """
    Map IntentType to experiential delta.

    Uses existing IntentType enum from ActivationPlan.

    FORMULA:
        Δ_exp = 1 if intent ∈ {COMMAND, SHOULD, REFLECTION}
                else 0

    Args:
        intent_type: IntentType value as string (e.g., "COMMAND", "WHAT")

    Returns:
        Experiential delta (0.0 or 1.0)

    Determinism Guarantee:
        Same input always produces same output.
    """
    if intent_type.upper() in EXPERIENTIAL_INTENT_TYPES:
        return 1.0
    return 0.0


# =============================================================================
# Semantic Delta from Similarity Module
# =============================================================================

def compute_semantic_delta_from_vectors(
    query_aspect_probs: Dict[str, float],
    candidate_aspect_probs: Dict[str, float],
) -> float:
    """
    Compute semantic delta using aspect probability vectors.

    Reuses the same cosine similarity approach as similarity.py but
    operates on aspect probability dictionaries.

    FORMULA:
        Δ_sem = 1 - cosine_similarity(query_aspects, candidate_aspects)

    Args:
        query_aspect_probs: Aspect probabilities from query context
        candidate_aspect_probs: Aspect probabilities from candidate

    Returns:
        Semantic delta in [0, 1]
    """
    import math

    # Get all keys
    all_keys = set(query_aspect_probs.keys()) | set(candidate_aspect_probs.keys())

    if not all_keys:
        return 0.0

    # Extract aligned vectors
    vec_q = [query_aspect_probs.get(k, 0.0) for k in sorted(all_keys)]
    vec_c = [candidate_aspect_probs.get(k, 0.0) for k in sorted(all_keys)]

    # Dot product
    dot = sum(q * c for q, c in zip(vec_q, vec_c))

    # Magnitudes
    mag_q = math.sqrt(sum(q * q for q in vec_q))
    mag_c = math.sqrt(sum(c * c for c in vec_c))

    # Cosine similarity
    if mag_q < 1e-9 or mag_c < 1e-9:
        cosine = 0.0
    else:
        cosine = dot / (mag_q * mag_c)
        cosine = max(-1.0, min(1.0, cosine))

    # Delta = 1 - cosine
    delta = 1.0 - cosine
    return max(0.0, min(1.0, delta))


# =============================================================================
# Structural Delta from Stitching Diagnostics
# =============================================================================

def compute_structural_delta_from_stitching(
    cross_domain_count: int,
    max_jumps: int = MAX_STRUCTURAL_JUMPS,
) -> float:
    """
    Compute structural delta from stitching diagnostics.

    FORMULA:
        Δ_str_norm = min(cross_domain_count, MAX_JUMPS) / MAX_JUMPS

    Args:
        cross_domain_count: From StitchingDecision.diagnostics["cross_domain_count"]
        max_jumps: Maximum structural jumps for normalization

    Returns:
        Normalized structural delta in [0, 1]
    """
    if max_jumps <= 0:
        return 0.0

    clamped = min(cross_domain_count, max_jumps)
    return clamped / max_jumps


# =============================================================================
# Entropy from RouterContext
# =============================================================================

def extract_entropy_from_router_context(
    H_G: float,
    H_D: float,
    H_K: float,
    mode: EntropyMode,
) -> Tuple[float, EntropyWiringAudit]:
    """
    Extract and normalize entropy from RouterContext values.

    The RouterContext already contains H_G, H_D, H_K. This function
    selects the appropriate one and normalizes to [0, 1].

    FORMULAS:
        GUNA:        H = H_G / ln(3)
        DIMENSIONAL: H = H_D / ln(10)
        KOSHA:       H = H_K / ln(5)

    Args:
        H_G: Guna entropy from RouterContext [0, ln(3)]
        H_D: Dimensional entropy from RouterContext [0, ln(10)]
        H_K: Kosha entropy from RouterContext [0, ln(5)]
        mode: Operator-selected entropy mode

    Returns:
        Tuple of (H_normalized, audit_record)
    """
    if mode == EntropyMode.GUNA:
        H_raw = max(0.0, min(LN_3, H_G))
        H_norm = H_raw / LN_3 if LN_3 > 0 else 0.0
    elif mode == EntropyMode.DIMENSIONAL:
        H_raw = max(0.0, min(LN_10, H_D))
        H_norm = H_raw / LN_10 if LN_10 > 0 else 0.0
    elif mode == EntropyMode.KOSHA:
        H_raw = max(0.0, min(LN_5, H_K))
        H_norm = H_raw / LN_5 if LN_5 > 0 else 0.0
    else:
        raise ValueError(f"Invalid entropy mode: {mode}")

    H_norm = max(0.0, min(1.0, H_norm))

    audit = EntropyWiringAudit(
        entropy_mode=mode.value,
        H_raw=H_raw,
        H_normalized=H_norm,
    )

    return (H_norm, audit)


# =============================================================================
# Pipeline Context Dataclass
# =============================================================================

@dataclass(frozen=True)
class PipelineSignalContext:
    """
    Aggregated context from pipeline stages for Guna modulation.

    This dataclass collects signals from:
        - RouterContext (entropy values, aspect_probs)
        - ActivationPlan (intent)
        - StitchingDecision (cross_domain_count)
        - Coherence signals (C_s)

    It serves as the input for the pipeline adapter.
    """
    # From RouterContext
    H_G: float
    H_D: float
    H_K: float
    query_aspect_probs: Dict[str, float]

    # From ActivationPlan
    intent_type: str  # IntentType.value

    # From StitchingDecision
    cross_domain_count: int

    # From Candidate
    candidate_aspect_probs: Dict[str, float]

    # From Coherence signals
    C_s: float  # Structural coherence

    @classmethod
    def from_pipeline_stages(
        cls,
        router_context: "RouterContext",
        activation_plan: "ActivationPlan",
        stitching_decision: "StitchingDecision",
        candidate_aspect_probs: Dict[str, float],
        C_s: float,
    ) -> "PipelineSignalContext":
        """
        Create context from actual pipeline stage outputs.

        Args:
            router_context: TTOR RouterContext with entropy values
            activation_plan: MLCR ActivationPlan with intent
            stitching_decision: Stitching output with diagnostics
            candidate_aspect_probs: Aspect probs from selected candidate
            C_s: Structural coherence from coherence engine

        Returns:
            PipelineSignalContext with all required signals
        """
        return cls(
            H_G=router_context.H_G,
            H_D=router_context.H_D,
            H_K=router_context.H_K,
            query_aspect_probs=dict(router_context.aspect_probs),
            intent_type=activation_plan.intent.value,
            cross_domain_count=stitching_decision.diagnostics.get("cross_domain_count", 0),
            candidate_aspect_probs=candidate_aspect_probs,
            C_s=C_s,
        )


# =============================================================================
# Pipeline Signal Adapter
# =============================================================================

def wire_from_pipeline_context(
    context: PipelineSignalContext,
    config: SignalWiringConfig,
) -> WiredSignals:
    """
    Wire H and M from existing pipeline signals.

    This is the main adapter function that extracts signals from
    the pipeline context and produces wired H and M values.

    Args:
        context: Aggregated pipeline signal context
        config: Signal wiring configuration

    Returns:
        WiredSignals with H, M, and complete audit trail
    """
    # Extract H from RouterContext entropy values
    H, entropy_audit = extract_entropy_from_router_context(
        H_G=context.H_G,
        H_D=context.H_D,
        H_K=context.H_K,
        mode=config.entropy_mode,
    )

    # Compute motion deltas from pipeline signals
    delta_sem = compute_semantic_delta_from_vectors(
        context.query_aspect_probs,
        context.candidate_aspect_probs,
    )
    delta_str = compute_structural_delta_from_stitching(
        context.cross_domain_count,
    )
    delta_exp = intent_to_experiential_delta(context.intent_type)

    # Compute M using selected mode
    M, motion_audit = compute_M(
        semantic_delta=delta_sem,
        structural_delta=delta_str,
        experiential_delta=delta_exp,
        mode=config.motion_mode,
        weights=config.composite_weights,
    )

    # Create combined audit
    audit = SignalWiringAudit(
        entropy_audit=entropy_audit,
        motion_audit=motion_audit,
        operator_config_snapshot=config.to_dict(),
    )

    return WiredSignals(H=H, M=M, audit=audit)


# =============================================================================
# Convenience Functions for Direct Pipeline Integration
# =============================================================================

def wire_signals_from_router_context(
    router_context: "RouterContext",
    candidate_aspect_probs: Dict[str, float],
    cross_domain_count: int,
    intent_type: str,
    config: SignalWiringConfig = None,
) -> WiredSignals:
    """
    Wire signals directly from RouterContext and other pipeline outputs.

    Convenience function for when you have individual pipeline outputs
    rather than a PipelineSignalContext.

    Args:
        router_context: TTOR RouterContext
        candidate_aspect_probs: Aspect probs from candidate
        cross_domain_count: From stitching diagnostics
        intent_type: IntentType value string
        config: Signal wiring configuration

    Returns:
        WiredSignals with H, M, and audit trail
    """
    from agentic.guna_modulation.signal_wiring import DEFAULT_WIRING_CONFIG

    config = config or DEFAULT_WIRING_CONFIG

    context = PipelineSignalContext(
        H_G=router_context.H_G,
        H_D=router_context.H_D,
        H_K=router_context.H_K,
        query_aspect_probs=dict(router_context.aspect_probs),
        intent_type=intent_type,
        cross_domain_count=cross_domain_count,
        candidate_aspect_probs=candidate_aspect_probs,
        C_s=0.0,  # Not used in wiring, passed separately to modulation
    )

    return wire_from_pipeline_context(context, config)


# =============================================================================
# Full Modulation from Pipeline Context
# =============================================================================

def modulate_from_pipeline_context(
    base_intensity: float,
    context: PipelineSignalContext,
    config: SignalWiringConfig = None,
    tier: str = "enterprise_tier_1",
) -> "IntegratedModulationResult":
    """
    Perform complete Guna modulation using pipeline context.

    This is the recommended integration point for the pipeline.

    Args:
        base_intensity: Intensity from upstream (e.g., fusion score)
        context: Aggregated pipeline signal context
        config: Signal wiring configuration
        tier: Modulation tier string

    Returns:
        IntegratedModulationResult with full audit trail
    """
    from agentic.guna_modulation.signal_wiring import DEFAULT_WIRING_CONFIG
    from agentic.guna_modulation.pipeline_integration import IntegratedModulationResult
    from agentic.guna_modulation.entropy_modulation_engine import create_engine_for_tier_name

    config = config or DEFAULT_WIRING_CONFIG

    # Wire signals from pipeline context
    wired = wire_from_pipeline_context(context, config)

    # Create modulation engine
    engine = create_engine_for_tier_name(tier)

    # Perform modulation
    modulation_result = engine.modulate(
        base_intensity=base_intensity,
        C_s=context.C_s,
        M=wired.M,
        H=wired.H,
    )

    return IntegratedModulationResult(
        wired_signals=wired,
        modulation_result=modulation_result,
        C_s=context.C_s,
    )
