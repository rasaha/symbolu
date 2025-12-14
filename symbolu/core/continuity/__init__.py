"""
Phase 37 - Adaptive Continuity Engine

P37 is an observation-only phase that computes whether the user's identity
trajectory is continuous, oscillating, or fragmenting over time, using
historical resonance memory + predictive drift.

P37 answers: "Is the identity evolution smooth, strained, or breaking?"

It:
- Computes continuity scores
- Classifies continuity mode (stable/strained/fragmenting)
- Detects oscillation patterns
- Emits explanatory tags

It does NOT:
- Predict behavior
- Influence regime, discourse, semantics, or tone
- Gate insights or actions
- Modify persona behavior

INVARIANTS:
    - INV-P37-1: Deterministic (same input -> same output)
    - INV-P37-2: No imports from governance, persona, DHA, renderer
    - INV-P37-3: Output never influences routing or gating
    - INV-P37-4: continuity_score is monotonic w.r.t inputs
    - INV-P37-5: No observer feeds upstream

Usage:
    from symbolu.core.continuity import (
        AdaptiveContinuityReport,
        compute_adaptive_continuity,
        compute_continuity_score,
        compute_continuity_pressure,
        compute_continuity_mode,
        detect_oscillation,
    )

    # Compute continuity report from P35 and P36 inputs
    report = compute_adaptive_continuity(
        p35_predicted_drift_score=0.30,
        p35_drift_risk_band="low",
        p36_identity_resonance_index=0.75,
        p36_persistence_score=0.80,
        p36_volatility_index=0.20,
        historical_resonance_values=[0.70, 0.72, 0.75, 0.78, 0.75],
    )

    # Access outputs
    print(report.continuity_score)      # [0.0, 1.0]
    print(report.continuity_mode)       # "stable" | "strained" | "fragmenting"
    print(report.continuity_pressure)   # [0.0, 1.0]
    print(report.oscillation_detected)  # True | False
    print(report.contributing_factors)  # tuple of tags
"""

from symbolu.core.continuity.continuity_models import (
    # Version
    P37_VERSION,
    # Constants
    W_PERSISTENCE,
    W_INVERSE_VOLATILITY,
    W_INVERSE_DRIFT,
    MODE_STABLE_THRESHOLD,
    MODE_STRAINED_THRESHOLD,
    OSCILLATION_VOLATILITY_THRESHOLD,
    OSCILLATION_MIN_REVERSALS,
    OSCILLATION_WINDOW_SIZE,
    HIGH_DRIFT_THRESHOLD,
    LOW_PERSISTENCE_THRESHOLD,
    HIGH_VOLATILITY_THRESHOLD,
    ALLOWED_CONTRIBUTING_FACTORS,
    # Dataclass
    AdaptiveContinuityReport,
    # Model helpers
    create_report,
    mode_from_score,
    create_empty_report,
)

from symbolu.core.continuity.adaptive_continuity_engine import (
    # Helpers
    clamp,
    safe_get,
    # Core formulas
    compute_continuity_score,
    compute_continuity_pressure,
    compute_continuity_mode,
    count_direction_reversals,
    detect_oscillation,
    compute_contributing_factors,
    # Main function
    compute_adaptive_continuity,
)


__all__ = [
    # Version
    "P37_VERSION",
    # Constants
    "W_PERSISTENCE",
    "W_INVERSE_VOLATILITY",
    "W_INVERSE_DRIFT",
    "MODE_STABLE_THRESHOLD",
    "MODE_STRAINED_THRESHOLD",
    "OSCILLATION_VOLATILITY_THRESHOLD",
    "OSCILLATION_MIN_REVERSALS",
    "OSCILLATION_WINDOW_SIZE",
    "HIGH_DRIFT_THRESHOLD",
    "LOW_PERSISTENCE_THRESHOLD",
    "HIGH_VOLATILITY_THRESHOLD",
    "ALLOWED_CONTRIBUTING_FACTORS",
    # Dataclass
    "AdaptiveContinuityReport",
    # Model helpers
    "create_report",
    "mode_from_score",
    "create_empty_report",
    # Engine helpers
    "clamp",
    "safe_get",
    # Core formulas
    "compute_continuity_score",
    "compute_continuity_pressure",
    "compute_continuity_mode",
    "count_direction_reversals",
    "detect_oscillation",
    "compute_contributing_factors",
    # Main function
    "compute_adaptive_continuity",
]
