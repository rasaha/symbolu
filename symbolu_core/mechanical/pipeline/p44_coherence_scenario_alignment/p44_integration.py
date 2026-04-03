"""
Phase 44: Coherence-Scenario Alignment Engine Pipeline Integration

Integration functions for running P44 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu_core.mechanical.pipeline.p44_coherence_scenario_alignment import (
        maybe_run_p44,
    )

    # In pipeline after P43:
    maybe_run_p44(ctx)

    # Access alignment report:
    if ctx.p44_coherence_scenario_alignment is not None:
        print(f"Base: {ctx.p44_coherence_scenario_alignment.base_alignment_score}")
        print(f"Band: {ctx.p44_coherence_scenario_alignment.alignment_band}")

INPUTS (Read-Only):
    Phase 44 MAY read:
        - ctx.coherence_score_v3 (Phase 10)
        - ctx.coherence_v3_quality (Phase 12)
        - ctx.p42_scenario_fusion (ScenarioFusionField)
        - ctx.p43_scenario_what_if (ScenarioWhatIfSet, optional)

    Phase 44 MUST NOT read:
        - Text, semantics, discourse, lexical content
        - Acoustic / vrtti / kosha data
        - Regime selection outputs (P6)
        - Governance phases (>=50)
        - Renderer / persona layers

CRITICAL CONSTRAINTS:
    - Must NOT choose a scenario
    - Must NOT rank variants
    - Must NOT forecast outcomes
    - Must NOT open or close gates
    - Must NOT feed results upstream

INVARIANTS:
    - INV-P44-1: Measurement only (no ranking, no preference, no selection)
    - INV-P44-2: Deterministic math only (no randomness, no learned parameters)
    - INV-P44-3: Variant isolation (variants do not influence base alignment)
    - INV-P44-4: No authority influence (output never affects regime, discourse, policy)
    - INV-P44-5: Absence-safe (missing inputs -> no output)
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from .p44_schema import (
    P44_VERSION,
    CoherenceScenarioAlignmentReport,
)
from .p44_alignment_engine import compute_alignment


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_coherence_v3_quality(ctx: Any) -> Optional[float]:
    """
    Extract coherence_v3_quality from context.

    Checks for:
        - ctx.coherence_v3_quality (direct)
        - ctx.coherence_state.coherence_v3_quality (nested)

    INV-P44-4: We read these values but NEVER modify them.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        coherence_v3_quality if present, None otherwise
    """
    # Check direct attribute
    quality = getattr(ctx, "coherence_v3_quality", None)
    if quality is not None:
        return quality

    # Check nested in coherence_state
    coherence_state = getattr(ctx, "coherence_state", None)
    if coherence_state is not None:
        quality = getattr(coherence_state, "coherence_v3_quality", None)
        if quality is not None:
            return quality

    return None


def _extract_scenario_fusion_confidence(ctx: Any) -> Optional[float]:
    """
    Extract scenario fusion confidence from context.

    Checks for:
        - ctx.p42_scenario_fusion_field.fusion_confidence
        - ctx.p42_scenario_fusion.fusion_confidence

    INV-P44-4: We read these values but NEVER modify them.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        fusion_confidence if present, None otherwise
    """
    # Check p42_scenario_fusion_field
    fusion_field = getattr(ctx, "p42_scenario_fusion_field", None)
    if fusion_field is not None:
        confidence = getattr(fusion_field, "fusion_confidence", None)
        if confidence is not None:
            return confidence

    # Check alternate naming p42_scenario_fusion
    fusion_field = getattr(ctx, "p42_scenario_fusion", None)
    if fusion_field is not None:
        confidence = getattr(fusion_field, "fusion_confidence", None)
        if confidence is not None:
            return confidence

    return None


def _extract_what_if_variants(ctx: Any) -> Optional[Tuple[Any, ...]]:
    """
    Extract what-if variants from context (if P43 present).

    Checks for:
        - ctx.p43_scenario_what_if.what_if_variants

    INV-P44-4: We read these values but NEVER modify them.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Tuple of ScenarioVariant if present, None otherwise
    """
    what_if_set = getattr(ctx, "p43_scenario_what_if", None)
    if what_if_set is not None:
        variants = getattr(what_if_set, "what_if_variants", None)
        if variants is not None:
            return tuple(variants)

    return None


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p44(ctx: Any) -> Optional[CoherenceScenarioAlignmentReport]:
    """
    Run P44 coherence-scenario alignment if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P44 should run
    2. Extracts coherence_v3_quality from context
    3. Extracts ScenarioFusionField from context
    4. Optionally extracts ScenarioWhatIfSet from context
    5. Runs the alignment computation
    6. Attaches the result to ctx.p44_coherence_scenario_alignment

    P44 is designed to run after P42/P43.
    Returns None if required inputs are unavailable (INV-P44-5).

    INV-P44-1: Measurement only - no ranking, preference, or selection.
    INV-P44-2: Deterministic - same inputs always produce same outputs.
    INV-P44-4: Observer-only - we only write to ctx.p44_coherence_scenario_alignment.
    INV-P44-5: Absence-safe - missing input produces None.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The CoherenceScenarioAlignmentReport if run, None if skipped
    """
    # Check if P44 is disabled on this context
    if is_p44_disabled(ctx):
        return None

    # Extract coherence_v3_quality
    coherence_v3_quality = _extract_coherence_v3_quality(ctx)

    # Extract scenario fusion confidence
    scenario_fusion_confidence = _extract_scenario_fusion_confidence(ctx)

    # INV-P44-5: Absence-safe - return None if required inputs missing
    if coherence_v3_quality is None or scenario_fusion_confidence is None:
        return None

    # Extract optional what-if variants (P43)
    what_if_variants = _extract_what_if_variants(ctx)

    # Run the alignment computation
    alignment_report = compute_alignment(
        coherence_v3_quality=coherence_v3_quality,
        scenario_fusion_confidence=scenario_fusion_confidence,
        what_if_variants=what_if_variants,
    )

    if alignment_report is None:
        return None

    # Attach to context (observer-only append)
    _attach_alignment_report_to_context(ctx, alignment_report)

    return alignment_report


def run_p44_directly(
    coherence_v3_quality: Optional[float],
    scenario_fusion_confidence: Optional[float],
    what_if_variants: Optional[Tuple[Any, ...]] = None,
) -> Optional[CoherenceScenarioAlignmentReport]:
    """
    Run P44 directly with explicit inputs (for testing).

    This bypasses context extraction and allows direct testing
    with mock values.

    INV-P44-2: Deterministic - same inputs always produce same outputs.
    INV-P44-5: Absence-safe - missing input produces None.

    Args:
        coherence_v3_quality: Quality score from Phase 12 [0.0, 1.0]
        scenario_fusion_confidence: Fusion confidence from Phase 42 [0.0, 1.0]
        what_if_variants: Optional tuple of ScenarioVariant from Phase 43

    Returns:
        CoherenceScenarioAlignmentReport if computation succeeds, None otherwise
    """
    return compute_alignment(
        coherence_v3_quality=coherence_v3_quality,
        scenario_fusion_confidence=scenario_fusion_confidence,
        what_if_variants=what_if_variants,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p44_disabled(ctx: Any) -> bool:
    """
    Check if P44 is disabled on this context.

    P44 can be disabled by setting ctx._p44_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P44 is disabled, False otherwise
    """
    return getattr(ctx, "_p44_disabled", False)


def has_p44_alignment_report(ctx: Any) -> bool:
    """
    Check if context has a P44 alignment report attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p44_coherence_scenario_alignment is set and not None
    """
    return getattr(ctx, "p44_coherence_scenario_alignment", None) is not None


def get_p44_alignment_report(ctx: Any) -> Optional[CoherenceScenarioAlignmentReport]:
    """
    Get the P44 alignment report from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The CoherenceScenarioAlignmentReport if present, None otherwise
    """
    return getattr(ctx, "p44_coherence_scenario_alignment", None)


def get_base_alignment_score(ctx: Any) -> float:
    """
    Get the base alignment score from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Base alignment score in [0.0, 1.0], or 0.0 if no report
    """
    report = get_p44_alignment_report(ctx)
    if report is None:
        return 0.0
    return report.base_alignment_score


def get_alignment_band(ctx: Any) -> str:
    """
    Get the alignment band from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Alignment band string, or "misaligned" if no report
    """
    report = get_p44_alignment_report(ctx)
    if report is None:
        return "misaligned"
    return report.alignment_band


def get_p44_version() -> str:
    """
    Get the current P44 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P44_VERSION


def _attach_alignment_report_to_context(
    ctx: Any,
    alignment_report: CoherenceScenarioAlignmentReport,
) -> None:
    """
    Attach the P44 alignment report to context.

    This is observer-only: we only append to ctx.p44_coherence_scenario_alignment,
    we do NOT modify any other context fields or influence behavior.

    INV-P44-4: Only writes to ctx.p44_coherence_scenario_alignment, nothing else.

    Args:
        ctx: PipelineContext
        alignment_report: The P44 alignment report to attach
    """
    # Attach to p44_coherence_scenario_alignment attribute
    if hasattr(ctx, "p44_coherence_scenario_alignment"):
        ctx.p44_coherence_scenario_alignment = alignment_report
    else:
        try:
            setattr(ctx, "p44_coherence_scenario_alignment", alignment_report)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p44",
    "run_p44_directly",
    # Helpers
    "is_p44_disabled",
    "has_p44_alignment_report",
    "get_p44_alignment_report",
    "get_base_alignment_score",
    "get_alignment_band",
    "get_p44_version",
]
