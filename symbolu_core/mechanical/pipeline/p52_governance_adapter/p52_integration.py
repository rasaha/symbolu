"""
Phase 52: Governance Adapter Pipeline Integration

Integration functions for running P52 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu_core.mechanical.pipeline.p52_governance_adapter import (
        maybe_run_p52,
    )

    # In pipeline after P51:
    maybe_run_p52(ctx)

    # Access governance request:
    if ctx.p52_governance_request is not None:
        print(f"Snapshot ID: {ctx.p52_governance_request.snapshot_id}")
        print(f"Readiness: {ctx.p52_governance_request.readiness_level}")

INPUTS (Read-Only):
    Phase 52 MAY read:
        - ctx.p51_governance_readiness (P51 GovernanceReadinessEnvelope)
        - ctx.phase_20_snapshot (P20 UnifiedCognitiveSnapshot)
        - ctx.p21_delivery_mode (P21 DeliveryModeDecision)

    Phase 52 MUST NOT read:
        - ctx.request (raw user text)
        - ctx.semantic_frame (semantic content)
        - ctx.lexical_frame (lexical content)
        - ctx.p10_acoustic, p11_prosodic_evidence (acoustic content)

CRITICAL CONSTRAINTS:
    - P52 assembles GovernanceRequest, nothing more
    - P52 stores request in ctx.p52_governance_request
    - P52 does NOT invoke external systems
    - P52 does NOT expect or require a response
    - P52 is a pure contract boundary

INVARIANTS:
    INV-P52-1: P52 MUST NOT execute or simulate governance
    INV-P52-2: P52 MUST NOT modify or reinterpret upstream data
    INV-P52-3: P52 MUST NOT introduce branching or gating
    INV-P52-4: P52 MUST NOT require GovernanceResponse to exist
    INV-P52-5: When P52 is removed, system behavior is bitwise identical
"""

from __future__ import annotations

from typing import Any, Optional

from .p52_schema import (
    P52_VERSION,
    GovernanceRequest,
)
from .p52_assembler import run_p52_directly


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_p51_envelope(ctx: Any) -> Any:
    """
    Extract P51 GovernanceReadinessEnvelope from context.

    INV-P52-2: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        GovernanceReadinessEnvelope if present, None otherwise
    """
    return getattr(ctx, "p51_governance_readiness", None)


def _extract_phase_20_snapshot(ctx: Any) -> Any:
    """
    Extract P20 UnifiedCognitiveSnapshot from context.

    INV-P52-2: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        UnifiedCognitiveSnapshot if present, None otherwise
    """
    return getattr(ctx, "phase_20_snapshot", None)


def _extract_p21_delivery_mode(ctx: Any) -> Any:
    """
    Extract P21 DeliveryModeDecision from context.

    INV-P52-2: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        DeliveryModeDecision if present, None otherwise
    """
    return getattr(ctx, "p21_delivery_mode", None)


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p52(ctx: Any) -> Optional[GovernanceRequest]:
    """
    Run P52 governance adapter if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P52 should run
    2. Extracts upstream phase outputs from context
    3. Assembles the GovernanceRequest
    4. Attaches the result to ctx.p52_governance_request

    P52 is designed to run after P51.
    Returns None if disabled or P51 not present.

    INV-P52-1: We assemble a request, never execute governance.
    INV-P52-2: We copy data verbatim, never reinterpret.
    INV-P52-3: No branching/gating — request is for observability only.
    INV-P52-4: GovernanceResponse is never created or expected.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The GovernanceRequest if assembled, None if skipped
    """
    # Check if P52 is disabled on this context
    if is_p52_disabled(ctx):
        return None

    # Extract upstream signals
    p51_envelope = _extract_p51_envelope(ctx)
    phase_20_snapshot = _extract_phase_20_snapshot(ctx)
    p21_delivery_mode = _extract_p21_delivery_mode(ctx)

    # Assemble the governance request
    request = run_p52_directly(
        p51_envelope=p51_envelope,
        phase_20_snapshot=phase_20_snapshot,
        p21_delivery_mode=p21_delivery_mode,
    )

    if request is None:
        return None

    # Attach to context (observer-only append)
    _attach_request_to_context(ctx, request)

    return request


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p52_disabled(ctx: Any) -> bool:
    """
    Check if P52 is disabled on this context.

    P52 can be disabled by setting ctx._p52_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P52 is disabled, False otherwise
    """
    return getattr(ctx, "_p52_disabled", False)


def has_p52_request(ctx: Any) -> bool:
    """
    Check if context has a P52 request attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p52_governance_request is set and not None
    """
    return getattr(ctx, "p52_governance_request", None) is not None


def get_p52_request(ctx: Any) -> Optional[GovernanceRequest]:
    """
    Get the P52 request from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The GovernanceRequest if present, None otherwise
    """
    return getattr(ctx, "p52_governance_request", None)


def get_p52_version() -> str:
    """
    Get the current P52 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P52_VERSION


def _attach_request_to_context(
    ctx: Any,
    request: GovernanceRequest,
) -> None:
    """
    Attach the P52 request to context.

    This is observer-only: we only append to ctx.p52_governance_request,
    we do NOT modify any other context fields or influence behavior.

    INV-P52-2: Only writes to ctx.p52_governance_request, nothing else.
    INV-P52-3: No gating — this doesn't block anything.

    Args:
        ctx: PipelineContext
        request: The P52 request to attach
    """
    # Attach to p52_governance_request attribute
    if hasattr(ctx, "p52_governance_request"):
        ctx.p52_governance_request = request
    else:
        try:
            setattr(ctx, "p52_governance_request", request)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p52",
    "run_p52_directly",
    # Helpers
    "is_p52_disabled",
    "has_p52_request",
    "get_p52_request",
    "get_p52_version",
]
