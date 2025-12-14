"""
P25 - Counterfactual Sandbox Pipeline Integration

Phase 25 provides a counterfactual simulation sandbox that answers:
"If certain cognitive inputs were different, how would coherence and
stability respond - hypothetically?"

This phase:
    - Simulates alternative internal states
    - Computes delta-effects on existing truth metrics
    - Never selects, recommends, or predicts outcomes

It is a sandbox, not a planner.

Usage:
    from symbolu.mechanical.pipeline.p25_counterfactual import (
        maybe_run_p25,
        run_p25_directly,
        CounterfactualScenario,
    )

    # Create scenarios
    scenarios = [
        CounterfactualScenario(
            scenario_id="coherence_drop",
            delta_coherence=-0.2,
        ),
    ]

    # Run in pipeline context
    maybe_run_p25(ctx, scenarios)

    # Or run directly for testing
    report = run_p25_directly(
        scenarios=scenarios,
        baseline_coherence=0.7,
    )

CRITICAL INVARIANTS:
    - INV-P25-1: Sandbox outputs are observational only
    - INV-P25-2: No mutation of PipelineContext
    - INV-P25-3: Counterfactuals never imply recommendations
    - INV-P25-4: UCF is recomputed, never overridden
    - INV-P25-5: No forward prediction allowed
"""

# Re-export schema types from core module
from symbolu.core.counterfactual.cf_schema import (
    P25_VERSION,
    CounterfactualScenario,
    CounterfactualResult,
    CounterfactualSandboxReport,
    create_scenario,
    create_result,
    create_report,
)

# Re-export engine functions from core module
from symbolu.core.counterfactual.cf_engine import (
    run_sandbox,
    simulate_scenario,
    simulate_single_scenario,
    verify_sandbox_determinism,
)

# Re-export analyzer functions from core module
from symbolu.core.counterfactual.cf_analyzer import (
    summarize_report,
    analyze_ucf_sensitivity,
    analyze_stability_transitions,
    analyze_risk_flags,
)

# Export integration functions
from symbolu.mechanical.pipeline.p25_counterfactual.p25_integration import (
    maybe_run_p25,
    run_p25_directly,
    is_p25_disabled,
    has_p25_report,
    get_p25_report,
    get_baseline_ucf,
    get_max_negative_delta,
    get_max_positive_delta,
    get_scenario_count,
    has_any_risk_flags,
    has_any_band_changes,
    get_p25_version,
)


__all__ = [
    # Version
    "P25_VERSION",
    # Schema types
    "CounterfactualScenario",
    "CounterfactualResult",
    "CounterfactualSandboxReport",
    # Schema helpers
    "create_scenario",
    "create_result",
    "create_report",
    # Engine functions
    "run_sandbox",
    "simulate_scenario",
    "simulate_single_scenario",
    "verify_sandbox_determinism",
    # Analyzer functions
    "summarize_report",
    "analyze_ucf_sensitivity",
    "analyze_stability_transitions",
    "analyze_risk_flags",
    # Integration functions
    "maybe_run_p25",
    "run_p25_directly",
    "is_p25_disabled",
    "has_p25_report",
    "get_p25_report",
    "get_baseline_ucf",
    "get_max_negative_delta",
    "get_max_positive_delta",
    "get_scenario_count",
    "has_any_risk_flags",
    "has_any_band_changes",
    "get_p25_version",
]
