"""
P21 - Delivery Mode Resolver Integration

Integration functions for running P21 within the pipeline.
Provides singleton access and pipeline-friendly entry points.

Usage:
    from symbolu.mechanical.pipeline.p21_delivery import maybe_run_p21

    # In pipeline after P20:
    maybe_run_p21(ctx)

    # Access decision:
    if ctx.p21 is not None:
        print(f"Delivery mode: {ctx.p21.delivery_mode}")
        print(f"Allowed: {ctx.p21.delivery_allowed}")

CRITICAL CONSTRAINTS:
    - Must not block pipeline execution
    - Must not modify routing, MLCR, TTOR, Fusion, DHA
    - Must not read acoustic, lexical, semantic, or ontology data
    - Attaches result to ctx.delivery_mode_decision (or ctx.p21)
"""

from __future__ import annotations

from typing import Any, Optional

from symbolu.mechanical.pipeline.p21_delivery.p21_delivery_schema import (
    P21_VERSION,
    DeliveryMode,
    DeliveryModeDecision,
    DeliveryInvariantViolation,
)
from symbolu.mechanical.pipeline.p21_delivery.p21_delivery_resolver import (
    DeliveryModeResolver,
)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================


_p21_resolver: Optional[DeliveryModeResolver] = None


def get_p21_resolver() -> DeliveryModeResolver:
    """
    Get the singleton DeliveryModeResolver instance.

    Returns:
        The shared DeliveryModeResolver instance
    """
    global _p21_resolver
    if _p21_resolver is None:
        _p21_resolver = DeliveryModeResolver()
    return _p21_resolver


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p21(ctx: Any) -> Optional[DeliveryModeDecision]:
    """
    Run P21 delivery mode resolution if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P21 should run
    2. Runs the delivery mode resolution
    3. Attaches the decision to ctx.p21 and ctx.delivery_mode_decision
    4. Never blocks pipeline execution (returns None on skip)

    P21 is designed to run after P20 (cognition complete) and before renderers.

    CRITICAL: This function:
    - Must NOT modify routing, MLCR, TTOR, Fusion, DHA
    - Must NOT read acoustic, lexical, semantic, or ontology data
    - Must NOT block pipeline execution

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The DeliveryModeDecision if run, None if skipped
    """
    # Check if P21 is disabled on this context
    if is_p21_disabled(ctx):
        return None

    # P21 can run with minimal context (conservative default)
    # Only skip if context is completely invalid
    if ctx is None:
        return None

    # Run the resolver
    try:
        resolver = get_p21_resolver()
        decision = resolver.resolve(ctx)
    except DeliveryInvariantViolation:
        # Re-raise invariant violations - these are critical
        raise
    except Exception:
        # For other errors, return None to not block pipeline
        # In production, this should be logged
        return None

    # Attach to context (multiple attribute names for compatibility)
    _attach_decision(ctx, decision)

    return decision


def run_p21(ctx: Any) -> DeliveryModeDecision:
    """
    Run P21 directly, always returning a decision.

    Unlike maybe_run_p21, this always runs and returns a decision.
    Use this for testing or when you need guaranteed output.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        DeliveryModeDecision (always returns, never None)
    """
    resolver = get_p21_resolver()
    return resolver.resolve(ctx)


def run_p21_directly(
    blocked: bool = False,
    regime: Optional[str] = None,
    acoustic_permission_flag: Optional[bool] = None,
    drift_risk_band: Optional[str] = None,
) -> DeliveryModeDecision:
    """
    Run P21 directly with explicit inputs (for testing).

    This bypasses context extraction and allows direct testing
    of the delivery mode resolution with mock values.

    Args:
        blocked: Whether upstream governance blocked
        regime: Operational regime (HOLD, OPEN, etc.)
        acoustic_permission_flag: Whether P13 permits acoustic features
        drift_risk_band: Drift risk band from P19 ("low", "moderate", "high")

    Returns:
        DeliveryModeDecision with computed delivery mode
    """
    # Create a minimal mock context
    class MockContext:
        pass

    ctx = MockContext()

    # Set up phase_minus_one for blocked status
    if blocked:
        class MockPO1:
            def is_blocked(self) -> bool:
                return True
        ctx.phase_minus_one = MockPO1()

    # Set up p6_regime
    if regime:
        class MockP6:
            pass
        p6 = MockP6()
        p6.regime = regime
        ctx.p6_regime = p6

    # Set up p13_safety_envelope
    if acoustic_permission_flag is not None:
        class MockP13:
            def is_safe(self) -> bool:
                return acoustic_permission_flag
        ctx.p13_safety_envelope = MockP13()

    # Set up p19 for drift risk
    if drift_risk_band:
        class MockP19:
            pass
        p19 = MockP19()
        p19.drift_risk_band = drift_risk_band
        ctx.p19 = p19

    return run_p21(ctx)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _attach_decision(ctx: Any, decision: DeliveryModeDecision) -> None:
    """
    Attach the delivery decision to context.

    Attaches to both ctx.p21 and ctx.delivery_mode_decision for compatibility.

    Args:
        ctx: PipelineContext
        decision: The P21 decision
    """
    # Attach to p21 (standard attribute)
    if hasattr(ctx, "p21"):
        ctx.p21 = decision
    else:
        try:
            setattr(ctx, "p21", decision)
        except AttributeError:
            pass  # Context is frozen

    # Attach to delivery_mode_decision (alternate attribute)
    if hasattr(ctx, "delivery_mode_decision"):
        ctx.delivery_mode_decision = decision
    else:
        try:
            setattr(ctx, "delivery_mode_decision", decision)
        except AttributeError:
            pass  # Context is frozen


