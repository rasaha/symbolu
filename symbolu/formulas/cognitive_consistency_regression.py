"""
Cognitive Consistency Regression Engine (CCRE) v1.0 - Phase 50

Deterministic, zero-LLM, observation-only regression engine that measures how stable
and self-consistent all Phase 35-49 predictive and stability metrics are over time.

This engine performs multi-window regression analysis over historical signals to detect:
- Regression stability (how stable regression patterns are across windows)
- Regression drift (how much signals are drifting vs stabilizing)
- Cross-signal alignment (how well signals agree with each other)
- Prediction reversal risk (whether slope directions flip between windows)
- Internal consistency strength (composite consistency metric)

CCRE is the final "internal cognition stability" check before RAG (Phase 51).

This engine analyzes regression patterns across:
- Phase 35: Predictive Persona Drift
- Phase 36: Identity Resonance Memory
- Phase 37: Adaptive Continuity Engine
- Phase 38: Temporal Coherence Forecasting
- Phase 39: Multi-Horizon Temporal Forecasting
- Phase 42: Scenario Fusion Engine
- Phase 44: Coherence-Scenario Alignment
- Phase 46: Trajectory Field Convergence
- Phase 47: Unified Trajectory-Scenario Synthesis
- Phase 48: Macro-Stability Regulator
- Phase 49: Unified Cross-Phase Temporal Stability

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Metadata-only persona integration: NO tone or semantic changes
    - Diagnostics/UI only: Feeds coherence state, session summary, unified API, and DILchat badges
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Fully bounded: All outputs [0.0, 1.0]
    - Graceful degradation: Returns None if insufficient data (<3 non-empty signals)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Any, Dict, Tuple
import math


@dataclass
class CognitiveConsistencyRegressionSnapshot:
    """
    Immutable snapshot of Cognitive Consistency Regression Engine computation.

    This snapshot measures how stable and self-consistent Phase 35-49 predictive
    and stability metrics are over time via multi-window regression analysis.

    Fields:
        regression_stability_index (RSI): [0.0, 1.0] - how stable regression patterns are across windows
        regression_drift_score (CDR): [0.0, 1.0] - how much signals are drifting vs stabilizing
        regression_alignment_score (CLRA): [0.0, 1.0] - cross-signal agreement
        prediction_reversal_risk (PRR): [0.0, 1.0] - whether slope directions flip between windows
        internal_consistency_strength (ICS): [0.0, 1.0] - composite consistency metric
        band: Consistency classification: "high_consistency" | "medium_consistency" | "low_consistency" | "internal_conflict"
        diagnostic_tags: List of diagnostic pattern indicators
        metadata: Optional extra info (e.g., window sizes, counts)
    """

    regression_stability_index: float = 0.0  # RSI [0.0, 1.0]
    regression_drift_score: float = 0.0  # CDR [0.0, 1.0]
    regression_alignment_score: float = 0.0  # CLRA [0.0, 1.0]
    prediction_reversal_risk: float = 0.0  # PRR [0.0, 1.0]
    internal_consistency_strength: float = 0.0  # ICS [0.0, 1.0]
    band: str = "low_consistency"
    diagnostic_tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp value to [min_val, max_val] range.

    Args:
        value: Value to clamp
        min_val: Minimum value (default 0.0)
        max_val: Maximum value (default 1.0)

    Returns:
        float: Clamped value
    """
    return max(min_val, min(max_val, value))


def _compute_mean(values: List[float]) -> float:
    """
    Compute mean of a list of values.

    Args:
        values: List of float values

    Returns:
        float: Mean value or 0.0 if empty
    """
    if not values:
        return 0.0
    return sum(values) / len(values)


def _compute_variance(values: List[float]) -> float:
    """
    Compute variance of a list of values.

    Args:
        values: List of float values

    Returns:
        float: Variance [0.0, ∞)
    """
    if not values or len(values) < 2:
        return 0.0

    mean = _compute_mean(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)

    return variance


