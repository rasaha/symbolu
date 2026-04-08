"""
P25 - Counterfactual Sandbox Analyzer

Analysis utilities for counterfactual sandbox results.

This module provides helper functions for analyzing and summarizing
counterfactual simulation results. All functions are pure and deterministic.

CRITICAL: This module MUST NOT:
    - Make predictions
    - Provide recommendations
    - Influence any decisions
    - Trigger any actions

It is for observational analysis only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from agentic.core.counterfactual.cf_schema import (
    CounterfactualScenario,
    CounterfactualResult,
    CounterfactualSandboxReport,
)


# ============================================================================
# PURE ANALYSIS FUNCTIONS - No state, no side effects
# ============================================================================


def analyze_ucf_sensitivity(
    report: CounterfactualSandboxReport,
) -> Dict[str, Any]:
    """
    Analyze UCF sensitivity to counterfactual perturbations.

    This is a pure, observational function. It does not make predictions
    or recommendations.

    Args:
        report: The sandbox report to analyze

    Returns:
        Dictionary with sensitivity metrics:
        - max_negative_impact: Largest negative UCF change
        - max_positive_impact: Largest positive UCF change
        - sensitivity_range: Total range of UCF changes
        - most_sensitive_scenario: ID of scenario with largest |delta|
        - least_sensitive_scenario: ID of scenario with smallest |delta|
    """
    if not report.results:
        return {
            "max_negative_impact": 0.0,
            "max_positive_impact": 0.0,
            "sensitivity_range": 0.0,
            "most_sensitive_scenario": None,
            "least_sensitive_scenario": None,
        }

    # Find extremes
    deltas = [(r.scenario_id, r.ucf_delta) for r in report.results]

    max_negative = min(d[1] for d in deltas)
    max_positive = max(d[1] for d in deltas)
    sensitivity_range = max_positive - max_negative

    # Find most/least sensitive scenarios by absolute delta
    abs_deltas = [(r.scenario_id, abs(r.ucf_delta)) for r in report.results]
    most_sensitive = max(abs_deltas, key=lambda x: x[1])
    least_sensitive = min(abs_deltas, key=lambda x: x[1])

    return {
        "max_negative_impact": max_negative,
        "max_positive_impact": max_positive,
        "sensitivity_range": sensitivity_range,
        "most_sensitive_scenario": most_sensitive[0],
        "least_sensitive_scenario": least_sensitive[0],
    }


def analyze_stability_transitions(
    report: CounterfactualSandboxReport,
) -> Dict[str, Any]:
    """
    Analyze stability band transitions across scenarios.

    This is a pure, observational function. It reports what transitions
    would occur, not what should be done about them.

    Args:
        report: The sandbox report to analyze

    Returns:
        Dictionary with transition metrics:
        - transitions_count: Number of scenarios causing band changes
        - stable_to_transitional: Count of stable -> transitional
        - transitional_to_unstable: Count of transitional -> unstable
        - unstable_to_transitional: Count of unstable -> transitional
        - transitional_to_stable: Count of transitional -> stable
        - transition_scenarios: List of scenario IDs causing transitions
    """
    if not report.results:
        return {
            "transitions_count": 0,
            "stable_to_transitional": 0,
            "transitional_to_unstable": 0,
            "unstable_to_transitional": 0,
            "transitional_to_stable": 0,
            "transition_scenarios": [],
        }

    transitions = {
        "stable_to_transitional": 0,
        "transitional_to_unstable": 0,
        "unstable_to_transitional": 0,
        "transitional_to_stable": 0,
        "stable_to_unstable": 0,
        "unstable_to_stable": 0,
    }

    transition_scenarios: List[str] = []

    for result in report.results:
        before = result.stability_band_before
        after = result.stability_band_after

        if before != after:
            transition_scenarios.append(result.scenario_id)

            key = f"{before}_to_{after}"
            if key in transitions:
                transitions[key] += 1

    return {
        "transitions_count": len(transition_scenarios),
        "stable_to_transitional": transitions["stable_to_transitional"],
        "transitional_to_unstable": transitions["transitional_to_unstable"],
        "unstable_to_transitional": transitions["unstable_to_transitional"],
        "transitional_to_stable": transitions["transitional_to_stable"],
        "stable_to_unstable": transitions["stable_to_unstable"],
        "unstable_to_stable": transitions["unstable_to_stable"],
        "transition_scenarios": transition_scenarios,
    }


def analyze_risk_flags(
    report: CounterfactualSandboxReport,
) -> Dict[str, Any]:
    """
    Analyze risk flag distribution across scenarios.

    This is a pure, observational function. It reports flag occurrences,
    not recommendations.

    Args:
        report: The sandbox report to analyze

    Returns:
        Dictionary with risk flag metrics:
        - total_flagged_scenarios: Count of scenarios with any flags
        - flag_counts: Dict mapping flag name to occurrence count
        - most_common_flag: Flag that appears most frequently
        - flagged_scenario_ids: List of scenario IDs with flags
    """
    if not report.results:
        return {
            "total_flagged_scenarios": 0,
            "flag_counts": {},
            "most_common_flag": None,
            "flagged_scenario_ids": [],
        }

    flag_counts: Dict[str, int] = {}
    flagged_scenario_ids: List[str] = []

    for result in report.results:
        if result.has_risk_flags():
            flagged_scenario_ids.append(result.scenario_id)

        for flag in result.risk_flags:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1

    most_common_flag = None
    if flag_counts:
        most_common_flag = max(flag_counts, key=flag_counts.get)

    return {
        "total_flagged_scenarios": len(flagged_scenario_ids),
        "flag_counts": flag_counts,
        "most_common_flag": most_common_flag,
        "flagged_scenario_ids": flagged_scenario_ids,
    }


def summarize_report(
    report: CounterfactualSandboxReport,
) -> Dict[str, Any]:
    """
    Generate a comprehensive summary of a sandbox report.

    This combines all analysis functions into a single summary.
    It is purely observational and makes no recommendations.

    Args:
        report: The sandbox report to summarize

    Returns:
        Dictionary with complete summary:
        - baseline: Baseline metrics
        - sensitivity: UCF sensitivity analysis
        - transitions: Stability band transition analysis
        - risk_flags: Risk flag distribution
        - scenario_count: Total scenarios simulated
    """
    return {
        "baseline": {
            "ucf": report.baseline_ucf,
            "stability_band": report.baseline_stability_band,
        },
        "sensitivity": analyze_ucf_sensitivity(report),
        "transitions": analyze_stability_transitions(report),
        "risk_flags": analyze_risk_flags(report),
        "scenario_count": report.scenario_count(),
        "max_negative_delta": report.max_negative_delta,
        "max_positive_delta": report.max_positive_delta,
        "observer_only": True,
    }


def find_boundary_scenarios(
    report: CounterfactualSandboxReport,
) -> Dict[str, List[str]]:
    """
    Find scenarios that cross stability boundaries.

    This identifies which scenarios cause transitions between
    stable/transitional/unstable bands.

    Args:
        report: The sandbox report to analyze

    Returns:
        Dictionary mapping transition type to scenario IDs:
        - crossing_to_stable: Scenarios that cross into stable band
        - crossing_to_transitional: Scenarios that cross into transitional band
        - crossing_to_unstable: Scenarios that cross into unstable band
    """
    crossing_to_stable: List[str] = []
    crossing_to_transitional: List[str] = []
    crossing_to_unstable: List[str] = []

    for result in report.results:
        before = result.stability_band_before
        after = result.stability_band_after

        if before != after:
            if after == "stable":
                crossing_to_stable.append(result.scenario_id)
            elif after == "transitional":
                crossing_to_transitional.append(result.scenario_id)
            elif after == "unstable":
                crossing_to_unstable.append(result.scenario_id)

    return {
        "crossing_to_stable": crossing_to_stable,
        "crossing_to_transitional": crossing_to_transitional,
        "crossing_to_unstable": crossing_to_unstable,
    }


def compute_delta_distribution(
    report: CounterfactualSandboxReport,
) -> Dict[str, Any]:
    """
    Compute distribution statistics for UCF deltas.

    This is a pure observational function providing descriptive statistics.

    Args:
        report: The sandbox report to analyze

    Returns:
        Dictionary with distribution statistics:
        - count: Number of scenarios
        - min: Minimum UCF delta
        - max: Maximum UCF delta
        - mean: Mean UCF delta
        - positive_count: Count of positive deltas
        - negative_count: Count of negative deltas
        - zero_count: Count of zero deltas
    """
    if not report.results:
        return {
            "count": 0,
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "positive_count": 0,
            "negative_count": 0,
            "zero_count": 0,
        }

    deltas = [r.ucf_delta for r in report.results]

    positive_count = sum(1 for d in deltas if d > 0)
    negative_count = sum(1 for d in deltas if d < 0)
    zero_count = sum(1 for d in deltas if d == 0)

    return {
        "count": len(deltas),
        "min": min(deltas),
        "max": max(deltas),
        "mean": sum(deltas) / len(deltas),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "zero_count": zero_count,
    }


def filter_results_by_flag(
    report: CounterfactualSandboxReport,
    flag: str,
) -> List[CounterfactualResult]:
    """
    Filter results to only those containing a specific risk flag.

    Args:
        report: The sandbox report to filter
        flag: The risk flag to filter by

    Returns:
        List of CounterfactualResult that have the specified flag
    """
    return [r for r in report.results if r.has_flag(flag)]


def filter_results_by_band_change(
    report: CounterfactualSandboxReport,
    from_band: Optional[str] = None,
    to_band: Optional[str] = None,
) -> List[CounterfactualResult]:
    """
    Filter results by stability band transition.

    Args:
        report: The sandbox report to filter
        from_band: Filter to only this starting band (optional)
        to_band: Filter to only this ending band (optional)

    Returns:
        List of CounterfactualResult matching the criteria
    """
    results: List[CounterfactualResult] = []

    for r in report.results:
        # Skip if no band change and we're filtering for changes
        if from_band or to_band:
            if r.stability_band_before == r.stability_band_after:
                continue

        # Filter by from_band if specified
        if from_band and r.stability_band_before != from_band:
            continue

        # Filter by to_band if specified
        if to_band and r.stability_band_after != to_band:
            continue

        results.append(r)

    return results


def compare_scenarios(
    result1: CounterfactualResult,
    result2: CounterfactualResult,
) -> Dict[str, Any]:
    """
    Compare two counterfactual results.

    This is a pure observational function for comparing scenario outcomes.

    Args:
        result1: First result to compare
        result2: Second result to compare

    Returns:
        Dictionary with comparison metrics:
        - ucf_delta_difference: Difference in UCF deltas
        - both_change_band: Whether both scenarios change the stability band
        - shared_flags: Flags present in both results
        - unique_flags_1: Flags only in result1
        - unique_flags_2: Flags only in result2
    """
    flags1 = set(result1.risk_flags)
    flags2 = set(result2.risk_flags)

    return {
        "ucf_delta_difference": result1.ucf_delta - result2.ucf_delta,
        "both_change_band": (
            result1.band_changed() and result2.band_changed()
        ),
        "shared_flags": list(flags1 & flags2),
        "unique_flags_1": list(flags1 - flags2),
        "unique_flags_2": list(flags2 - flags1),
    }


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================

__all__ = [
    # Analysis functions
    "analyze_ucf_sensitivity",
    "analyze_stability_transitions",
    "analyze_risk_flags",
    "summarize_report",
    "find_boundary_scenarios",
    "compute_delta_distribution",
    # Filter functions
    "filter_results_by_flag",
    "filter_results_by_band_change",
    # Comparison functions
    "compare_scenarios",
]
