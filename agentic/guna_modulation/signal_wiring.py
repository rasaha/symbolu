"""
Signal Wiring for Guna Entropy Modulation
==========================================

Symbol-U v2.6 - Deterministic, Zero-Parameter, Non-Learning System

This module implements the deterministic wiring of Entropy (H) and Motion (M)
signals from the pipeline into the Guna modulation layer.

All behavior is expressed as closed-form equations.
If something cannot be expressed as a formula, it is excluded.

EXPLICIT NON-CAPABILITIES (MANDATORY):
    - No learning
    - No feedback loops
    - No preference updates
    - No moral reasoning
    - No user psychology inference
    - No policy evaluation
    - No AGI claims

PIPELINE PLACEMENT:
    STL -> C x R x S -> Routing -> (optional AGI)
    -> Entropy/Motion Wiring (THIS MODULE)
    -> Guna Modulation
    -> Renderer

This layer ONLY wires existing signals. It does NOT:
    - Change STL
    - Change Stitching
    - Change Fusion
    - Influence candidate selection
    - Override truth

Version: 2.6.0
Date: 2025-12-22
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from agentic.guna_modulation.types import EPSILON


# =============================================================================
# Constants (Fixed - No Modifications Allowed)
# =============================================================================

# Entropy normalization bounds (from TTOR specification)
LN_3: float = math.log(3)   # ~1.0986 - max H_G
LN_5: float = math.log(5)   # ~1.6094 - max H_K
LN_10: float = math.log(10) # ~2.3026 - max H_D

# Motion configuration
MAX_STRUCTURAL_JUMPS: int = 5
"""Maximum structural jump count for normalization."""

# Experiential intent set (fixed - no inference)
EXPERIENTIAL_MOTION_INTENTS: frozenset = frozenset({
    "directive",
    "corrective",
    "inverse_jolt",
})
"""Fixed intent set that triggers experiential motion = 1."""


# =============================================================================
# Entropy Mode Enum
# =============================================================================

class EntropyMode(Enum):
    """
    Operator-selectable entropy source mode.

    Each mode maps a different pipeline entropy signal to H [0,1].
    Mode MUST be operator-configured. No auto-selection logic.
    """
    GUNA = "guna"           # H = H_G / ln(3) - PREFERRED / DEFAULT
    DIMENSIONAL = "dimensional"  # H = H_D / ln(10)
    KOSHA = "kosha"         # H = H_K / ln(5)


# =============================================================================
# Motion Mode Enum
# =============================================================================

class MotionMode(Enum):
    """
    Operator-selectable motion computation mode.

    Each mode uses a different formula to compute M [0,1].
    Mode MUST be operator-configured. No auto-selection logic.
    """
    SEMANTIC = "semantic"       # M = delta_sem - DEFAULT
    STRUCTURAL = "structural"   # M = delta_str_norm
    EXPERIENTIAL = "experiential"  # M = delta_exp (0 or 1)
    COMPOSITE = "composite"     # M = weighted average


# =============================================================================
# Entropy Wiring Audit Record
# =============================================================================

@dataclass(frozen=True)
class EntropyWiringAudit:
    """
    Audit record for entropy signal wiring.

    Every entropy computation MUST produce this record.
    No summaries. No prose. Numeric values only.
    """
    entropy_mode: str
    H_raw: float
    H_normalized: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entropy_mode": self.entropy_mode,
            "H_raw": self.H_raw,
            "H_normalized": self.H_normalized,
        }


# =============================================================================
# Motion Wiring Audit Record
# =============================================================================

@dataclass(frozen=True)
class MotionWiringAudit:
    """
    Audit record for motion signal wiring.

    Every motion computation MUST produce this record.
    No summaries. No prose. Numeric values only.
    """
    motion_mode: str
    delta_sem: float
    delta_str_norm: float
    delta_exp: float
    M: float
    weights: Optional[Tuple[float, float, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "motion_mode": self.motion_mode,
            "delta_sem": self.delta_sem,
            "delta_str_norm": self.delta_str_norm,
            "delta_exp": self.delta_exp,
            "M": self.M,
        }
        if self.weights is not None:
            result["weights"] = {
                "w1": self.weights[0],
                "w2": self.weights[1],
                "w3": self.weights[2],
            }
        return result


# =============================================================================
# Combined Signal Wiring Audit
# =============================================================================

@dataclass(frozen=True)
class SignalWiringAudit:
    """
    Complete audit record for all signal wiring.

    Every request MUST log this record.
    """
    entropy_audit: EntropyWiringAudit
    motion_audit: MotionWiringAudit
    operator_config_snapshot: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entropy_mode": self.entropy_audit.entropy_mode,
            "H_raw": self.entropy_audit.H_raw,
            "H_normalized": self.entropy_audit.H_normalized,
            "motion_mode": self.motion_audit.motion_mode,
            "delta_sem": self.motion_audit.delta_sem,
            "delta_str_norm": self.motion_audit.delta_str_norm,
            "delta_exp": self.motion_audit.delta_exp,
            "M": self.motion_audit.M,
            "operator_config_snapshot": self.operator_config_snapshot,
        }


# =============================================================================
# Wired Pipeline Signals
# =============================================================================

@dataclass(frozen=True)
class WiredSignals:
    """
    Wired H and M signals ready for modulation layer.

    Contains the final normalized values plus complete audit trail.
    """
    H: float  # Normalized entropy [0, 1]
    M: float  # Normalized motion [0, 1]
    audit: SignalWiringAudit

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "H": self.H,
            "M": self.M,
            "audit": self.audit.to_dict(),
        }


# =============================================================================
# PART 1: Entropy Input H Computation
# =============================================================================

def compute_H(
    H_G: float,
    H_D: float,
    H_K: float,
    mode: EntropyMode = EntropyMode.GUNA,
) -> Tuple[float, EntropyWiringAudit]:
    """
    Compute normalized entropy H from pipeline signals.

    MANDATORY FORMULAS:

    Option A - Guna Entropy (Preferred / Clean / Default):
        H = H_G / ln(3)

    Option B - Dimensional Entropy:
        H = H_D / ln(10)

    Option C - Kosha Entropy:
        H = H_K / ln(5)

    Requirements:
        - Clamp raw entropy before normalization
        - Final H MUST be in [0, 1]
        - Mode MUST be operator-configured
        - No auto-selection logic

    Args:
        H_G: Guna entropy [0, ln(3)]
        H_D: Dimensional entropy [0, ln(10)]
        H_K: Kosha entropy [0, ln(5)]
        mode: Operator-selected entropy mode (default: GUNA)

    Returns:
        Tuple of (H_normalized, audit_record)

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    # Select source and normalization based on mode
    if mode == EntropyMode.GUNA:
        # Clamp raw entropy to valid range
        H_raw = max(0.0, min(LN_3, H_G))
        # Normalize: H = H_G / ln(3)
        H_normalized = H_raw / LN_3 if LN_3 > 0 else 0.0

    elif mode == EntropyMode.DIMENSIONAL:
        # Clamp raw entropy to valid range
        H_raw = max(0.0, min(LN_10, H_D))
        # Normalize: H = H_D / ln(10)
        H_normalized = H_raw / LN_10 if LN_10 > 0 else 0.0

    elif mode == EntropyMode.KOSHA:
        # Clamp raw entropy to valid range
        H_raw = max(0.0, min(LN_5, H_K))
        # Normalize: H = H_K / ln(5)
        H_normalized = H_raw / LN_5 if LN_5 > 0 else 0.0

    else:
        raise ValueError(f"Invalid entropy mode: {mode}")

    # Final clamp to [0, 1]
    H_normalized = max(0.0, min(1.0, H_normalized))

    # Create audit record
    audit = EntropyWiringAudit(
        entropy_mode=mode.value,
        H_raw=H_raw,
        H_normalized=H_normalized,
    )

    return (H_normalized, audit)


