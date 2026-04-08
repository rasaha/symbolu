"""
P25 - Counterfactual Sandbox Integration

Integration functions for running P25 within the pipeline.
Provides singleton access and pipeline-friendly entry points.

Usage:
    from symbolu_core.mechanical.pipeline.p25_counterfactual import (
        maybe_run_p25,
        run_p25_directly,
    )

    # In pipeline (with scenarios already defined):
    maybe_run_p25(ctx, scenarios)

    # Access sandbox report:
    if ctx.p25 is not None:
        print(f"Baseline UCF: {ctx.p25.baseline_ucf}")
        print(f"Max negative impact: {ctx.p25.max_negative_delta}")

CRITICAL: P25 is observation-only. The report MUST NOT be used for:
    - Routing decisions
    - Regime selection
    - Discourse determination
    - Semantic slot filling
    - Lexical selection
    - Delivery mode selection
    - Any behavioral modification
    - Prediction of future states
    - Recommendation of actions

Invariants:
    - INV-P25-1: Sandbox outputs are observational only
    - INV-P25-2: No mutation of PipelineContext
    - INV-P25-3: Counterfactuals never imply recommendations
    - INV-P25-4: UCF is recomputed, never overridden
    - INV-P25-5: No forward prediction allowed
"""

from __future__ import annotations

from typing import Any, List, Optional

from agentic.core.counterfactual.cf_schema import (
    P25_VERSION,
    CounterfactualScenario,
    CounterfactualSandboxReport,
    create_report,
)

from agentic.core.counterfactual.cf_engine import (
    run_sandbox,
)

from agentic.core.consciousness.ucf_schema import (
    NEUTRAL_DEFAULT,
)


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p25(
    ctx: Any,
    scenarios: List[CounterfactualScenario],
) -> Optional[CounterfactualSandboxReport]:
    """
    Run P25 Counterfactual Sandbox if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P25 should run (not disabled)
    2. Extracts baseline values from context
    3. Runs the sandbox with provided scenarios
    4. Attaches the report to ctx.p25 (WITHOUT modifying any authoritative state)

    P25 is designed to run after P18/P19/P26/P33 and after coherence computation.

    Args:
        ctx: PipelineContext or compatible object
        scenarios: List of CounterfactualScenario to simulate

    Returns:
        The CounterfactualSandboxReport if run, None if skipped

    Note:
        The returned report is observation-only and MUST NOT be used
        for any routing, behavioral, or predictive decisions.
    """
    # Check if P25 is disabled on this context
    if is_p25_disabled(ctx):
        return None

    # P25 requires at least some coherence data to be meaningful
    has_any_input = hasattr(ctx, "coherence_state") or hasattr(ctx, "p26")

    if not has_any_input:
        # Context has none of the expected attributes, skip P25
        return None

    try:
        # Extract baseline values from context
        baseline = _extract_baseline_from_context(ctx)

        # Run the sandbox
        report = run_sandbox(
            scenarios=scenarios,
            baseline_coherence=baseline["coherence"],
            baseline_drift=baseline["drift"],
            baseline_entropy=baseline["entropy"],
            baseline_schema_stability=baseline["schema_stability"],
            baseline_identity_harmonics=baseline["identity_harmonics"],
        )

        # Attach to context (observational only - no mutation of authority)
        _attach_to_context(ctx, report)

        return report

    except Exception:
        # P25 must not break the pipeline (INV-P25-5)
        # Return None on error - sandbox is optional
        return None


