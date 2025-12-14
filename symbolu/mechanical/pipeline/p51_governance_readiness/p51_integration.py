"""
Phase 51: Governance Readiness Pipeline Integration

Integration functions for running P51 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu.mechanical.pipeline.p51_governance_readiness import (
        maybe_run_p51,
    )

    # In pipeline after P50:
    maybe_run_p51(ctx)

    # Access readiness envelope:
    if ctx.p51_governance_readiness is not None:
        print(f"Ready: {ctx.p51_governance_readiness.ready}")
        print(f"Level: {ctx.p51_governance_readiness.readiness_level}")

INPUTS (Read-Only):
    Phase 51 MAY read:
        - ctx.phase_20_snapshot (P20 UnifiedCognitiveSnapshot)
        - ctx.p21_delivery_mode (P21 DeliveryModeDecision)
        - ctx.p6_regime (P6 RegimeEnvelope)
        - ctx.p7_discourse_envelope (P7 DiscourseEnvelope)
        - ctx.p18 (P18 Temporal Entropy Differential)
        - ctx.p19_drift_fusion (P19 Drift Fusion Report)
        - ctx.p50_cognitive_consistency (P50 Cognitive Consistency Report)
        - ctx.coherence_state (CoherenceState)

    Phase 51 MUST NOT read:
        - ctx.request (raw user text)
        - ctx.semantic_frame (semantic content)
        - ctx.lexical_frame (lexical content)
        - ctx.p10_acoustic, p11_prosodic_evidence (acoustic content)

CRITICAL CONSTRAINTS:
    - Must NOT influence any upstream phase
    - Must NOT gate or block output
    - Must NOT modify any context fields except p51_governance_readiness
    - P51 is observer-only: output goes to observability, not behavior

INVARIANTS:
    INV-P51-1: P51 MUST NOT modify any upstream data
    INV-P51-2: P51 MUST NOT introduce new classifications or decisions
    INV-P51-3: P51 MUST NOT block or gate output
    INV-P51-4: P51 MUST NOT depend on future governance logic
    INV-P51-5: When P51 is removed, system behavior is bitwise identical
"""

from __future__ import annotations

from typing import Any, Optional

from .p51_schema import (
    P51_VERSION,
    GovernanceReadinessEnvelope,
    ReadinessLevel,
)
from .p51_analyzer import run_p51_directly


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_phase_20_snapshot(ctx: Any) -> Any:
    """
    Extract P20 UnifiedCognitiveSnapshot from context.

    INV-P51-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        UnifiedCognitiveSnapshot if present, None otherwise
    """
    return getattr(ctx, "phase_20_snapshot", None)


def _extract_p21_delivery_mode(ctx: Any) -> Any:
    """
    Extract P21 DeliveryModeDecision from context.

    INV-P51-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        DeliveryModeDecision if present, None otherwise
    """
    return getattr(ctx, "p21_delivery_mode", None)


def _extract_p6_regime(ctx: Any) -> Any:
    """
    Extract P6 RegimeEnvelope from context.

    INV-P51-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        RegimeEnvelope if present, None otherwise
    """
    return getattr(ctx, "p6_regime", None)


def _extract_p7_discourse(ctx: Any) -> Any:
    """
    Extract P7 DiscourseEnvelope from context.

    INV-P51-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        DiscourseEnvelope if present, None otherwise
    """
    return getattr(ctx, "p7_discourse_envelope", None)


def _extract_p18_entropy(ctx: Any) -> Any:
    """
    Extract P18 Temporal Entropy report from context.

    INV-P51-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        P18TemporalEntropyReport if present, None otherwise
    """
    return getattr(ctx, "p18", None)


def _extract_p19_drift(ctx: Any) -> Any:
    """
    Extract P19 Drift Fusion report from context.

    INV-P51-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        P19DriftFusionReport if present, None otherwise
    """
    # Try multiple attribute names for compatibility
    drift = getattr(ctx, "p19_drift_fusion", None)
    if drift is None:
        drift = getattr(ctx, "p19", None)
    return drift


def _extract_p50_cognitive_consistency(ctx: Any) -> Any:
    """
    Extract P50 Cognitive Consistency report from context.

    INV-P51-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        CognitiveConsistencyReport if present, None otherwise
    """
    return getattr(ctx, "p50_cognitive_consistency", None)


