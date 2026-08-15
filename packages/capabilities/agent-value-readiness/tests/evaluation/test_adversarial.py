"""Adversarial tests: the evaluator must not be talked out of a hard answer.

Each test names the attack it defeats. Passing means the *security property*
holds, not merely that the evaluator returned something.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

import pytest

from ugence_uvi_policy_contracts.api import PolicyFamily, PolicyGate, PolicyReference
from ugence_agent_value_readiness.api import (
    ConditionDecisionCode,
    ConditionStatus,
    GateResult,
    GateStatus,
    ReadinessClassification,
    ReadinessEvaluationCase,
    ReadinessEvaluationError,
    ReadinessReasonCode,
    ReadinessRuleId,
    evaluate_readiness,
)

from _fixtures import (  # noqa: E402
    BOTH,
    CONDITIONAL,
    D,
    FUTURE,
    MANDATORY,
    NOW,
    PAST,
    PILOT,
    PROD,
    T0,
    case,
    condition,
    context,
    gate,
    gate_result,
    readiness_policy,
)

PASS = GateStatus.PASS
FAIL = GateStatus.FAIL
IND = GateStatus.INDETERMINATE
CLS = ReadinessClassification


def run(c, when=NOW):
    return evaluate_readiness(c, evaluation_time=when)


# --------------------------------------------------------------------------- #
# Attack: omit the difficult gate from the evaluation
# --------------------------------------------------------------------------- #
def test_omitted_mandatory_gate_is_not_treated_as_pass():
    p = readiness_policy([gate("m-easy", MANDATORY), gate("m-hard", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m-easy", PASS)]))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert r.rule_id == ReadinessRuleId.ASSESSABILITY_GAP.value
    assert r.trace.missing_required_gate_ids == ("m-hard",)
    assert ReadinessReasonCode.APPLICABLE_GATE_RESULT_MISSING.value in r.reason_codes


def test_omitted_conditional_gate_is_not_treated_as_pass():
    p = readiness_policy([gate("m1", MANDATORY), gate("c-hard", CONDITIONAL, compensable=True)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert r.trace.missing_required_gate_ids == ("c-hard",)


def test_omitting_every_gate_is_not_deployment_ready():
    p = readiness_policy([gate("m1", MANDATORY)])
    assert run(case(policy=p)).classification is CLS.NOT_ASSESSABLE


# --------------------------------------------------------------------------- #
# Attack: supply a gate result that is not the policy's gate
# --------------------------------------------------------------------------- #
def test_gate_result_from_another_policy_is_rejected():
    p = readiness_policy([gate("m1", MANDATORY)])
    other = PolicyReference(policy_id="other", policy_family=PolicyFamily.READINESS,
                            version="9", content_digest=D)
    foreign = gate_result(p, "m1", PASS, policy_ref=other)
    with pytest.raises(ReadinessEvaluationError, match="different ReadinessPolicy"):
        case(policy=p, gate_results=[foreign])


def test_gate_result_for_a_gate_absent_from_the_policy_is_rejected():
    p = readiness_policy([gate("m1", MANDATORY)])
    stranger = PolicyGate(gate_id="ghost", category=gate("x", MANDATORY).category,
                          requirement_class=MANDATORY, applicability=BOTH)
    result = GateResult(policy_gate=stranger, readiness_policy_ref=p.reference,
                        requested_target=PROD, status=PASS)
    with pytest.raises(ReadinessEvaluationError, match="does not exist in the supplied"):
        case(policy=p, gate_results=[gate_result(p, "m1", PASS), result])


def test_redefined_gate_definition_is_rejected():
    """A caller cannot smuggle in a compensable clone of a strict policy gate."""

    p = readiness_policy([gate("c1", CONDITIONAL, compensable=False)])
    forged = PolicyGate(gate_id="c1", category=gate("c1", CONDITIONAL).category,
                        requirement_class=CONDITIONAL, applicability=BOTH,
                        conditionally_compensable=True)
    result = GateResult(policy_gate=forged, readiness_policy_ref=p.reference,
                        requested_target=PROD, status=FAIL)
    with pytest.raises(ReadinessEvaluationError, match="differs from the ReadinessPolicy"):
        case(policy=p, gate_results=[result])


def test_duplicate_gate_result_is_rejected():
    p = readiness_policy([gate("m1", MANDATORY)])
    with pytest.raises(ReadinessEvaluationError, match="more than one result"):
        case(policy=p, gate_results=[gate_result(p, "m1", FAIL), gate_result(p, "m1", PASS)])


def test_gate_result_evaluated_for_another_target_is_rejected():
    p = readiness_policy([gate("m1", MANDATORY)])
    with pytest.raises(ReadinessEvaluationError, match="not the requested"):
        case(policy=p, target=PROD, gate_results=[gate_result(p, "m1", PASS, target=PILOT)])


def test_policy_reference_must_match_the_supplied_policy_body():
    p = readiness_policy([gate("m1", MANDATORY)])
    wrong = PolicyReference(policy_id="rp", policy_family=PolicyFamily.READINESS,
                            version="2", content_digest=D)
    with pytest.raises(ReadinessEvaluationError, match="does not match the supplied"):
        case(policy=p, policy_ref=wrong, gate_results=[])


# --------------------------------------------------------------------------- #
# Attack: talk a conditional concern into READY_WITH_CONDITIONS
# --------------------------------------------------------------------------- #
def test_conditional_class_alone_does_not_make_a_concern_compensable():
    """`RequirementClass.CONDITIONAL` is not enough — the policy must opt in."""

    p = readiness_policy([gate("c1", CONDITIONAL, compensable=False)])
    r = run(case(policy=p, gate_results=[gate_result(p, "c1", FAIL)],
                 conditions=[condition("cond-1", "c1")]))
    assert r.classification is CLS.NOT_READY
    decision = r.trace.condition_decisions[0]
    assert decision.decision_code == ConditionDecisionCode.CONCERN_NOT_COMPENSABLE.value
    assert decision.accepted is False


def test_condition_for_a_different_gate_does_not_cover():
    """Coverage is per-gate: one control never compensates an unrelated concern."""

    p = readiness_policy([
        gate("c1", CONDITIONAL, compensable=True),
        gate("c2", CONDITIONAL, compensable=True),
    ])
    r = run(case(policy=p,
                 gate_results=[gate_result(p, "c1", FAIL), gate_result(p, "c2", FAIL)],
                 conditions=[condition("cond-2", "c2")]))
    assert r.classification is CLS.NOT_READY
    assert r.rule_id == ReadinessRuleId.CONDITIONAL_UNCOVERED.value
    assert r.trace.uncovered_conditional_gate_ids == ("c1",)
    assert r.trace.accepted_condition_ids == ("cond-2",)


def test_condition_naming_a_failing_mandatory_gate_is_never_coverage():
    """D-6: a mandatory concern is never compensable, whatever a control claims."""

    p = readiness_policy([gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(policy=p,
                 gate_results=[gate_result(p, "m1", FAIL), gate_result(p, "c1", PASS)],
                 conditions=[condition("cond-m", "m1")]))
    assert r.classification is CLS.NOT_READY
    assert r.rule_id == ReadinessRuleId.MANDATORY_FAIL.value
    codes = {d.condition_id: d.decision_code for d in r.trace.condition_decisions}
    assert codes["cond-m"] == ConditionDecisionCode.CONCERN_NOT_CONDITIONAL.value
    assert r.trace.accepted_condition_ids == ()


def test_active_condition_over_a_passing_mandatory_gate_is_internally_inconsistent():
    p = readiness_policy([gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(policy=p,
                 gate_results=[gate_result(p, "m1", PASS), gate_result(p, "c1", FAIL)],
                 conditions=[condition("cond-m", "m1")]))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert ReadinessReasonCode.ACTIVE_CONDITION_WITHOUT_UNRESOLVED_CONCERN.value in r.reason_codes


@pytest.mark.parametrize(
    "status,expected_code",
    [
        (ConditionStatus.PROPOSED, ConditionDecisionCode.STATUS_PROPOSED),
        (ConditionStatus.EXPIRED, ConditionDecisionCode.STATUS_EXPIRED),
        (ConditionStatus.REVOKED, ConditionDecisionCode.STATUS_REVOKED),
        (ConditionStatus.SATISFIED, ConditionDecisionCode.STATUS_SATISFIED_HISTORICAL),
    ],
)
def test_non_active_condition_status_is_not_coverage(status, expected_code):
    p = readiness_policy([gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(policy=p, gate_results=[gate_result(p, "c1", FAIL)],
                 conditions=[condition("cond-1", "c1", status=status)]))
    assert r.classification is CLS.NOT_READY
    assert r.trace.condition_decisions[0].decision_code == expected_code.value
    assert r.trace.accepted_condition_ids == ()


@pytest.mark.parametrize(
    "kwargs,expected_code",
    [
        ({"effective_from": FUTURE}, ConditionDecisionCode.NOT_YET_EFFECTIVE),
        ({"effective_from": T0, "effective_to": PAST}, ConditionDecisionCode.WINDOW_ENDED),
        ({"effective_from": T0, "expiry": PAST}, ConditionDecisionCode.EXPIRED_AT_EVALUATION_TIME),
    ],
)
def test_condition_outside_its_window_is_not_coverage(kwargs, expected_code):
    p = readiness_policy([gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(policy=p, gate_results=[gate_result(p, "c1", FAIL)],
                 conditions=[condition("cond-1", "c1", **kwargs)]))
    assert r.classification is CLS.NOT_READY
    assert r.trace.condition_decisions[0].decision_code == expected_code.value


def test_half_open_interval_boundaries():
    """effective_from <= t < effective_to, evaluated only against the caller's t."""

    p = readiness_policy([gate("c1", CONDITIONAL, compensable=True)])
    c = case(policy=p, gate_results=[gate_result(p, "c1", FAIL)],
             conditions=[condition("cond-1", "c1", effective_from=PAST, effective_to=FUTURE)])
    assert run(c, when=PAST).classification is CLS.READY_WITH_CONDITIONS      # inclusive start
    assert run(c, when=FUTURE).classification is CLS.NOT_READY                # exclusive end


