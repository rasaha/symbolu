"""
Enhanced SMI Formula - Phase 13 Patent-Level Coefficients
==========================================================

Patent-accurate SMI formula with full coefficient weighting.

This module implements the enhanced SMI formula from the Symbol-U patent
with the following features:
- Patent-weighted coefficients (α, β, γ, δ, ε, ζ)
- Deterministic, zero-LLM computation
- Graceful handling of missing inputs
- Bounded output to [0.0, 1.0]

Formula:
    enhanced_smi = clamp(
        α * dim_resonance
      + β * vrtti_balance
      + γ * bhava_alignment
      + δ * semantic_weighting
      + ε * temporal_decay
      + ζ * noise_suppression
    )

Version: 1.0 (Phase 13)
Date: 2025-12-10
"""

from dataclasses import dataclass
from typing import Optional


# ==============================================================================
# PATENT-LEVEL COEFFICIENTS (MODULE-LEVEL CONSTANTS)
# ==============================================================================

# α: Dimensional resonance weight - primary consciousness state signal
ALPHA = 0.30

# β: Vrtti balance weight - mental fluctuation equilibrium
BETA = 0.25

# γ: Bhava alignment weight - emotional state positioning
GAMMA = 0.20

# δ: Semantic weighting - meaning coherence factor
DELTA = 0.15

# ε: Temporal decay weight - time-based stability signal
EPSILON = 0.05

# ζ: Noise suppression weight - signal clarity enhancement
ZETA = 0.05


@dataclass
class EnhancedSMISnapshot:
    """
    Snapshot of enhanced SMI computation with all components.

    This dataclass holds the computed enhanced SMI value and all its
    constituent components for observability and debugging.

    Attributes:
        enhanced_smi: Final computed enhanced SMI value [0.0, 1.0]
        dim_resonance: Dimensional resonance input [0.0, 1.0]
        vrtti_balance: Vrtti balance input [0.0, 1.0]
        bhava_alignment: Bhava alignment input [0.0, 1.0]
        semantic_weighting: Semantic weighting input [0.0, 1.0]
        temporal_decay: Temporal decay input [0.0, 1.0]
        noise_suppression: Noise suppression input [0.0, 1.0]
    """

    enhanced_smi: Optional[float] = None
    dim_resonance: Optional[float] = None
    vrtti_balance: Optional[float] = None
    bhava_alignment: Optional[float] = None
    semantic_weighting: Optional[float] = None
    temporal_decay: Optional[float] = None
    noise_suppression: Optional[float] = None

    def to_dict(self):
        """Convert snapshot to JSON-safe dictionary."""
        return {
            "enhanced_smi": self.enhanced_smi,
            "dim_resonance": self.dim_resonance,
            "vrtti_balance": self.vrtti_balance,
            "bhava_alignment": self.bhava_alignment,
            "semantic_weighting": self.semantic_weighting,
            "temporal_decay": self.temporal_decay,
            "noise_suppression": self.noise_suppression,
        }