def _extract_coherence_state(ctx: Any) -> Any:
    """
    Extract CoherenceState from context.

    INV-P51-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        CoherenceState if present, None otherwise
    """
    return getattr(ctx, "coherence_state", None)


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p51(ctx: Any) -> Optional[GovernanceReadinessEnvelope]:
    """
    Run P51 governance readiness if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P51 should run
    2. Extracts upstream phase outputs from context
    3. Runs the readiness computation
    4. Attaches the result to ctx.p51_governance_readiness

    P51 is designed to run after P50.
    Returns None if disabled.

    INV-P51-1: We only read from ctx, never modify upstream fields.
    INV-P51-2: We report readiness, not create decisions.
    INV-P51-3: We don't gate - output is for observability only.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The GovernanceReadinessEnvelope if run, None if skipped
    """
    # Check if P51 is disabled on this context
    if is_p51_disabled(ctx):
        return None

    # Extract upstream signals
    phase_20_snapshot = _extract_phase_20_snapshot(ctx)
    p21_delivery_mode = _extract_p21_delivery_mode(ctx)
    p6_regime = _extract_p6_regime(ctx)
    p7_discourse = _extract_p7_discourse(ctx)
    p18_entropy = _extract_p18_entropy(ctx)
    p19_drift = _extract_p19_drift(ctx)
    p50_cognitive_consistency = _extract_p50_cognitive_consistency(ctx)
    coherence_state = _extract_coherence_state(ctx)

    # Run the readiness computation
    envelope = run_p51_directly(
        phase_20_snapshot=phase_20_snapshot,
        p21_delivery_mode=p21_delivery_mode,
        p6_regime=p6_regime,
        p7_discourse_envelope=p7_discourse,
        p18_entropy=p18_entropy,
        p19_drift=p19_drift,
        p50_cognitive_consistency=p50_cognitive_consistency,
        coherence_state=coherence_state,
    )

    if envelope is None:
        return None

    # Attach to context (observer-only append)
    _attach_envelope_to_context(ctx, envelope)

    return envelope


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p51_disabled(ctx: Any) -> bool:
    """
    Check if P51 is disabled on this context.

    P51 can be disabled by setting ctx._p51_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P51 is disabled, False otherwise
    """
    return getattr(ctx, "_p51_disabled", False)


def has_p51_envelope(ctx: Any) -> bool:
    """
    Check if context has a P51 envelope attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p51_governance_readiness is set and not None
    """
    return getattr(ctx, "p51_governance_readiness", None) is not None


def get_p51_envelope(ctx: Any) -> Optional[GovernanceReadinessEnvelope]:
    """
    Get the P51 envelope from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The GovernanceReadinessEnvelope if present, None otherwise
    """
    return getattr(ctx, "p51_governance_readiness", None)


def get_readiness_level(ctx: Any) -> ReadinessLevel:
    """
    Get the readiness level from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Readiness level string, or "READY" if no envelope (assume ready)
    """
    envelope = get_p51_envelope(ctx)
    if envelope is None:
        return "READY"
    return envelope.readiness_level


def is_governance_ready(ctx: Any) -> bool:
    """
    Check if context is governance ready.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ready, False otherwise
    """
    envelope = get_p51_envelope(ctx)
    if envelope is None:
        return True  # Assume ready if no envelope
    return envelope.ready


def get_blocking_factors(ctx: Any) -> tuple:
    """
    Get blocking factors from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Tuple of blocking factor strings, or empty tuple if no envelope
    """
    envelope = get_p51_envelope(ctx)
    if envelope is None:
        return ()
    return envelope.blocking_factors


def get_advisory_notes(ctx: Any) -> tuple:
    """
    Get advisory notes from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Tuple of advisory note strings, or empty tuple if no envelope
    """
    envelope = get_p51_envelope(ctx)
    if envelope is None:
        return ()
    return envelope.advisory_notes


def get_p51_version() -> str:
    """
    Get the current P51 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P51_VERSION


def _attach_envelope_to_context(
    ctx: Any,
    envelope: GovernanceReadinessEnvelope,
) -> None:
    """
    Attach the P51 envelope to context.

    This is observer-only: we only append to ctx.p51_governance_readiness,
    we do NOT modify any other context fields or influence behavior.

    INV-P51-1: Only writes to ctx.p51_governance_readiness, nothing else.
    INV-P51-3: No gating - this doesn't block anything.

    Args:
        ctx: PipelineContext
        envelope: The P51 envelope to attach
    """
    # Attach to p51_governance_readiness attribute
    if hasattr(ctx, "p51_governance_readiness"):
        ctx.p51_governance_readiness = envelope
    else:
        try:
            setattr(ctx, "p51_governance_readiness", envelope)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p51",
    "run_p51_directly",
    # Helpers
    "is_p51_disabled",
    "has_p51_envelope",
    "get_p51_envelope",
    "get_readiness_level",
    "is_governance_ready",
    "get_blocking_factors",
    "get_advisory_notes",
    "get_p51_version",
]
