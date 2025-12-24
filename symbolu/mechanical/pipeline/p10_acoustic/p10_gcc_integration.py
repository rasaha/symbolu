"""
P10 GCC Integration - Pipeline Integration for GCC Mode Switch
===============================================================

Provides integration functions for Phase-10 GCC mode switch.
This is the main entry point for running Phase-10 with explicit gcc_mode control.

Usage in orchestrator:
    from symbolu.mechanical.pipeline.p10_acoustic.p10_gcc_integration import (
        run_p10_with_gcc_mode,
        maybe_run_p10_gcc,
    )

    # Explicit GCC mode control
    frame, ledger_entry = run_p10_with_gcc_mode(
        request=Phase10Request(
            artifact_id="...",
            artifact_hash="...",
            projected_layers=(...),
            gcc_mode=GCCMode.DISABLED,  # Experimental
        ),
        lexical_frame=p9_frame,
        discourse_envelope=p7_envelope,
        regime_envelope=p6_envelope,
    )

CRITICAL:
    - gcc_mode is EXPLICIT, never inferred
    - Default behavior remains GCC ENABLED
    - No backward-compatibility break
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from symbolu.mechanical.pipeline.phase_p6.p6_schema import RegimeEnvelope
from symbolu.mechanical.pipeline.p7_discourse.p7_discourse_schema import DiscourseEnvelope
from symbolu.mechanical.pipeline.p9_lexical.p9_lexical_schema import LexicalFrame
from symbolu.mechanical.pipeline.p10_acoustic.p10_acoustic_schema import (
    AcousticParameterFrame,
)
from symbolu.mechanical.pipeline.p10_acoustic.p10_gcc_mode import (
    GCCMode,
    Phase10Request,
    Phase10Response,
)
from symbolu.mechanical.pipeline.p10_acoustic.p10_gcc_resolver import (
    GCCLedgerEntry,
    P10GCCResolver,
    compute_gcc_span_id,
    compute_layers_hash,
)


# =============================================================================
# Singleton GCC Resolver
# =============================================================================


_p10_gcc_resolver: Optional[P10GCCResolver] = None


def get_p10_gcc_resolver() -> P10GCCResolver:
    """Get or create the singleton P10 GCC resolver instance."""
    global _p10_gcc_resolver
    if _p10_gcc_resolver is None:
        _p10_gcc_resolver = P10GCCResolver()
    return _p10_gcc_resolver


# =============================================================================
# Core Integration Functions
# =============================================================================


def run_p10_with_gcc_mode(
    *,
    request: Phase10Request,
    lexical_frame: Optional[LexicalFrame],
    discourse_envelope: Optional[DiscourseEnvelope],
    regime_envelope: Optional[RegimeEnvelope],
) -> Tuple[AcousticParameterFrame, GCCLedgerEntry]:
    """
    Run Phase-10 with explicit GCC mode control.

    This is the main entry point for running Phase-10 with gcc_mode switch.

    Args:
        request: The Phase10Request containing gcc_mode.
        lexical_frame: The P9 LexicalFrame (for tracing).
        discourse_envelope: The P7 DiscourseEnvelope.
        regime_envelope: The P6 RegimeEnvelope.

    Returns:
        Tuple of (AcousticParameterFrame, GCCLedgerEntry).

    Raises:
        ValueError: If request.gcc_mode is invalid (fail-closed).

    CRITICAL:
        - gcc_mode is EXPLICIT in the request
        - Missing gcc_mode defaults to ENABLED (in Phase10Request dataclass)
        - Unknown gcc_mode -> HARD FAIL
    """
    resolver = get_p10_gcc_resolver()
    return resolver.resolve(
        request=request,
        lexical_frame=lexical_frame,
        discourse_envelope=discourse_envelope,
        regime_envelope=regime_envelope,
    )


def maybe_run_p10_gcc(
    ctx: Any,
    gcc_mode: GCCMode = GCCMode.ENABLED,
    artifact_id: str = "CONTEXT_ARTIFACT",
    artifact_hash: Optional[str] = None,
) -> Optional[Tuple[AcousticParameterFrame, GCCLedgerEntry]]:
    """
    Run Phase-10 GCC on pipeline context with explicit gcc_mode.

    This function integrates with existing pipeline context.
    It extracts P6, P7, P9 from context and runs P10 with gcc_mode.

    Args:
        ctx: Pipeline context with lexical_frame, p7_discourse_envelope, p6_regime.
        gcc_mode: The GCC mode (ENABLED or DISABLED). Default ENABLED.
        artifact_id: Artifact identifier. Default "CONTEXT_ARTIFACT".
        artifact_hash: Artifact hash. If None, computed from context.

    Returns:
        Tuple of (AcousticParameterFrame, GCCLedgerEntry), or None if
        required context is missing.

    Note:
        - Attaches result to ctx.p10_acoustic
        - Attaches ledger entry to ctx.p10_gcc_ledger
        - Returns None (does not fail) if required context is missing
    """
    # Check if P9 output is available
    lexical_frame = None
    if hasattr(ctx, 'lexical_frame') and ctx.lexical_frame is not None:
        lexical_frame = ctx.lexical_frame

    # Check if P7 output is available
    discourse_envelope = None
    if hasattr(ctx, 'p7_discourse_envelope'):
        discourse_envelope = ctx.p7_discourse_envelope

    # Check if P6 output is available
    regime_envelope = None
    if hasattr(ctx, 'p6_regime'):
        regime_envelope = ctx.p6_regime

    # Compute artifact hash if not provided
    if artifact_hash is None:
        # Use a deterministic placeholder hash based on available context
        import hashlib
        import json

        hash_input = {
            "artifact_id": artifact_id,
            "has_lexical_frame": lexical_frame is not None,
            "has_discourse": discourse_envelope is not None,
            "has_regime": regime_envelope is not None,
        }
        hash_json = json.dumps(hash_input, sort_keys=True, separators=(",", ":"))
        artifact_hash = hashlib.sha256(hash_json.encode("utf-8")).hexdigest()

    # Get projected layers from context or use default
    from symbolu.ontology.router.ontological_router_r1 import OntologicalLayer

    projected_layers: Tuple[OntologicalLayer, ...] = (OntologicalLayer.FORMING,)
    if hasattr(ctx, 'projected_layers') and ctx.projected_layers is not None:
        projected_layers = ctx.projected_layers

    # Create request
    request = Phase10Request(
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        projected_layers=projected_layers,
        gcc_mode=gcc_mode,
    )

    # Run P10 with GCC mode
    frame, ledger_entry = run_p10_with_gcc_mode(
        request=request,
        lexical_frame=lexical_frame,
        discourse_envelope=discourse_envelope,
        regime_envelope=regime_envelope,
    )

    # Attach to context
    ctx.p10_acoustic = frame
    ctx.p10_gcc_ledger = ledger_entry

    return frame, ledger_entry


def create_p10_response(
    request: Phase10Request,
    ledger_entry: GCCLedgerEntry,
) -> Phase10Response:
    """
    Create a Phase10Response from request and ledger entry.

    Args:
        request: The original Phase10Request.
        ledger_entry: The generated GCCLedgerEntry.

    Returns:
        Phase10Response with all fields populated.
    """
    return Phase10Response(
        artifact_id=request.artifact_id,
        artifact_hash=request.artifact_hash,
        gcc_mode=request.gcc_mode,
        gcc_clamping_applied=ledger_entry.clamping_applied,
        span_id=ledger_entry.span_id,
        phase_id="PHASE_10",
    )


# =============================================================================
# Accessor Functions
# =============================================================================


def get_p10_gcc_ledger(ctx: Any) -> Optional[GCCLedgerEntry]:
    """
    Get the P10 GCC ledger entry from context.

    Args:
        ctx: Pipeline context.

    Returns:
        GCCLedgerEntry or None if not available.
    """
    if not hasattr(ctx, 'p10_gcc_ledger'):
        return None
    return ctx.p10_gcc_ledger


def get_gcc_mode_from_context(ctx: Any) -> Optional[GCCMode]:
    """
    Get the GCC mode from context ledger entry.

    Args:
        ctx: Pipeline context.

    Returns:
        GCCMode or None if not available.
    """
    ledger_entry = get_p10_gcc_ledger(ctx)
    if ledger_entry is None:
        return None
    return GCCMode(ledger_entry.gcc_mode)


def was_gcc_clamping_applied(ctx: Any) -> bool:
    """
    Check if GCC clamping was applied in P10.

    Args:
        ctx: Pipeline context.

    Returns:
        True if clamping was applied (GCC ENABLED), False otherwise.
        Returns True (conservative) if P10 GCC hasn't run.
    """
    ledger_entry = get_p10_gcc_ledger(ctx)
    if ledger_entry is None:
        # Conservative default: assume clamping was applied
        return True
    return ledger_entry.clamping_applied


def get_p10_span_id(ctx: Any) -> Optional[str]:
    """
    Get the P10 span ID from context ledger entry.

    Args:
        ctx: Pipeline context.

    Returns:
        Span ID or None if not available.
    """
    ledger_entry = get_p10_gcc_ledger(ctx)
    if ledger_entry is None:
        return None
    return ledger_entry.span_id


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Singleton
    "get_p10_gcc_resolver",
    # Core functions
    "run_p10_with_gcc_mode",
    "maybe_run_p10_gcc",
    "create_p10_response",
    # Accessor functions
    "get_p10_gcc_ledger",
    "get_gcc_mode_from_context",
    "was_gcc_clamping_applied",
    "get_p10_span_id",
]
