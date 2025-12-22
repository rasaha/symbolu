"""
Policy Utility Computation for SymbolU v2.7
============================================

Computes the policy utility U_t and target state θ*_t using
closed-form deterministic formulas.

This is NOT ethics. It is policy-aligned operational utility.

Version: 2.7
Date: 2025-12-22
"""

from dataclasses import dataclass
from typing import Tuple

from symbolu.guna_modulation.state_types import (
    StateRegister,
    StateBounds,
    DEFAULT_BOUNDS,
    DEFAULT_STATE,
    softmax_3,
    clip,
    EPSILON,
)
from symbolu.guna_modulation.observables import Observables


# =============================================================================
# Fixed Constants (NOT configurable per-run)
# =============================================================================

# Utility penalty coefficients
LAMBDA_H: float = 0.3   # Entropy penalty
LAMBDA_C: float = 0.5   # Contradiction penalty
LAMBDA_F: float = 0.4   # Failure penalty

# 768-skip threshold coefficients
A1: float = 0.1   # Utility influence on skip threshold
A2: float = 0.05  # Entropy influence on skip threshold

# 175B escalation threshold coefficients
B1: float = 0.08  # Low utility triggers easier escalation
B2: float = 0.1   # Contradiction triggers easier escalation

# Tone weight logit coefficients
K1: float = 1.0   # Sattva promotes sweetness
K2: float = 0.5   # Tamas reduces sweetness
K3: float = 0.8   # Rajas promotes jolt
K4: float = 0.3   # Contradiction promotes jolt
K5: float = 0.6   # Entropy promotes metaphor
K6: float = 0.4   # Rajas also promotes metaphor


# =============================================================================
# Utility Computation
# =============================================================================

@dataclass(frozen=True)
class UtilityAudit:
    """
    Audit trail for utility computation.

    Shows all components that contributed to U_t.
    """
    # Guna contribution
    guna_term: float  # w_S × s - w_R × r - w_T × t

    # Penalty terms (all negative contributions)
    entropy_penalty: float    # -λ_H × H
    contradiction_penalty: float  # -λ_C × C_contr
    failure_penalty: float    # -λ_F × F_fail

    # Final utility
    utility: float  # U_t

    @property
    def total_penalties(self) -> float:
        """Sum of all penalty terms."""
        return self.entropy_penalty + self.contradiction_penalty + self.failure_penalty


def compute_utility(
    observables: Observables,
    state: StateRegister,
) -> Tuple[float, UtilityAudit]:
    """
    Compute policy utility U_t.

    Formula:
        U_t = w_S × s - w_R × r - w_T × t
              - λ_H × H
              - λ_C × C_contr
              - λ_F × F_fail

    Args:
        observables: Observable signals from pipeline
        state: Current state register (provides guna weights)

    Returns:
        (U_t, UtilityAudit) tuple
    """
    # Guna contribution (weighted by state preferences)
    guna_term = (
        state.w_S * observables.s -
        state.w_R * observables.r -
        state.w_T * observables.t
    )

    # Penalty terms
    entropy_penalty = -LAMBDA_H * observables.H
    contradiction_penalty = -LAMBDA_C * observables.C_contr
    failure_penalty = -LAMBDA_F * observables.F_fail

    # Total utility
    utility = guna_term + entropy_penalty + contradiction_penalty + failure_penalty

    audit = UtilityAudit(
        guna_term=guna_term,
        entropy_penalty=entropy_penalty,
        contradiction_penalty=contradiction_penalty,
        failure_penalty=failure_penalty,
        utility=utility,
    )

    return utility, audit


# =============================================================================
# Target State Computation
# =============================================================================

@dataclass(frozen=True)
class TargetStateAudit:
    """
    Audit trail for target state computation.

    Shows how each target component was computed.
    """
    # Computed targets
    tau_768_target: float
    tau_175_target: float
    w_tone_target: Tuple[float, float, float]

    # Intermediate values for tone computation
    logit_sweet: float
    logit_jolt: float
    logit_metaphor: float


def compute_target_tau_768(
    utility: float,
    entropy: float,
    default_tau: float = DEFAULT_STATE.tau_768,
    bounds: StateBounds = DEFAULT_BOUNDS,
) -> float:
    """
    Compute target τ^768*.

    Formula:
        τ^768* = clip(τ^768_0 + a₁ × U - a₂ × H, [min, max])

    Higher utility → more aggressive skipping
    Higher entropy → more conservative (lower threshold)
    """
    raw = default_tau + A1 * utility - A2 * entropy
    return bounds.clip_tau_768(raw)


def compute_target_tau_175(
    utility: float,
    contradiction: float,
    default_tau: float = DEFAULT_STATE.tau_175,
    bounds: StateBounds = DEFAULT_BOUNDS,
) -> float:
    """
    Compute target τ^175*.

    Formula:
        τ^175* = clip(τ^175_0 - b₁ × (1 - U) - b₂ × C_contr, [min, max])

    Lower utility → lower threshold → easier escalation
    Higher contradiction → lower threshold → easier escalation
    """
    raw = default_tau - B1 * (1 - utility) - B2 * contradiction
    return bounds.clip_tau_175(raw)


def compute_target_w_tone(
    observables: Observables,
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """
    Compute target tone weights w^tone*.

    Formula:
        ℓ_sweet = k₁ × s - k₂ × t
        ℓ_jolt = k₃ × r + k₄ × C_contr
        ℓ_metaphor = k₅ × H + k₆ × r

        w^tone* = softmax([ℓ_sweet, ℓ_jolt, ℓ_metaphor])

    Returns:
        (w_tone_target, logits) tuple
    """
    # Compute logits
    logit_sweet = K1 * observables.s - K2 * observables.t
    logit_jolt = K3 * observables.r + K4 * observables.C_contr
    logit_metaphor = K5 * observables.H + K6 * observables.r

    # Apply softmax
    w_tone_target = softmax_3((logit_sweet, logit_jolt, logit_metaphor))

    return w_tone_target, (logit_sweet, logit_jolt, logit_metaphor)


def compute_target_state(
    observables: Observables,
    utility: float,
    current_state: StateRegister,
    bounds: StateBounds = DEFAULT_BOUNDS,
) -> Tuple[StateRegister, TargetStateAudit]:
    """
    Compute complete target state θ*.

    Combines all target computation formulas.

    Args:
        observables: Observable signals
        utility: Computed utility U_t
        current_state: Current state (for guna weights)
        bounds: State bounds

    Returns:
        (target_state, audit) tuple
    """
    # Compute individual targets
    tau_768_target = compute_target_tau_768(
        utility, observables.H, bounds=bounds
    )
    tau_175_target = compute_target_tau_175(
        utility, observables.C_contr, bounds=bounds
    )
    w_tone_target, logits = compute_target_w_tone(observables)

    # Compute policy bias delta (small, bounded)
    # δ_policy = sign(U) × min(|U|, 0.01)
    delta_policy = (1 if utility > 0 else -1) * min(abs(utility), 0.01)
    b_policy_target = bounds.clip_b_policy(delta_policy)

    # Construct target state
    target_state = StateRegister(
        tau_768=tau_768_target,
        tau_175=tau_175_target,
        w_tone=w_tone_target,
        w_guna=current_state.w_guna,  # w_guna only changes via config, not evolution
        b_policy=b_policy_target,
    )

    audit = TargetStateAudit(
        tau_768_target=tau_768_target,
        tau_175_target=tau_175_target,
        w_tone_target=w_tone_target,
        logit_sweet=logits[0],
        logit_jolt=logits[1],
        logit_metaphor=logits[2],
    )

    return target_state, audit
