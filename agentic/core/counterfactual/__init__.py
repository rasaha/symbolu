"""
P25 - Counterfactual Sandbox Core Module

Phase 25 provides a counterfactual simulation sandbox for bounded perturbation
analysis. It answers one question only:

    "If certain cognitive inputs were different, how would coherence and
    stability respond - hypothetically?"

This module:
    - Simulates alternative internal states
    - Computes delta-effects on existing truth metrics
    - Never selects, recommends, or predicts outcomes

It is a sandbox, not a planner.

Usage:
    from agentic.core.counterfactual import (
        CounterfactualScenario,
        CounterfactualSandboxReport,
        run_sandbox,
        summarize_report,
    )

    # Create scenarios
    scenarios = [
        CounterfactualScenario(
            scenario_id="coherence_drop",
            delta_coherence=-0.2,
        ),
        CounterfactualScenario(
            scenario_id="drift_spike",
            delta_drift=0.3,
        ),
    ]

    # Run sandbox
    report = run_sandbox(
        scenarios=scenarios,
        baseline_coherence=0.7,
        baseline_drift=0.3,
        baseline_entropy=0.2,
    )

    # Analyze results
    summary = summarize_report(report)

CRITICAL INVARIANTS:
    - INV-P25-1: Sandbox outputs are observational only
    - INV-P25-2: No mutation of PipelineContext
    - INV-P25-3: Counterfactuals never imply recommendations
    - INV-P25-4: UCF is recomputed, never overridden
    - INV-P25-5: No forward prediction allowed
"""

from agentic.core.counterfactual.cf_schema import (
    # Version
    P25_VERSION,
    # Constants
    DELTA_MIN,
    DELTA_MAX,
    STABILITY_DROP_THRESHOLD,
    ENTROPY_SPIKE_THRESHOLD,
    DRIFT_ACCELERATION_THRESHOLD,
    UCF_THRESHOLD_CROSS_STABLE,
    UCF_THRESHOLD_CROSS_TRANSITIONAL,
    # Dataclasses
    CounterfactualScenario,
    CounterfactualResult,
    CounterfactualSandboxReport,
    # Helpers
    clamp,
    create_scenario,
    create_result,
    create_report,
)

from agentic.core.counterfactual.cf_engine import (
    # Core functions
    compute_adjusted_value,
    detect_risk_flags,
    simulate_scenario,
    run_sandbox,
    # Convenience functions
    simulate_single_scenario,
    verify_sandbox_determinism,
)

from agentic.core.counterfactual.cf_analyzer import (
    # Analysis functions
    analyze_ucf_sensitivity,
    analyze_stability_transitions,
    analyze_risk_flags,
    summarize_report,
    find_boundary_scenarios,
    compute_delta_distribution,
    # Filter functions
    filter_results_by_flag,
    filter_results_by_band_change,
    # Comparison functions
    compare_scenarios,
)


__all__ = [
    # Version
    "P25_VERSION",
    # Constants
    "DELTA_MIN",
    "DELTA_MAX",
    "STABILITY_DROP_THRESHOLD",
    "ENTROPY_SPIKE_THRESHOLD",
    "DRIFT_ACCELERATION_THRESHOLD",
    "UCF_THRESHOLD_CROSS_STABLE",
    "UCF_THRESHOLD_CROSS_TRANSITIONAL",
    # Dataclasses
    "CounterfactualScenario",
    "CounterfactualResult",
    "CounterfactualSandboxReport",
    # Schema helpers
    "clamp",
    "create_scenario",
    "create_result",
    "create_report",
    # Engine functions
    "compute_adjusted_value",
    "detect_risk_flags",
    "simulate_scenario",
    "run_sandbox",
    "simulate_single_scenario",
    "verify_sandbox_determinism",
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
