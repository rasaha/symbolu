"""
P10 PPV Envelope - Phase-10 Result with Optional PPV Attachment
================================================================

This module provides a wrapper (envelope) for Phase-10 results that can
optionally carry a PPV (Phonemic Propensity Vector).

Design Principles:
    - PPV is OPTIONAL attachment, not required
    - Original Phase-10 hashes are PRESERVED
    - Envelope adds PPV metadata without changing existing contracts
    - If PPV absent, envelope behaves exactly like raw Phase10Result

Hard Constraints:
    - NO change to existing Phase-10 hashes unless versioned
    - PPV attachment is purely additive
    - Fail-closed if PPV invalid
    - Deterministic envelope hash includes PPV presence

GOVERNED Mode Policy:
    - PPV may exist in GOVERNED mode
    - PPV must only influence output through predefined template slots
    - PPV never as text generation, only numeric metrics
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from symbolu_core.ppv.ppv_contract_v1 import PPVVector, validate_ppv_invariants_v1
from symbolu_core.mechanical.pipeline.p11_controller.p11_schema import Phase10Result


# =============================================================================
# Version Constant
# =============================================================================

PPV_ENVELOPE_VERSION = "1.0.0"


# =============================================================================
# Phase-10 PPV Envelope
# =============================================================================


@dataclass(frozen=True)
class Phase10Envelope:
    """
    Envelope wrapping Phase-10 result with optional PPV attachment.

    This envelope provides:
        - Original Phase10Result unchanged
        - Optional PPV attachment
        - Deterministic envelope_hash that accounts for PPV presence
        - Backward-compatible (envelope with no PPV behaves like raw result)

    Attributes:
        phase10_result: The original Phase10Result (unchanged)
        ppv: Optional PPVVector attachment
        envelope_hash: Deterministic hash of envelope (includes PPV if present)
        envelope_version: Version of the envelope format

    Invariants:
        - phase10_result.artifact_hash is NEVER modified
        - If ppv present, ppv must pass validate_ppv_invariants_v1
        - envelope_hash is deterministic over (phase10_result, ppv)
    """
    phase10_result: Phase10Result
    ppv: Optional[PPVVector]
    envelope_hash: str
    envelope_version: str = PPV_ENVELOPE_VERSION

    def __post_init__(self) -> None:
        """Validate Phase10Envelope invariants."""
        # Validate phase10_result
        if not isinstance(self.phase10_result, Phase10Result):
            raise ValueError(
                f"Phase10Envelope.phase10_result must be Phase10Result, "
                f"got {type(self.phase10_result).__name__}"
            )

        # Validate ppv (if present)
        if self.ppv is not None:
            if not isinstance(self.ppv, PPVVector):
                raise ValueError(
                    f"Phase10Envelope.ppv must be PPVVector or None, "
                    f"got {type(self.ppv).__name__}"
                )
            # Validate PPV invariants
            try:
                validate_ppv_invariants_v1(self.ppv)
            except ValueError as e:
                raise ValueError(f"Phase10Envelope.ppv invalid: {e}")

        # Validate envelope_hash
        if not isinstance(self.envelope_hash, str):
            raise ValueError(
                f"Phase10Envelope.envelope_hash must be str, "
                f"got {type(self.envelope_hash).__name__}"
            )
        if len(self.envelope_hash) != 64:
            raise ValueError(
                f"Phase10Envelope.envelope_hash must be 64 hex chars, "
                f"got {len(self.envelope_hash)} chars"
            )
        try:
            int(self.envelope_hash, 16)
        except ValueError:
            raise ValueError(
                "Phase10Envelope.envelope_hash must contain only hex characters"
            )

        # Verify envelope_hash is correct
        expected_hash = _compute_envelope_hash(self.phase10_result, self.ppv)
        if self.envelope_hash != expected_hash:
            raise ValueError(
                f"Phase10Envelope.envelope_hash mismatch: "
                f"expected {expected_hash}, got {self.envelope_hash}"
            )

    @property
    def has_ppv(self) -> bool:
        """Check if PPV is attached."""
        return self.ppv is not None

    @property
    def artifact_hash(self) -> str:
        """Get the original artifact hash (unchanged)."""
        return self.phase10_result.artifact_hash

    @property
    def vc_facts(self) -> Tuple[str, ...]:
        """Get VC facts from the Phase10Result."""
        return self.phase10_result.vc_facts

    @property
    def acoustic_regime(self) -> str:
        """Get acoustic regime from the Phase10Result."""
        return self.phase10_result.acoustic_regime

    @property
    def source_data(self) -> Dict[str, Any]:
        """Get source data from the Phase10Result."""
        return self.phase10_result.source_data

    @property
    def ppv_hash(self) -> Optional[str]:
        """Get PPV hash if PPV is attached."""
        return self.ppv.ppv_hash if self.ppv else None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "phase10_result": {
                "artifact_hash": self.phase10_result.artifact_hash,
                "vc_facts": self.phase10_result.vc_facts,
                "acoustic_regime": self.phase10_result.acoustic_regime,
                "source_data": self.phase10_result.source_data,
            },
            "ppv": self.ppv.to_dict() if self.ppv else None,
            "envelope_hash": self.envelope_hash,
            "envelope_version": self.envelope_version,
        }
        return result


# =============================================================================
# Envelope Hash Computation
# =============================================================================


def _compute_envelope_hash(
    phase10_result: Phase10Result,
    ppv: Optional[PPVVector],
) -> str:
    """
    Compute deterministic envelope hash.

    The envelope hash includes:
        - Phase10Result.artifact_hash
        - PPV.ppv_hash (if present, else "NO_PPV")

    Args:
        phase10_result: The Phase10Result.
        ppv: Optional PPVVector.

    Returns:
        64-char hex envelope hash.
    """
    ppv_component = ppv.ppv_hash if ppv else "NO_PPV"
    hash_input = f"envelope:{phase10_result.artifact_hash}|ppv:{ppv_component}"
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()


# =============================================================================
# Envelope Factory
# =============================================================================


def create_phase10_envelope(
    phase10_result: Phase10Result,
    ppv: Optional[PPVVector] = None,
) -> Phase10Envelope:
    """
    Create a Phase10Envelope with optional PPV.

    This is the canonical factory for creating Phase10Envelope instances.

    Args:
        phase10_result: The Phase10Result to wrap.
        ppv: Optional PPVVector to attach.

    Returns:
        Valid Phase10Envelope instance.

    Raises:
        ValueError: If inputs are invalid.
    """
    # Compute envelope hash
    envelope_hash = _compute_envelope_hash(phase10_result, ppv)

    return Phase10Envelope(
        phase10_result=phase10_result,
        ppv=ppv,
        envelope_hash=envelope_hash,
    )


def wrap_with_ppv(
    phase10_result: Phase10Result,
    context: Optional[Dict[str, Any]] = None,
) -> Phase10Envelope:
    """
    Wrap Phase10Result with PPV if possible.

    This function attempts to build PPV from the Phase10Result and context,
    then wraps the result in an envelope.

    If PPV cannot be built (missing data), returns envelope without PPV.

    Args:
        phase10_result: The Phase10Result to wrap.
        context: Optional additional context for PPV building.

    Returns:
        Phase10Envelope with PPV if possible, without PPV otherwise.
    """
    from symbolu_core.ppv.ppv_builder_v1 import build_ppv_for_artifact

    # Attempt to build PPV
    ppv = build_ppv_for_artifact(phase10_result, context=context)

    # Create envelope (with or without PPV)
    return create_phase10_envelope(phase10_result, ppv)


# =============================================================================
# PPV Extraction Helpers
# =============================================================================


def extract_ppv_metrics(envelope: Phase10Envelope) -> Dict[str, Any]:
    """
    Extract PPV metrics from envelope for template use.

    Returns a dictionary of numeric-only PPV metrics suitable for
    template rendering in GOVERNED mode.

    Args:
        envelope: The Phase10Envelope to extract from.

    Returns:
        Dictionary with PPV metrics (all numeric values).
    """
    if envelope.ppv is None:
        return {
            "PPV_PRESENT": False,
            "PPV_AGGREGATE": 0,
            "PPV_DIM_SUMMARY": (),
            "PPV_HASH": "",
        }

    return {
        "PPV_PRESENT": True,
        "PPV_AGGREGATE": envelope.ppv.aggregate,
        "PPV_DIM_SUMMARY": envelope.ppv.values,
        "PPV_HASH": envelope.ppv.ppv_hash[:16],  # Truncated for template use
    }


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "PPV_ENVELOPE_VERSION",
    # Dataclasses
    "Phase10Envelope",
    # Functions
    "create_phase10_envelope",
    "wrap_with_ppv",
    "extract_ppv_metrics",
]
