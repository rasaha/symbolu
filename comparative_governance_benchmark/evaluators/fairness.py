"""Automated cross-strategy fairness controls (Task 12).

Verifies every strategy sees identical inputs and identical execution behaviour,
and that simpler strategies gained no hidden access to governance they do not
possess. ``grid`` maps strategy_id -> list of (scenario, StrategyResult) in a
fixed scenario order.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FairnessCheck:
    name: str
    passed: bool
    detail: str = ""


def check_fairness(grid: dict) -> list:
    strategies = list(grid)
    checks: list[FairnessCheck] = []

    # F1: identical scenario ordering + identity across strategies
    orders = {sid: [r.scenario_id for _s, r in pairs] for sid, pairs in grid.items()}
    ref = orders[strategies[0]]
    checks.append(FairnessCheck(
        "identical_scenario_ordering", all(o == ref for o in orders.values()),
        "all strategies run the same scenarios in the same order"))

    # F2 (B12): for each scenario, strategies that dispatched agree on execution outcome
    by_scenario = {}
    for sid, pairs in grid.items():
        for _s, r in pairs:
            by_scenario.setdefault(r.scenario_id, []).append(r)
    disagreements = []
    for scid, results in by_scenario.items():
        outcomes = {r.execution_outcome for r in results if r.dispatched
                    and r.execution_outcome not in ("NOT_PERFORMED",)}
        if len(outcomes) > 1:
            disagreements.append(f"{scid}:{sorted(outcomes)}")
    checks.append(FairnessCheck(
        "identical_execution_behavior_for_same_dispatch", not disagreements,
        f"disagreements: {disagreements[:5]}"))

    # F3: simpler strategies have no hidden governance access
    def all_true(sid, pred):
        return all(pred(r) for _s, r in grid[sid])
    checks.append(FairnessCheck(
        "no_governance_has_no_assertion_or_authorization",
        all_true("no_governance", lambda r: not r.assertion_evaluated
                 and not r.authorization_performed),
        "no-governance never evaluates assertions or authorizes"))
    checks.append(FairnessCheck(
        "action_only_has_no_assertion_evaluation",
        all_true("action_only", lambda r: not r.assertion_evaluated),
        "action-only never evaluates assertions"))
    checks.append(FairnessCheck(
        "assertion_only_has_no_authorization",
        all_true("assertion_only", lambda r: not r.authorization_performed),
        "assertion-only never authorizes actions"))
    return checks


def fairness_passed(checks: list) -> bool:
    return all(c.passed for c in checks)