# =============================================================================
# PART 2: Motion Input M Computation - Component Functions
# =============================================================================

def compute_semantic_delta(
    candidate_aspect_vector: Dict[str, float],
    context_aspect_vector: Dict[str, float],
) -> float:
    """
    Compute semantic motion (delta_sem).

    MANDATORY FORMULA:
        delta_sem = 1 - cosine_similarity(
            candidate.aspect_vector,
            context.aspect_vector
        )

    Bounds: delta_sem in [0, 1]

    Args:
        candidate_aspect_vector: Aspect vector from candidate
        context_aspect_vector: Aspect vector from context

    Returns:
        Semantic delta in [0, 1]

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    # Get all keys from both vectors
    all_keys = set(candidate_aspect_vector.keys()) | set(context_aspect_vector.keys())

    if not all_keys:
        # No dimensions - no motion
        return 0.0

    # Extract aligned vectors
    vec_a = [candidate_aspect_vector.get(k, 0.0) for k in sorted(all_keys)]
    vec_b = [context_aspect_vector.get(k, 0.0) for k in sorted(all_keys)]

    # Compute dot product
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))

    # Compute magnitudes
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))

    # Compute cosine similarity
    if mag_a < EPSILON or mag_b < EPSILON:
        # Zero magnitude - maximum motion (undefined direction)
        cosine_sim = 0.0
    else:
        cosine_sim = dot_product / (mag_a * mag_b)
        # Clamp to [-1, 1] for numerical stability
        cosine_sim = max(-1.0, min(1.0, cosine_sim))

    # delta_sem = 1 - cosine_similarity
    delta_sem = 1.0 - cosine_sim

    # Clamp to [0, 1]
    return max(0.0, min(1.0, delta_sem))


def compute_structural_delta(
    domain_jump_count: int,
    layer_transition_count: int = 0,
) -> float:
    """
    Compute structural motion (delta_str_norm).

    MANDATORY FORMULAS:
        delta_str = min(
            domain_jump_count + layer_transition_count,
            MAX_STRUCTURAL_JUMPS
        )
        delta_str_norm = delta_str / MAX_STRUCTURAL_JUMPS

    Args:
        domain_jump_count: Number of domain jumps
        layer_transition_count: Number of layer transitions

    Returns:
        Normalized structural delta in [0, 1]

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    # Compute raw structural displacement
    delta_str = min(
        domain_jump_count + layer_transition_count,
        MAX_STRUCTURAL_JUMPS
    )

    # Normalize
    if MAX_STRUCTURAL_JUMPS > 0:
        delta_str_norm = delta_str / MAX_STRUCTURAL_JUMPS
    else:
        delta_str_norm = 0.0

    # Clamp to [0, 1]
    return max(0.0, min(1.0, delta_str_norm))


