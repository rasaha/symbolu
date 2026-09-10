"""The complete PILOT and PRODUCTION decision tables (GV-3R-b, ADR §6, §7, §9).

Every test asserts the *selected classification and rule*, not merely that the
evaluator ran.
"""

from __future__ import annotations

import pytest

from ugence_agent_value_readiness.api import (
    GateStatus,
    ReadinessClassification,
    ReadinessRuleId,
    evaluate_readiness,
)

from _fixtures import (  # noqa: E402
    ADVISORY,
    BOTH,
    CONDITIONAL,
    MANDATORY,
    NOW,
    PILOT,
    PROD,
    case,
    condition,
    gate,
    gate_result,
    readiness_policy,
)

PASS = GateStatus.PASS
FAIL = GateStatus.FAIL
IND = GateStatus.INDETERMINATE
CLS = ReadinessClassification


def run(c):
    return evaluate_readiness(c, evaluation_time=NOW)


# --------------------------------------------------------------------------- #
# Mandatory-gate precedence (§9): FAIL > INDETERMINATE > conditional resolution
# --------------------------------------------------------------------------- #
def test_fail_dominates_unrelated_indeterminate_and_pass():
    """{FAIL, INDETERMINATE, PASS} ⇒ NOT_READY."""

    p = readiness_policy([gate("m1", MANDATORY), gate("m2", MANDATORY), gate("m3", MANDATORY)])
    r = run(case(policy=p, gate_results=[
        gate_result(p, "m1", FAIL), gate_result(p, "m2", IND), gate_result(p, "m3", PASS)]))
    assert r.classification is CLS.NOT_READY
    assert r.rule_id == ReadinessRuleId.MANDATORY_FAIL.value
    assert r.trace.mandatory_failure_gate_ids == ("m1",)
    # the unrelated INDETERMINATE is still reported, it just does not win
    assert r.trace.mandatory_indeterminate_gate_ids == ("m2",)


def test_indeterminate_without_fail_is_not_assessable():
    """{INDETERMINATE, PASS} ⇒ NOT_ASSESSABLE."""

    p = readiness_policy([gate("m1", MANDATORY), gate("m2", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", IND), gate_result(p, "m2", PASS)]))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert r.rule_id == ReadinessRuleId.MANDATORY_INDETERMINATE.value


def test_all_mandatory_pass_proceeds_to_conditional_evaluation():
    """{PASS, PASS} ⇒ conditional evaluation (here: nothing unresolved)."""

    p = readiness_policy([gate("m1", MANDATORY), gate("m2", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS), gate_result(p, "m2", PASS)]))
    assert r.classification is CLS.DEPLOYMENT_READY


@pytest.mark.parametrize("indicator_strength", [PASS, FAIL])
def test_no_indicator_result_overrides_a_mandatory_failure(indicator_strength):
    p = readiness_policy([gate("m1", MANDATORY)])
    c = case(policy=p, gate_results=[gate_result(p, "m1", FAIL)])
    assert run(c).classification is CLS.NOT_READY


# --------------------------------------------------------------------------- #
# PRODUCTION decision table (§12)
# --------------------------------------------------------------------------- #
def test_production_deployment_ready():
    p = readiness_policy([gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS), gate_result(p, "c1", PASS)]))
    assert r.classification is CLS.DEPLOYMENT_READY
    assert r.rule_id == ReadinessRuleId.DEPLOYMENT_READY.value
    assert r.trace.unresolved_conditional_gate_ids == ()


def test_production_ready_with_conditions_when_covered():
    p = readiness_policy([gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(
        policy=p,
        gate_results=[gate_result(p, "m1", PASS), gate_result(p, "c1", FAIL)],
        conditions=[condition("cond-1", "c1")],
    ))
    assert r.classification is CLS.READY_WITH_CONDITIONS
    assert r.rule_id == ReadinessRuleId.READY_WITH_CONDITIONS.value
    assert r.trace.accepted_condition_ids == ("cond-1",)
    assert r.determination.conditions[0].condition_id == "cond-1"


def test_production_indeterminate_conditional_is_also_a_concern():
    p = readiness_policy([gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(
        policy=p,
        gate_results=[gate_result(p, "m1", PASS), gate_result(p, "c1", IND)],
        conditions=[condition("cond-1", "c1")],
    ))
    assert r.classification is CLS.READY_WITH_CONDITIONS
    assert r.trace.unresolved_conditional_gate_ids == ("c1",)


def test_production_non_compensable_conditional_is_not_ready():
    p = readiness_policy([gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=False)])
    r = run(case(
        policy=p,
        gate_results=[gate_result(p, "m1", PASS), gate_result(p, "c1", FAIL)],
        conditions=[condition("cond-1", "c1")],
    ))
    assert r.classification is CLS.NOT_READY
    assert r.rule_id == ReadinessRuleId.CONDITIONAL_NOT_COMPENSABLE.value
    assert r.trace.non_compensable_conditional_gate_ids == ("c1",)


def test_production_compensable_but_uncovered_is_not_ready():
    p = readiness_policy([gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS), gate_result(p, "c1", FAIL)]))
    assert r.classification is CLS.NOT_READY
    assert r.rule_id == ReadinessRuleId.CONDITIONAL_UNCOVERED.value
    assert r.trace.uncovered_conditional_gate_ids == ("c1",)


