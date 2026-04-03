"""
Guna Derivation Formulas
========================

CANONICAL RUNTIME GUNA DERIVATION
===================================
This is the canonical source for runtime pipeline-level guna computation.
All runtime paths needing (S, R, T) from (C_s, M, H) should call
derive_guna_vector() or derive_guna_from_values() from this module.

Symbol-U v2.6 - Deterministic, Zero-Parameter, Non-Learning System

This module implements the MANDATORY Guna derivation formulas.
All formulas are closed-form and deterministic.

FORMULAS IMPLEMENTED:

Raw Guna Components:
    S_raw = C_s * (1 - H)
    R_raw = M * (1 - |H - H_mid|)
    T_raw = H * (1 - C_s)

Normalization:
    Z = S_raw + R_raw + T_raw + epsilon
    S = S_raw / Z
    R = R_raw / Z
    T = T_raw / Z

Constraint: S + R + T = 1

Where:
    C_s: Structural coherence [0,1]
    M: Motion / transformation magnitude [0,1]
    H: Entropy [0,1]
    H_mid = 0.5
    epsilon = 10^-9

EXPLICIT NON-CAPABILITIES:
    - No learning
    - No adaptation
    - No state memory
    - No evaluation of "better" or "worse"
    - No psychology
    - No morality
    - No feedback loops
    - No preference formation

All computations are purely mathematical.

Version: 2.6.0
Date: 2025-12-22
"""

from typing import Tuple

from symbolu.guna_modulation.types import (
    H_MID,
    EPSILON,
    GunaVector,
    PipelineInputs,
    ModulationTraceEntry,
)


# =============================================================================
# Raw Guna Component Computation
# =============================================================================

def compute_sattva_raw(C_s: float, H: float) -> float:
    """
    Compute raw Sattva component.

    Formula: S_raw = C_s * (1 - H)

    Sattva emerges from high structural coherence with low entropy.

    Args:
        C_s: Structural coherence [0.0, 1.0]
        H: Entropy [0.0, 1.0]

    Returns:
        Raw Sattva value (unnormalized)

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    return C_s * (1.0 - H)


def compute_rajas_raw(M: float, H: float) -> float:
    """
    Compute raw Rajas component.

    Formula: R_raw = M * (1 - |H - H_mid|)

    Rajas emerges from high motion when entropy is near midpoint.
    Maximum Rajas occurs when H = H_mid (entropy at equilibrium).

    Args:
        M: Motion / transformation magnitude [0.0, 1.0]
        H: Entropy [0.0, 1.0]

    Returns:
        Raw Rajas value (unnormalized)

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    entropy_distance = abs(H - H_MID)
    return M * (1.0 - entropy_distance)


def compute_tamas_raw(H: float, C_s: float) -> float:
    """
    Compute raw Tamas component.

    Formula: T_raw = H * (1 - C_s)

    Tamas emerges from high entropy with low structural coherence.

    Args:
        H: Entropy [0.0, 1.0]
        C_s: Structural coherence [0.0, 1.0]

    Returns:
        Raw Tamas value (unnormalized)

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    return H * (1.0 - C_s)


# =============================================================================
# Normalization
# =============================================================================

def normalize_guna_components(
    S_raw: float,
    R_raw: float,
    T_raw: float,
) -> Tuple[float, float, float, float]:
    """
    Normalize raw Guna components to sum to 1.0.

    Formula:
        Z = S_raw + R_raw + T_raw + epsilon
        S = S_raw / Z
        R = R_raw / Z
        T = T_raw / Z

    Constraint: S + R + T = 1

    Args:
        S_raw: Raw Sattva value
        R_raw: Raw Rajas value
        T_raw: Raw Tamas value

    Returns:
        Tuple of (S, R, T, Z) where S + R + T ≈ 1.0

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    Z = S_raw + R_raw + T_raw + EPSILON

    S = S_raw / Z
    R = R_raw / Z
    T = T_raw / Z

    return (S, R, T, Z)


# =============================================================================
# Main Guna Derivation Function
# =============================================================================