def test_complete_active_coverage_is_accepted():
    p = readiness_policy([gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(policy=p, gate_results=[gate_result(p, "c1", FAIL)],
                 conditions=[condition("cond-1", "c1")]))
    assert r.classification is CLS.READY_WITH_CONDITIONS
    assert r.trace.condition_decisions[0].decision_code == (
        ConditionDecisionCode.ACCEPTED_ACTIVE_COVERAGE.value
    )


# --------------------------------------------------------------------------- #
# Attack: an open control alongside a clean gate set
# --------------------------------------------------------------------------- #
def test_active_condition_over_a_passing_gate_blocks_deployment_ready():
    p = readiness_policy([gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(policy=p, gate_results=[gate_result(p, "c1", PASS)],
                 conditions=[condition("cond-1", "c1")]))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert ReadinessReasonCode.ACTIVE_CONDITION_WITHOUT_UNRESOLVED_CONCERN.value in r.reason_codes


def test_satisfied_condition_over_a_passing_gate_allows_deployment_ready():
    p = readiness_policy([gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(policy=p, gate_results=[gate_result(p, "c1", PASS)],
                 conditions=[condition("cond-1", "c1", status=ConditionStatus.SATISFIED)]))
    assert r.classification is CLS.DEPLOYMENT_READY
    assert [c.condition_id for c in r.determination.conditions] == ["cond-1"]


def test_pilot_target_ignores_a_condition_over_a_production_only_gate():
    p = readiness_policy([
        gate("m1", MANDATORY, applicability=(PILOT,)),
        gate("c-prod", CONDITIONAL, applicability=(PROD,), compensable=True),
    ])
    r = run(case(policy=p, target=PILOT,
                 gate_results=[gate_result(p, "m1", PASS, target=PILOT)],
                 conditions=[condition("cond-prod", "c-prod")]))
    assert r.classification is CLS.PILOT_READY
    assert r.trace.condition_decisions[0].decision_code == (
        ConditionDecisionCode.CONCERN_NOT_APPLICABLE_TO_TARGET.value
    )


def test_condition_naming_an_unknown_reference_is_recorded_not_accepted():
    p = readiness_policy([gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(policy=p, gate_results=[gate_result(p, "c1", FAIL)],
                 conditions=[condition("cond-x", "finding-42")]))
    assert r.classification is CLS.NOT_READY
    codes = {d.condition_id: d.decision_code for d in r.trace.condition_decisions}
    assert codes["cond-x"] == ConditionDecisionCode.CONCERN_NOT_A_POLICY_GATE.value


# --------------------------------------------------------------------------- #
# Attack: incomplete assessment inputs
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "field,code",
    [
        ("intelligence", ReadinessReasonCode.INTELLIGENCE_RESULT_MISSING),
        ("capability", ReadinessReasonCode.CAPABILITY_RESULT_MISSING),
        ("adoption", ReadinessReasonCode.ADOPTION_RESULT_MISSING),
    ],
)
def test_missing_indicator_family_is_not_assessable(field, code):
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)], **{field: ()}))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert code.value in r.reason_codes


