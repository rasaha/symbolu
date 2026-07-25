"""Independent benchmark expectation layer (Task 4/7).

Derives, from each frozen scenario's semantics (never from any strategy output),
what a correct governance system should do. The oracle compares strategy results
against this. Reads only the frozen ``Scenario`` (its expected region is the
Phase 5I full-governance ground truth) — it calls no provider.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioExpectation:
    scenario_id: str
    #: a governance-provider failure is injected/baked-in for this scenario
    failing_component: str            # "tap" / "actiongate" / "" (none)
    #: whether the action should ultimately dispatch (base action, ignoring an
    #: injected governance-provider failure)
    should_dispatch: bool
    #: the governance layer that must block a should-not-dispatch scenario
    block_layer: str                  # "assertion" / "action" / "constraint" / "none"
    ground_truth_compliance: str      # COMPLIANT / NONCOMPLIANT / NOT_APPLICABLE
    noncompliance_reason: str         # "obligation" / "reconciliation" / "execution" / "none"
    is_execution_failure: bool


def derive(scenario) -> ScenarioExpectation:
    exp = scenario.expected
    failing = ("tap" if scenario.tap_policy.fail else
               "actiongate" if scenario.action_policy.fail else "")

    if failing:
        # the injected/baked-in governance-provider failure is the only blocker;
        # the underlying action would otherwise proceed.
        return ScenarioExpectation(
            scenario_id=scenario.scenario_id, failing_component=failing,
            should_dispatch=True, block_layer="none",
            ground_truth_compliance="NOT_APPLICABLE", noncompliance_reason="none",
            is_execution_failure=False)

    if exp.tap_outcome in ("UNSUPPORTED", "INDETERMINATE"):
        block_layer = "assertion"
    elif exp.execution_behavior == "DISPATCH_BLOCKED_BY_CONSTRAINT":
        block_layer = "constraint"
    elif exp.actiongate_outcome in ("DENIED", "INDETERMINATE"):
        block_layer = "action"
    else:
        block_layer = "none"

    is_exec_fail = exp.execution_behavior in ("EXECUTION_FAILED", "TRANSPORT_FAILED")
    reason = "none"
    if exp.compliance_verdict == "NONCOMPLIANT":
        if is_exec_fail:
            reason = "execution"
        elif exp.reconciliation == "MISMATCHED":
            reason = "reconciliation"
        else:
            reason = "obligation"

    return ScenarioExpectation(
        scenario_id=scenario.scenario_id, failing_component="",
        should_dispatch=exp.dispatched, block_layer=block_layer,
        ground_truth_compliance=exp.compliance_verdict, noncompliance_reason=reason,
        is_execution_failure=is_exec_fail)
