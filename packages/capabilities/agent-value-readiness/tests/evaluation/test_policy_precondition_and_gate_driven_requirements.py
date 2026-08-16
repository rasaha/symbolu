"""Closure-audit corrections: RA-01 (gate-driven requirements) and AUD-01
(policy lifecycle + effective period as ADR §6 precondition row 0).

Every test here fails on the pre-correction evaluator (formula GV-3R-b.1) and
passes after it. All exercise the public API only.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from ugence_uvi_policy_contracts.api import PolicyLifecycleState
from ugence_agent_value_readiness.api import (
    AdvisoryComposite,
    GateStatus,
    ReadinessClassification,
    ReadinessReasonCode,
    ReadinessRuleId,
    evaluate_readiness,
)

from _fixtures import (  # noqa: E402
    ADVISORY,
    CONDITIONAL,
    MANDATORY,
    NOW,
    PILOT,
    PROD,
    T0,
    T1,
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
NONE3 = dict(intelligence=(), capability=(), adoption=())

#: Every lifecycle state the merged package defines that is NOT approved-active.
NON_ACTIVE_STATES = [
    s for s in PolicyLifecycleState if s is not PolicyLifecycleState.APPROVED_ACTIVE
]


def run(c, when=NOW):
    return evaluate_readiness(c, evaluation_time=when)


def composite(score):
    return AdvisoryComposite(method_id="m", method_version="1", score=Decimal(score),
                             scale_min=Decimal("0"), scale_max=Decimal("100"),
                             component_result_refs=("r1",))


# =========================================================================== #
# RA-01 — indicator requirements are policy/gate-driven, never global presence
# =========================================================================== #
def test_no_indicator_records_at_all_is_deployment_ready():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)], **NONE3))
    assert r.classification is CLS.DEPLOYMENT_READY, r.classification
    assert r.rule_id == ReadinessRuleId.DEPLOYMENT_READY.value


@pytest.mark.parametrize("absent", ["intelligence", "capability", "adoption"])
def test_each_family_independently_absent_is_deployment_ready(absent):
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)], **{absent: ()}))
    assert r.classification is CLS.DEPLOYMENT_READY, (absent, r.classification)


def test_pilot_with_no_indicators_is_pilot_ready():
    p = readiness_policy([gate("m1", MANDATORY, applicability=(PILOT,))])
    r = run(case(policy=p, target=PILOT,
                 gate_results=[gate_result(p, "m1", PASS, target=PILOT)], **NONE3))
    assert r.classification is CLS.PILOT_READY, r.classification


def test_no_indicator_presence_reason_code_exists_any_more():
    names = {m.name for m in ReadinessReasonCode}
    assert not any(n.endswith("_RESULT_MISSING") and n != "APPLICABLE_GATE_RESULT_MISSING"
                   for n in names), names


def test_missing_applicable_mandatory_gate_still_fails_closed_without_indicators():
    p = readiness_policy([gate("m1", MANDATORY), gate("m2", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)], **NONE3))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert r.trace.missing_required_gate_ids == ("m2",)


def test_missing_applicable_conditional_gate_still_fails_closed_without_indicators():
    p = readiness_policy([gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)], **NONE3))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert r.trace.missing_required_gate_ids == ("c1",)


def test_mandatory_fail_without_indicators_is_not_ready():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", FAIL)], **NONE3))
    assert r.classification is CLS.NOT_READY
    assert r.rule_id == ReadinessRuleId.MANDATORY_FAIL.value


def test_mandatory_indeterminate_without_indicators_is_not_assessable():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", IND)], **NONE3))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert r.rule_id == ReadinessRuleId.MANDATORY_INDETERMINATE.value


def test_failing_advisory_indicator_cannot_influence_the_tier():
    """A useless indicator must neither unlock nor block: the tier is gate-driven."""

    import dataclasses

    p = readiness_policy([gate("m1", MANDATORY)])
    gates = [gate_result(p, "m1", PASS)]
    from _fixtures import indicators  # fixture builder, not a test helper
    _, _, adoption = indicators(target=PROD)
    weak = (dataclasses.replace(adoption[0], result_id="weak", status=FAIL,
                                requirement_class=ADVISORY),)
    without = run(case(policy=p, gate_results=gates, **NONE3))
    with_weak = run(case(policy=p, gate_results=gates, intelligence=(), capability=(),
                         adoption=weak))
    assert without.classification is with_weak.classification is CLS.DEPLOYMENT_READY
    assert without.rule_id == with_weak.rule_id
    assert without.reason_codes == with_weak.reason_codes


def test_indicator_presence_never_changes_the_classification():
    """Identical gate states, with and without diagnostics ⇒ identical tier."""

    p = readiness_policy([gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=True)])
    for statuses, conds in (((PASS, PASS), []), ((FAIL, PASS), []), ((IND, PASS), []),
                            ((PASS, FAIL), [("x", "c1")]), ((PASS, FAIL), [])):
        gates = [gate_result(p, "m1", statuses[0]), gate_result(p, "c1", statuses[1])]
        cs = [condition(cid, src) for cid, src in conds]
        full = run(case(policy=p, gate_results=gates, conditions=cs))
        bare = run(case(policy=p, gate_results=gates, conditions=cs, **NONE3))
        assert full.classification is bare.classification, (statuses, conds)
        assert full.rule_id == bare.rule_id
        assert full.reason_codes == bare.reason_codes


def test_supplied_indicator_is_still_structurally_validated():
    """Removing the presence rule must not weaken validation of what IS supplied."""

    from _fixtures import indicators
    p = readiness_policy([gate("m1", MANDATORY)])
    wrong_ctx = indicators(target=PROD, context_id="ctx-OTHER")
    from ugence_agent_value_readiness.api import ReadinessEvaluationError
    with pytest.raises(ReadinessEvaluationError):
        case(policy=p, gate_results=[gate_result(p, "m1", PASS)],
             intelligence=wrong_ctx[0], capability=wrong_ctx[1], adoption=wrong_ctx[2])


def test_composite_min_max_with_no_indicators_is_inert():
    p = readiness_policy([gate("m1", MANDATORY)])
    gates = [gate_result(p, "m1", PASS)]
    lo = run(case(policy=p, gate_results=gates, composite=composite("0"), **NONE3))
    hi = run(case(policy=p, gate_results=gates, composite=composite("100"), **NONE3))
    assert lo.classification is hi.classification is CLS.DEPLOYMENT_READY
    assert lo.rule_id == hi.rule_id and lo.reason_codes == hi.reason_codes


def test_gate_ordering_irrelevant_without_indicators():
    p = readiness_policy([gate("m1", MANDATORY), gate("m2", MANDATORY),
                          gate("c1", CONDITIONAL, compensable=True)])
    g = [gate_result(p, "m1", PASS), gate_result(p, "m2", PASS), gate_result(p, "c1", FAIL)]
    cs = [condition("x1", "c1")]
    a = run(case(policy=p, gate_results=g, conditions=cs, **NONE3))
    b = run(case(policy=p, gate_results=list(reversed(g)), conditions=cs, **NONE3))
    assert a.determination.canonical_digest() == b.determination.canonical_digest()
    assert a.trace.canonical_digest() == b.trace.canonical_digest()


# =========================================================================== #
# AUD-01 — policy lifecycle is precondition row 0
# =========================================================================== #
@pytest.mark.parametrize("state", NON_ACTIVE_STATES, ids=lambda s: s.value)
def test_non_active_lifecycle_is_not_assessable(state):
    p = readiness_policy([gate("m1", MANDATORY)], state=state)
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]))
    assert r.classification is CLS.NOT_ASSESSABLE, (state, r.classification)
    assert r.rule_id == ReadinessRuleId.POLICY_PRECONDITION.value
    assert ReadinessReasonCode.READINESS_POLICY_NOT_APPROVED_ACTIVE.value in r.reason_codes
    assert ReadinessReasonCode.READINESS_POLICY_NOT_APPROVED_ACTIVE.value in (
        r.trace.assessability_gap_codes)


@pytest.mark.parametrize("state", NON_ACTIVE_STATES, ids=lambda s: s.value)
def test_non_active_lifecycle_emits_no_ready_tier(state):
    """No gate arrangement or composite can produce a ready tier."""

    p = readiness_policy([gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=True)],
                         state=state)
    for statuses in ((PASS, PASS), (FAIL, PASS), (IND, PASS), (PASS, FAIL)):
        for comp in (None, composite("0"), composite("100")):
            r = run(case(policy=p,
                         gate_results=[gate_result(p, "m1", statuses[0]),
                                       gate_result(p, "c1", statuses[1])],
                         conditions=[condition("x1", "c1")], composite=comp))
            assert r.classification is CLS.NOT_ASSESSABLE, (state, statuses, comp)


def test_lifecycle_precondition_beats_mandatory_fail():
    """Row 0 dominates: an invalid policy asserts no gate headline at all."""

    p = readiness_policy([gate("m1", MANDATORY)], state=PolicyLifecycleState.REVOKED)
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", FAIL)]))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert r.rule_id == ReadinessRuleId.POLICY_PRECONDITION.value
    # no headline asserted over gates ...
    assert r.determination.gate_results == ()
    assert r.determination.blocking_gate_ids == ()
    # ... but the failure is still reported diagnostically on the trace
    assert r.trace.mandatory_failure_gate_ids == ("m1",)


def test_approved_active_and_effective_still_evaluates_normally():
    p = readiness_policy([gate("m1", MANDATORY)])
    assert run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)])).classification \
        is CLS.DEPLOYMENT_READY
    assert run(case(policy=p, gate_results=[gate_result(p, "m1", FAIL)])).classification \
        is CLS.NOT_READY
    assert run(case(policy=p, gate_results=[gate_result(p, "m1", IND)])).classification \
        is CLS.NOT_ASSESSABLE


def test_lifecycle_gate_ordering_and_composite_cannot_alter_row0():
    p = readiness_policy([gate("m1", MANDATORY), gate("m2", MANDATORY)],
                         state=PolicyLifecycleState.SUPERSEDED)
    g = [gate_result(p, "m1", FAIL), gate_result(p, "m2", PASS)]

    # differing composites: same decision, and the composite never enters it
    a = run(case(policy=p, gate_results=g, composite=composite("0")))
    b = run(case(policy=p, gate_results=g, composite=composite("100")))
    assert a.classification is b.classification is CLS.NOT_ASSESSABLE
    assert a.rule_id == b.rule_id and a.reason_codes == b.reason_codes
    assert a.trace.mandatory_failure_gate_ids == b.trace.mandatory_failure_gate_ids

    # pure reordering, inputs otherwise identical: byte-identical trace
    c = run(case(policy=p, gate_results=list(reversed(g)), composite=composite("0")))
    assert a.trace.canonical_digest() == c.trace.canonical_digest()
    assert a.determination.canonical_digest() == c.determination.canonical_digest()


# =========================================================================== #
# AUD-01 — effective period, half-open [effective_from, effective_to)
# =========================================================================== #
ONE_SEC = timedelta(seconds=1)


def test_before_effective_from_is_not_assessable():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]), when=T0 - ONE_SEC)
    assert r.classification is CLS.NOT_ASSESSABLE
    assert ReadinessReasonCode.READINESS_POLICY_NOT_EFFECTIVE_AT_EVALUATION_TIME.value \
        in r.reason_codes


def test_exactly_at_effective_from_is_effective():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]), when=T0)
    assert r.classification is CLS.DEPLOYMENT_READY, r.classification


def test_immediately_before_effective_to_is_effective():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]), when=T1 - ONE_SEC)
    assert r.classification is CLS.DEPLOYMENT_READY, r.classification


def test_exactly_at_effective_to_is_not_assessable():
    """Half-open: effective_to is exclusive."""

    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]), when=T1)
    assert r.classification is CLS.NOT_ASSESSABLE, r.classification
    assert ReadinessReasonCode.READINESS_POLICY_NOT_EFFECTIVE_AT_EVALUATION_TIME.value \
        in r.reason_codes


def test_after_effective_to_is_not_assessable():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]), when=T1 + ONE_SEC)
    assert r.classification is CLS.NOT_ASSESSABLE


def test_absent_effective_to_is_open_ended():
    p = readiness_policy([gate("m1", MANDATORY)], effective_to=None)
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]), when=T1 + ONE_SEC)
    assert r.classification is CLS.DEPLOYMENT_READY, r.classification


def test_context_bound_while_valid_then_evaluated_after_expiry():
    """The binder's as_of cannot cover a later evaluation_time."""

    p = readiness_policy([gate("m1", MANDATORY)])
    ctx = context(p)                      # bind_policies succeeds at NOW (policy valid)
    c = case(policy=p, ctx=ctx, gate_results=[gate_result(p, "m1", PASS)])
    assert run(c, when=NOW).classification is CLS.DEPLOYMENT_READY
    assert run(c, when=T1 + ONE_SEC).classification is CLS.NOT_ASSESSABLE