def test_unbound_readiness_policy_is_not_assessable():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, ctx=context(p, bind_readiness=False),
                 gate_results=[gate_result(p, "m1", PASS)]))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert ReadinessReasonCode.READINESS_POLICY_NOT_BOUND_TO_CONTEXT.value in r.reason_codes


def test_context_bound_to_a_different_readiness_policy_is_not_assessable():
    bound = readiness_policy([gate("m1", MANDATORY)], pid="rp")
    supplied = readiness_policy([gate("m1", MANDATORY)], pid="rp2")
    r = run(case(policy=supplied, ctx=context(bound),
                 gate_results=[gate_result(supplied, "m1", PASS)]))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert ReadinessReasonCode.READINESS_POLICY_REF_CONTEXT_MISMATCH.value in r.reason_codes


def test_target_not_governed_by_the_policy_is_not_assessable():
    p = readiness_policy([gate("m1", MANDATORY, applicability=(PROD,))], targets=(PROD,))
    r = run(case(policy=p, target=PILOT, gate_results=[]))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert ReadinessReasonCode.REQUESTED_TARGET_NOT_GOVERNED_BY_POLICY.value in r.reason_codes


def test_incomplete_inputs_do_not_raise():
    """An incomplete-but-valid assessment is NOT_ASSESSABLE, never an exception."""

    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[], with_indicators=False,
                 ctx=context(p, bind_readiness=False)))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert len(r.trace.assessability_gap_codes) >= 4


