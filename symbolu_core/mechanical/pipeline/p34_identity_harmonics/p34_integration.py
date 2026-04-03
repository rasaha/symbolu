"""
P34 Identity Harmonics Layer Integration
==========================================

Integration shim for running P34 Identity Harmonics Layer phase within
the Symbol-U pipeline orchestrator.

Wraps the existing formula:
    symbolu/formulas/identity_harmonics.py

Usage in orchestrator:
    from .p34_identity_harmonics import maybe_run_p34, get_p34_output

    # After P27-P33 stages
    p34_result = maybe_run_p34(ctx)
    if p34_result:
        ctx.p34_identity_harmonics = p34_result
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .p34_identity_harmonics_schema import (
    VERSION,
    P34Authority,
    P34Output,
)

if TYPE_CHECKING:
    from symbolu_core.mechanical.pipeline.models import PipelineContext

# =============================================================================
# FORMULA IMPORT (graceful degradation)
# =============================================================================

try:
    from symbolu_core.formulas.identity_harmonics import (
        IdentityHarmonicsSnapshot,
        compute_identity_harmonics,
    )
    HAS_FORMULA = True
except ImportError:
    HAS_FORMULA = False
    IdentityHarmonicsSnapshot = None
    compute_identity_harmonics = None


# =============================================================================
# SIGNAL EXTRACTION
# =============================================================================


def extract_p34_signals(ctx: "PipelineContext") -> Dict[str, Any]:
    """
    Extract signals from pipeline context for P34 computation.

    Extracts signals from:
    - P17 (Semantic Integrity)
    - P18 (Temporal Entropy)
    - P26 (Unified Consciousness Formula)
    - P27 (Symbolic Harmonization)
    - CoherenceState (cognitive drift, persona drift, loop alignment)

    Args:
        ctx: Pipeline context with upstream phase outputs.

    Returns:
        Dictionary of signals for compute_identity_harmonics().
    """
    signals: Dict[str, Any] = {}

    # Try to get signals from coherence_state
    coherence_state = getattr(ctx, 'coherence_state', None)
    if coherence_state:
        # Semantic signals
        signals['semantic_integrity'] = getattr(coherence_state, 'semantic_integrity', None)
        signals['semantic_integrity_history'] = getattr(
            coherence_state, 'semantic_integrity_history', None
        )

        # Cognitive/temporal signals
        signals['cognitive_drift_v3'] = getattr(coherence_state, 'cognitive_drift_v3', None)
        signals['cognitive_drift_history'] = getattr(
            coherence_state, 'cognitive_drift_v3_history', None
        )
        signals['temporal_entropy_volatility'] = getattr(
            coherence_state, 'temporal_entropy_volatility', None
        )

        # Persona signals
        signals['persona_drift_score'] = getattr(coherence_state, 'persona_drift_score', None)

        # Loop alignment
        signals['loop_alignment'] = getattr(coherence_state, 'loop_alignment', None)

        # Guna/Kosha resonance
        signals['guna_resonance_index'] = getattr(coherence_state, 'guna_resonance_index', None)
        signals['kosha_resonance_index'] = getattr(coherence_state, 'kosha_resonance_index', None)

    # Try to get P27 symbolic harmonization
    p27_output = getattr(ctx, 'p27_persona', None)
    if p27_output is None:
        p27_output = getattr(ctx, 'symbolic_harmonization', None)

    if p27_output:
        # Try different attribute names for SHI
        shi = getattr(p27_output, 'symbolic_harmonization_index', None)
        if shi is None:
            shi = getattr(p27_output, 'shi', None)
        signals['symbolic_harmonization_index'] = shi

        shi_history = getattr(p27_output, 'shi_history', None)
        if shi_history is None:
            shi_history = getattr(p27_output, 'symbolic_harmonization_history', None)
        signals['symbolic_harmonization_history'] = shi_history

    # Try to get P26 consciousness signals
    p26_output = getattr(ctx, 'consciousness', None)
    if p26_output is None:
        p26_output = getattr(ctx, 'ucf', None)

    if p26_output:
        signals['consciousness_order_index'] = getattr(p26_output, 'coi', None)
        if signals['consciousness_order_index'] is None:
            signals['consciousness_order_index'] = getattr(
                p26_output, 'consciousness_order_index', None
            )

    return signals


# =============================================================================
# HARMONICS COMPUTATION
# =============================================================================


def run_p34_harmonics(signals: Dict[str, Any]) -> Optional[P34Output]:
    """
    Run P34 identity harmonics computation.

    Args:
        signals: Dictionary of signals extracted by extract_p34_signals().

    Returns:
        P34Output if computation succeeded, None otherwise.
    """
    if not HAS_FORMULA:
        return None

    trace: List[str] = []
    trace.append("Running P34 Identity Harmonics Layer")

    # Call the formula
    try:
        snapshot = compute_identity_harmonics(**signals)
    except Exception as e:
        trace.append(f"Formula error: {str(e)}")
        return None

    if snapshot is None:
        trace.append("Formula returned None (insufficient data)")
        return None

    trace.append(f"IHI computed: {snapshot.identity_harmonics_index:.3f}")
    trace.append(f"CIH: {snapshot.core_identity_harmonic:.3f}")
    trace.append(f"AIH: {snapshot.adaptive_identity_harmonic:.3f}")
    trace.append(f"RIH: {snapshot.relational_identity_harmonic:.3f}")

    # Convert snapshot to P34Output
    return P34Output(
        core_identity_harmonic=snapshot.core_identity_harmonic,
        adaptive_identity_harmonic=snapshot.adaptive_identity_harmonic,
        relational_identity_harmonic=snapshot.relational_identity_harmonic,
        identity_harmonics_index=snapshot.identity_harmonics_index,
        identity_entropy=snapshot.identity_entropy,
        identity_stability_score=snapshot.identity_stability_score,
        identity_flexibility_score=snapshot.identity_flexibility_score,
        authority=P34Authority.OBSERVER,
        diagnostic_tags=list(snapshot.notes) if snapshot.notes else [],
        processing_trace=trace,
    )


# =============================================================================
# MAIN INTEGRATION
# =============================================================================


def maybe_run_p34(ctx: "PipelineContext") -> Optional[P34Output]:
    """
    Conditionally run P34 Identity Harmonics Layer phase.

    This is the main integration function to call from the pipeline orchestrator.

    Args:
        ctx: Pipeline context with upstream phase outputs.

    Returns:
        P34Output if phase executed, None otherwise.
    """
    if not HAS_FORMULA:
        return None

    # Extract signals from context
    signals = extract_p34_signals(ctx)

    # Run harmonics computation
    return run_p34_harmonics(signals)


# =============================================================================
# OUTPUT ACCESSORS
# =============================================================================


def get_p34_output(ctx: "PipelineContext") -> Optional[P34Output]:
    """
    Get P34 output from context if available.

    Args:
        ctx: Pipeline context.

    Returns:
        P34Output if available, None otherwise.
    """
    return getattr(ctx, 'p34_identity_harmonics', None)


def get_p34_identity_harmonics_index(ctx: "PipelineContext") -> float:
    """
    Get Identity Harmonics Index (IHI) from P34 output.

    Args:
        ctx: Pipeline context.

    Returns:
        IHI score [0.0, 1.0], defaults to 0.5 if not available.
    """
    output = get_p34_output(ctx)
    if output:
        return output.identity_harmonics_index
    return 0.5


def get_p34_stability_score(ctx: "PipelineContext") -> float:
    """
    Get identity stability score from P34 output.

    Args:
        ctx: Pipeline context.

    Returns:
        Stability score [0.0, 1.0], defaults to 0.5 if not available.
    """
    output = get_p34_output(ctx)
    if output:
        return output.identity_stability_score
    return 0.5


def get_p34_flexibility_score(ctx: "PipelineContext") -> float:
    """
    Get identity flexibility score from P34 output.

    Args:
        ctx: Pipeline context.

    Returns:
        Flexibility score [0.0, 1.0], defaults to 0.5 if not available.
    """
    output = get_p34_output(ctx)
    if output:
        return output.identity_flexibility_score
    return 0.5


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "extract_p34_signals",
    "run_p34_harmonics",
    "maybe_run_p34",
    "get_p34_output",
    "get_p34_identity_harmonics_index",
    "get_p34_stability_score",
    "get_p34_flexibility_score",
    "HAS_FORMULA",
    "VERSION",
]
