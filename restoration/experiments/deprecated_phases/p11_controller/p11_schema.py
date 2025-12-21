"""
P11 Controller Schema - Phase-11 OPEN/GOVERNED Switch Types
=============================================================

This module defines the data contracts for the Phase-11 Controller,
the first controlled generative surface in Symbol-U.

The Phase-11 Controller provides:
- Fully wired execution pipeline
- Full observability via ledger recording
- Optional enforcement via RenderMode
- Impossible for "unsafe" generation to leak silently

RenderMode Controls:
    OPEN:
        - For experimentation, marketing, exploration
        - Output is released even if verifier fails
        - Verifier STILL RUNS (always observable)
        - Ledger STILL RECORDS (always auditable)

    GOVERNED:
        - For production, compliance, safety
        - Output is BLOCKED if verifier fails
        - Fail-closed behavior
        - No unsafe output can escape

Hard Safety Boundaries (ALWAYS ENFORCED regardless of RenderMode):
    - NO randomness
    - NO ML/NLP imports
    - NO time/datetime
    - NO mutation of inputs
    - Same input -> byte-identical output
    - Verifier always executes
    - Ledger always records
    - GOVERNED mode is fail-closed

CRITICAL INVARIANTS:
    - render_mode is explicit, never inferred
    - Default behavior is GOVERNED (fail-closed)
    - Unknown render_mode -> HARD FAIL
    - OPEN without explicit request -> NOT POSSIBLE
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Literal, Tuple


# =============================================================================
# Version Constant
# =============================================================================

P11_CONTROLLER_VERSION = "1.0.0"


# =============================================================================
# RenderMode Enum
# =============================================================================


class RenderMode(str, Enum):
    """
    Render mode for Phase-11 Controller output gating.

    Values:
        OPEN: Experimentation mode - output released regardless of verifier
        GOVERNED: Production mode - output blocked if verifier fails

    CRITICAL:
        - This is EXPLICIT, never inferred
        - OPEN requires explicit request
        - Unknown values -> HARD FAIL
        - Both modes execute the SAME internal pipeline
        - Only the final commit rule differs
    """
    OPEN = "open"          # experimentation, marketing, exploration
    GOVERNED = "governed"  # production, compliance, safety


# =============================================================================
# Phase10Result Opaque Type
# =============================================================================


@dataclass(frozen=True)
class Phase10Result:
    """
    Opaque result from Phase-10 to be passed into Phase-11.

    This is an opaque container that Phase-11 does not interpret.
    Phase-11 only extracts allowed VC facts (VC-1 through VC-5).

    Attributes:
        artifact_hash: The artifact hash from Phase-10 (64-char hex)
        vc_facts: Tuple of allowed VC fact identifiers
        acoustic_regime: The acoustic regime string from P10
        source_data: Opaque data blob for VC extraction

    Invariants:
        - All fields immutable after construction
        - artifact_hash must be 64 hex characters
        - vc_facts must only contain VC-1 through VC-5
    """
    artifact_hash: str
    vc_facts: Tuple[str, ...]
    acoustic_regime: str
    source_data: Dict[str, Any]

    def __post_init__(self) -> None:
        """Validate Phase10Result invariants."""
        # Validate artifact_hash
        if not isinstance(self.artifact_hash, str):
            raise ValueError(
                f"Phase10Result.artifact_hash must be str, "
                f"got {type(self.artifact_hash).__name__}"
            )
        if len(self.artifact_hash) != 64:
            raise ValueError(
                f"Phase10Result.artifact_hash must be 64 hex chars, "
                f"got {len(self.artifact_hash)} chars"
            )
        try:
            int(self.artifact_hash, 16)
        except ValueError:
            raise ValueError(
                "Phase10Result.artifact_hash must contain only hex characters"
            )

        # Validate vc_facts
        if not isinstance(self.vc_facts, tuple):
            raise ValueError(
                f"Phase10Result.vc_facts must be tuple, "
                f"got {type(self.vc_facts).__name__}"
            )
        allowed_vc_facts = {"VC-1", "VC-2", "VC-3", "VC-4", "VC-5"}
        for fact in self.vc_facts:
            if not isinstance(fact, str):
                raise ValueError(
                    f"Phase10Result.vc_facts elements must be str, "
                    f"got {type(fact).__name__}"
                )
            if fact not in allowed_vc_facts:
                raise ValueError(
                    f"Phase10Result.vc_facts contains invalid fact '{fact}'. "
                    f"Only VC-1 through VC-5 are allowed."
                )

        # Validate acoustic_regime
        if not isinstance(self.acoustic_regime, str) or not self.acoustic_regime.strip():
            raise ValueError(
                "Phase10Result.acoustic_regime must be a non-empty string"
            )

        # Validate source_data
        if not isinstance(self.source_data, dict):
            raise ValueError(
                f"Phase10Result.source_data must be dict, "
                f"got {type(self.source_data).__name__}"
            )


# =============================================================================
# Phase11Request (Frozen)
# =============================================================================


@dataclass(frozen=True)
class Phase11Request:
    """
    Phase-11 input contract for controlled generative rendering.

    This is a FROZEN dataclass - immutable after construction.

    Attributes:
        artifact_id: Opaque artifact identifier (non-empty string)
        artifact_hash: Precomputed artifact hash (64-char hex string)
        phase10_result: Opaque Phase10Result from upstream
        render_mode: OPEN (experimentation) or GOVERNED (production)
        explicit_absolving_opt_in: Explicit opt-in for ABSOLVING (unchanged behavior)

    Rules:
        - render_mode is EXPLICIT, never inferred
        - Default behavior is GOVERNED (fail-closed)
        - Missing artifact_hash -> HARD FAIL
        - Invalid render_mode -> HARD FAIL

    Invariants:
        - All fields immutable after construction
        - artifact_hash must be 64 hex characters
        - phase10_result must be a valid Phase10Result
        - render_mode must be a valid RenderMode enum value
    """
    artifact_id: str
    artifact_hash: str
    phase10_result: Phase10Result
    render_mode: RenderMode
    explicit_absolving_opt_in: bool = False

    def __post_init__(self) -> None:
        """Validate Phase11Request invariants (fail-closed)."""
        # Validate artifact_id
        if not isinstance(self.artifact_id, str):
            raise ValueError(
                f"Phase11Request.artifact_id must be str, "
                f"got {type(self.artifact_id).__name__}"
            )
        if len(self.artifact_id) == 0:
            raise ValueError("Phase11Request.artifact_id must be non-empty")

        # Validate artifact_hash (must be 64 hex chars)
        if not isinstance(self.artifact_hash, str):
            raise ValueError(
                f"Phase11Request.artifact_hash must be str, "
                f"got {type(self.artifact_hash).__name__}"
            )
        if len(self.artifact_hash) != 64:
            raise ValueError(
                f"Phase11Request.artifact_hash must be 64 hex chars, "
                f"got {len(self.artifact_hash)} chars"
            )
        try:
            int(self.artifact_hash, 16)
        except ValueError:
            raise ValueError(
                "Phase11Request.artifact_hash must contain only hex characters"
            )

        # Validate phase10_result
        if not isinstance(self.phase10_result, Phase10Result):
            raise ValueError(
                f"Phase11Request.phase10_result must be Phase10Result, "
                f"got {type(self.phase10_result).__name__}"
            )

        # Validate render_mode - HARD FAIL on unknown
        if not isinstance(self.render_mode, RenderMode):
            raise ValueError(
                f"Phase11Request.render_mode must be RenderMode enum, "
                f"got {type(self.render_mode).__name__}"
            )
        # Explicit check for valid enum values (fail-closed)
        if self.render_mode not in (RenderMode.OPEN, RenderMode.GOVERNED):
            raise ValueError(
                f"Phase11Request.render_mode must be OPEN or GOVERNED, "
                f"got {self.render_mode}"
            )

        # Validate explicit_absolving_opt_in
        if not isinstance(self.explicit_absolving_opt_in, bool):
            raise ValueError(
                f"Phase11Request.explicit_absolving_opt_in must be bool, "
                f"got {type(self.explicit_absolving_opt_in).__name__}"
            )


# =============================================================================
# Phase11Response (Frozen)
# =============================================================================


@dataclass(frozen=True)
class Phase11Response:
    """
    Phase-11 output contract for controlled generative rendering.

    This is a FROZEN dataclass - immutable after construction.

    Attributes:
        output_text: The rendered output text, or "RENDER_BLOCKED" if blocked
        verifier_passed: Whether the verifier check passed
        verifier_report_hash: Hash of the verifier report (16-char hex)
        candidate_output_hash: Hash of the candidate output (16-char hex)
        mode_applied: The RenderMode that was applied
        ledger_span_id: Deterministic span ID for ledger recording (hash-only)

    Invariants:
        - All fields immutable after construction
        - If mode_applied is GOVERNED and verifier_passed is False,
          output_text MUST be "RENDER_BLOCKED"
        - Hashes are 16-char hex strings
        - ledger_span_id is deterministically derived (no timestamps)
    """
    output_text: str | Literal["RENDER_BLOCKED"]
    verifier_passed: bool
    verifier_report_hash: str
    candidate_output_hash: str
    mode_applied: RenderMode
    ledger_span_id: str

    def __post_init__(self) -> None:
        """Validate Phase11Response invariants (fail-closed)."""
        # Validate output_text
        if not isinstance(self.output_text, str):
            raise ValueError(
                f"Phase11Response.output_text must be str, "
                f"got {type(self.output_text).__name__}"
            )

        # Validate verifier_passed
        if not isinstance(self.verifier_passed, bool):
            raise ValueError(
                f"Phase11Response.verifier_passed must be bool, "
                f"got {type(self.verifier_passed).__name__}"
            )

        # Validate verifier_report_hash
        if not isinstance(self.verifier_report_hash, str):
            raise ValueError(
                f"Phase11Response.verifier_report_hash must be str, "
                f"got {type(self.verifier_report_hash).__name__}"
            )
        if len(self.verifier_report_hash) != 16:
            raise ValueError(
                f"Phase11Response.verifier_report_hash must be 16 hex chars, "
                f"got {len(self.verifier_report_hash)} chars"
            )
        try:
            int(self.verifier_report_hash, 16)
        except ValueError:
            raise ValueError(
                "Phase11Response.verifier_report_hash must contain only hex characters"
            )

        # Validate candidate_output_hash
        if not isinstance(self.candidate_output_hash, str):
            raise ValueError(
                f"Phase11Response.candidate_output_hash must be str, "
                f"got {type(self.candidate_output_hash).__name__}"
            )
        if len(self.candidate_output_hash) != 16:
            raise ValueError(
                f"Phase11Response.candidate_output_hash must be 16 hex chars, "
                f"got {len(self.candidate_output_hash)} chars"
            )
        try:
            int(self.candidate_output_hash, 16)
        except ValueError:
            raise ValueError(
                "Phase11Response.candidate_output_hash must contain only hex characters"
            )

        # Validate mode_applied
        if not isinstance(self.mode_applied, RenderMode):
            raise ValueError(
                f"Phase11Response.mode_applied must be RenderMode enum, "
                f"got {type(self.mode_applied).__name__}"
            )

        # Validate ledger_span_id
        if not isinstance(self.ledger_span_id, str):
            raise ValueError(
                f"Phase11Response.ledger_span_id must be str, "
                f"got {type(self.ledger_span_id).__name__}"
            )
        if len(self.ledger_span_id) == 0:
            raise ValueError("Phase11Response.ledger_span_id must be non-empty")

        # CRITICAL INVARIANT: GOVERNED mode with failed verifier -> RENDER_BLOCKED
        if (self.mode_applied == RenderMode.GOVERNED and
                not self.verifier_passed and
                self.output_text != "RENDER_BLOCKED"):
            raise ValueError(
                "Phase11Response: GOVERNED mode with verifier_passed=False "
                "MUST have output_text='RENDER_BLOCKED'"
            )

    def is_blocked(self) -> bool:
        """Check if output was blocked."""
        return self.output_text == "RENDER_BLOCKED"

    def was_governed(self) -> bool:
        """Check if GOVERNED mode was applied."""
        return self.mode_applied == RenderMode.GOVERNED


# =============================================================================
# Validation Helpers
# =============================================================================


def validate_render_mode(render_mode: RenderMode) -> None:
    """
    Validate that render_mode is a valid RenderMode enum value.

    This is a FAIL-CLOSED validation. Unknown values cause hard failure.

    Args:
        render_mode: The render mode to validate.

    Raises:
        ValueError: If render_mode is not a valid RenderMode enum value.
    """
    if not isinstance(render_mode, RenderMode):
        raise ValueError(
            f"render_mode must be RenderMode enum, got {type(render_mode).__name__}"
        )
    if render_mode not in (RenderMode.OPEN, RenderMode.GOVERNED):
        raise ValueError(
            f"render_mode must be OPEN or GOVERNED, got {render_mode}"
        )


def is_open_mode(render_mode: RenderMode) -> bool:
    """
    Check if render mode is OPEN.

    Args:
        render_mode: The render mode to check.

    Returns:
        True if OPEN, False if GOVERNED.

    Raises:
        ValueError: If render_mode is not a valid RenderMode enum value.
    """
    validate_render_mode(render_mode)
    return render_mode == RenderMode.OPEN


def is_governed_mode(render_mode: RenderMode) -> bool:
    """
    Check if render mode is GOVERNED (production/safety mode).

    Args:
        render_mode: The render mode to check.

    Returns:
        True if GOVERNED, False if OPEN.

    Raises:
        ValueError: If render_mode is not a valid RenderMode enum value.
    """
    validate_render_mode(render_mode)
    return render_mode == RenderMode.GOVERNED


def compute_hash(data: str) -> str:
    """
    Compute a deterministic 16-char hex hash from string data.

    Args:
        data: The string data to hash.

    Returns:
        16-character hex hash string.
    """
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "P11_CONTROLLER_VERSION",
    # Enums
    "RenderMode",
    # Dataclasses
    "Phase10Result",
    "Phase11Request",
    "Phase11Response",
    # Validation helpers
    "validate_render_mode",
    "is_open_mode",
    "is_governed_mode",
    "compute_hash",
]
