"""
Policy Utility Computation for SymbolU v2.7
============================================

Computes the policy utility U_t and target state θ*_t using
closed-form deterministic formulas.

This is NOT ethics. It is policy-aligned operational utility.

Version: 2.7.1
Date: 2025-12-22
"""

from dataclasses import dataclass
from typing import Tuple, Optional

from agentic.guna_modulation.state_types import (
    StateRegister,
    StateBounds,
    DEFAULT_BOUNDS,
    DEFAULT_STATE,
    softmax_3,
    clip,
    EPSILON,
)
from agentic.guna_modulation.observables import Observables
from agentic.guna_modulation.v27_config import (
    UtilityCoefficients,
    ToneLogitConfig,
    DEFAULT_UTILITY_COEFFICIENTS,
    DEFAULT_TONE_CONFIG,
)


# =============================================================================
# Legacy Constants (for backward compatibility)
# =============================================================================

# These are preserved for backward compatibility with tests
# New code should use UtilityCoefficients and ToneLogitConfig
LAMBDA_H: float = 0.3   # Entropy penalty magnitude
LAMBDA_C: float = 0.5   # Contradiction penalty magnitude
LAMBDA_F: float = 0.4   # Failure penalty magnitude

# 768-skip threshold coefficients
A1: float = 0.1   # Utility influence on skip threshold
A2: float = 0.05  # Entropy influence on skip threshold

# 175B escalation threshold coefficients
B1: float = 0.08  # Low utility triggers easier escalation
B2: float = 0.1   # Contradiction triggers easier escalation


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
    guna_term: float  # c_S×w_S×s + c_R×w_R×r + c_T×w_T×t

    # Penalty terms
    entropy_penalty: float       # λ_H × H
    contradiction_penalty: float # λ_C × C_contr
    failure_penalty: float       # λ_F × F_fail

    # Final utility
    utility: float  # U_t

    # Coefficients used (for audit)
    coefficients_used: str = "default"

    @property
    def total_penalties(self) -> float:
        """Sum of all penalty terms."""
        return self.entropy_penalty + self.contradiction_penalty + self.failure_penalty


def compute_utility(
    observables: Observables,
    state: StateRegister,
    coefficients: Optional[UtilityCoefficients] = None,
) -> Tuple[float, UtilityAudit]:
    """
    Compute policy utility U_t.

    Formula (with configurable signs):
        U_t = (c_S × w_S × s + c_R × w_R × r + c_T × w_T × t)
              + λ_H × H + λ_C × C_contr + λ_F × F_fail

    Args:
        observables: Observable signals from pipeline
        state: Current state register (provides guna weights)
        coefficients: Utility coefficients (default: DEFAULT_UTILITY_COEFFICIENTS)

    Returns:
        (U_t, UtilityAudit) tuple
    """
    if coefficients is None:
        coefficients = DEFAULT_UTILITY_COEFFICIENTS

    # Guna contribution (with configurable signs)
    guna_term = coefficients.compute_guna_term(
        s=observables.s,
        r=observables.r,
        t=observables.t,
        w_S=state.w_S,
        w_R=state.w_R,
        w_T=state.w_T,
    )

    # Penalty terms (using coefficients)
    entropy_penalty = coefficients.lambda_H * observables.H
    contradiction_penalty = coefficients.lambda_C * observables.C_contr
    failure_penalty = coefficients.lambda_F * observables.F_fail

    # Total utility
    utility = guna_term + entropy_penalty + contradiction_penalty + failure_penalty

    audit = UtilityAudit(
        guna_term=guna_term,
        entropy_penalty=entropy_penalty,
        contradiction_penalty=contradiction_penalty,
        failure_penalty=failure_penalty,
        utility=utility,
        coefficients_used="custom" if coefficients != DEFAULT_UTILITY_COEFFICIENTS else "default",
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

    # Config used
    tone_config_used: str = "default"


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
    tone_config: Optional[ToneLogitConfig] = None,
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """
    Compute target tone weights w^tone*.

    Formula (with named coefficients):
        ℓ_sweet = k_sweet_sattva × s - k_sweet_tamas × t
        ℓ_jolt = k_jolt_rajas × r + k_jolt_contr × C_contr
        ℓ_metaphor = k_metaphor_entropy × H + k_metaphor_rajas × r

        w^tone* = softmax([ℓ_sweet, ℓ_jolt, ℓ_metaphor])

    Args:
        observables: Observable signals
        tone_config: Tone logit configuration (default: DEFAULT_TONE_CONFIG)

    Returns:
        (w_tone_target, logits) tuple
    """
    if tone_config is None:
        tone_config = DEFAULT_TONE_CONFIG

    # Compute logits using named config
    logits = tone_config.compute_logits(
        s=observables.s,
        r=observables.r,
        t=observables.t,
        H=observables.H,
        C_contr=observables.C_contr,
    )

    # Apply softmax
    w_tone_target = softmax_3(logits)

    return w_tone_target, logits


def compute_target_state(
    observables: Observables,
    utility: float,
    current_state: StateRegister,
    bounds: StateBounds = DEFAULT_BOUNDS,
    tone_config: Optional[ToneLogitConfig] = None,
) -> Tuple[StateRegister, TargetStateAudit]:
    """
    Compute complete target state θ*.

    Combines all target computation formulas.

    Args:
        observables: Observable signals
        utility: Computed utility U_t
        current_state: Current state (for guna weights)
        bounds: State bounds
        tone_config: Tone logit configuration

    Returns:
        (target_state, audit) tuple
    """
    if tone_config is None:
        tone_config = DEFAULT_TONE_CONFIG

    # Compute individual targets
    tau_768_target = compute_target_tau_768(
        utility, observables.H, bounds=bounds
    )
    tau_175_target = compute_target_tau_175(
        utility, observables.C_contr, bounds=bounds
    )
    w_tone_target, logits = compute_target_w_tone(observables, tone_config)

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
        tone_config_used="custom" if tone_config != DEFAULT_TONE_CONFIG else "default",
    )

    return target_state, audit