def derive_guna_vector(
    inputs: PipelineInputs,
) -> Tuple[GunaVector, Tuple[ModulationTraceEntry, ...]]:
    """
    Derive the Guna vector from pipeline inputs.

    This is the MANDATORY Guna derivation computation.
    No heuristics, classifiers, or substitutions are allowed.

    Formulas:
        S_raw = C_s * (1 - H)
        R_raw = M * (1 - |H - H_mid|)
        T_raw = H * (1 - C_s)

        Z = S_raw + R_raw + T_raw + epsilon

        S = S_raw / Z
        R = R_raw / Z
        T = T_raw / Z

    Args:
        inputs: Pipeline inputs (C_s, M, H)

    Returns:
        Tuple of:
            - GunaVector with normalized (S, R, T)
            - Audit trace entries

    Determinism Guarantee:
        Same inputs always produce same outputs.
    """
    # Extract inputs
    C_s = inputs.C_s
    M = inputs.M
    H = inputs.H

    # Compute raw components
    S_raw = compute_sattva_raw(C_s, H)
    R_raw = compute_rajas_raw(M, H)
    T_raw = compute_tamas_raw(H, C_s)

    # Normalize
    S, R, T, Z = normalize_guna_components(S_raw, R_raw, T_raw)

    # Create Guna vector
    guna_vector = GunaVector(sattva=S, rajas=R, tamas=T)

    # Build audit trace
    trace = (
        ModulationTraceEntry(
            step_name="sattva_raw",
            inputs=(("C_s", C_s), ("H", H)),
            output=S_raw,
            formula="S_raw = C_s * (1 - H)",
        ),
        ModulationTraceEntry(
            step_name="rajas_raw",
            inputs=(("M", M), ("H", H), ("H_mid", H_MID)),
            output=R_raw,
            formula="R_raw = M * (1 - |H - H_mid|)",
        ),
        ModulationTraceEntry(
            step_name="tamas_raw",
            inputs=(("H", H), ("C_s", C_s)),
            output=T_raw,
            formula="T_raw = H * (1 - C_s)",
        ),
        ModulationTraceEntry(
            step_name="normalization",
            inputs=(
                ("S_raw", S_raw),
                ("R_raw", R_raw),
                ("T_raw", T_raw),
                ("epsilon", EPSILON),
            ),
            output=Z,
            formula="Z = S_raw + R_raw + T_raw + epsilon",
        ),
        ModulationTraceEntry(
            step_name="guna_vector",
            inputs=(("S_raw/Z", S), ("R_raw/Z", R), ("T_raw/Z", T)),
            output=S + R + T,  # Should be ~1.0
            formula="g = [S_raw/Z, R_raw/Z, T_raw/Z]",
        ),
    )

    return (guna_vector, trace)


# =============================================================================
# Convenience Functions
# =============================================================================

def derive_guna_from_values(
    C_s: float,
    M: float,
    H: float,
) -> GunaVector:
    """
    Convenience function to derive Guna vector from raw values.

    Args:
        C_s: Structural coherence [0.0, 1.0]
        M: Motion / transformation magnitude [0.0, 1.0]
        H: Entropy [0.0, 1.0]

    Returns:
        GunaVector with normalized (S, R, T)

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    inputs = PipelineInputs(C_s=C_s, M=M, H=H)
    guna_vector, _ = derive_guna_vector(inputs)
    return guna_vector


def derive_guna_with_trace(
    C_s: float,
    M: float,
    H: float,
) -> Tuple[GunaVector, Tuple[ModulationTraceEntry, ...]]:
    """
    Derive Guna vector with full audit trace.

    Args:
        C_s: Structural coherence [0.0, 1.0]
        M: Motion / transformation magnitude [0.0, 1.0]
        H: Entropy [0.0, 1.0]

    Returns:
        Tuple of (GunaVector, trace)

    Determinism Guarantee:
        Same inputs always produce same output.
    """
    inputs = PipelineInputs(C_s=C_s, M=M, H=H)
    return derive_guna_vector(inputs)
