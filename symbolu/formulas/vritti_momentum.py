"""
Vritti Momentum Formula (VMF) - Phase 14 Temporal Formula
==========================================================

An advanced emotional-derivative formula extending ΔSMI with weighted components:
- Weighted ΔSMI
- Emotional polarity (vṛtti direction)
- Bhava direction
- Patent-coefficients for smoothing & stabilization
- Nonlinear amplification for large shifts

This formula is OBSERVATION-ONLY and does not affect any pipeline behavior.

Formula (canonical v1.0):
    vritti_momentum = clamp(
        0.50 * delta_smi
      + 0.20 * bhava_direction_term
      + 0.20 * vrtti_sign_term
      + 0.10 * nonlinear_accel,
      -1.0, 1.0
    )

Where:
    bhava_direction_term = +1 if upward, -1 if downward, else 0
    vrtti_sign_term = sign(delta_smi) * |delta_smi|
    nonlinear_accel = delta_smi^3  (patent smoothing)

Output range: [-1.0, +1.0]

Version: 1.0 (Phase 14)
Date: 2025-12-10
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class VrittiMomentumSnapshot:
    """
    Snapshot of computed Vritti Momentum Formula values.

    Attributes:
        vritti_momentum: Main VMF value in [-1.0, +1.0]
        delta_smi: Input ΔSMI value
        bhava_direction: Input bhava direction ("upward" | "downward" | "neutral")
        bhava_direction_term: Computed bhava direction component
        vrtti_sign_term: Computed vṛtti sign component
        nonlinear_accel: Computed nonlinear acceleration component
    """

    vritti_momentum: float
    delta_smi: float
    bhava_direction: str
    bhava_direction_term: float
    vrtti_sign_term: float
    nonlinear_accel: float


def compute_vritti_momentum(
    delta_smi: float,
    bhava_direction: str,
    vrtti_sign: Optional[float] = None,
) -> Optional[VrittiMomentumSnapshot]:
    """
    Compute Vritti Momentum Formula (VMF).

    This formula captures emotional momentum by combining:
    1. Weighted ΔSMI (50% weight) - base momentum
    2. Bhava direction term (20% weight) - consciousness state trajectory
    3. Vṛtti sign term (20% weight) - emotional polarity alignment
    4. Nonlinear acceleration (10% weight) - large shift amplification

    Args:
        delta_smi: ΔSMI value in [-1.0, +1.0]
        bhava_direction: Direction of bhava evolution ("upward", "downward", "neutral")
        vrtti_sign: Optional vṛtti sign override (defaults to sign(delta_smi))

    Returns:
        VrittiMomentumSnapshot with computed values, or None on error

    Raises:
        ValueError: If inputs are outside expected ranges
    """
    # Input validation
    if not (-1.0 <= delta_smi <= 1.0):
        raise ValueError(f"delta_smi must be in [-1.0, 1.0], got {delta_smi}")

    if bhava_direction not in ("upward", "downward", "neutral"):
        raise ValueError(
            f"bhava_direction must be 'upward', 'downward', or 'neutral', got '{bhava_direction}'"
        )

    try:
        # Component 1: Bhava direction term
        if bhava_direction == "upward":
            bhava_direction_term = 1.0
        elif bhava_direction == "downward":
            bhava_direction_term = -1.0
        else:  # neutral
            bhava_direction_term = 0.0

        # Component 2: Vṛtti sign term (emotional polarity)
        # vrtti_sign_term = sign(delta_smi) * |delta_smi|
        # This is equivalent to delta_smi itself, maintaining polarity
        vrtti_sign_term = delta_smi

        # Component 3: Nonlinear acceleration (cubic smoothing)
        # Amplifies large shifts while dampening small fluctuations
        nonlinear_accel = delta_smi ** 3

        # Compute weighted Vritti Momentum with canonical coefficients
        raw_momentum = (
            0.50 * delta_smi
            + 0.20 * bhava_direction_term
            + 0.20 * vrtti_sign_term
            + 0.10 * nonlinear_accel
        )

        # Clamp to output range [-1.0, +1.0]
        vritti_momentum = max(-1.0, min(1.0, raw_momentum))

        # Return snapshot with all computed values
        return VrittiMomentumSnapshot(
            vritti_momentum=vritti_momentum,
            delta_smi=delta_smi,
            bhava_direction=bhava_direction,
            bhava_direction_term=bhava_direction_term,
            vrtti_sign_term=vrtti_sign_term,
            nonlinear_accel=nonlinear_accel,
        )

    except Exception as e:
        # Fail-safe: return None on any computation error
        # This ensures the formula never crashes the pipeline
        return None


def _sign(value: float) -> int:
    """
    Compute sign of a value.

    Args:
        value: Input value

    Returns:
        +1 if value > 0, -1 if value < 0, 0 if value == 0
    """
    if value > 0:
        return 1
    elif value < 0:
        return -1
    else:
        return 0
