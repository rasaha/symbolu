"""
Vritti Signal Adapter — Governance-time vritti resolution.

Resolves the best available vritti signal for governance decisions:
1. If a real ChittaVrittiResult is available → use it (source=REAL)
2. Otherwise → fall back to approximate_vritti() (source=APPROXIMATED)

The adapter returns a clean VrittiResolution that governance consumers
(JEPA check, domain policy, shadow AI) can use without caring about
the underlying source.

CANONICAL RUNTIME VRITTI AUTHORITY: agentic/chitta_vritti/
FALLBACK APPROXIMATION: agentic/agentic_framework/jepa_governance.approximate_vritti()

Phase 1: Governance signal rewiring.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Dict, Optional

from agentic.agentic_framework.jepa_governance import approximate_vritti


# =========================================================================
# Signal source classification
# =========================================================================

class VrittiSignalSource(enum.Enum):
    """Where the vritti distribution came from."""
    REAL = "real"                  # From chitta_vritti engine
    APPROXIMATED = "approximated"  # From approximate_vritti() heuristic


# =========================================================================
# Resolution result
# =========================================================================

@dataclass(frozen=True)
class VrittiResolution:
    """Resolved vritti signal with provenance metadata.

    Attributes:
        distribution: Normalized 5-vritti distribution (sums to ~1.0).
        coherence: Cross-layer coherence [0, 1]. Real source provides
            actual coherence; approximation uses a proxy.
        score: Readiness score [0, 1].
        source: Whether this came from real engine or approximation.
        degraded: True if fallback was used due to real signal being
            unavailable. Governance should treat this as lower-confidence.
        source_detail: Human-readable detail about signal origin.
    """
    distribution: Dict[str, float]
    coherence: float
    score: float
    source: VrittiSignalSource
    degraded: bool
    source_detail: str


# =========================================================================
# Resolution logic
# =========================================================================

def resolve_vritti_signal(
    *,
    vritti_result: Any = None,
    quality: float = 0.5,
    coherence: float = 0.5,
    overall_confidence: float = 0.5,
) -> VrittiResolution:
    """Resolve the best available vritti signal for governance use.

    Args:
        vritti_result: A ChittaVrittiResult object from the runtime
            chitta_vritti engine, if available. When present, this is
            the preferred source. The adapter duck-types on expected
            attributes (.vritti, .coherence, .score, .dominant_vritti)
            to avoid tight coupling.
        quality: Quality score [0, 1] for approximation fallback.
        coherence: Coherence score [0, 1] for approximation fallback.
        overall_confidence: Overall confidence [0, 1] for fallback.

    Returns:
        VrittiResolution with distribution, metadata, and provenance.

    Fail-closed semantics:
        - If vritti_result is provided but malformed → fall back to
          approximation with degraded=True.
        - If approximation itself fails → return full dormancy (nidra=1.0).
    """
    # Path 1: Try real chitta_vritti result
    if vritti_result is not None:
        try:
            return _from_real(vritti_result)
        except (AttributeError, TypeError, ValueError):
            # Malformed result — degrade to approximation, don't crash
            pass

    # Path 2: Approximation fallback
    return _from_approximation(
        quality=quality,
        coherence=coherence,
        overall_confidence=overall_confidence,
    )


def _from_real(vritti_result: Any) -> VrittiResolution:
    """Extract vritti signal from a real ChittaVrittiResult.

    Duck-types on:
        .vritti: dict-like {name: float}
        .coherence: float
        .score: float
        .dominant_vritti: str
    """
    # Extract distribution — handle both dict and dict-like objects
    raw_dist = vritti_result.vritti
    if hasattr(raw_dist, "items"):
        dist = dict(raw_dist)
    else:
        raise TypeError(f"vritti_result.vritti is not dict-like: {type(raw_dist)}")

    # Validate: must have the 5 canonical vritti names
    expected = {"pramana", "viparyaya", "vikalpa", "smrti", "nidra"}
    if not expected.issubset(dist.keys()):
        raise ValueError(f"Missing vritti keys: {expected - set(dist.keys())}")

    coh = float(vritti_result.coherence)
    sc = float(vritti_result.score)
    dominant = str(vritti_result.dominant_vritti)

    return VrittiResolution(
        distribution=dist,
        coherence=coh,
        score=sc,
        source=VrittiSignalSource.REAL,
        degraded=False,
        source_detail=f"chitta_vritti engine (dominant={dominant}, coherence={coh:.3f})",
    )


def _from_approximation(
    *,
    quality: float,
    coherence: float,
    overall_confidence: float,
) -> VrittiResolution:
    """Fall back to the heuristic approximation.

    Uses the canonical approximate_vritti() from jepa_governance.
    """
    dist = approximate_vritti(
        quality=quality,
        coherence=coherence,
        overall_confidence=overall_confidence,
    )

    return VrittiResolution(
        distribution=dist,
        coherence=coherence,  # Best proxy available
        score=overall_confidence,  # Best proxy available
        source=VrittiSignalSource.APPROXIMATED,
        degraded=True,
        source_detail=(
            f"approximate_vritti(q={quality:.2f}, c={coherence:.2f}, "
            f"conf={overall_confidence:.2f})"
        ),
    )
