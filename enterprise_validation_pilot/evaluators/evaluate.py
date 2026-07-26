"""Scenario evaluation (Task 103) — compare actual run against frozen expected.

Evaluators are the *only* consumer of a scenario's ``expected`` region. They never
touch a provider. A run's actual outcomes are compared field-by-field against the
independently-authored ground truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..runners.workflow import ScenarioRun
from ..schemas.scenario import Scenario


@dataclass(frozen=True)
class FieldMismatch:
    field: str
    expected: object
    actual: object


@dataclass
class ScenarioEvaluation:
    scenario_id: str
    domain: str
    assertion_class: str
    action_class: str
    cross_class: str
    passed: bool
    mismatches: tuple[FieldMismatch, ...] = ()
    error: str | None = None


def _approx(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= 1e-6


def _set_eq(a, b) -> bool:
    return set(a or ()) == set(b or ())


def evaluate(scenario: Scenario, run: ScenarioRun) -> ScenarioEvaluation:
    exp = scenario.expected
    mism: list[FieldMismatch] = []

    def check(field_name, expected, actual, eq=lambda a, b: a == b):
        if not eq(expected, actual):
            mism.append(FieldMismatch(field_name, expected, actual))

    check("tap_outcome", exp.tap_outcome, run.tap_outcome)
    check("supported_components", exp.supported_components, run.supported_components, _set_eq)
    check("unsupported_components", exp.unsupported_components, run.unsupported_components, _set_eq)
    check("omitted_qualifiers", exp.omitted_qualifiers, run.omitted_qualifiers, _set_eq)
    check("evidence_coverage", exp.evidence_coverage, run.evidence_coverage, _approx)
    check("recommendation_posture", exp.recommendation_posture, run.recommendation_posture)
    check("actiongate_outcome", exp.actiongate_outcome, run.actiongate_outcome)
    check("constraints", exp.constraints, run.constraints, _set_eq)
    check("obligations", exp.obligations, run.obligations, _set_eq)
    check("dispatched", exp.dispatched, run.dispatched)
    check("execution_behavior", exp.execution_behavior, run.execution_behavior)
    check("reconciliation", exp.reconciliation, run.reconciliation)
    check("compliance_verdict", exp.compliance_verdict, run.compliance_verdict)

    return ScenarioEvaluation(
        scenario_id=scenario.scenario_id, domain=scenario.domain,
        assertion_class=scenario.assertion_class, action_class=scenario.action_class,
        cross_class=scenario.cross_class, passed=not mism and run.error is None,
        mismatches=tuple(mism), error=run.error)
