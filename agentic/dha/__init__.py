"""
DHA (Delivery Harmonization Algorithm) Module
==============================================

Tier-safe, deterministic, zero-parameter, formula-only delivery modulation.

This module computes delivery modulation parameters from upstream signals
using closed-form formulas. It runs after Fusion and before Renderer.

Key Properties:
    - Tier-safe: Different configurations per tier
    - Deterministic: Same inputs produce same outputs
    - Zero-parameter: No learned/trained parameters
    - Formula-only: Closed-form mathematical computations
    - Full audit: Complete metadata trail for all computations

What DHA Does:
    - Computes tone weights (sweet, jolt, metaphor) from Guna distribution
    - Computes intensity scalar from coherence and motion
    - Computes restraint scalar from policy biases
    - Computes delivery modulation factor D = T × I × R
    - Outputs full audit trail for observability

What DHA Does NOT Do:
    - Change semantic meaning of base output
    - Do psychology inference
    - Do moral judgments
    - Introduce learning, feedback loops, or state

Usage:
    from agentic.dha import DHAEngine, DHAConfig, DHAInputs

    # Create engine (disabled by default)
    config = DHAConfig(enabled=True)
    engine = DHAEngine(config)

    # Create inputs from pipeline signals
    signals = DHAInputs.from_pipeline_signals(
        coherence_score=0.8,
        motion_magnitude=0.3,
        guna_entropy=0.5,
        sattva=0.5, rajas=0.3, tamas=0.2,
        tier="consumer"
    )

    # Apply DHA
    base_output = "Response text from Fusion"
    output, result = engine.apply(base_output, signals)

    # Use result
    print(f"Delivery factor: {result.D}")
    print(f"Dominant tone: {result.dominant_tone}")
    print(f"Audit: {result.audit}")

Pipeline Integration:
    from agentic.dha import DHAStage, maybe_run_dha

    # In pipeline orchestrator
    dha_stage = DHAStage(config)
    ctx = dha_stage.run(ctx)

    # Or use helper
    dha_result = maybe_run_dha(ctx, config)

Version: 1.0
Date: 2025-12-22
"""

# Configuration
from .config import (
    DHAConfig,
    EntropySource,
    ToneLogitConfig,
    IntensityConfig,
    RestraintConfig,
    NumericsConfig,
)

# Types
from .types import (
    Tier,
    ToneWeights,
    DHAInputs,
    DHAResult,
    DHANoOpResult,
    DeliveryProfile,
)

# Math utilities
from .math import (
    LN_3,
    LN_5,
    LN_10,
    EPSILON,
    clip,
    clamp,
    softmax,
    softmax3,
    normalize_entropy_guna,
    normalize_entropy_dimensional,
    normalize_entropy_kosha,
    get_normalized_entropy,
    compute_tone_logits,
    compute_intensity,
    compute_restraint,
    compute_delivery_factor,
    compute_delivery_factor_simple,
    round_for_audit,
    round_dict_for_audit,
)

# Engine
from .engine import (
    DHAEngine,
    apply_dha,
    compute_dha,
)

# Integration
from .integration import (
    DHAStage,
    extract_signals_from_context,
    extract_base_output,
    maybe_run_dha,
    get_dha_delivery_profile,
)

# Signal Extraction (Canonical)
from .signal_extraction import (
    extract_dha_inputs,
    extract_signals_from_context_v2,
    SignalExtractionAudit,
    LN_3 as SIGNAL_LN_3,
    LN_5 as SIGNAL_LN_5,
    LN_10 as SIGNAL_LN_10,
)


# Public API
__all__ = [
    # Configuration
    "DHAConfig",
    "EntropySource",
    "ToneLogitConfig",
    "IntensityConfig",
    "RestraintConfig",
    "NumericsConfig",
    # Types
    "Tier",
    "ToneWeights",
    "DHAInputs",
    "DHAResult",
    "DHANoOpResult",
    "DeliveryProfile",
    # Math
    "LN_3",
    "LN_5",
    "LN_10",
    "EPSILON",
    "clip",
    "clamp",
    "softmax",
    "softmax3",
    "normalize_entropy_guna",
    "normalize_entropy_dimensional",
    "normalize_entropy_kosha",
    "get_normalized_entropy",
    "compute_tone_logits",
    "compute_intensity",
    "compute_restraint",
    "compute_delivery_factor",
    "compute_delivery_factor_simple",
    "round_for_audit",
    # Engine
    "DHAEngine",
    "apply_dha",
    "compute_dha",
    # Integration
    "DHAStage",
    "extract_signals_from_context",
    "extract_base_output",
    "maybe_run_dha",
    "get_dha_delivery_profile",
    # Signal Extraction (Canonical)
    "extract_dha_inputs",
    "extract_signals_from_context_v2",
    "SignalExtractionAudit",
]

__version__ = "1.0.0"