def compute_enhanced_smi(
    dim_resonance: Optional[float] = None,
    vrtti_balance: Optional[float] = None,
    bhava_alignment: Optional[float] = None,
    semantic_weighting: Optional[float] = None,
    temporal_decay: Optional[float] = None,
    noise_suppression: Optional[float] = None,
) -> Optional[float]:
    """
    Compute enhanced SMI with patent-level coefficients.

    This function computes the patent-accurate SMI formula using weighted
    contributions from six components:
    - dim_resonance: Dimensional resonance (primary signal)
    - vrtti_balance: Mental fluctuation equilibrium
    - bhava_alignment: Emotional state positioning
    - semantic_weighting: Meaning coherence factor
    - temporal_decay: Time-based stability signal
    - noise_suppression: Signal clarity enhancement

    Formula:
        enhanced_smi = clamp(
            α * dim_resonance
          + β * vrtti_balance
          + γ * bhava_alignment
          + δ * semantic_weighting
          + ε * temporal_decay
          + ζ * noise_suppression,
          0.0, 1.0
        )

    Missing Data Handling:
        If ANY required input is None, the function returns None.
        All inputs must be present for valid computation.

    Args:
        dim_resonance: Dimensional resonance [0.0, 1.0] (optional)
        vrtti_balance: Vrtti balance [0.0, 1.0] (optional)
        bhava_alignment: Bhava alignment [0.0, 1.0] (optional)
        semantic_weighting: Semantic weighting [0.0, 1.0] (optional)
        temporal_decay: Temporal decay [0.0, 1.0] (optional)
        noise_suppression: Noise suppression [0.0, 1.0] (optional)

    Returns:
        Enhanced SMI value [0.0, 1.0], or None if any input is missing

    Raises:
        ValueError: If any input is outside [0.0, 1.0] range
    """
    # Missing data check: If ANY input is None, return None
    if (
        dim_resonance is None
        or vrtti_balance is None
        or bhava_alignment is None
        or semantic_weighting is None
        or temporal_decay is None
        or noise_suppression is None
    ):
        return None

    # Input validation: All inputs must be in [0.0, 1.0]
    if not (0.0 <= dim_resonance <= 1.0):
        raise ValueError(f"dim_resonance must be in [0.0, 1.0], got {dim_resonance}")
    if not (0.0 <= vrtti_balance <= 1.0):
        raise ValueError(f"vrtti_balance must be in [0.0, 1.0], got {vrtti_balance}")
    if not (0.0 <= bhava_alignment <= 1.0):
        raise ValueError(f"bhava_alignment must be in [0.0, 1.0], got {bhava_alignment}")
    if not (0.0 <= semantic_weighting <= 1.0):
        raise ValueError(f"semantic_weighting must be in [0.0, 1.0], got {semantic_weighting}")
    if not (0.0 <= temporal_decay <= 1.0):
        raise ValueError(f"temporal_decay must be in [0.0, 1.0], got {temporal_decay}")
    if not (0.0 <= noise_suppression <= 1.0):
        raise ValueError(f"noise_suppression must be in [0.0, 1.0], got {noise_suppression}")

    # Compute weighted sum with patent-level coefficients
    enhanced_smi = (
        ALPHA * dim_resonance
        + BETA * vrtti_balance
        + GAMMA * bhava_alignment
        + DELTA * semantic_weighting
        + EPSILON * temporal_decay
        + ZETA * noise_suppression
    )

    # Clamp to [0.0, 1.0] (should already be in range, but ensure safety)
    enhanced_smi = max(0.0, min(1.0, enhanced_smi))

    return enhanced_smi


def compute_enhanced_smi_snapshot(
    dim_resonance: Optional[float] = None,
    vrtti_balance: Optional[float] = None,
    bhava_alignment: Optional[float] = None,
    semantic_weighting: Optional[float] = None,
    temporal_decay: Optional[float] = None,
    noise_suppression: Optional[float] = None,
) -> EnhancedSMISnapshot:
    """
    Compute enhanced SMI and return a snapshot with all components.

    This function wraps compute_enhanced_smi() and returns a dataclass
    snapshot containing both the computed enhanced SMI value and all
    input components for observability and debugging.

    Args:
        dim_resonance: Dimensional resonance [0.0, 1.0] (optional)
        vrtti_balance: Vrtti balance [0.0, 1.0] (optional)
        bhava_alignment: Bhava alignment [0.0, 1.0] (optional)
        semantic_weighting: Semantic weighting [0.0, 1.0] (optional)
        temporal_decay: Temporal decay [0.0, 1.0] (optional)
        noise_suppression: Noise suppression [0.0, 1.0] (optional)

    Returns:
        EnhancedSMISnapshot with all components and computed enhanced_smi

    Note:
        This function does NOT raise exceptions - it returns a snapshot
        with enhanced_smi=None if computation fails.
    """
    snapshot = EnhancedSMISnapshot(
        dim_resonance=dim_resonance,
        vrtti_balance=vrtti_balance,
        bhava_alignment=bhava_alignment,
        semantic_weighting=semantic_weighting,
        temporal_decay=temporal_decay,
        noise_suppression=noise_suppression,
    )

    try:
        snapshot.enhanced_smi = compute_enhanced_smi(
            dim_resonance=dim_resonance,
            vrtti_balance=vrtti_balance,
            bhava_alignment=bhava_alignment,
            semantic_weighting=semantic_weighting,
            temporal_decay=temporal_decay,
            noise_suppression=noise_suppression,
        )
    except (ValueError, Exception):
        # Graceful degradation: set enhanced_smi to None on error
        snapshot.enhanced_smi = None

    return snapshot
