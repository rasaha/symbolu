"""
P37 Adaptive Continuity Engine Integration
============================================

Integration shim for running P37 Adaptive Continuity Engine phase within
the Symbol-U pipeline orchestrator.

Wraps the existing formula:
    symbolu/formulas/adaptive_continuity_engine.py

Usage in orchestrator:
    from .p37_continuity import maybe_run_p37, get_p37_output

    # After P34-P36 stages
    p37_result = maybe_run_p37(ctx)
    if p37_result:
        ctx.p37_continuity = p37_result
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .p37_continuity_schema import (
    VERSION,
    P37Authority,
    ContinuityBand,
    P37Output,
)

if TYPE_CHECKING:
    from symbolu.mechanical.pipeline.models import PipelineContext

# =============================================================================
# FORMULA IMPORT (graceful degradation)
# =============================================================================

try:
    from symbolu.formulas.adaptive_continuity_engine import (
        AdaptiveContinuitySnapshot,
        compute_adaptive_continuity,
    )
    HAS_FORMULA = True
except ImportError:
    HAS_FORMULA = False
    AdaptiveContinuitySnapshot = None
    compute_adaptive_continuity = None


# =============================================================================
# SIGNAL EXTRACTION
# =============================================================================


def extract_p37_signals(ctx: "PipelineContext") -> Dict[str, Any]:
    """
    Extract signals from pipeline context for P37 computation.

    Extracts signals from:
    - P17 (Semantic Integrity)
    - P18 (Temporal Entropy)
    - P24 (Resonance Weighting)
    - P26 (Unified Consciousness Formula)
    - P27 (Symbolic Harmonization)
    - P34 (Identity Harmonics)
    - P35 (Predictive Persona Drift)
    - P36 (Identity Resonance Memory)
    - CoherenceState

    Args:
        ctx: Pipeline context with upstream phase outputs.

    Returns:
        Dictionary of signals for compute_adaptive_continuity().
    """
    signals: Dict[str, Any] = {}

    # Try to get signals from coherence_state
    coherence_state = getattr(ctx, 'coherence_state', None)
    if coherence_state:
        # P17: Semantic Integrity
        signals['semantic_integrity'] = getattr(coherence_state, 'semantic_integrity', None)
        signals['semantic_integrity_history'] = getattr(
            coherence_state, 'semantic_integrity_history', None
        )

        # P18: Temporal Entropy
        signals['temporal_entropy_volatility'] = getattr(
            coherence_state, 'temporal_entropy_volatility', None
        )
        signals['temporal_entropy_diff'] = getattr(
            coherence_state, 'temporal_entropy_diff', None
        )
        signals['temporal_entropy_volatility_history'] = getattr(
            coherence_state, 'temporal_entropy_volatility_history', None
        )

        # P24: Resonance Weighting
        signals['resonance_weighting_entropy'] = getattr(
            coherence_state, 'resonance_weighting_entropy', None
        )

    # P27: Symbolic Harmonization
    p27_output = getattr(ctx, 'p27_persona', None)
    if p27_output is None:
        p27_output = getattr(ctx, 'symbolic_harmonization', None)

    if p27_output:
        shi = getattr(p27_output, 'symbolic_harmonization_index', None)
        if shi is None:
            shi = getattr(p27_output, 'shi', None)
        signals['symbolic_harmonization_index'] = shi
        signals['symbolic_harmonization_history'] = getattr(
            p27_output, 'symbolic_harmonization_history', None
        )

    # P26: Unified Consciousness Formula
    p26_output = getattr(ctx, 'consciousness', None)
    if p26_output is None:
        p26_output = getattr(ctx, 'ucf', None)

    if p26_output:
        signals['consciousness_order_index'] = getattr(p26_output, 'coi', None)
        signals['consciousness_stability_index'] = getattr(p26_output, 'csi', None)
        signals['consciousness_order_history'] = getattr(
            p26_output, 'consciousness_order_history', None
        )
        signals['consciousness_stability_history'] = getattr(
            p26_output, 'consciousness_stability_history', None
        )

    # P34: Identity Harmonics
    p34_output = getattr(ctx, 'p34_identity_harmonics', None)
    if p34_output:
        signals['core_identity_harmonic'] = getattr(p34_output, 'core_identity_harmonic', None)
        signals['adaptive_identity_harmonic'] = getattr(
            p34_output, 'adaptive_identity_harmonic', None
        )
        signals['relational_identity_harmonic'] = getattr(
            p34_output, 'relational_identity_harmonic', None
        )
        signals['identity_stability_score'] = getattr(
            p34_output, 'identity_stability_score', None
        )
        signals['identity_harmonics_index'] = getattr(
            p34_output, 'identity_harmonics_index', None
        )

    # P35: Predictive Persona Drift
    p35_output = getattr(ctx, 'predictive_drift', None)
    if p35_output is None:
        p35_output = getattr(ctx, 'ppdm', None)

    if p35_output:
        signals['drift_magnitude_prediction'] = getattr(
            p35_output, 'drift_magnitude_prediction', None
        )
        signals['drift_stability_score'] = getattr(p35_output, 'drift_stability_score', None)
        signals['drift_likelihood_band'] = getattr(p35_output, 'drift_likelihood_band', None)

    # P36: Identity Resonance Memory
    p36_output = getattr(ctx, 'identity_resonance', None)
    if p36_output is None:
        p36_output = getattr(ctx, 'irm', None)

    if p36_output:
        signals['identity_memory_strength'] = getattr(p36_output, 'ims', None)
        if signals['identity_memory_strength'] is None:
            signals['identity_memory_strength'] = getattr(
                p36_output, 'identity_memory_strength', None
            )
        signals['identity_echo_persistence'] = getattr(p36_output, 'iep', None)
        if signals['identity_echo_persistence'] is None:
            signals['identity_echo_persistence'] = getattr(
                p36_output, 'identity_echo_persistence', None
            )
        signals['identity_drift_anchoring'] = getattr(p36_output, 'ida', None)
        if signals['identity_drift_anchoring'] is None:
            signals['identity_drift_anchoring'] = getattr(
                p36_output, 'identity_drift_anchoring', None
            )
        signals['ims_history'] = getattr(p36_output, 'ims_history', None)
        signals['iep_history'] = getattr(p36_output, 'iep_history', None)
        signals['ida_history'] = getattr(p36_output, 'ida_history', None)

    return signals


# =============================================================================
# CONTINUITY COMPUTATION
# =============================================================================


def run_p37_continuity(signals: Dict[str, Any]) -> Optional[P37Output]:
    """
    Run P37 adaptive continuity computation.

    Args:
        signals: Dictionary of signals extracted by extract_p37_signals().

    Returns:
        P37Output if computation succeeded, None otherwise.
    """
    if not HAS_FORMULA:
        return None

    trace: List[str] = []
    trace.append("Running P37 Adaptive Continuity Engine")

    # Call the formula
    try:
        snapshot = compute_adaptive_continuity(**signals)
    except Exception as e:
        trace.append(f"Formula error: {str(e)}")
        return None

    if snapshot is None:
        trace.append("Formula returned None (insufficient data)")
        return None

    trace.append(f"NCC computed: {snapshot.ncc:.3f}")
    trace.append(f"ICC computed: {snapshot.icc:.3f}")
    trace.append(f"CSS computed: {snapshot.css:.3f}")
    trace.append(f"Continuity band: {snapshot.continuity_band}")

    # Map continuity band string to enum
    band_map = {
        "HIGH": ContinuityBand.HIGH,
        "MEDIUM": ContinuityBand.MEDIUM,
        "LOW": ContinuityBand.LOW,
    }
    continuity_band = band_map.get(snapshot.continuity_band, ContinuityBand.MEDIUM)

    # Convert snapshot to P37Output
    return P37Output(
        ncc=snapshot.ncc,
        icc=snapshot.icc,
        css=snapshot.css,
        continuity_band=continuity_band,
        authority=P37Authority.PREDICTIVE,
        continuity_tags=list(snapshot.continuity_tags) if snapshot.continuity_tags else [],
        raw_signals=dict(snapshot.raw_signals) if snapshot.raw_signals else {},
        processing_trace=trace,
    )


# =============================================================================
# MAIN INTEGRATION
# =============================================================================


def maybe_run_p37(ctx: "PipelineContext") -> Optional[P37Output]:
    """
    Conditionally run P37 Adaptive Continuity Engine phase.

    This is the main integration function to call from the pipeline orchestrator.

    Args:
        ctx: Pipeline context with upstream phase outputs.

    Returns:
        P37Output if phase executed, None otherwise.
    """
    if not HAS_FORMULA:
        return None

    # Extract signals from context
    signals = extract_p37_signals(ctx)

    # Run continuity computation
    return run_p37_continuity(signals)


# =============================================================================
# OUTPUT ACCESSORS
# =============================================================================


def get_p37_output(ctx: "PipelineContext") -> Optional[P37Output]:
    """
    Get P37 output from context if available.

    Args:
        ctx: Pipeline context.

    Returns:
        P37Output if available, None otherwise.
    """
    return getattr(ctx, 'p37_continuity', None)


def get_p37_ncc(ctx: "PipelineContext") -> float:
    """
    Get Narrative Continuity Coefficient (NCC) from P37 output.

    Args:
        ctx: Pipeline context.

    Returns:
        NCC score [0.0, 1.0], defaults to 0.5 if not available.
    """
    output = get_p37_output(ctx)
    if output:
        return output.ncc
    return 0.5


def get_p37_icc(ctx: "PipelineContext") -> float:
    """
    Get Identity Continuity Coefficient (ICC) from P37 output.

    Args:
        ctx: Pipeline context.

    Returns:
        ICC score [0.0, 1.0], defaults to 0.5 if not available.
    """
    output = get_p37_output(ctx)
    if output:
        return output.icc
    return 0.5


def get_p37_css(ctx: "PipelineContext") -> float:
    """
    Get Continuity Stability Score (CSS) from P37 output.

    Args:
        ctx: Pipeline context.

    Returns:
        CSS score [0.0, 1.0], defaults to 0.5 if not available.
    """
    output = get_p37_output(ctx)
    if output:
        return output.css
    return 0.5


def get_p37_continuity_band(ctx: "PipelineContext") -> str:
    """
    Get continuity band classification from P37 output.

    Args:
        ctx: Pipeline context.

    Returns:
        "HIGH", "MEDIUM", or "LOW", defaults to "MEDIUM" if not available.
    """
    output = get_p37_output(ctx)
    if output:
        return output.continuity_band.value
    return "MEDIUM"


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "extract_p37_signals",
    "run_p37_continuity",
    "maybe_run_p37",
    "get_p37_output",
    "get_p37_ncc",
    "get_p37_icc",
    "get_p37_css",
    "get_p37_continuity_band",
    "HAS_FORMULA",
    "VERSION",
]