def compute_experiential_delta(intent: str) -> float:
    """
    Compute experiential motion (delta_exp).

    MANDATORY FORMULA:
        delta_exp = 1 if intent in {directive, corrective, inverse_jolt}
                    else 0

    Uses a fixed intent mapping table. No inference.

    Args:
        intent: Intent string from fusion context

    Returns:
        Experiential delta (0 or 1)

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    # Fixed intent mapping - no inference
    if intent.lower() in EXPERIENTIAL_MOTION_INTENTS:
        return 1.0
    else:
        return 0.0


# =============================================================================
# PART 2: Motion Input M Computation - Main Function
# =============================================================================

def compute_M(
    semantic_delta: float,
    structural_delta: float,
    experiential_delta: float,
    mode: MotionMode = MotionMode.SEMANTIC,
    weights: Optional[Tuple[float, float, float]] = None,
) -> Tuple[float, MotionWiringAudit]:
    """
    Compute normalized motion M from derived components.

    MANDATORY MODES:

    Mode 1 - Semantic Primary (Default):
        M = delta_sem

    Mode 2 - Structural Primary:
        M = delta_str_norm

    Mode 3 - Experiential Primary:
        M = delta_exp

    Mode 4 - Composite (Enterprise Advanced):
        M = (w1 * delta_sem + w2 * delta_str_norm + w3 * delta_exp) / (w1 + w2 + w3)
        Where:
            - w1, w2, w3 are operator-supplied constants
            - All weights >= 0
            - Result MUST be clamped to [0, 1]

    Args:
        semantic_delta: Pre-computed delta_sem [0, 1]
        structural_delta: Pre-computed delta_str_norm [0, 1]
        experiential_delta: Pre-computed delta_exp (0 or 1)
        mode: Operator-selected motion mode (default: SEMANTIC)
        weights: Optional (w1, w2, w3) for COMPOSITE mode

    Returns:
        Tuple of (M, audit_record)

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    # Ensure inputs are clamped
    delta_sem = max(0.0, min(1.0, semantic_delta))
    delta_str_norm = max(0.0, min(1.0, structural_delta))
    delta_exp = max(0.0, min(1.0, experiential_delta))

    # Compute M based on mode
    if mode == MotionMode.SEMANTIC:
        M = delta_sem

    elif mode == MotionMode.STRUCTURAL:
        M = delta_str_norm

    elif mode == MotionMode.EXPERIENTIAL:
        M = delta_exp

    elif mode == MotionMode.COMPOSITE:
        # Validate weights
        if weights is None:
            raise ValueError("COMPOSITE mode requires weights (w1, w2, w3)")

        w1, w2, w3 = weights

        # Validate all weights are non-negative
        if w1 < 0 or w2 < 0 or w3 < 0:
            raise ValueError("All weights must be >= 0")

        # Compute weighted average
        weight_sum = w1 + w2 + w3
        if weight_sum < EPSILON:
            # All weights zero - default to zero motion
            M = 0.0
        else:
            M = (w1 * delta_sem + w2 * delta_str_norm + w3 * delta_exp) / weight_sum
    else:
        raise ValueError(f"Invalid motion mode: {mode}")

    # Final clamp to [0, 1]
    M = max(0.0, min(1.0, M))

    # Create audit record
    audit = MotionWiringAudit(
        motion_mode=mode.value,
        delta_sem=delta_sem,
        delta_str_norm=delta_str_norm,
        delta_exp=delta_exp,
        M=M,
        weights=weights if mode == MotionMode.COMPOSITE else None,
    )

    return (M, audit)