def is_p21_disabled(ctx: Any) -> bool:
    """
    Check if P21 is disabled on this context.

    P21 can be disabled by setting ctx._p21_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P21 is disabled, False otherwise
    """
    return getattr(ctx, "_p21_disabled", False)


def has_p21_decision(ctx: Any) -> bool:
    """
    Check if context has a P21 decision attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p21 or ctx.delivery_mode_decision is set
    """
    return (
        getattr(ctx, "p21", None) is not None or
        getattr(ctx, "delivery_mode_decision", None) is not None
    )


def get_p21_decision(ctx: Any) -> Optional[DeliveryModeDecision]:
    """
    Get the P21 decision from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The DeliveryModeDecision if present, None otherwise
    """
    decision = getattr(ctx, "p21", None)
    if decision is None:
        decision = getattr(ctx, "delivery_mode_decision", None)
    return decision


def get_delivery_mode(ctx: Any) -> DeliveryMode:
    """
    Get the delivery mode from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        DeliveryMode enum value, or TEXT_ONLY as safe default
    """
    decision = get_p21_decision(ctx)
    if decision is None:
        return DeliveryMode.TEXT_ONLY
    return decision.delivery_mode


def is_delivery_allowed(ctx: Any) -> bool:
    """
    Check if delivery is allowed from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if delivery is allowed, False otherwise
    """
    decision = get_p21_decision(ctx)
    if decision is None:
        return True  # Conservative: assume allowed if no decision
    return decision.delivery_allowed


def allows_voice_delivery(ctx: Any) -> bool:
    """
    Check if voice delivery is allowed.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if voice delivery is permitted
    """
    decision = get_p21_decision(ctx)
    if decision is None:
        return False  # Conservative: no voice without decision
    return decision.allows_voice()


def allows_text_delivery(ctx: Any) -> bool:
    """
    Check if text delivery is allowed.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if text delivery is permitted
    """
    decision = get_p21_decision(ctx)
    if decision is None:
        return True  # Conservative: text allowed by default
    return decision.allows_text()


def is_suppressed(ctx: Any) -> bool:
    """
    Check if delivery is suppressed.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if delivery is completely suppressed
    """
    decision = get_p21_decision(ctx)
    if decision is None:
        return False
    return decision.is_suppressed()


def get_p21_version() -> str:
    """
    Get the current P21 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P21_VERSION


def validate_renderer_compliance(ctx: Any, renderer_mode: str) -> None:
    """
    Validate that a renderer is complying with the P21 decision.

    This should be called by renderers before delivering output.

    Args:
        ctx: PipelineContext with P21 decision
        renderer_mode: The mode the renderer intends to use ("text", "voice", "both", "none")

    Raises:
        DeliveryInvariantViolation: If renderer would violate the decision
    """
    decision = get_p21_decision(ctx)
    if decision is None:
        return  # No decision to enforce

    resolver = get_p21_resolver()
    resolver.validate_renderer_compliance(decision, renderer_mode)


# Public exports
__all__ = [
    # Singleton
    "get_p21_resolver",
    # Integration
    "maybe_run_p21",
    "run_p21",
    "run_p21_directly",
    # Helpers
    "is_p21_disabled",
    "has_p21_decision",
    "get_p21_decision",
    "get_delivery_mode",
    "is_delivery_allowed",
    "allows_voice_delivery",
    "allows_text_delivery",
    "is_suppressed",
    "get_p21_version",
    "validate_renderer_compliance",
]
