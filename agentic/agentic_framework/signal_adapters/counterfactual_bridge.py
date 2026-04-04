"""
Counterfactual Sandbox Bridge — P25 → Governance Replay/Simulation
===================================================================

Phase C4: Bridges the counterfactual sandbox (P25) into the governance
framework as a replay/simulation-only capability. NOT used in live
authorization decisions.

Purpose:
    - Approval workflows: "what-if" analysis before human approves
    - Audit replay: recompute governance outcomes under hypothetical deltas
    - Testing/validation: verify governance sensitivity to signal changes

This bridge does NOT:
    - Affect live authorization confidence, escalation, or decisions
    - Produce penalties or escalation bias
    - Require the sandbox to be available at governance time

Design:
    Thin wrapper that calls ``cf_engine.run_sandbox()`` and
    ``cf_analyzer.summarize_report()`` from the core counterfactual
    module, with fail-safe fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agentic.core.counterfactual.cf_schema import (
    CounterfactualSandboxReport,
    CounterfactualScenario,
    create_scenario,
)
from agentic.core.counterfactual.cf_engine import (
    run_sandbox,
    simulate_single_scenario,
)
from agentic.core.counterfactual.cf_analyzer import (
    summarize_report,
    find_boundary_scenarios,
)


# =========================================================================
# Governance-facing contract
# =========================================================================

@dataclass(frozen=True)
class CounterfactualBridgeResult:
    """Result of a counterfactual simulation for governance replay.

    This is NOT used in live authorization. It is a replay/simulation
    artifact for approval workflows, audit, and testing.

    Fields:
        report          The raw CounterfactualSandboxReport (if available).
        summary         Analyzer summary dict (UCF sensitivity, transitions, flags).
        boundary_scenarios  Scenarios at stability band boundaries.
        scenario_count  Number of scenarios evaluated.
        risk_flag_count Total risk flags across all scenarios.
        available       Whether simulation completed successfully.
        error           Error message if simulation failed.
    """
    report: Optional[CounterfactualSandboxReport]
    summary: Optional[Dict[str, Any]]
    boundary_scenarios: Optional[Dict[str, List[str]]]
    scenario_count: int
    risk_flag_count: int
    available: bool
    error: Optional[str] = None

    def to_audit_dict(self) -> Dict[str, Any]:
        """Serialize to audit-safe dictionary (excludes full report)."""
        return {
            "scenario_count": self.scenario_count,
            "risk_flag_count": self.risk_flag_count,
            "available": self.available,
            "error": self.error,
            "summary": self.summary,
            "boundary_scenarios": self.boundary_scenarios,
            "baseline_ucf": (
                round(self.report.baseline_ucf, 6) if self.report else None
            ),
            "baseline_stability_band": (
                self.report.baseline_stability_band if self.report else None
            ),
        }


# =========================================================================
# Empty/fallback result
# =========================================================================

def _empty_result(error: str = "no simulation data") -> CounterfactualBridgeResult:
    return CounterfactualBridgeResult(
        report=None,
        summary=None,
        boundary_scenarios=None,
        scenario_count=0,
        risk_flag_count=0,
        available=False,
        error=error,
    )


# =========================================================================
# Main bridge functions
# =========================================================================

def run_counterfactual_simulation(
    *,
    scenarios: Optional[List[CounterfactualScenario]] = None,
    baseline_coherence: Optional[float] = None,
    baseline_drift: Optional[float] = None,
    baseline_entropy: Optional[float] = None,
    baseline_schema_stability: Optional[float] = None,
    baseline_identity_harmonics: Optional[float] = None,
) -> CounterfactualBridgeResult:
    """Run a counterfactual simulation through the governance bridge.

    This is a replay/simulation-only operation. It does NOT affect
    live authorization decisions.

    Args:
        scenarios: List of CounterfactualScenario objects to simulate.
            If None or empty, returns an empty result.
        baseline_coherence: Current coherence signal [0, 1].
        baseline_drift: Current drift signal [0, 1].
        baseline_entropy: Current entropy signal [0, 1].
        baseline_schema_stability: Current schema stability [0, 1].
        baseline_identity_harmonics: Current identity harmonics [0, 1].

    Returns:
        CounterfactualBridgeResult with simulation outcomes.
    """
    if not scenarios:
        return _empty_result("no scenarios provided")

    try:
        report = run_sandbox(
            scenarios=scenarios,
            baseline_coherence=baseline_coherence,
            baseline_drift=baseline_drift,
            baseline_entropy=baseline_entropy,
            baseline_schema_stability=baseline_schema_stability,
            baseline_identity_harmonics=baseline_identity_harmonics,
        )

        summary = summarize_report(report)
        boundaries = find_boundary_scenarios(report)

        total_flags = sum(len(r.risk_flags) for r in report.results)

        return CounterfactualBridgeResult(
            report=report,
            summary=summary,
            boundary_scenarios=boundaries,
            scenario_count=len(report.results),
            risk_flag_count=total_flags,
            available=True,
        )
    except Exception as exc:
        return _empty_result(f"simulation failed: {exc}")


def create_standard_scenarios(
    delta_magnitude: float = 0.2,
) -> List[CounterfactualScenario]:
    """Create a standard set of counterfactual scenarios for governance replay.

    Generates scenarios that test sensitivity to coherence drops,
    entropy spikes, drift acceleration, and combined perturbations.

    Args:
        delta_magnitude: Magnitude of perturbation deltas [0, 1].

    Returns:
        List of CounterfactualScenario objects.
    """
    mag = min(1.0, max(0.0, delta_magnitude))
    return [
        create_scenario("coherence_drop", delta_coherence=-mag),
        create_scenario("coherence_boost", delta_coherence=mag),
        create_scenario("entropy_spike", delta_entropy=mag),
        create_scenario("entropy_drop", delta_entropy=-mag),
        create_scenario("drift_increase", delta_drift=mag),
        create_scenario("drift_decrease", delta_drift=-mag),
        create_scenario("combined_stress", delta_coherence=-mag, delta_entropy=mag, delta_drift=mag),
        create_scenario("combined_improve", delta_coherence=mag, delta_entropy=-mag, delta_drift=-mag),
    ]