# =============================================================================
# Convenience Functions for Raw Signal Extraction
# =============================================================================

def compute_M_from_raw(
    candidate_aspect_vector: Dict[str, float],
    context_aspect_vector: Dict[str, float],
    domain_jump_count: int,
    intent: str,
    mode: MotionMode = MotionMode.SEMANTIC,
    layer_transition_count: int = 0,
    weights: Optional[Tuple[float, float, float]] = None,
) -> Tuple[float, MotionWiringAudit]:
    """
    Compute motion M directly from raw pipeline signals.

    Convenience function that derives all delta components before computing M.

    Args:
        candidate_aspect_vector: Aspect vector from candidate
        context_aspect_vector: Aspect vector from context
        domain_jump_count: Number of domain jumps
        intent: Intent string from fusion context
        mode: Operator-selected motion mode
        layer_transition_count: Number of layer transitions (default: 0)
        weights: Optional weights for COMPOSITE mode

    Returns:
        Tuple of (M, audit_record)
    """
    # Compute all delta components
    delta_sem = compute_semantic_delta(
        candidate_aspect_vector,
        context_aspect_vector,
    )
    delta_str_norm = compute_structural_delta(
        domain_jump_count,
        layer_transition_count,
    )
    delta_exp = compute_experiential_delta(intent)

    # Compute M using derived components
    return compute_M(
        semantic_delta=delta_sem,
        structural_delta=delta_str_norm,
        experiential_delta=delta_exp,
        mode=mode,
        weights=weights,
    )


# =============================================================================
# PART 3: Full Signal Wiring Function
# =============================================================================

