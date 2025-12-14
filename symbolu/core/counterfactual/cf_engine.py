"""
P25 - Counterfactual Sandbox Engine

Pure, deterministic computation engine for counterfactual simulations.

This module contains ONLY the mathematical computation of counterfactual
simulations. No state, no side effects, no LLM calls, no randomness.

The engine performs bounded perturbation analysis:
    - "If coherence dropped by X, what happens to UCF?"
    - "If drift increased, does stability cross a threshold?"

No semantic rewriting. No language. No prediction.

CRITICAL: This module MUST NOT import:
    - P6-P9 (regime, discourse, semantics, lexical)
    - P21 delivery logic
    - Renderer, DHA, Persona
    - Observer-only phases (P22-P24)
    - Acoustic/phonetic modules

This module MAY import:
    - P26 UCF formula (for recomputation)
    - Core formula utilities
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from symbolu.core.counterfactual.cf_schema import (
    P25_VERSION,
    STABILITY_DROP_THRESHOLD,
    ENTROPY_SPIKE_THRESHOLD,
    DRIFT_ACCELERATION_THRESHOLD,
    UCF_THRESHOLD_CROSS_STABLE,
    UCF_THRESHOLD_CROSS_TRANSITIONAL,
    CounterfactualScenario,
    CounterfactualResult,
    CounterfactualSandboxReport,
    clamp,
    create_result,
    create_report,
)

# Import UCF formula for recomputation (allowed per P25 spec)
from symbolu.core.consciousness.ucf_formula import (
    compute_ucf,
    compute_stability_band,
)
from symbolu.core.consciousness.ucf_schema import (
    StabilityBand,
    STABILITY_THRESHOLDS,
    NEUTRAL_DEFAULT,
)


# ============================================================================
# PURE FUNCTIONS - No state, no side effects
# ============================================================================


def compute_adjusted_value(
    baseline: Optional[float],
    delta: float,
    default: float = NEUTRAL_DEFAULT,
) -> float:
    """
    Compute an adjusted value by applying a delta to a baseline.

    This is a pure function. The result is always clamped to [0.0, 1.0].

    Args:
        baseline: Baseline value (may be None)
        delta: Delta to apply [-1.0, +1.0]
        default: Default value if baseline is None

    Returns:
        Adjusted value clamped to [0.0, 1.0]
    """
    base = baseline if baseline is not None else default
    return clamp(base + delta)


def detect_risk_flags(
    baseline_ucf: float,
    adjusted_ucf: float,
    baseline_coherence: float,
    adjusted_coherence: float,
    delta_entropy: float,
    delta_drift: float,
) -> List[str]:
    """
    Detect risk flags based on scenario effects.

    This is a pure, rule-based function. No heuristics.

    Args:
        baseline_ucf: UCF score before counterfactual
        adjusted_ucf: UCF score after counterfactual
        baseline_coherence: Coherence before counterfactual
        adjusted_coherence: Coherence after counterfactual
        delta_entropy: Applied entropy delta
        delta_drift: Applied drift delta

    Returns:
        List of risk flag strings (may be empty)
    """
    flags: List[str] = []

    # STABILITY_DROP: UCF dropped significantly
    ucf_drop = adjusted_ucf - baseline_ucf
    if ucf_drop < STABILITY_DROP_THRESHOLD:
        flags.append("STABILITY_DROP")

    # ENTROPY_SPIKE: Entropy increased significantly
    if delta_entropy > ENTROPY_SPIKE_THRESHOLD:
        flags.append("ENTROPY_SPIKE")

    # DRIFT_ACCELERATION: Drift increased significantly
    if delta_drift > DRIFT_ACCELERATION_THRESHOLD:
        flags.append("DRIFT_ACCELERATION")

    # UCF_THRESHOLD_CROSS: UCF crossed a stability threshold
    baseline_band = compute_stability_band(baseline_ucf)
    adjusted_band = compute_stability_band(adjusted_ucf)

    if baseline_band != adjusted_band:
        # Determine direction of crossing
        if (baseline_ucf >= UCF_THRESHOLD_CROSS_STABLE and
                adjusted_ucf < UCF_THRESHOLD_CROSS_STABLE):
            flags.append("UCF_THRESHOLD_CROSS")
        elif (baseline_ucf >= UCF_THRESHOLD_CROSS_TRANSITIONAL and
              adjusted_ucf < UCF_THRESHOLD_CROSS_TRANSITIONAL):
            flags.append("UCF_THRESHOLD_CROSS")
        elif (baseline_ucf < UCF_THRESHOLD_CROSS_TRANSITIONAL and
              adjusted_ucf >= UCF_THRESHOLD_CROSS_TRANSITIONAL):
            flags.append("UCF_THRESHOLD_CROSS")
        elif (baseline_ucf < UCF_THRESHOLD_CROSS_STABLE and
              adjusted_ucf >= UCF_THRESHOLD_CROSS_STABLE):
            flags.append("UCF_THRESHOLD_CROSS")

    return flags


def simulate_scenario(
    scenario: CounterfactualScenario,
    baseline_coherence: Optional[float],
    baseline_drift: Optional[float],
    baseline_entropy: Optional[float],
    baseline_schema_stability: Optional[float],
    baseline_identity_harmonics: Optional[float],
) -> Tuple[CounterfactualResult, float]:
    """
    Simulate a single counterfactual scenario.

    This is the core computation function. It:
    1. Applies deltas virtually (no mutation)
    2. Recomputes adjusted values
    3. Recomputes UCF using P26 formula
    4. Compares before vs after

    Args:
        scenario: The counterfactual scenario to simulate
        baseline_coherence: Baseline coherence_v3_quality
        baseline_drift: Baseline drift_fusion_index
        baseline_entropy: Baseline entropy_volatility
        baseline_schema_stability: Baseline schema_stability
        baseline_identity_harmonics: Baseline identity_harmonics_stability

    Returns:
        Tuple of (CounterfactualResult, adjusted_ucf)
    """
    debug: Dict[str, Any] = {}

    # ========================================================================
    # STEP 1: Compute baseline UCF
    # ========================================================================

    baseline_state = compute_ucf(
        coherence_v3_quality=baseline_coherence,
        drift_fusion_index=baseline_drift,
        entropy_volatility=baseline_entropy,
        schema_stability=baseline_schema_stability,
        identity_harmonics_stability=baseline_identity_harmonics,
    )
    baseline_ucf = baseline_state.ucf_score
    baseline_band = baseline_state.stability_band

    debug["baseline_ucf"] = baseline_ucf
    debug["baseline_band"] = baseline_band.value

    # ========================================================================
    # STEP 2: Compute adjusted values (virtual, no mutation)
    # ========================================================================

    adjusted_coherence = compute_adjusted_value(
        baseline_coherence, scenario.delta_coherence
    )
    adjusted_entropy = compute_adjusted_value(
        baseline_entropy, scenario.delta_entropy
    )
    adjusted_drift = compute_adjusted_value(
        baseline_drift, scenario.delta_drift
    )

    # Schema stability delta is optional
    if scenario.delta_schema_stability is not None:
        adjusted_schema = compute_adjusted_value(
            baseline_schema_stability, scenario.delta_schema_stability
        )
    else:
        adjusted_schema = baseline_schema_stability

    debug["adjusted_coherence"] = adjusted_coherence
    debug["adjusted_entropy"] = adjusted_entropy
    debug["adjusted_drift"] = adjusted_drift
    debug["adjusted_schema"] = adjusted_schema

    # ========================================================================
    # STEP 3: Recompute UCF with adjusted values
    # ========================================================================

    adjusted_state = compute_ucf(
        coherence_v3_quality=adjusted_coherence,
        drift_fusion_index=adjusted_drift,
        entropy_volatility=adjusted_entropy,
        schema_stability=adjusted_schema,
        identity_harmonics_stability=baseline_identity_harmonics,
    )
    adjusted_ucf = adjusted_state.ucf_score
    adjusted_band = adjusted_state.stability_band

    debug["adjusted_ucf"] = adjusted_ucf
    debug["adjusted_band"] = adjusted_band.value

    # ========================================================================
    # STEP 4: Compute deltas and detect risk flags
    # ========================================================================

    ucf_delta = adjusted_ucf - baseline_ucf
    coherence_delta = adjusted_coherence - (
        baseline_coherence if baseline_coherence is not None else NEUTRAL_DEFAULT
    )

    debug["ucf_delta"] = ucf_delta
    debug["coherence_delta"] = coherence_delta

    risk_flags = detect_risk_flags(
        baseline_ucf=baseline_ucf,
        adjusted_ucf=adjusted_ucf,
        baseline_coherence=(
            baseline_coherence if baseline_coherence is not None
            else NEUTRAL_DEFAULT
        ),
        adjusted_coherence=adjusted_coherence,
        delta_entropy=scenario.delta_entropy,
        delta_drift=scenario.delta_drift,
    )

    debug["risk_flags"] = risk_flags

    # ========================================================================
    # STEP 5: Create and return result
    # ========================================================================

    result = create_result(
        scenario_id=scenario.scenario_id,
        ucf_delta=ucf_delta,
        coherence_delta=coherence_delta,
        stability_band_before=baseline_band.value,
        stability_band_after=adjusted_band.value,
        risk_flags=risk_flags,
        debug=debug,
    )

    return result, adjusted_ucf


def run_sandbox(
    scenarios: List[CounterfactualScenario],
    baseline_coherence: Optional[float] = None,
    baseline_drift: Optional[float] = None,
    baseline_entropy: Optional[float] = None,
    baseline_schema_stability: Optional[float] = None,
    baseline_identity_harmonics: Optional[float] = None,
) -> CounterfactualSandboxReport:
    """
    Run the counterfactual sandbox with multiple scenarios.

    This is the main entry point for counterfactual analysis.
    It simulates all scenarios and produces a comprehensive report.

    Args:
        scenarios: List of CounterfactualScenario to simulate
        baseline_coherence: Baseline coherence_v3_quality
        baseline_drift: Baseline drift_fusion_index
        baseline_entropy: Baseline entropy_volatility
        baseline_schema_stability: Baseline schema_stability
        baseline_identity_harmonics: Baseline identity_harmonics_stability

    Returns:
        CounterfactualSandboxReport with all results
    """
    debug: Dict[str, Any] = {
        "inputs": {
            "baseline_coherence": baseline_coherence,
            "baseline_drift": baseline_drift,
            "baseline_entropy": baseline_entropy,
            "baseline_schema_stability": baseline_schema_stability,
            "baseline_identity_harmonics": baseline_identity_harmonics,
        },
        "scenario_count": len(scenarios),
    }

    # ========================================================================
    # STEP 1: Compute baseline UCF
    # ========================================================================

    baseline_state = compute_ucf(
        coherence_v3_quality=baseline_coherence,
        drift_fusion_index=baseline_drift,
        entropy_volatility=baseline_entropy,
        schema_stability=baseline_schema_stability,
        identity_harmonics_stability=baseline_identity_harmonics,
    )
    baseline_ucf = baseline_state.ucf_score
    baseline_band = baseline_state.stability_band

    debug["baseline_ucf"] = baseline_ucf
    debug["baseline_band"] = baseline_band.value

    # ========================================================================
    # STEP 2: Handle empty scenario list
    # ========================================================================

    if not scenarios:
        return create_report(
            baseline_ucf=baseline_ucf,
            baseline_stability_band=baseline_band.value,
            results=[],
            notes="No scenarios provided",
            debug=debug,
        )

    # ========================================================================
    # STEP 3: Simulate all scenarios
    # ========================================================================

    results: List[CounterfactualResult] = []

    for scenario in scenarios:
        result, _ = simulate_scenario(
            scenario=scenario,
            baseline_coherence=baseline_coherence,
            baseline_drift=baseline_drift,
            baseline_entropy=baseline_entropy,
            baseline_schema_stability=baseline_schema_stability,
            baseline_identity_harmonics=baseline_identity_harmonics,
        )
        results.append(result)

    debug["results_count"] = len(results)

    # ========================================================================
    # STEP 4: Create and return report
    # ========================================================================

    return create_report(
        baseline_ucf=baseline_ucf,
        baseline_stability_band=baseline_band.value,
        results=results,
        notes=None,
        debug=debug,
    )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def simulate_single_scenario(
    scenario: CounterfactualScenario,
    baseline_coherence: Optional[float] = None,
    baseline_drift: Optional[float] = None,
    baseline_entropy: Optional[float] = None,
    baseline_schema_stability: Optional[float] = None,
    baseline_identity_harmonics: Optional[float] = None,
) -> CounterfactualResult:
    """
    Convenience function to simulate a single scenario.

    Args:
        scenario: The counterfactual scenario to simulate
        baseline_coherence: Baseline coherence_v3_quality
        baseline_drift: Baseline drift_fusion_index
        baseline_entropy: Baseline entropy_volatility
        baseline_schema_stability: Baseline schema_stability
        baseline_identity_harmonics: Baseline identity_harmonics_stability

    Returns:
        CounterfactualResult for the scenario
    """
    result, _ = simulate_scenario(
        scenario=scenario,
        baseline_coherence=baseline_coherence,
        baseline_drift=baseline_drift,
        baseline_entropy=baseline_entropy,
        baseline_schema_stability=baseline_schema_stability,
        baseline_identity_harmonics=baseline_identity_harmonics,
    )
    return result


def verify_sandbox_determinism(
    scenarios: List[CounterfactualScenario],
    baseline_coherence: Optional[float] = None,
    baseline_drift: Optional[float] = None,
    baseline_entropy: Optional[float] = None,
    baseline_schema_stability: Optional[float] = None,
    baseline_identity_harmonics: Optional[float] = None,
    iterations: int = 10,
) -> Tuple[bool, CounterfactualSandboxReport]:
    """
    Verify sandbox is deterministic by running it multiple times.

    This is a testing utility to verify P25 determinism guarantees.

    Args:
        scenarios: List of scenarios to simulate
        All baseline parameters
        iterations: Number of times to run the sandbox

    Returns:
        Tuple of (is_deterministic, report)
        is_deterministic is True if all iterations produced identical results
    """
    reports = []
    for _ in range(iterations):
        report = run_sandbox(
            scenarios=scenarios,
            baseline_coherence=baseline_coherence,
            baseline_drift=baseline_drift,
            baseline_entropy=baseline_entropy,
            baseline_schema_stability=baseline_schema_stability,
            baseline_identity_harmonics=baseline_identity_harmonics,
        )
        reports.append(report)

    # Check all reports are identical
    if not reports:
        return True, create_report(
            baseline_ucf=0.5,
            baseline_stability_band="transitional",
            results=[],
        )

    first_report = reports[0]
    is_deterministic = True

    for report in reports[1:]:
        if report.baseline_ucf != first_report.baseline_ucf:
            is_deterministic = False
            break
        if report.max_negative_delta != first_report.max_negative_delta:
            is_deterministic = False
            break
        if report.max_positive_delta != first_report.max_positive_delta:
            is_deterministic = False
            break
        if len(report.results) != len(first_report.results):
            is_deterministic = False
            break
        for r1, r2 in zip(report.results, first_report.results):
            if r1.ucf_delta != r2.ucf_delta:
                is_deterministic = False
                break

    return is_deterministic, first_report


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================

__all__ = [
    # Core functions
    "compute_adjusted_value",
    "detect_risk_flags",
    "simulate_scenario",
    "run_sandbox",
    # Convenience functions
    "simulate_single_scenario",
    "verify_sandbox_determinism",
]