def test_active_label_cannot_override_an_expired_window():
    p = readiness_policy([gate("m1", MANDATORY)])   # APPROVED_ACTIVE
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]), when=T1 + ONE_SEC)
    assert r.classification is CLS.NOT_ASSESSABLE
    assert ReadinessReasonCode.READINESS_POLICY_NOT_APPROVED_ACTIVE.value not in r.reason_codes


def test_valid_window_cannot_override_a_non_active_lifecycle():
    p = readiness_policy([gate("m1", MANDATORY)], state=PolicyLifecycleState.DRAFT)
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]), when=NOW)
    assert r.classification is CLS.NOT_ASSESSABLE
    assert ReadinessReasonCode.READINESS_POLICY_NOT_APPROVED_ACTIVE.value in r.reason_codes
    assert ReadinessReasonCode.READINESS_POLICY_NOT_EFFECTIVE_AT_EVALUATION_TIME.value \
        not in r.reason_codes


def test_both_defects_reported_together():
    p = readiness_policy([gate("m1", MANDATORY)], state=PolicyLifecycleState.EXPIRED)
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]), when=T1 + ONE_SEC)
    assert r.classification is CLS.NOT_ASSESSABLE
    assert ReadinessReasonCode.READINESS_POLICY_NOT_APPROVED_ACTIVE.value in r.reason_codes
    assert ReadinessReasonCode.READINESS_POLICY_NOT_EFFECTIVE_AT_EVALUATION_TIME.value \
        in r.reason_codes