@dataclass(frozen=True)
class SignalWiringConfig:
    """
    Operator configuration for signal wiring.

    All values are operator-configured. No auto-selection.
    """
    entropy_mode: EntropyMode = EntropyMode.GUNA
    motion_mode: MotionMode = MotionMode.SEMANTIC
    composite_weights: Optional[Tuple[float, float, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "entropy_mode": self.entropy_mode.value,
            "motion_mode": self.motion_mode.value,
        }
        if self.composite_weights is not None:
            result["composite_weights"] = {
                "w1": self.composite_weights[0],
                "w2": self.composite_weights[1],
                "w3": self.composite_weights[2],
            }
        return result


# Default configuration
DEFAULT_WIRING_CONFIG = SignalWiringConfig(
    entropy_mode=EntropyMode.GUNA,
    motion_mode=MotionMode.SEMANTIC,
)


def wire_signals(
    # Entropy inputs (from TTOR)
    H_G: float,
    H_D: float,
    H_K: float,
    # Motion inputs (from pipeline)
    candidate_aspect_vector: Dict[str, float],
    context_aspect_vector: Dict[str, float],
    domain_jump_count: int,
    intent: str,
    # Optional inputs
    layer_transition_count: int = 0,
    # Configuration
    config: SignalWiringConfig = DEFAULT_WIRING_CONFIG,
) -> WiredSignals:
    """
    Wire all pipeline signals to produce H and M for modulation.

    This is the main entry point for signal wiring.

    PIPELINE PLACEMENT:
        STL -> C x R x S -> Routing -> (optional AGI)
        -> [THIS FUNCTION]
        -> Guna Modulation
        -> Renderer

    Args:
        H_G: Guna entropy [0, ln(3)]
        H_D: Dimensional entropy [0, ln(10)]
        H_K: Kosha entropy [0, ln(5)]
        candidate_aspect_vector: Aspect vector from candidate
        context_aspect_vector: Aspect vector from context
        domain_jump_count: Number of domain jumps
        intent: Intent string from fusion context
        layer_transition_count: Number of layer transitions
        config: Operator wiring configuration

    Returns:
        WiredSignals containing H, M, and complete audit trail

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    # Compute H
    H, entropy_audit = compute_H(
        H_G=H_G,
        H_D=H_D,
        H_K=H_K,
        mode=config.entropy_mode,
    )

    # Compute M
    M, motion_audit = compute_M_from_raw(
        candidate_aspect_vector=candidate_aspect_vector,
        context_aspect_vector=context_aspect_vector,
        domain_jump_count=domain_jump_count,
        intent=intent,
        mode=config.motion_mode,
        layer_transition_count=layer_transition_count,
        weights=config.composite_weights,
    )

    # Create combined audit
    audit = SignalWiringAudit(
        entropy_audit=entropy_audit,
        motion_audit=motion_audit,
        operator_config_snapshot=config.to_dict(),
    )

    return WiredSignals(H=H, M=M, audit=audit)


def wire_signals_simple(
    # Pre-computed delta values
    H_raw: float,
    entropy_mode: EntropyMode,
    delta_sem: float,
    delta_str_norm: float,
    delta_exp: float,
    motion_mode: MotionMode = MotionMode.SEMANTIC,
    weights: Optional[Tuple[float, float, float]] = None,
) -> WiredSignals:
    """
    Wire signals using pre-computed delta values.

    Simplified version for when delta components are already computed.

    Args:
        H_raw: Raw entropy value in source's native range
        entropy_mode: Which entropy mode is being used
        delta_sem: Pre-computed semantic delta
        delta_str_norm: Pre-computed structural delta
        delta_exp: Pre-computed experiential delta
        motion_mode: Operator-selected motion mode
        weights: Optional weights for COMPOSITE mode

    Returns:
        WiredSignals containing H, M, and complete audit trail
    """
    # Normalize H based on mode
    if entropy_mode == EntropyMode.GUNA:
        H_clamped = max(0.0, min(LN_3, H_raw))
        H = H_clamped / LN_3 if LN_3 > 0 else 0.0
    elif entropy_mode == EntropyMode.DIMENSIONAL:
        H_clamped = max(0.0, min(LN_10, H_raw))
        H = H_clamped / LN_10 if LN_10 > 0 else 0.0
    elif entropy_mode == EntropyMode.KOSHA:
        H_clamped = max(0.0, min(LN_5, H_raw))
        H = H_clamped / LN_5 if LN_5 > 0 else 0.0
    else:
        raise ValueError(f"Invalid entropy mode: {entropy_mode}")

    H = max(0.0, min(1.0, H))

    entropy_audit = EntropyWiringAudit(
        entropy_mode=entropy_mode.value,
        H_raw=H_raw,
        H_normalized=H,
    )

    # Compute M
    M, motion_audit = compute_M(
        semantic_delta=delta_sem,
        structural_delta=delta_str_norm,
        experiential_delta=delta_exp,
        mode=motion_mode,
        weights=weights,
    )

    # Create config snapshot
    config_snapshot = {
        "entropy_mode": entropy_mode.value,
        "motion_mode": motion_mode.value,
    }
    if weights is not None:
        config_snapshot["composite_weights"] = {
            "w1": weights[0],
            "w2": weights[1],
            "w3": weights[2],
        }

    audit = SignalWiringAudit(
        entropy_audit=entropy_audit,
        motion_audit=motion_audit,
        operator_config_snapshot=config_snapshot,
    )

    return WiredSignals(H=H, M=M, audit=audit)
