"""
Entropy Signal Adapter — Governance-time entropy resolution.

Resolves entropy as a governance signal from the canonical entropy engine.
When entropy inputs are unavailable, returns a diagnostic-only placeholder
that does not influence decisions (fail-closed: absence of entropy does
not weaken governance).

Phase 1 approach:
- Wire entropy into governance decision context
- Expose it in audit/reasoning metadata
- Apply bounded confidence penalty when entropy is high
- Do NOT hard-block on entropy alone in this phase

CANONICAL ENTROPY AUTHORITY: agentic/entropy/
Phase 1: Governance signal rewiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


# =========================================================================
# Resolution result
# =========================================================================

@dataclass(frozen=True)
class EntropyResolution:
    """Resolved entropy signal for governance use.

    Attributes:
        combined_entropy: Combined entropy [0, 1]. Higher = more incoherent.
            None if entropy was not computed.
        guna_entropy: Guna-specific entropy [0, 1], or None.
        kosha_entropy: Kosha-specific entropy [0, 1], or None.
        cross_domain_entropy: Cross-domain entropy [0, 1], or None.
        gate: Entropy gate classification (ALLOW/ALLOW_WITH_MODULATION/BLOCK)
            as a string, or None if not computed.
        confidence_penalty: A bounded [0, 0.15] penalty to subtract from
            governance confidence when entropy is elevated. Zero when
            entropy is low or unavailable.
        available: Whether entropy was successfully computed.
        source_detail: Human-readable description of what happened.
    """
    combined_entropy: Optional[float]
    guna_entropy: Optional[float]
    kosha_entropy: Optional[float]
    cross_domain_entropy: Optional[float]
    gate: Optional[str]
    confidence_penalty: float
    available: bool
    source_detail: str


# =========================================================================
# Confidence penalty computation
# =========================================================================

# Phase 1: bounded confidence penalty from entropy.
# Max penalty is 0.15 (15% confidence reduction for extreme incoherence).
# Penalty only kicks in above the LOW threshold.
_ENTROPY_LOW_THRESHOLD = 0.3     # Below this: no penalty
_ENTROPY_HIGH_THRESHOLD = 0.7    # Above this: max penalty
_MAX_CONFIDENCE_PENALTY = 0.15   # Never reduce confidence by more than this


def _compute_confidence_penalty(combined_entropy: float) -> float:
    """Compute bounded confidence penalty from entropy.

    Linear interpolation between thresholds.
    Below low threshold: 0.0 penalty.
    Above high threshold: max penalty.
    """
    if combined_entropy <= _ENTROPY_LOW_THRESHOLD:
        return 0.0
    if combined_entropy >= _ENTROPY_HIGH_THRESHOLD:
        return _MAX_CONFIDENCE_PENALTY
    # Linear interpolation
    ratio = (combined_entropy - _ENTROPY_LOW_THRESHOLD) / (
        _ENTROPY_HIGH_THRESHOLD - _ENTROPY_LOW_THRESHOLD
    )
    return ratio * _MAX_CONFIDENCE_PENALTY


# =========================================================================
# Resolution logic
# =========================================================================

def resolve_entropy_signal(
    *,
    entropy_result: object = None,
    combined_entropy: Optional[float] = None,
) -> EntropyResolution:
    """Resolve entropy as a governance signal.

    Args:
        entropy_result: An EntropyResult from agentic.entropy.EntropyEngine,
            if available. Duck-typed on .combined_entropy, .guna_entropy,
            .kosha_entropy, .cross_domain_entropy, .gate attributes.
        combined_entropy: Direct combined entropy value [0, 1] if an
            EntropyResult object is not available but the scalar is.

    Returns:
        EntropyResolution with entropy metrics and bounded confidence penalty.

    Fail-closed semantics:
        - If no entropy data at all → available=False, penalty=0.0,
          governance proceeds on existing signals (entropy absence does
          NOT weaken governance posture).
        - If entropy_result is malformed → same as no data.
    """
    # Path 1: Full EntropyResult object
    if entropy_result is not None:
        try:
            return _from_entropy_result(entropy_result)
        except (AttributeError, TypeError, ValueError):
            pass

    # Path 2: Direct scalar
    if combined_entropy is not None:
        try:
            ce = float(combined_entropy)
            ce = max(0.0, min(1.0, ce))
            return EntropyResolution(
                combined_entropy=ce,
                guna_entropy=None,
                kosha_entropy=None,
                cross_domain_entropy=None,
                gate=None,
                confidence_penalty=_compute_confidence_penalty(ce),
                available=True,
                source_detail=f"direct scalar (combined={ce:.3f})",
            )
        except (TypeError, ValueError):
            pass

    # Path 3: No entropy available
    return EntropyResolution(
        combined_entropy=None,
        guna_entropy=None,
        kosha_entropy=None,
        cross_domain_entropy=None,
        gate=None,
        confidence_penalty=0.0,
        available=False,
        source_detail="no entropy data available",
    )


def _from_entropy_result(entropy_result: object) -> EntropyResolution:
    """Extract from a full EntropyResult object."""
    ce = float(entropy_result.combined_entropy)  # type: ignore[union-attr]
    ge = float(entropy_result.guna_entropy)  # type: ignore[union-attr]
    ke = float(entropy_result.kosha_entropy)  # type: ignore[union-attr]
    cde = float(entropy_result.cross_domain_entropy)  # type: ignore[union-attr]
    gate_val = entropy_result.gate  # type: ignore[union-attr]
    gate_str = gate_val.value if hasattr(gate_val, "value") else str(gate_val)

    return EntropyResolution(
        combined_entropy=ce,
        guna_entropy=ge,
        kosha_entropy=ke,
        cross_domain_entropy=cde,
        gate=gate_str,
        confidence_penalty=_compute_confidence_penalty(ce),
        available=True,
        source_detail=(
            f"entropy engine (combined={ce:.3f}, gate={gate_str})"
        ),
    )
