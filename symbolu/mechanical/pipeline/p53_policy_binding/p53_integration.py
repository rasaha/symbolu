"""
Phase 53: External Policy Binding Pipeline Integration

Integration functions for running P53 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu.mechanical.pipeline.p53_policy_binding import (
        maybe_run_p53,
    )

    # In pipeline after P52:
    maybe_run_p53(ctx)

    # Access binding envelope:
    if ctx.p53_policy_binding is not None:
        print(f"Bound: {ctx.p53_policy_binding.bound}")
        print(f"Decision: {ctx.p53_policy_binding.decision}")

INPUTS (Read-Only):
    Phase 53 MAY read:
        - ctx.p52_governance_request (P52 GovernanceRequest)
        - ctx.p53_governance_response (external, optional)
        - ctx.p53_authority_id (external, optional)

    Phase 53 MUST NOT read:
        - ctx.request (raw user text)
        - ctx.semantic_frame (semantic content)
        - ctx.lexical_frame (lexical content)
        - ctx.p10_acoustic, p11_prosodic_evidence (acoustic content)
        - Any regime or intent logic

CRITICAL CONSTRAINTS:
    - P53 binds external governance response, nothing more
    - P53 stores envelope in ctx.p53_policy_binding
    - P53 does NOT interpret decisions
    - P53 does NOT act on decisions
    - P53 is a binding layer, not a judge

INVARIANTS:
    INV-P53-1: P53 MUST NOT modify cognition, regime, discourse, or delivery
    INV-P53-2: P53 MUST NOT reinterpret governance decisions
    INV-P53-3: P53 MUST NOT introduce fallback logic if governance is absent
    INV-P53-4: P53 MUST NOT assume authority correctness
    INV-P53-5: P53 MUST remain removable without changing cognitive outputs
"""

from __future__ import annotations

from typing import Any, Optional

from .p53_schema import (
    P53_VERSION,
    GovernanceBindingEnvelope,
)
from .p53_binder import (
    bind_governance_response,
    GovernanceResponseValidationError,
)


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_p52_request(ctx: Any) -> Any:
    """
    Extract P52 GovernanceRequest from context.

    INV-P53-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        GovernanceRequest if present, None otherwise
    """
    return getattr(ctx, "p52_governance_request", None)


def _extract_governance_response(ctx: Any) -> Any:
    """
    Extract external GovernanceResponse from context.

    This is the ONLY place P53 looks for an external governance response.
    If no response exists, P53 creates an unbound envelope.

    INV-P53-2: We read this value verbatim, never reinterpret.
    INV-P53-3: No fallback logic — we just record absence.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        GovernanceResponse if present, None otherwise
    """
    return getattr(ctx, "p53_governance_response", None)


def _extract_authority_id(ctx: Any) -> Optional[str]:
    """
    Extract authority identifier from context.

    Authority ID is opaque — no parsing, no validation.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Authority ID string if present, None otherwise
    """
    return getattr(ctx, "p53_authority_id", None)


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p53(ctx: Any) -> Optional[GovernanceBindingEnvelope]:
    """
    Run P53 policy binding if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P53 should run
    2. Extracts governance response from context (if present)
    3. Binds the response (or records absence)
    4. Attaches the result to ctx.p53_policy_binding

    P53 is designed to run after P52.
    Returns None only if disabled.

    INV-P53-1: We bind governance, never modify cognition.
    INV-P53-2: We copy response verbatim, never reinterpret.
    INV-P53-3: No fallback logic — just absence recording.
    INV-P53-4: We don't validate authority correctness.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The GovernanceBindingEnvelope if created, None if skipped

    Raises:
        GovernanceResponseValidationError: If response structure is invalid
    """
    # Check if P53 is disabled on this context
    if is_p53_disabled(ctx):
        return None

    # Extract governance response (may be None)
    response = _extract_governance_response(ctx)
    authority_id = _extract_authority_id(ctx)

    # Bind the response (or record absence)
    envelope = bind_governance_response(response, authority_id)

    # Attach to context (observer-only append)
    _attach_binding_to_context(ctx, envelope)

    return envelope


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p53_disabled(ctx: Any) -> bool:
    """
    Check if P53 is disabled on this context.

    P53 can be disabled by setting ctx._p53_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P53 is disabled, False otherwise
    """
    return getattr(ctx, "_p53_disabled", False)


def has_p53_binding(ctx: Any) -> bool:
    """
    Check if context has a P53 binding envelope attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p53_policy_binding is set and not None
    """
    return getattr(ctx, "p53_policy_binding", None) is not None


def get_p53_binding(ctx: Any) -> Optional[GovernanceBindingEnvelope]:
    """
    Get the P53 binding envelope from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The GovernanceBindingEnvelope if present, None otherwise
    """
    return getattr(ctx, "p53_policy_binding", None)


def is_governance_bound(ctx: Any) -> bool:
    """
    Check if governance has been bound to this context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if bound, False otherwise
    """
    envelope = get_p53_binding(ctx)
    if envelope is None:
        return False
    return envelope.bound


def get_governance_decision(ctx: Any) -> Optional[str]:
    """
    Get the governance decision if bound.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        "ALLOW", "DENY", "DEFER", or None if not bound
    """
    envelope = get_p53_binding(ctx)
    if envelope is None or not envelope.bound:
        return None
    return envelope.decision


def get_p53_version() -> str:
    """
    Get the current P53 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P53_VERSION


def _attach_binding_to_context(
    ctx: Any,
    envelope: GovernanceBindingEnvelope,
) -> None:
    """
    Attach the P53 binding envelope to context.

    This is observer-only: we only append to ctx.p53_policy_binding,
    we do NOT modify any other context fields or influence behavior.

    INV-P53-1: Only writes to ctx.p53_policy_binding, nothing else.
    INV-P53-5: This is the only effect P53 has on context.

    Args:
        ctx: PipelineContext
        envelope: The P53 binding envelope to attach
    """
    # Attach to p53_policy_binding attribute
    if hasattr(ctx, "p53_policy_binding"):
        ctx.p53_policy_binding = envelope
    else:
        try:
            setattr(ctx, "p53_policy_binding", envelope)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p53",
    # Helpers
    "is_p53_disabled",
    "has_p53_binding",
    "get_p53_binding",
    "is_governance_bound",
    "get_governance_decision",
    "get_p53_version",
    # Exceptions
    "GovernanceResponseValidationError",
]
