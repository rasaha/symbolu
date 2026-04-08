"""
Sovereign Insight Gate — Pure-Function Extractions (Phase S2).

Float-friendly, PyTorch-free versions of the InsightGate gating logic
extracted from insight_gate.py. These can be consumed by the governance
pipeline for bounded validation/enrichment.

Extracted pieces:
- InsightGateConfig (re-exported, already a pure dataclass)
- calculate_stability_pure(): STAB score from floats
- calculate_risk_pure(): RISK score from floats
- check_eligibility_pure(): deterministic eligibility check
- check_release_pure(): deterministic release check
- compute_surfacing_penalty_pure(): bounded penalty from gate state
- run_insight_gate_pure(): full two-stage gate in one call

The original nn.Module InsightGate in insight_gate.py remains untouched
for training-side use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


# Re-export the config dataclass (it's already pure Python)
# but redefine here to avoid importing from insight_gate.py
# which imports torch at module level.

@dataclass
class InsightGateConfig:
    """Configuration for the Insight Gate (pure copy, no torch import)."""
    stability_threshold: float = 0.78
    risk_threshold: float = 0.25

    # Stability weights (Formula [259])
    w_r: float = 0.35
    w_gc: float = 0.30
    w_s: float = 0.20
    w_d: float = 0.15

    # Risk weights
    risk_w_gc: float = 0.50
    risk_w_drift: float = 0.30
    risk_w_auth: float = 0.20

    # Accuracy requirements
    r_acc_min: float = 0.92
    s_acc_min: float = 0.85

    # Vritti modes that allow insight release (PRAMANA=0, SMRTI=3)
    allowed_vritti: Tuple[int, ...] = (0, 3)

    # Guna coherence minimum
    guna_coherence_min: float = 0.70

    # Drift normalization
    d_max_initial: float = 1.0


# =========================================================================
# Pure-function gate computations
# =========================================================================

def calculate_stability_pure(
    *,
    r_acc: float,
    s_acc: float,
    guna_coherence: float,
    drift: float,
    d_max: float = 1.0,
    config: Optional[InsightGateConfig] = None,
) -> float:
    """Calculate System Stability Score (STAB) — Formula [259].

    STAB = w_r * R_acc + w_gc * GC + w_s * S_acc + w_d * (1 - drift/D_max)

    All inputs are plain floats. Returns clamped [0, 1].
    """
    if config is None:
        config = InsightGateConfig()

    d_max_safe = max(d_max, 0.1)
    drift_norm = max(0.0, min(1.0, drift / d_max_safe))

    stab = (
        config.w_r * r_acc
        + config.w_gc * guna_coherence
        + config.w_s * s_acc
        + config.w_d * (1.0 - drift_norm)
    )
    return max(0.0, min(1.0, stab))


def calculate_risk_pure(
    *,
    guna_coherence: float,
    drift: float,
    authority: float,
    d_max: float = 1.0,
    config: Optional[InsightGateConfig] = None,
) -> float:
    """Calculate Disruption Risk (RISK) score.

    RISK = 0.5 * (1 - GC) + 0.3 * (drift/D_max) + 0.2 * (1 - authority)

    All inputs are plain floats. Returns clamped [0, 1].
    """
    if config is None:
        config = InsightGateConfig()

    d_max_safe = max(d_max, 0.1)
    drift_norm = max(0.0, min(1.0, drift / d_max_safe))

    risk = (
        config.risk_w_gc * (1.0 - guna_coherence)
        + config.risk_w_drift * drift_norm
        + config.risk_w_auth * (1.0 - authority)
    )
    return max(0.0, min(1.0, risk))


def check_eligibility_pure(
    *,
    stab_score: float,
    r_acc: float,
    s_acc: float,
    vritti: int,
    guna_coherence: float,
    config: Optional[InsightGateConfig] = None,
) -> bool:
    """Stage 1: Deterministic eligibility check.

    Eligibility requires all of:
    - STAB >= stability_threshold
    - R_acc >= r_acc_min
    - S_acc >= s_acc_min
    - Vritti in allowed modes
    - Guna coherence >= guna_coherence_min
    """
    if config is None:
        config = InsightGateConfig()

    return (
        stab_score >= config.stability_threshold
        and r_acc >= config.r_acc_min
        and s_acc >= config.s_acc_min
        and vritti in config.allowed_vritti
        and guna_coherence >= config.guna_coherence_min
    )


def check_release_pure(
    *,
    eligible: bool,
    risk_score: float,
    config: Optional[InsightGateConfig] = None,
) -> bool:
    """Stage 2: Deterministic release check.

    Release requires eligibility AND risk <= threshold.
    """
    if config is None:
        config = InsightGateConfig()
    return eligible and risk_score <= config.risk_threshold


def compute_surfacing_penalty_pure(
    *,
    can_release: bool,
    stab_score: float,
    token_entropy: float,
    lambda_insight: float = 0.5,
    entropy_threshold: float = 5.0,
) -> float:
    """Compute surfacing penalty (Formula [1195]).

    penalty = lambda * (1 - STAB) when trying to be creative without stability.
    Returns 0.0 when release is allowed or entropy is below threshold.
    """
    if can_release:
        return 0.0
    if token_entropy <= entropy_threshold:
        return 0.0
    return lambda_insight * (1.0 - stab_score)


# =========================================================================
# Full two-stage gate (convenience wrapper)
# =========================================================================

@dataclass(frozen=True)
class InsightGateResult:
    """Result of a pure insight gate evaluation."""
    eligible: bool
    can_release: bool
    stab_score: float
    risk_score: float
    reason_codes: Tuple[str, ...]

    def to_audit_dict(self) -> Dict[str, object]:
        """Serialize for governance audit."""
        return {
            "insight_eligible": self.eligible,
            "insight_can_release": self.can_release,
            "insight_stab_score": round(self.stab_score, 4),
            "insight_risk_score": round(self.risk_score, 4),
            "insight_reason_codes": list(self.reason_codes),
        }


def run_insight_gate_pure(
    *,
    r_acc: float = 0.5,
    s_acc: float = 0.5,
    guna_coherence: float = 0.5,
    drift: float = 0.0,
    authority: float = 1.0,
    vritti: int = 0,
    d_max: float = 1.0,
    config: Optional[InsightGateConfig] = None,
) -> InsightGateResult:
    """Run the full two-stage insight gate on plain floats.

    This is the primary entry point for governance consumption.
    Returns a structured InsightGateResult with eligibility, release
    decision, scores, and reason codes.
    """
    if config is None:
        config = InsightGateConfig()

    stab = calculate_stability_pure(
        r_acc=r_acc, s_acc=s_acc, guna_coherence=guna_coherence,
        drift=drift, d_max=d_max, config=config,
    )
    risk = calculate_risk_pure(
        guna_coherence=guna_coherence, drift=drift, authority=authority,
        d_max=d_max, config=config,
    )
    eligible = check_eligibility_pure(
        stab_score=stab, r_acc=r_acc, s_acc=s_acc,
        vritti=vritti, guna_coherence=guna_coherence, config=config,
    )
    can_release = check_release_pure(
        eligible=eligible, risk_score=risk, config=config,
    )

    # Build reason codes
    codes: list[str] = []
    if not eligible:
        if stab < config.stability_threshold:
            codes.append(f"STAB_LOW:{stab:.3f}<{config.stability_threshold}")
        if r_acc < config.r_acc_min:
            codes.append(f"R_ACC_LOW:{r_acc:.3f}<{config.r_acc_min}")
        if s_acc < config.s_acc_min:
            codes.append(f"S_ACC_LOW:{s_acc:.3f}<{config.s_acc_min}")
        if vritti not in config.allowed_vritti:
            codes.append(f"VRITTI_BLOCKED:{vritti}")
        if guna_coherence < config.guna_coherence_min:
            codes.append(f"GC_LOW:{guna_coherence:.3f}<{config.guna_coherence_min}")
    elif not can_release:
        codes.append(f"RISK_HIGH:{risk:.3f}>{config.risk_threshold}")

    return InsightGateResult(
        eligible=eligible,
        can_release=can_release,
        stab_score=stab,
        risk_score=risk,
        reason_codes=tuple(codes),
    )
