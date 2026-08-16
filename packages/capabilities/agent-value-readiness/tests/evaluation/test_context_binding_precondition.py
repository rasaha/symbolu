"""Context-to-readiness-policy binding is an R0 precondition (ADR §6 row 0).

An absent or mismatched binding means the assessment is not governed by the
policy being evaluated, so no gate-derived headline may be trusted — the result
is NOT_ASSESSABLE via R0, *before* any gate precedence. Every test here fails
against head de03b0ef (where the binding gaps ran in the later R2 rule) and
passes after the correction. Public API only.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from ugence_uvi_policy_contracts.api import (
    AssessmentContext,
    PolicyFamily,
    PolicyLifecycleState,
    PolicyReference,
    PolicyScope,
)
from ugence_agent_value_readiness.api import (
    AdvisoryComposite,
    GateStatus,
    ReadinessClassification,
    ReadinessReasonCode,
    ReadinessRuleId,
    evaluate_readiness,
)

from _fixtures import (  # noqa: E402
    CONDITIONAL,
    D,
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
R0 = ReadinessRuleId.POLICY_PRECONDITION.value
NOT_BOUND = ReadinessReasonCode.READINESS_POLICY_NOT_BOUND_TO_CONTEXT.value
MISMATCH = ReadinessReasonCode.READINESS_POLICY_REF_CONTEXT_MISMATCH.value
NOT_ACTIVE = ReadinessReasonCode.READINESS_POLICY_NOT_APPROVED_ACTIVE.value
NOT_EFFECTIVE = ReadinessReasonCode.READINESS_POLICY_NOT_EFFECTIVE_AT_EVALUATION_TIME.value
SEC = timedelta(seconds=1)


def run(c, when=NOW):
    return evaluate_readiness(c, evaluation_time=when)


def unbound_ctx(policy):
    return context(policy, bind_readiness=False)


def ref_ctx(policy, ref):
    """A context that binds ``ref`` instead of ``policy.reference``."""

    base = context(policy)
    return AssessmentContext(
        context_id=base.context_id, tenant_id=base.tenant_id, subject_id=base.subject_id,
        geography_ref=base.geography_ref, domain_ref=base.domain_ref,
        intended_outcome_ref=base.intended_outcome_ref, readiness_ref=ref)


def composite(v):
    return AdvisoryComposite(method_id="m", method_version="1", score=Decimal(v),
                             scale_min=Decimal("0"), scale_max=Decimal("100"),
                             component_result_refs=("r",))


def assert_r0(r, *codes):
    assert r.classification is CLS.NOT_ASSESSABLE, r.classification
    assert r.rule_id == R0, r.rule_id
    for c in codes:
        assert c in r.reason_codes, (c, r.reason_codes)
        assert c in r.trace.assessability_gap_codes
    # no gate-derived headline is asserted under an invalid context/policy
    assert r.determination.gate_results == ()
    assert r.determination.blocking_gate_ids == ()
    assert r.determination.indeterminate_gate_ids == ()


# =========================================================================== #
# 1-6: binding gaps beat every gate state
# =========================================================================== #
def test_no_binding_with_mandatory_fail():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, ctx=unbound_ctx(p), gate_results=[gate_result(p, "m1", FAIL)]))
    assert_r0(r, NOT_BOUND)
    # the failure is still visible as a diagnostic
    assert r.trace.mandatory_failure_gate_ids == ("m1",)


def test_mismatched_reference_with_mandatory_fail():
    p = readiness_policy([gate("m1", MANDATORY)], pid="rp-A")
    other = readiness_policy([gate("m1", MANDATORY)], pid="rp-B")
    r = run(case(policy=p, ctx=ref_ctx(p, other.reference),
                 gate_results=[gate_result(p, "m1", FAIL)]))
    assert_r0(r, MISMATCH)
    assert r.trace.mandatory_failure_gate_ids == ("m1",)


def test_no_binding_with_mandatory_indeterminate():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, ctx=unbound_ctx(p), gate_results=[gate_result(p, "m1", IND)]))
    assert_r0(r, NOT_BOUND)
    assert r.trace.mandatory_indeterminate_gate_ids == ("m1",)


def test_mismatch_with_missing_applicable_gate():
    p = readiness_policy([gate("m1", MANDATORY), gate("m2", MANDATORY)], pid="rp-A")
    other = readiness_policy([gate("m1", MANDATORY)], pid="rp-B")
    r = run(case(policy=p, ctx=ref_ctx(p, other.reference),
                 gate_results=[gate_result(p, "m1", PASS)]))
    assert_r0(r, MISMATCH)
    assert r.trace.missing_required_gate_ids == ("m2",)


def test_no_binding_with_all_gates_passing():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, ctx=unbound_ctx(p), gate_results=[gate_result(p, "m1", PASS)]))
    assert_r0(r, NOT_BOUND)


def test_mismatch_with_all_gates_passing():
    p = readiness_policy([gate("m1", MANDATORY)], pid="rp-A")
    other = readiness_policy([gate("m1", MANDATORY)], pid="rp-B")
    r = run(case(policy=p, ctx=ref_ctx(p, other.reference),
                 gate_results=[gate_result(p, "m1", PASS)]))
    assert_r0(r, MISMATCH)


def test_binding_gap_beats_pilot_ready():
    p = readiness_policy([gate("m1", MANDATORY, applicability=(PILOT,))])
    r = run(case(policy=p, target=PILOT, ctx=unbound_ctx(p),
                 gate_results=[gate_result(p, "m1", PASS, target=PILOT)]))
    assert_r0(r, NOT_BOUND)


def test_binding_gap_beats_ready_with_conditions():
    p = readiness_policy([gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(policy=p, ctx=unbound_ctx(p), gate_results=[gate_result(p, "c1", FAIL)],
                 conditions=[condition("x1", "c1")]))
    assert_r0(r, NOT_BOUND)


# =========================================================================== #
# 13: identity components compared individually
# =========================================================================== #
@pytest.mark.parametrize(
    "kwargs,label",
    [
        (dict(policy_id="different-id"), "policy_id"),
        (dict(version="99"), "version"),
        (dict(content_digest="b" * 64), "content_digest"),
        (dict(scope=PolicyScope.TENANT, tenant_id="t1"), "scope/tenant"),
    ],
)
def test_each_identity_component_mismatch_is_r0(kwargs, label):
    p = readiness_policy([gate("m1", MANDATORY)])
    base = dict(policy_id=p.reference.policy_id, policy_family=PolicyFamily.READINESS,
                version=p.reference.version, content_digest=p.reference.content_digest,
                scope=p.reference.scope, tenant_id=p.reference.tenant_id)
    base.update(kwargs)
    r = run(case(policy=p, ctx=ref_ctx(p, PolicyReference(**base)),
                 gate_results=[gate_result(p, "m1", PASS)]))
    assert_r0(r, MISMATCH)


def test_family_mismatch_is_unconstructible_on_the_context():
    """AssessmentContext already refuses a non-READINESS readiness_ref."""

    from ugence_uvi_policy_contracts.api import PolicyContractError
    p = readiness_policy([gate("m1", MANDATORY)])
    wrong_family = PolicyReference(policy_id="x", policy_family=PolicyFamily.DOMAIN,
                                   version="1", content_digest=D)
    with pytest.raises(PolicyContractError):
        ref_ctx(p, wrong_family)


# =========================================================================== #
# 7-9: valid binding preserves normal precedence
# =========================================================================== #
def test_valid_binding_mandatory_fail_is_not_ready():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", FAIL)]))
    assert r.classification is CLS.NOT_READY
    assert r.rule_id == ReadinessRuleId.MANDATORY_FAIL.value
    assert r.determination.blocking_gate_ids == ("m1",)


def test_valid_binding_mandatory_indeterminate_uses_its_own_rule():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", IND)]))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert r.rule_id == ReadinessRuleId.MANDATORY_INDETERMINATE.value


def test_valid_binding_missing_gate_uses_the_incomplete_input_rule():
    p = readiness_policy([gate("m1", MANDATORY), gate("m2", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]))
    assert r.classification is CLS.NOT_ASSESSABLE
    assert r.rule_id == ReadinessRuleId.ASSESSABILITY_GAP.value


def test_valid_binding_all_pass_is_deployment_ready():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]))
    assert r.classification is CLS.DEPLOYMENT_READY


def test_valid_binding_pilot_ready():
    p = readiness_policy([gate("m1", MANDATORY, applicability=(PILOT,))])
    r = run(case(policy=p, target=PILOT,
                 gate_results=[gate_result(p, "m1", PASS, target=PILOT)]))
    assert r.classification is CLS.PILOT_READY


def test_valid_binding_ready_with_conditions():
    p = readiness_policy([gate("c1", CONDITIONAL, compensable=True)])
    r = run(case(policy=p, gate_results=[gate_result(p, "c1", FAIL)],
                 conditions=[condition("x1", "c1")]))
    assert r.classification is CLS.READY_WITH_CONDITIONS


def test_production_only_failure_stays_diagnostic_during_pilot():
    p = readiness_policy([gate("mp", MANDATORY, applicability=(PILOT,)),
                          gate("mprod", MANDATORY, applicability=(PROD,))])
    r = run(case(policy=p, target=PILOT,
                 gate_results=[gate_result(p, "mp", PASS, target=PILOT),
                               gate_result(p, "mprod", FAIL, target=PILOT)]))
    assert r.classification is CLS.PILOT_READY
    assert r.trace.diagnostic_gate_ids == ("mprod",)


# =========================================================================== #
# 10-12: combined R0 failures
# =========================================================================== #
def test_binding_gap_plus_expired_policy():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, ctx=unbound_ctx(p), gate_results=[gate_result(p, "m1", PASS)]),
            when=T1 + SEC)
    assert_r0(r, NOT_BOUND, NOT_EFFECTIVE)


def test_binding_gap_plus_invalid_lifecycle():
    p = readiness_policy([gate("m1", MANDATORY)], state=PolicyLifecycleState.REVOKED)
    r = run(case(policy=p, ctx=unbound_ctx(p), gate_results=[gate_result(p, "m1", PASS)]))
    assert_r0(r, NOT_BOUND, NOT_ACTIVE)


def test_mismatch_plus_not_yet_effective():
    p = readiness_policy([gate("m1", MANDATORY)],
                         effective_from=T1, effective_to=T1 + timedelta(days=365))
    other = readiness_policy([gate("m1", MANDATORY)], pid="rp-B")
    r = run(case(policy=p, ctx=ref_ctx(p, other.reference),
                 gate_results=[gate_result(p, "m1", PASS)]))
    assert_r0(r, MISMATCH, NOT_EFFECTIVE)


def test_all_r0_reasons_plus_mandatory_fail_retained_and_ordered():
    p = readiness_policy([gate("m1", MANDATORY)], state=PolicyLifecycleState.EXPIRED,
                         effective_to=T0 + timedelta(days=1))
    other = readiness_policy([gate("m1", MANDATORY)], pid="rp-B")
    r = run(case(policy=p, ctx=ref_ctx(p, other.reference),
                 gate_results=[gate_result(p, "m1", FAIL)]))
    assert_r0(r, MISMATCH, NOT_ACTIVE, NOT_EFFECTIVE)
    # declaration-driven ordering: lifecycle, effectivity, binding
    expected = [c for c in (NOT_ACTIVE, NOT_EFFECTIVE, MISMATCH) if c in r.reason_codes]
    assert [c for c in r.reason_codes if c in expected] == expected
    assert r.trace.mandatory_failure_gate_ids == ("m1",)


# =========================================================================== #
# 14-16: determinism and inertness under R0
# =========================================================================== #
def test_reordering_and_composite_cannot_change_r0():
    p = readiness_policy([gate("m1", MANDATORY), gate("m2", MANDATORY)])
    g = [gate_result(p, "m1", FAIL), gate_result(p, "m2", PASS)]
    ctx_ = unbound_ctx(p)
    a = run(case(policy=p, ctx=ctx_, gate_results=g, composite=composite("0")))
    b = run(case(policy=p, ctx=ctx_, gate_results=g, composite=composite("100")))
    assert a.classification is b.classification is CLS.NOT_ASSESSABLE
    assert a.rule_id == b.rule_id and a.reason_codes == b.reason_codes

    c = run(case(policy=p, ctx=ctx_, gate_results=list(reversed(g)), composite=composite("0")))
    assert a.canonical_digest() == c.canonical_digest()
    assert a.trace.canonical_digest() == c.trace.canonical_digest()


def test_identical_inputs_identical_output_under_r0():
    p = readiness_policy([gate("m1", MANDATORY)])
    mk = lambda: case(policy=p, ctx=unbound_ctx(p), gate_results=[gate_result(p, "m1", PASS)])
    a, b = run(mk()), run(mk())
    assert a.canonical_digest() == b.canonical_digest()
    assert a.reason_codes == b.reason_codes
    assert a.trace.canonical_digest() == b.trace.canonical_digest()


def test_r0_binding_preserves_advisories_and_authorizes_nothing():
    p = readiness_policy([gate("m1", MANDATORY)])
    r = run(case(policy=p, ctx=unbound_ctx(p), gate_results=[gate_result(p, "m1", PASS)]))
    for code in ("GV3RB_ADV_ADVISORY_ONLY_NOT_DEPLOYMENT_AUTHORIZATION",
                 "GV3RB_ADV_POLICY_AUTHENTICITY_NOT_VERIFIED",
                 "GV3RB_ADV_GATE_STATUS_STRUCTURALLY_SUPPLIED",
                 "GV3RB_ADV_EVIDENCE_CLASSIFICATION_PRESERVED",
                 "GV3RB_ADV_READINESS_IS_LEADING_INDICATOR_ONLY"):
        assert code in r.advisory_codes, code
    assert r.authorizes_deployment is False and r.is_advisory is True
    assert r.trace.formula_version == "GV-3R-b.3"


def test_single_canonical_detection_path():
    """The binding gaps must not also fire in the later incomplete-input rule."""

    p = readiness_policy([gate("m1", MANDATORY), gate("m2", MANDATORY)])
    # a case whose ONLY problem is an incomplete gate set must not report binding
    r = run(case(policy=p, gate_results=[gate_result(p, "m1", PASS)]))
    assert r.rule_id == ReadinessRuleId.ASSESSABILITY_GAP.value
    assert NOT_BOUND not in r.reason_codes and MISMATCH not in r.reason_codes
