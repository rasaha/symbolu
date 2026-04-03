"""
Arc-Tension Harmonizer (ATH) Formula - Phase 14 Temporal Formula
================================================================

A harmonics-based stabilizer combining:
- Vritti Momentum
- Bhava Gap
- Tension Corridor
- Arc alignment & smoothness

This formula is OBSERVATION-ONLY and does not affect any pipeline behavior.

Formula (canonical v1.0):
    arc_tension_harmonizer = clamp(
        0.40 * (1 - tension_corridor)
      + 0.30 * (1 - abs(vritti_momentum))
      + 0.20 * arc_alignment_index
      + 0.10 * smoothing_term,
      0.0, 1.0
    )

Where:
    smoothing_term = exp(-abs(delta_smi))  # harmonic damping

Output range: [0.0, 1.0]

Version: 1.0 (Phase 14)
Date: 2025-12-10
"""

from dataclasses import dataclass
from typing import Optional
import math


@dataclass
class ArcTensionSnapshot:
    """
    Snapshot of computed Arc-Tension Harmonizer values.

    Attributes:
        arc_tension_harmonizer: Main ATH value in [0.0, 1.0]
        vritti_momentum: Input vritti momentum value
        tension_corridor: Input tension corridor value
        arc_alignment_index: Input arc alignment index
        delta_smi: Input ΔSMI (for smoothing calculation)
        tension_stability_term: Computed tension stability component
        momentum_stability_term: Computed momentum stability component
        arc_alignment_term: Computed arc alignment component
        smoothing_term: Computed harmonic damping component
    """

    arc_tension_harmonizer: float
    vritti_momentum: float
    tension_corridor: float
    arc_alignment_index: float
    delta_smi: Optional[float]
    tension_stability_term: float
    momentum_stability_term: float
    arc_alignment_term: float
    smoothing_term: float


def compute_arc_tension_harmonizer(
    vritti_momentum: float,
    tension_corridor: float,
    arc_alignment_index: float,
    delta_smi: Optional[float] = None,
) -> Optional[ArcTensionSnapshot]:
    """
    Compute Arc-Tension Harmonizer (ATH) Formula.

    This formula measures system stability and harmonic alignment by combining:
    1. Tension stability (40% weight) - inverse of tension corridor
    2. Momentum stability (30% weight) - inverse of absolute vritti momentum
    3. Arc alignment (20% weight) - temporal pattern alignment
    4. Harmonic smoothing (10% weight) - exponential damping based on ΔSMI

    The ATH acts as a quality signal: higher values indicate more stable,
    harmonious temporal patterns with good arc alignment.

    Args:
        vritti_momentum: Vritti momentum value in [-1.0, +1.0]
        tension_corridor: Tension corridor value in [0.0, 1.0]
        arc_alignment_index: Arc alignment index in [0.0, 1.0]
        delta_smi: Optional ΔSMI for smoothing term (defaults to 0.0 if None)

    Returns:
        ArcTensionSnapshot with computed values, or None on error

    Raises:
        ValueError: If inputs are outside expected ranges
    """
    # Input validation
    if not (-1.0 <= vritti_momentum <= 1.0):
        raise ValueError(f"vritti_momentum must be in [-1.0, 1.0], got {vritti_momentum}")

    if not (0.0 <= tension_corridor <= 1.0):
        raise ValueError(f"tension_corridor must be in [0.0, 1.0], got {tension_corridor}")

    if not (0.0 <= arc_alignment_index <= 1.0):
        raise ValueError(f"arc_alignment_index must be in [0.0, 1.0], got {arc_alignment_index}")

    # Default delta_smi to 0.0 if not provided
    if delta_smi is None:
        delta_smi = 0.0
    else:
        if not (-1.0 <= delta_smi <= 1.0):
            raise ValueError(f"delta_smi must be in [-1.0, 1.0], got {delta_smi}")

    try:
        # Component 1: Tension stability term
        # Lower tension → higher stability
        tension_stability_term = 1.0 - tension_corridor

        # Component 2: Momentum stability term
        # Lower absolute momentum → higher stability
        momentum_stability_term = 1.0 - abs(vritti_momentum)

        # Component 3: Arc alignment term
        # Direct contribution from arc alignment index
        arc_alignment_term = arc_alignment_index

        # Component 4: Harmonic smoothing term
        # Exponential damping: exp(-|ΔSMI|)
        # Large changes → more damping (lower smoothing_term)
        # Small changes → less damping (higher smoothing_term)
        smoothing_term = math.exp(-abs(delta_smi))

        # Compute weighted Arc-Tension Harmonizer with canonical coefficients
        raw_harmonizer = (
            0.40 * tension_stability_term
            + 0.30 * momentum_stability_term
            + 0.20 * arc_alignment_term
            + 0.10 * smoothing_term
        )

        # Clamp to output range [0.0, 1.0]
        arc_tension_harmonizer = max(0.0, min(1.0, raw_harmonizer))

        # Return snapshot with all computed values
        return ArcTensionSnapshot(
            arc_tension_harmonizer=arc_tension_harmonizer,
            vritti_momentum=vritti_momentum,
            tension_corridor=tension_corridor,
            arc_alignment_index=arc_alignment_index,
            delta_smi=delta_smi,
            tension_stability_term=tension_stability_term,
            momentum_stability_term=momentum_stability_term,
            arc_alignment_term=arc_alignment_term,
            smoothing_term=smoothing_term,
        )

    except Exception as e:
        # Fail-safe: return None on any computation error
        # This ensures the formula never crashes the pipeline
        return None