def _compute_std_dev(values: List[float]) -> float:
    """
    Compute standard deviation of a list of values.

    Args:
        values: List of float values

    Returns:
        float: Standard deviation [0.0, ∞)
    """
    variance = _compute_variance(values)
    return math.sqrt(variance)


def _compute_linear_slope(values: List[float]) -> float:
    """
    Compute simple linear regression slope.

    Uses least-squares linear regression: slope = Cov(x,y) / Var(x)
    where x = [0, 1, 2, ..., n-1] and y = values

    Args:
        values: List of float values

    Returns:
        float: Slope value (can be positive, negative, or zero)
    """
    if not values or len(values) < 2:
        return 0.0

    n = len(values)
    x = list(range(n))

    # Compute means
    x_mean = sum(x) / n
    y_mean = sum(values) / n

    # Compute covariance and variance
    cov = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n)) / n
    var_x = sum((xi - x_mean) ** 2 for xi in x) / n

    if var_x == 0:
        return 0.0

    slope = cov / var_x
    return slope


def _compute_window_regression_stats(
    signal_history: List[float],
    window_sizes: List[int],
) -> Dict[str, Any]:
    """
    Compute regression statistics (slope, variance) for multiple window sizes.

    Args:
        signal_history: List of historical signal values
        window_sizes: List of window sizes to analyze (e.g., [3, 5, 10, 20])

    Returns:
        Dict with 'slopes', 'variances', 'mean_slope', 'slope_variance', 'slope_reversal'
    """
    if not signal_history or len(signal_history) < 3:
        return {
            "slopes": [],
            "variances": [],
            "mean_slope": 0.0,
            "slope_variance": 0.0,
            "slope_reversal": False,
        }

    slopes = []
    variances = []

    for window_size in window_sizes:
        if len(signal_history) >= window_size:
            # Take the last 'window_size' values
            window_values = signal_history[-window_size:]
            slope = _compute_linear_slope(window_values)
            variance = _compute_variance(window_values)

            slopes.append(slope)
            variances.append(variance)

    # Compute statistics
    mean_slope = _compute_mean(slopes) if slopes else 0.0
    slope_variance = _compute_variance(slopes) if len(slopes) >= 2 else 0.0

    # Detect slope reversal (short-term vs long-term direction flip)
    slope_reversal = False
    if len(slopes) >= 2:
        # Check if shortest window slope has opposite sign from longest window slope
        short_slope = slopes[0]
        long_slope = slopes[-1]
        if (short_slope > 0 and long_slope < 0) or (short_slope < 0 and long_slope > 0):
            slope_reversal = True

    return {
        "slopes": slopes,
        "variances": variances,
        "mean_slope": mean_slope,
        "slope_variance": slope_variance,
        "slope_reversal": slope_reversal,
    }


