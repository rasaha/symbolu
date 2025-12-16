"""
P10 GCC Mode - Global Constraint Clamp Control for Phase-10
============================================================

This module defines the GCC (Global Constraint Clamp) mode switch for Phase-10
consequence propagation. This is an experimental aperture to study generative
downstream effects - NOT a relaxation of system safety.

GCC Mode Controls:
    ENABLED (default):
        - Apply all consequence bounds
        - Enforce collapse thresholds
        - Block escalation
        - Bit-identical to current Phase-10 behavior

    DISABLED (experimental):
        - Skip consequence clamping ONLY
        - Still enforce: determinism, structural validity, ledger recording
        - Consequences may propagate freely but remain structural
        - NO semantics, NO intent, NO interpretation

Hard Safety Boundaries (ALWAYS ENFORCED regardless of GCCMode):
    - NO mutation of Phase 1b-9 artifacts
    - NO new routing
    - NO new layer access
    - NO ABSOLVING access
    - NO generation
    - NO probabilistic logic
    - NO heuristics
    - NO inference

This switch only affects consequence attenuation, NOT authority.

CRITICAL INVARIANTS:
    - gcc_mode is explicit, never inferred
    - Default behavior remains GCC ENABLED
    - No backward-compatibility break
    - Unknown gcc_mode -> HARD FAIL
    - DISABLED without explicit request -> NOT POSSIBLE
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from symbolu.ontology.router.ontological_router_r1 import OntologicalLayer


# =============================================================================
# GCC Mode Enum
# =============================================================================


class GCCMode(str, Enum):
    """
    Global Constraint Clamp mode for Phase-10 consequence propagation.

    Values:
        ENABLED: Default behavior - apply all GCC checks
        DISABLED: Experimental - allow consequence flow without clamp

    CRITICAL:
        - This is EXPLICIT, never inferred
        - DISABLED requires explicit request
        - Unknown values -> HARD FAIL
    """
    ENABLED = "ENABLED"    # Default (current behavior)
    DISABLED = "DISABLED"  # Experimental: allow consequence flow without clamp


# =============================================================================
# Phase-10 Input Contract
# =============================================================================


@dataclass(frozen=True)
class Phase10Request:
    """
    Phase-10 input contract for consequence propagation.

    This is a FROZEN dataclass - immutable after construction.

    Attributes:
        artifact_id: Opaque artifact identifier (non-empty string)
        artifact_hash: Precomputed artifact hash (64-char hex string)
        projected_layers: Tuple of ontological layers for this artifact
        gcc_mode: GCC mode - ENABLED (default) or DISABLED (experimental)

    Rules:
        - gcc_mode is EXPLICIT, never inferred
        - Default behavior remains GCC ENABLED
        - Missing artifact_hash -> HARD FAIL
        - Invalid gcc_mode -> HARD FAIL

    Invariants:
        - All fields immutable after construction
        - artifact_hash must be 64 hex characters
        - projected_layers must be a tuple of OntologicalLayer
        - gcc_mode must be a valid GCCMode enum value
    """
    artifact_id: str
    artifact_hash: str
    projected_layers: Tuple[OntologicalLayer, ...]
    gcc_mode: GCCMode = GCCMode.ENABLED

    def __post_init__(self) -> None:
        """Validate Phase10Request invariants (fail-closed)."""
        # Validate artifact_id
        if not isinstance(self.artifact_id, str):
            raise ValueError(
                f"Phase10Request.artifact_id must be str, "
                f"got {type(self.artifact_id).__name__}"
            )
        if len(self.artifact_id) == 0:
            raise ValueError("Phase10Request.artifact_id must be non-empty")

        # Validate artifact_hash (must be 64 hex chars)
        if not isinstance(self.artifact_hash, str):
            raise ValueError(
                f"Phase10Request.artifact_hash must be str, "
                f"got {type(self.artifact_hash).__name__}"
            )
        if len(self.artifact_hash) != 64:
            raise ValueError(
                f"Phase10Request.artifact_hash must be 64 hex chars, "
                f"got {len(self.artifact_hash)} chars"
            )
        # Validate hex characters
        try:
            int(self.artifact_hash, 16)
        except ValueError:
            raise ValueError(
                "Phase10Request.artifact_hash must contain only hex characters"
            )

        # Validate projected_layers
        if not isinstance(self.projected_layers, tuple):
            raise ValueError(
                f"Phase10Request.projected_layers must be tuple, "
                f"got {type(self.projected_layers).__name__}"
            )
        for i, layer in enumerate(self.projected_layers):
            if not isinstance(layer, OntologicalLayer):
                raise ValueError(
                    f"Phase10Request.projected_layers[{i}] must be OntologicalLayer, "
                    f"got {type(layer).__name__}"
                )

        # Validate gcc_mode - HARD FAIL on unknown
        if not isinstance(self.gcc_mode, GCCMode):
            raise ValueError(
                f"Phase10Request.gcc_mode must be GCCMode enum, "
                f"got {type(self.gcc_mode).__name__}"
            )
        # Explicit check for valid enum values (fail-closed)
        if self.gcc_mode not in (GCCMode.ENABLED, GCCMode.DISABLED):
            raise ValueError(
                f"Phase10Request.gcc_mode must be ENABLED or DISABLED, "
                f"got {self.gcc_mode}"
            )


# =============================================================================
# Phase-10 Response Contract
# =============================================================================


@dataclass(frozen=True)
class Phase10Response:
    """
    Phase-10 output contract for consequence propagation result.

    This is a FROZEN dataclass - immutable after construction.

    Attributes:
        artifact_id: Opaque artifact identifier (from request)
        artifact_hash: Precomputed artifact hash (from request)
        gcc_mode: The GCC mode that was applied
        gcc_clamping_applied: Whether GCC clamping was applied
        span_id: Deterministic span ID for ledger recording
        phase_id: Always "PHASE_10"

    Invariants:
        - All fields immutable after construction
        - gcc_clamping_applied is True IFF gcc_mode == ENABLED
        - span_id is deterministically derived
    """
    artifact_id: str
    artifact_hash: str
    gcc_mode: GCCMode
    gcc_clamping_applied: bool
    span_id: str
    phase_id: str = "PHASE_10"

    def __post_init__(self) -> None:
        """Validate Phase10Response invariants (fail-closed)."""
        # Validate artifact_id
        if not isinstance(self.artifact_id, str) or len(self.artifact_id) == 0:
            raise ValueError("Phase10Response.artifact_id must be non-empty string")

        # Validate artifact_hash
        if not isinstance(self.artifact_hash, str) or len(self.artifact_hash) != 64:
            raise ValueError("Phase10Response.artifact_hash must be 64 hex chars")

        # Validate gcc_mode
        if not isinstance(self.gcc_mode, GCCMode):
            raise ValueError("Phase10Response.gcc_mode must be GCCMode enum")

        # Validate gcc_clamping_applied consistency
        if not isinstance(self.gcc_clamping_applied, bool):
            raise ValueError("Phase10Response.gcc_clamping_applied must be bool")

        # Invariant: gcc_clamping_applied IFF gcc_mode == ENABLED
        expected_clamping = (self.gcc_mode == GCCMode.ENABLED)
        if self.gcc_clamping_applied != expected_clamping:
            raise ValueError(
                f"Phase10Response.gcc_clamping_applied must be {expected_clamping} "
                f"when gcc_mode is {self.gcc_mode.value}"
            )

        # Validate span_id
        if not isinstance(self.span_id, str) or len(self.span_id) == 0:
            raise ValueError("Phase10Response.span_id must be non-empty string")

        # Validate phase_id
        if self.phase_id != "PHASE_10":
            raise ValueError("Phase10Response.phase_id must be 'PHASE_10'")


# =============================================================================
# GCC Mode Validation Helpers
# =============================================================================


def validate_gcc_mode(gcc_mode: GCCMode) -> None:
    """
    Validate that gcc_mode is a valid GCCMode enum value.

    This is a FAIL-CLOSED validation. Unknown values cause hard failure.

    Args:
        gcc_mode: The GCC mode to validate.

    Raises:
        ValueError: If gcc_mode is not a valid GCCMode enum value.
    """
    if not isinstance(gcc_mode, GCCMode):
        raise ValueError(
            f"gcc_mode must be GCCMode enum, got {type(gcc_mode).__name__}"
        )
    if gcc_mode not in (GCCMode.ENABLED, GCCMode.DISABLED):
        raise ValueError(
            f"gcc_mode must be ENABLED or DISABLED, got {gcc_mode}"
        )


def is_gcc_enabled(gcc_mode: GCCMode) -> bool:
    """
    Check if GCC is enabled.

    Args:
        gcc_mode: The GCC mode to check.

    Returns:
        True if GCC is ENABLED, False if DISABLED.

    Raises:
        ValueError: If gcc_mode is not a valid GCCMode enum value.
    """
    validate_gcc_mode(gcc_mode)
    return gcc_mode == GCCMode.ENABLED


def is_gcc_disabled(gcc_mode: GCCMode) -> bool:
    """
    Check if GCC is disabled (experimental mode).

    Args:
        gcc_mode: The GCC mode to check.

    Returns:
        True if GCC is DISABLED, False if ENABLED.

    Raises:
        ValueError: If gcc_mode is not a valid GCCMode enum value.
    """
    validate_gcc_mode(gcc_mode)
    return gcc_mode == GCCMode.DISABLED


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Enums
    "GCCMode",
    # Dataclasses
    "Phase10Request",
    "Phase10Response",
    # Validation helpers
    "validate_gcc_mode",
    "is_gcc_enabled",
    "is_gcc_disabled",
]