def test_mandatory_fail_still_dominates_an_incomplete_case():
    """ADR §8 / D-6: a definite mandatory failure is never downgraded away."""

    p = readiness_policy([gate("m1", MANDATORY), gate("m2", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", FAIL)], with_indicators=False))
    assert r.classification is CLS.NOT_READY
    assert r.rule_id == ReadinessRuleId.MANDATORY_FAIL.value
    # the gaps are still reported, they simply do not win
    assert ReadinessReasonCode.APPLICABLE_GATE_RESULT_MISSING.value in r.reason_codes
    assert ReadinessReasonCode.INTELLIGENCE_RESULT_MISSING.value in r.reason_codes


# --------------------------------------------------------------------------- #
# Attack: cross-tenant / malformed structure / caller-chosen classification
# --------------------------------------------------------------------------- #
def test_cross_tenant_case_is_rejected():
    p = readiness_policy([gate("m1", MANDATORY)])
    with pytest.raises(ReadinessEvaluationError, match="cross-tenant"):
        case(policy=p, ctx=context(p, tenant="t1"), tenant="t2")


def test_case_has_no_classification_field():
    names = {f.name for f in dataclasses.fields(ReadinessEvaluationCase)}
    assert not any("classification" in n for n in names)
    assert not any("readiness_class" in n for n in names)


def test_naive_evaluation_time_is_rejected():
    p = readiness_policy([gate("m1", MANDATORY)])
    c = case(policy=p, gate_results=[gate_result(p, "m1", PASS)])
    with pytest.raises(ReadinessEvaluationError, match="timezone-aware"):
        evaluate_readiness(c, evaluation_time=datetime(2026, 6, 1))


def test_evaluation_time_is_keyword_only():
    p = readiness_policy([gate("m1", MANDATORY)])
    c = case(policy=p, gate_results=[gate_result(p, "m1", PASS)])
    with pytest.raises(TypeError):
        evaluate_readiness(c, NOW)  # type: ignore[misc]


def test_non_case_input_is_rejected():
    with pytest.raises(ReadinessEvaluationError, match="ReadinessEvaluationCase"):
        evaluate_readiness({"classification": "DEPLOYMENT_READY"}, evaluation_time=NOW)


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_result_is_independent_of_input_ordering():
    p = readiness_policy([
        gate("m1", MANDATORY), gate("m2", MANDATORY),
        gate("c1", CONDITIONAL, compensable=True), gate("c2", CONDITIONAL, compensable=True),
    ])
    gates = [gate_result(p, "m1", PASS), gate_result(p, "m2", PASS),
             gate_result(p, "c1", FAIL), gate_result(p, "c2", IND)]
    conds = [condition("cond-a", "c1"), condition("cond-b", "c2")]

    forward = run(case(policy=p, gate_results=gates, conditions=conds))
    reversed_ = run(case(policy=p, gate_results=list(reversed(gates)),
                         conditions=list(reversed(conds))))

    assert forward.classification is reversed_.classification
    assert forward.rule_id == reversed_.rule_id
    assert forward.reason_codes == reversed_.reason_codes
    assert forward.trace.canonical_digest() == reversed_.trace.canonical_digest()
    assert forward.determination.canonical_digest() == reversed_.determination.canonical_digest()
    assert forward.canonical_digest() == reversed_.canonical_digest()
    assert forward.trace.input_digest == reversed_.trace.input_digest


def test_repeated_evaluation_is_identical():
    p = readiness_policy([gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=True)])
    c = case(policy=p, gate_results=[gate_result(p, "m1", PASS), gate_result(p, "c1", FAIL)],
             conditions=[condition("cond-1", "c1")])
    assert run(c).canonical_digest() == run(c).canonical_digest()


def test_evaluation_time_changes_only_through_the_supplied_instant():
    p = readiness_policy([gate("c1", CONDITIONAL, compensable=True)])
    c = case(policy=p, gate_results=[gate_result(p, "c1", FAIL)],
             conditions=[condition("cond-1", "c1", effective_from=T0, expiry=FUTURE)])
    assert run(c, when=NOW).classification is CLS.READY_WITH_CONDITIONS
    assert run(c, when=FUTURE).classification is CLS.NOT_READY