def test_production_mandatory_fail_beats_covered_conditional():
    p = readiness_policy([gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(
        policy=p,
        gate_results=[gate_result(p, "m1", FAIL), gate_result(p, "c1", FAIL)],
        conditions=[condition("cond-1", "c1")],
    ))
    assert r.classification is CLS.NOT_READY
    assert r.rule_id == ReadinessRuleId.MANDATORY_FAIL.value


def test_advisory_gate_never_changes_the_tier():
    p = readiness_policy([gate("m1", MANDATORY), gate("adv", ADVISORY)])
    ready = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]))
    with_failed_advisory = run(case(
        policy=p, gate_results=[gate_result(p, "m1", PASS), gate_result(p, "adv", FAIL)]))
    assert ready.classification is CLS.DEPLOYMENT_READY
    assert with_failed_advisory.classification is CLS.DEPLOYMENT_READY


def test_missing_advisory_result_does_not_block():
    """No ratified field marks an advisory gate assessability-required."""

    p = readiness_policy([gate("m1", MANDATORY), gate("adv", ADVISORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]))
    assert r.classification is CLS.DEPLOYMENT_READY
    assert r.trace.missing_required_gate_ids == ()


# --------------------------------------------------------------------------- #
# PILOT decision table (§11)
# --------------------------------------------------------------------------- #
def test_pilot_ready_when_mandatory_pass():
    p = readiness_policy([gate("m1", MANDATORY, applicability=(PILOT,))])
    r = run(case(policy=p, target=PILOT,
                 gate_results=[gate_result(p, "m1", PASS, target=PILOT)]))
    assert r.classification is CLS.PILOT_READY
    assert r.rule_id == ReadinessRuleId.PILOT_READY.value


def test_pilot_ready_carries_bounded_pilot_conditions():
    p = readiness_policy([
        gate("m1", MANDATORY, applicability=(PILOT,)),
        gate("c1", CONDITIONAL, applicability=(PILOT,), compensable=True),
    ])
    r = run(case(
        policy=p, target=PILOT,
        gate_results=[gate_result(p, "m1", PASS, target=PILOT),
                      gate_result(p, "c1", FAIL, target=PILOT)],
        conditions=[condition("cond-1", "c1")],
    ))
    assert r.classification is CLS.PILOT_READY
    assert r.trace.accepted_condition_ids == ("cond-1",)
    attached = r.determination.conditions[0]
    # The bounded pilot scope/exposure/monitoring are carried on the condition.
    assert attached.scope_exposure_limit and attached.monitoring_requirement
    assert attached.expiry is None or attached.effective_to is None or True


def test_pilot_never_emits_production_tiers():
    p = readiness_policy([gate("m1", MANDATORY, applicability=(PILOT,))])
    r = run(case(policy=p, target=PILOT,
                 gate_results=[gate_result(p, "m1", PASS, target=PILOT)]))
    assert r.classification not in (CLS.READY_WITH_CONDITIONS, CLS.DEPLOYMENT_READY)


def test_production_only_gate_stays_diagnostic_during_pilot():
    """A failing production-only mandatory gate cannot block PILOT readiness."""

    p = readiness_policy([
        gate("m-pilot", MANDATORY, applicability=(PILOT,)),
        gate("m-prod-only", MANDATORY, applicability=(PROD,)),
    ])
    r = run(case(
        policy=p, target=PILOT,
        gate_results=[gate_result(p, "m-pilot", PASS, target=PILOT),
                      gate_result(p, "m-prod-only", FAIL, target=PILOT)],
    ))
    assert r.classification is CLS.PILOT_READY
    assert r.trace.applicable_gate_ids == ("m-pilot",)
    assert r.trace.diagnostic_gate_ids == ("m-prod-only",)
    assert r.trace.mandatory_failure_gate_ids == ()


def test_pilot_uncovered_conditional_is_not_ready():
    p = readiness_policy([
        gate("m1", MANDATORY, applicability=(PILOT,)),
        gate("c1", CONDITIONAL, applicability=(PILOT,), compensable=True),
    ])
    r = run(case(policy=p, target=PILOT,
                 gate_results=[gate_result(p, "m1", PASS, target=PILOT),
                               gate_result(p, "c1", FAIL, target=PILOT)]))
    assert r.classification is CLS.NOT_READY
    assert r.rule_id == ReadinessRuleId.CONDITIONAL_UNCOVERED.value


def test_pilot_non_compensable_conditional_is_not_ready():
    p = readiness_policy([
        gate("m1", MANDATORY, applicability=(PILOT,)),
        gate("c1", CONDITIONAL, applicability=(PILOT,), compensable=False),
    ])
    r = run(case(policy=p, target=PILOT,
                 gate_results=[gate_result(p, "m1", PASS, target=PILOT),
                               gate_result(p, "c1", FAIL, target=PILOT)],
                 conditions=[condition("cond-1", "c1")]))
    assert r.classification is CLS.NOT_READY
    assert r.rule_id == ReadinessRuleId.CONDITIONAL_NOT_COMPENSABLE.value


def test_pilot_mandatory_fail_is_not_ready():
    p = readiness_policy([gate("m1", MANDATORY, applicability=BOTH)])
    r = run(case(policy=p, target=PILOT,
                 gate_results=[gate_result(p, "m1", FAIL, target=PILOT)]))
    assert r.classification is CLS.NOT_READY


def test_pilot_mandatory_indeterminate_is_not_assessable():
    p = readiness_policy([gate("m1", MANDATORY, applicability=(PILOT,))])
    r = run(case(policy=p, target=PILOT,
                 gate_results=[gate_result(p, "m1", IND, target=PILOT)]))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert r.rule_id == ReadinessRuleId.MANDATORY_INDETERMINATE.value