# =========================================================================== #
# Honesty + determinism of the new precondition
# =========================================================================== #
def test_row0_preserves_every_standing_trust_advisory():
    p = readiness_policy([gate("m1", MANDATORY)], state=PolicyLifecycleState.REVOKED)
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]))
    for code in ("GV3RB_ADV_ADVISORY_ONLY_NOT_DEPLOYMENT_AUTHORIZATION",
                 "GV3RB_ADV_POLICY_AUTHENTICITY_NOT_VERIFIED",
                 "GV3RB_ADV_GATE_STATUS_STRUCTURALLY_SUPPLIED",
                 "GV3RB_ADV_EVIDENCE_CLASSIFICATION_PRESERVED",
                 "GV3RB_ADV_READINESS_IS_LEADING_INDICATOR_ONLY"):
        assert code in r.advisory_codes, code
    # a lifecycle read is NOT an authenticity claim
    assert r.authorizes_deployment is False and r.is_advisory is True


def test_row0_is_deterministic_and_classification_agrees():
    p = readiness_policy([gate("m1", MANDATORY)], state=PolicyLifecycleState.EXPIRED)
    mk = lambda: case(policy=p, gate_results=[gate_result(p, "m1", PASS)])
    a, b = run(mk()), run(mk())
    assert a.canonical_digest() == b.canonical_digest()
    assert a.determination.classification is a.trace.classification
    assert a.trace.formula_version == "GV-3R-b.2"


def test_row0_still_requires_timezone_aware_time():
    from datetime import datetime
    from ugence_agent_value_readiness.api import ReadinessEvaluationError
    p = readiness_policy([gate("m1", MANDATORY)], state=PolicyLifecycleState.REVOKED)
    c = case(policy=p, gate_results=[gate_result(p, "m1", PASS)])
    with pytest.raises(ReadinessEvaluationError):
        evaluate_readiness(c, evaluation_time=datetime(2026, 7, 1))