def compute_cognitive_consistency_regression(
    *,
    drift_history: Optional[Sequence[float]] = None,
    identity_history: Optional[Sequence[float]] = None,
    continuity_history: Optional[Sequence[float]] = None,
    single_horizon_history: Optional[Sequence[float]] = None,
    multi_horizon_history: Optional[Sequence[float]] = None,
    scenario_fusion_history: Optional[Sequence[float]] = None,
    scenario_alignment_history: Optional[Sequence[float]] = None,
    trajectory_convergence_history: Optional[Sequence[float]] = None,
    unified_synthesis_history: Optional[Sequence[float]] = None,
    macro_stability_history: Optional[Sequence[float]] = None,
    unified_temporal_stability_history: Optional[Sequence[float]] = None,
) -> Optional[CognitiveConsistencyRegressionSnapshot]:
    """
    Compute Cognitive Consistency Regression Engine (CCRE) v1.0.

    This function performs multi-window regression analysis over Phase 35-49 metrics
    to measure cognitive consistency and detect prediction reversals.

    Args:
        drift_history: Phase 35 drift magnitude history
        identity_history: Phase 36 identity drift anchoring (IDA) history
        continuity_history: Phase 37 continuity stability score (CSS) history
        single_horizon_history: Phase 38 forecast strength history
        multi_horizon_history: Phase 39 future stability envelope (FSE) history
        scenario_fusion_history: Phase 42 scenario alignment history
        scenario_alignment_history: Phase 44 alignment score history
        trajectory_convergence_history: Phase 46 convergence index history
        unified_synthesis_history: Phase 47 synthesis integrity history
        macro_stability_history: Phase 48 macro-stability index history
        unified_temporal_stability_history: Phase 49 temporal stability index history

    Returns:
        CognitiveConsistencyRegressionSnapshot or None if insufficient data

    Formula Design:
        - Multi-window regression analysis (windows: 3, 5, 10, 20 if available)
        - For each signal: compute slope and variance per window
        - Regression Stability Index (RSI): how stable regression patterns are
        - Regression Drift Score (CDR): how much signals are drifting
        - Regression Alignment Score (CLRA): cross-signal agreement
        - Prediction Reversal Risk (PRR): slope direction flips
        - Internal Consistency Strength (ICS): composite consistency

        Band Classification:
            * high_consistency: ICS >= 0.70 and PRR <= 0.35
            * medium_consistency: ICS >= 0.50 and PRR <= 0.60
            * low_consistency: ICS >= 0.35 or PRR <= 0.75
            * internal_conflict: ICS < 0.35 and PRR > 0.75

    Graceful Degradation:
        Returns None if fewer than 3 non-empty signal histories or too little data.
    """
    # ========================================================================
    # STEP 1: COLLECT AND VALIDATE SIGNAL HISTORIES
    # ========================================================================

    # Collect all non-empty signal histories
    signal_histories = []
    signal_names = []

    if drift_history and len(drift_history) >= 3:
        signal_histories.append(list(drift_history))
        signal_names.append("drift")

    if identity_history and len(identity_history) >= 3:
        signal_histories.append(list(identity_history))
        signal_names.append("identity")

    if continuity_history and len(continuity_history) >= 3:
        signal_histories.append(list(continuity_history))
        signal_names.append("continuity")

    if single_horizon_history and len(single_horizon_history) >= 3:
        signal_histories.append(list(single_horizon_history))
        signal_names.append("single_horizon")

    if multi_horizon_history and len(multi_horizon_history) >= 3:
        signal_histories.append(list(multi_horizon_history))
        signal_names.append("multi_horizon")

    if scenario_fusion_history and len(scenario_fusion_history) >= 3:
        signal_histories.append(list(scenario_fusion_history))
        signal_names.append("scenario_fusion")

    if scenario_alignment_history and len(scenario_alignment_history) >= 3:
        signal_histories.append(list(scenario_alignment_history))
        signal_names.append("scenario_alignment")

    if trajectory_convergence_history and len(trajectory_convergence_history) >= 3:
        signal_histories.append(list(trajectory_convergence_history))
        signal_names.append("trajectory_convergence")

    if unified_synthesis_history and len(unified_synthesis_history) >= 3:
        signal_histories.append(list(unified_synthesis_history))
        signal_names.append("unified_synthesis")

    if macro_stability_history and len(macro_stability_history) >= 3:
        signal_histories.append(list(macro_stability_history))
        signal_names.append("macro_stability")

    if unified_temporal_stability_history and len(unified_temporal_stability_history) >= 3:
        signal_histories.append(list(unified_temporal_stability_history))
        signal_names.append("unified_temporal_stability")

    # Need at least 3 non-empty signals for meaningful regression
    if len(signal_histories) < 3:
        return None

    # ========================================================================
    # STEP 2: DEFINE WINDOW SIZES FOR MULTI-WINDOW ANALYSIS
    # ========================================================================

    # Determine available window sizes based on shortest history
    min_history_length = min(len(h) for h in signal_histories)

    # Define window sizes: [3, 5, 10, 20] but only use those <= min_history_length
    available_windows = []
    for window_size in [3, 5, 10, 20]:
        if window_size <= min_history_length:
            available_windows.append(window_size)

    # Need at least 2 windows for meaningful multi-window analysis
    if len(available_windows) < 2:
        available_windows = [min_history_length]  # Use single window as fallback

    # ========================================================================
    # STEP 3: COMPUTE REGRESSION STATISTICS FOR EACH SIGNAL
    # ========================================================================

    all_signal_stats = []

    for signal_history in signal_histories:
        stats = _compute_window_regression_stats(signal_history, available_windows)
        all_signal_stats.append(stats)

    # ========================================================================
    # STEP 4: COMPUTE REGRESSION STABILITY INDEX (RSI)
    # ========================================================================

    # RSI measures how stable regression patterns are across windows and signals
    # High RSI = low variance in slopes across windows (consistent trends)

    # Collect all slope variances
    slope_variances = [stats["slope_variance"] for stats in all_signal_stats]

    # Normalize slope variances to [0, 1]
    # Lower variance = higher stability
    if slope_variances:
        mean_slope_variance = _compute_mean(slope_variances)
        # Normalize: typical slope variance for [0,1] bounded signals is ~0.01-0.1
        # We'll use 0.1 as max expected variance
        normalized_variance = min(mean_slope_variance / 0.1, 1.0)
        regression_stability_index = 1.0 - normalized_variance
        regression_stability_index = _clamp(regression_stability_index, 0.0, 1.0)
    else:
        regression_stability_index = 0.5  # Default moderate

    # ========================================================================
    # STEP 5: COMPUTE REGRESSION DRIFT SCORE (CDR)
    # ========================================================================

    # CDR measures how much signals are drifting (changing) vs stabilizing
    # High CDR = high absolute slopes (signals changing rapidly)

    # Collect all mean slopes
    mean_slopes = [stats["mean_slope"] for stats in all_signal_stats]

    # Compute average absolute slope magnitude
    if mean_slopes:
        avg_abs_slope = _compute_mean([abs(slope) for slope in mean_slopes])
        # Normalize: typical slope for [0,1] bounded signals over 10 turns is ~0.1
        # We'll use 0.2 as max expected slope
        regression_drift_score = min(avg_abs_slope / 0.2, 1.0)
        regression_drift_score = _clamp(regression_drift_score, 0.0, 1.0)
    else:
        regression_drift_score = 0.5  # Default moderate

    # ========================================================================
    # STEP 6: COMPUTE REGRESSION ALIGNMENT SCORE (CLRA)
    # ========================================================================

    # CLRA measures cross-signal agreement (how aligned slopes are)
    # High CLRA = low variance in slopes across signals (all moving same direction)

    if len(mean_slopes) >= 2:
        slope_std_dev = _compute_std_dev(mean_slopes)
        # Normalize: max std dev for slopes in [-0.2, 0.2] is ~0.2
        normalized_std_dev = min(slope_std_dev / 0.2, 1.0)
        regression_alignment_score = 1.0 - normalized_std_dev
        regression_alignment_score = _clamp(regression_alignment_score, 0.0, 1.0)
    else:
        regression_alignment_score = 0.5  # Default moderate

    # ========================================================================
    # STEP 7: COMPUTE PREDICTION REVERSAL RISK (PRR)
    # ========================================================================

    # PRR measures whether slope directions flip between windows
    # (e.g., short-term up vs long-term down)
    # High PRR = many signals have slope reversals

    reversal_count = sum(1 for stats in all_signal_stats if stats["slope_reversal"])
    total_signals = len(all_signal_stats)

    if total_signals > 0:
        prediction_reversal_risk = reversal_count / total_signals
        prediction_reversal_risk = _clamp(prediction_reversal_risk, 0.0, 1.0)
    else:
        prediction_reversal_risk = 0.5  # Default moderate

    # ========================================================================
    # STEP 8: COMPUTE INTERNAL CONSISTENCY STRENGTH (ICS)
    # ========================================================================

    # ICS is a composite consistency metric combining:
    # - High stability (high RSI)
    # - Low drift (low CDR)
    # - High alignment (high CLRA)
    # - Low reversal risk (low PRR)

    ics = (
        0.30 * regression_stability_index +
        0.25 * (1.0 - regression_drift_score) +
        0.25 * regression_alignment_score +
        0.20 * (1.0 - prediction_reversal_risk)
    )
    internal_consistency_strength = _clamp(ics, 0.0, 1.0)

    # ========================================================================
    # STEP 9: CLASSIFY BAND
    # ========================================================================

    if internal_consistency_strength >= 0.70 and prediction_reversal_risk <= 0.35:
        band = "high_consistency"
    elif internal_consistency_strength >= 0.50 and prediction_reversal_risk <= 0.60:
        band = "medium_consistency"
    elif internal_consistency_strength >= 0.35 or prediction_reversal_risk <= 0.75:
        band = "low_consistency"
    else:
        band = "internal_conflict"

    # ========================================================================
    # STEP 10: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    tags = []

    # Stability tags
    if regression_stability_index >= 0.75:
        tags.append("regression_stable")
    elif regression_stability_index <= 0.35:
        tags.append("regression_unstable")
    else:
        tags.append("regression_caution")

    # Drift tags
    if regression_drift_score >= 0.70:
        tags.append("high_drift")
    elif regression_drift_score <= 0.30:
        tags.append("low_drift")

    # Alignment tags
    if regression_alignment_score >= 0.70:
        tags.append("multi_window_alignment_strong")
    elif regression_alignment_score <= 0.35:
        tags.append("multi_window_alignment_weak")

    # Reversal risk tags
    if prediction_reversal_risk >= 0.60:
        tags.append("reversal_risk_high")
    elif prediction_reversal_risk <= 0.25:
        tags.append("reversal_risk_low")

    # Consistency strength tags
    if internal_consistency_strength >= 0.75:
        tags.append("consistency_strong")
    elif internal_consistency_strength <= 0.35:
        tags.append("consistency_weak")

    # Band tags
    if band == "high_consistency":
        tags.append("cognitive_consistency_optimal")
    elif band == "internal_conflict":
        tags.append("regression_conflict")

    # Pattern tags based on combinations
    if (regression_stability_index >= 0.70 and
        regression_alignment_score >= 0.70 and
        prediction_reversal_risk <= 0.30):
        tags.append("regression_consensus")

    if (regression_drift_score >= 0.70 and
        prediction_reversal_risk >= 0.60):
        tags.append("regression_volatile")

    if (internal_consistency_strength >= 0.70 and
        regression_drift_score <= 0.35):
        tags.append("regression_stabilizing")

    if len(signal_histories) >= 8:
        tags.append("data_rich_regression")
    elif len(signal_histories) <= 3:
        tags.append("data_sparse_regression")

    # Sort and deduplicate for determinism
    tags = sorted(set(tags))

    # ========================================================================
    # STEP 11: BUILD METADATA
    # ========================================================================

    metadata = {
        "num_signals": len(signal_histories),
        "signal_names": signal_names,
        "window_sizes": available_windows,
        "min_history_length": min_history_length,
    }

    # ========================================================================
    # STEP 12: RETURN SNAPSHOT
    # ========================================================================

    return CognitiveConsistencyRegressionSnapshot(
        regression_stability_index=regression_stability_index,
        regression_drift_score=regression_drift_score,
        regression_alignment_score=regression_alignment_score,
        prediction_reversal_risk=prediction_reversal_risk,
        internal_consistency_strength=internal_consistency_strength,
        band=band,
        diagnostic_tags=tags,
        metadata=metadata,
    )