def run_p25_directly(
    scenarios: List[CounterfactualScenario],
    baseline_coherence: Optional[float] = None,
    baseline_drift: Optional[float] = None,
    baseline_entropy: Optional[float] = None,
    baseline_schema_stability: Optional[float] = None,
    baseline_identity_harmonics: Optional[float] = None,
) -> CounterfactualSandboxReport:
    """
    Run P25 directly with explicit inputs (for testing).

    This bypasses the context extraction and allows direct testing
    of the sandbox with explicit values.

    Args:
        scenarios: List of CounterfactualScenario to simulate
        baseline_coherence: Baseline coherence_v3_quality [0.0, 1.0]
        baseline_drift: Baseline drift_fusion_index [0.0, 1.0]
        baseline_entropy: Baseline entropy_volatility [0.0, 1.0]
        baseline_schema_stability: Baseline schema_stability [0.0, 1.0]
        baseline_identity_harmonics: Baseline identity_harmonics_stability [0.0, 1.0]

    Returns:
        CounterfactualSandboxReport with computed results
    """
    return run_sandbox(
        scenarios=scenarios,
        baseline_coherence=baseline_coherence,
        baseline_drift=baseline_drift,
        baseline_entropy=baseline_entropy,
        baseline_schema_stability=baseline_schema_stability,
        baseline_identity_harmonics=baseline_identity_harmonics,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p25_disabled(ctx: Any) -> bool:
    """
    Check if P25 is disabled on this context.

    P25 can be disabled by setting ctx._p25_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P25 is disabled, False otherwise
    """
    return getattr(ctx, "_p25_disabled", False)


def has_p25_report(ctx: Any) -> bool:
    """
    Check if context has a P25 report attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p25 is set and not None
    """
    return getattr(ctx, "p25", None) is not None


def get_p25_report(ctx: Any) -> Optional[CounterfactualSandboxReport]:
    """
    Get the P25 report from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The CounterfactualSandboxReport if present, None otherwise
    """
    return getattr(ctx, "p25", None)


def get_baseline_ucf(ctx: Any) -> float:
    """
    Get the baseline UCF from P25 report.

    Convenience function for downstream observability access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Baseline UCF score in [0.0, 1.0], or 0.5 (neutral) if no report
    """
    report = get_p25_report(ctx)
    if report is None:
        return NEUTRAL_DEFAULT
    return report.baseline_ucf


def get_max_negative_delta(ctx: Any) -> float:
    """
    Get the maximum negative UCF delta from P25 report.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Maximum negative delta, or 0.0 if no report
    """
    report = get_p25_report(ctx)
    if report is None:
        return 0.0
    return report.max_negative_delta


def get_max_positive_delta(ctx: Any) -> float:
    """
    Get the maximum positive UCF delta from P25 report.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Maximum positive delta, or 0.0 if no report
    """
    report = get_p25_report(ctx)
    if report is None:
        return 0.0
    return report.max_positive_delta


def get_scenario_count(ctx: Any) -> int:
    """
    Get the number of scenarios simulated in P25.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Number of scenarios, or 0 if no report
    """
    report = get_p25_report(ctx)
    if report is None:
        return 0
    return report.scenario_count()


def has_any_risk_flags(ctx: Any) -> bool:
    """
    Check if any scenario produced risk flags.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if any scenario has risk flags, False otherwise
    """
    report = get_p25_report(ctx)
    if report is None:
        return False
    return report.has_any_flags()


def has_any_band_changes(ctx: Any) -> bool:
    """
    Check if any scenario caused stability band changes.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if any scenario changed the stability band, False otherwise
    """
    report = get_p25_report(ctx)
    if report is None:
        return False
    return report.has_any_band_changes()


def get_p25_version() -> str:
    """
    Get the current P25 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P25_VERSION


# ============================================================================
# INTERNAL FUNCTIONS
# ============================================================================


def _extract_baseline_from_context(ctx: Any) -> dict:
    """
    Extract baseline values from pipeline context.

    This function reads from various context attributes to gather
    baseline values for the sandbox. All values are optional.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Dictionary with baseline values (may contain None values)
    """
    baseline = {
        "coherence": None,
        "drift": None,
        "entropy": None,
        "schema_stability": None,
        "identity_harmonics": None,
    }

    # Try to extract coherence_v3_quality from coherence_state
    coherence_state = getattr(ctx, "coherence_state", None)
    if coherence_state is not None:
        baseline["coherence"] = getattr(
            coherence_state, "coherence_v3_quality", None
        )
        baseline["identity_harmonics"] = getattr(
            coherence_state, "current_identity_harmonics_index", None
        )

    # Try to extract from P19 (drift_fusion_index)
    p19 = getattr(ctx, "p19", None)
    if p19 is not None:
        baseline["drift"] = getattr(p19, "drift_fusion_index", None)

    # Try to extract from P18 (entropy volatility)
    p18 = getattr(ctx, "p18", None)
    if p18 is not None:
        # P18 may have volatility as a band enum or as a numeric value
        volatility = getattr(p18, "volatility_band", None)
        if volatility is not None:
            # Convert band to numeric if needed
            if hasattr(volatility, "value"):
                # It's an enum
                band_map = {"LOW": 0.2, "MED": 0.5, "HIGH": 0.8}
                baseline["entropy"] = band_map.get(volatility.value, 0.5)
            elif isinstance(volatility, (int, float)):
                baseline["entropy"] = volatility
            else:
                # Try to parse as string
                band_map = {"LOW": 0.2, "MED": 0.5, "HIGH": 0.8}
                baseline["entropy"] = band_map.get(str(volatility), 0.5)

    # Try to extract from P33 (schema stability)
    p33 = getattr(ctx, "p33", None)
    if p33 is not None:
        # P33 may have confidence as a stability proxy
        schema_scores = getattr(p33, "schema_stability_scores", None)
        if schema_scores and isinstance(schema_scores, dict):
            # Average of all schema stability scores
            values = [v for v in schema_scores.values() if isinstance(v, (int, float))]
            if values:
                baseline["schema_stability"] = sum(values) / len(values)
        else:
            # Fall back to confidence
            baseline["schema_stability"] = getattr(p33, "confidence", None)

    # Try to get coherence from P26 if not already set
    p26 = getattr(ctx, "p26", None)
    if p26 is not None and baseline["coherence"] is None:
        # Use UCF contributing factors if available
        factors = getattr(p26, "contributing_factors", {})
        if factors:
            baseline["coherence"] = factors.get("coherence_v3_quality")

    return baseline


def _attach_to_context(ctx: Any, report: CounterfactualSandboxReport) -> None:
    """
    Attach P25 report to context.

    CRITICAL: This ONLY sets ctx.p25. It does NOT modify any authoritative
    pipeline state (regime, discourse, semantics, lexical, etc.)

    Args:
        ctx: PipelineContext or compatible object
        report: The sandbox report to attach
    """
    if hasattr(ctx, "p25"):
        ctx.p25 = report
    else:
        # Context doesn't have p25 attribute, try to set it anyway
        try:
            setattr(ctx, "p25", report)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================

__all__ = [
    # Integration
    "maybe_run_p25",
    "run_p25_directly",
    # Helpers
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
