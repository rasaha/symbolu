"""Determinism, immutability, and the request contract's refusals.

An identical assessment must produce an identical outcome — the same
classification, the same ordered codes, the same trace and the same digest —
regardless of the order the caller happened to supply its inputs, and regardless
of what the caller does to its own lists afterwards.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from _orchestration_fixtures import (
    ARBITRARY_DIGEST,
    CONDITIONAL,
    MANDATORY,
    PROD,
    T_MID,
    TENANT,
    StubConditionVerifier,
    StubGateVerifier,
    condition,
    context,
    gate,
    gate_result,
    issued_resolver,
    readiness_policy,
    request,
)
from ugence_uvi_policy_contracts.api import PolicyFamily, PolicyReference

from ugence_agent_value_readiness.api import (
    AdvisoryComposite,
    GateStatus,
    ReadinessAssessmentError,
    ReadinessAssessmentRequest,
    ReadinessTrustGapCode,
    assess_readiness,
)

POLICY = readiness_policy(
    [
        gate("m1", MANDATORY),
        gate("m2", MANDATORY),
        gate("c1", CONDITIONAL, compensable=True),
        gate("c2", CONDITIONAL, compensable=True),
    ],
    policy_id="determinism-policy",
)


def _assess(req, **kwargs):
    kwargs.setdefault("policy_resolver", issued_resolver(POLICY))
    kwargs.setdefault("gate_verifier", StubGateVerifier())
    kwargs.setdefault("condition_verifier", StubConditionVerifier())
    return assess_readiness(req, **kwargs)


def _results(order=("m1", "m2", "c1", "c2")):
    statuses = {"m1": GateStatus.PASS, "m2": GateStatus.PASS, "c1": GateStatus.FAIL,
                "c2": GateStatus.PASS}
    return [gate_result(POLICY, gid, statuses[gid]) for gid in order]


def _conditions(order=("cond-a", "cond-b")):
    sources = {"cond-a": "c1", "cond-b": "c1"}
    return [condition(cid, sources[cid]) for cid in order]


# --------------------------------------------------------------------------- #
# Order independence
# --------------------------------------------------------------------------- #
def test_reordering_gate_results_changes_nothing():
    forward = _assess(request(policy=POLICY, gate_results=_results()))
    reversed_ = _assess(
        request(policy=POLICY, gate_results=_results(("c2", "c1", "m2", "m1")))
    )

    assert forward.classification is reversed_.classification
    assert forward.trace.canonical_digest() == reversed_.trace.canonical_digest()
    assert forward.canonical_digest() == reversed_.canonical_digest()
    assert forward.trace.gate_verifications == reversed_.trace.gate_verifications
    assert forward.trust_gap_codes == reversed_.trust_gap_codes


def test_reordering_conditions_changes_nothing():
    forward = _assess(
        request(policy=POLICY, gate_results=_results(), conditions=_conditions())
    )
    reversed_ = _assess(
        request(
            policy=POLICY,
            gate_results=_results(),
            conditions=_conditions(("cond-b", "cond-a")),
        )
    )

    assert forward.classification is reversed_.classification
    assert forward.canonical_digest() == reversed_.canonical_digest()
    assert forward.trace.condition_verifications == reversed_.trace.condition_verifications


def test_a_reordered_request_has_the_same_canonical_digest():
    forward = request(policy=POLICY, gate_results=_results(), conditions=_conditions())
    backward = request(
        policy=POLICY,
        gate_results=_results(("c2", "c1", "m2", "m1")),
        conditions=_conditions(("cond-b", "cond-a")),
    )
    assert forward.canonical_digest() == backward.canonical_digest()


def test_repeating_an_identical_assessment_is_bit_for_bit_identical():
    req = request(policy=POLICY, gate_results=_results(), conditions=_conditions())
    first = _assess(req)
    second = _assess(req)

    assert first.canonical_digest() == second.canonical_digest()
    assert first.evaluation.canonical_digest() == second.evaluation.canonical_digest()
    assert first.trust_gap_codes == second.trust_gap_codes


def test_gap_codes_are_emitted_in_declaration_order_not_discovery_order():
    outcome = _assess(
        request(policy=POLICY, gate_results=_results()),
        policy_resolver=None,
    )
    declared = [c.value for c in ReadinessTrustGapCode]
    positions = [declared.index(code) for code in outcome.trust_gap_codes]
    assert positions == sorted(positions)


# --------------------------------------------------------------------------- #
# Immutability
# --------------------------------------------------------------------------- #
def test_mutating_a_caller_owned_list_afterwards_cannot_reach_the_request():
    results = _results()
    req = request(policy=POLICY, gate_results=results)
    digest_before = req.canonical_digest()

    results.append(gate_result(POLICY, "m1", GateStatus.FAIL))
    results.clear()

    assert isinstance(req.gate_results, tuple)
    assert len(req.gate_results) == 4
    assert req.canonical_digest() == digest_before


def test_mutating_a_caller_owned_condition_list_cannot_reach_the_request():
    conditions = _conditions()
    req = ReadinessAssessmentRequest(
        assessment_id="a1",
        tenant_id=TENANT,
        subject_id="a1",
        context=context(POLICY),
        readiness_policy_ref=POLICY.reference,
        requested_target=PROD,
        evaluation_time=T_MID,
        conditions=conditions,
    )
    conditions.clear()
    assert len(req.conditions) == 2


def test_the_request_is_frozen():
    req = request(policy=POLICY, gate_results=_results())
    with pytest.raises(Exception):
        req.evaluation_time = T_MID


def test_the_trace_collections_are_real_tuples():
    outcome = _assess(request(policy=POLICY, gate_results=_results(), conditions=_conditions()))
    for value in (
        outcome.trace.gate_verifications,
        outcome.trace.condition_verifications,
        outcome.trace.admitted_gate_ids,
        outcome.trace.rejected_gate_ids,
        outcome.trace.admitted_condition_ids,
        outcome.trace.rejected_condition_ids,
        outcome.trace.trust_gap_codes,
        outcome.trace.dispositions,
    ):
        assert isinstance(value, tuple)


# --------------------------------------------------------------------------- #
# Request-contract refusals
# --------------------------------------------------------------------------- #
def _request(**overrides):
    kwargs = dict(
        assessment_id="a1",
        tenant_id=TENANT,
        subject_id="a1",
        context=context(POLICY),
        readiness_policy_ref=POLICY.reference,
        requested_target=PROD,
        evaluation_time=T_MID,
    )
    kwargs.update(overrides)
    return ReadinessAssessmentRequest(**kwargs)


def test_a_naive_evaluation_time_is_rejected():
    with pytest.raises(ReadinessAssessmentError):
        _request(evaluation_time=datetime(2026, 6, 1))


def test_a_non_datetime_evaluation_time_is_rejected():
    for value in ("2026-06-01T00:00:00Z", 1780000000, None, object()):
        with pytest.raises(ReadinessAssessmentError):
            _request(evaluation_time=value)


def test_evaluation_time_has_no_default():
    import dataclasses

    field = {f.name: f for f in dataclasses.fields(ReadinessAssessmentRequest)}[
        "evaluation_time"
    ]
    assert field.default is dataclasses.MISSING
    assert field.default_factory is dataclasses.MISSING


def test_a_scalar_substituted_for_a_sequence_is_rejected():
    for field in ("gate_results", "conditions", "intelligence_results", "evidence_refs"):
        for scalar in ("m1", b"m1", bytearray(b"m1"), {"m1": 1}, 7):
            with pytest.raises(ReadinessAssessmentError):
                _request(**{field: scalar})


def test_a_cross_tenant_or_cross_subject_request_is_rejected():
    with pytest.raises(ReadinessAssessmentError):
        _request(tenant_id="another-tenant")
    with pytest.raises(ReadinessAssessmentError):
        _request(subject_id="another-subject")


def test_a_non_readiness_policy_reference_is_rejected():
    valuation_ref = PolicyReference(
        policy_id="v1",
        policy_family=PolicyFamily.VALUATION,
        version="1.0.0",
        content_digest=ARBITRARY_DIGEST,
    )
    with pytest.raises(ReadinessAssessmentError):
        _request(readiness_policy_ref=valuation_ref)


def test_a_foreign_object_is_not_an_assessment_request():
    with pytest.raises(ReadinessAssessmentError):
        assess_readiness({"assessment_id": "a1"})
    with pytest.raises(ReadinessAssessmentError):
        assess_readiness(None)


# --------------------------------------------------------------------------- #
# The request cannot express a conclusion
# --------------------------------------------------------------------------- #
def test_the_request_has_no_classification_trust_or_authorization_field():
    import dataclasses

    names = {f.name for f in dataclasses.fields(ReadinessAssessmentRequest)}
    for forbidden in (
        "classification",
        "readiness_classification",
        "determination",
        "resolved",
        "trusted",
        "verified",
        "is_verified",
        "authorizes_deployment",
        "deployment_authorized",
        "lifecycle_state",
        "policy_lifecycle",
        "readiness_policy",
    ):
        assert forbidden not in names, forbidden


def test_the_request_carries_no_financial_field():
    import dataclasses

    names = {f.name for f in dataclasses.fields(ReadinessAssessmentRequest)}
    for token in (
        "roi",
        "money",
        "cost",
        "benefit",
        "currency",
        "amount",
        "price",
        "revenue",
        "forecast",
        "value",
    ):
        assert not any(token in name for name in names), token


def test_the_request_cannot_carry_a_second_policy_body():
    """The policy body arrives only from resolution, so nothing can disagree."""

    import dataclasses

    from ugence_uvi_policy_contracts.api import ReadinessPolicy

    for field in dataclasses.fields(ReadinessAssessmentRequest):
        assert field.type is not ReadinessPolicy
        assert "ReadinessPolicy" not in str(field.type)

    with pytest.raises(TypeError):
        ReadinessAssessmentRequest(
            assessment_id="a1",
            tenant_id=TENANT,
            subject_id="a1",
            context=context(POLICY),
            readiness_policy_ref=POLICY.reference,
            requested_target=PROD,
            evaluation_time=T_MID,
            readiness_policy=POLICY,
        )


def test_the_composite_min_and_max_yield_identical_traces():
    def composite(score):
        return AdvisoryComposite(
            method_id="m",
            method_version="1",
            score=Decimal(score),
            scale_min=Decimal("0"),
            scale_max=Decimal("1"),
            component_result_refs=("r1",),
        )

    low = _assess(request(policy=POLICY, gate_results=_results(), composite=composite("0")))
    high = _assess(request(policy=POLICY, gate_results=_results(), composite=composite("1")))

    assert low.classification is high.classification
    assert low.trace.trust_gap_codes == high.trace.trust_gap_codes
    assert low.evaluation.trace.rule_id == high.evaluation.trace.rule_id
    assert low.evaluation.reason_codes == high.evaluation.reason_codes


# --------------------------------------------------------------------------- #
# No hidden inputs
# --------------------------------------------------------------------------- #
def test_the_outcome_never_depends_on_the_wall_clock():
    """Two assessments at very different real times agree completely."""

    req = request(policy=POLICY, gate_results=_results())
    first = _assess(req)
    # A second run cannot differ: nothing in the boundary reads a clock.
    second = _assess(req)
    assert first.canonical_digest() == second.canonical_digest()
    assert first.trace.evaluation_time == T_MID == req.evaluation_time


def test_an_explicit_evaluation_time_is_the_only_instant_used():
    early = request(
        policy=POLICY,
        gate_results=_results(),
        evaluation_time=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    late = request(
        policy=POLICY,
        gate_results=_results(),
        evaluation_time=datetime(2026, 11, 1, tzinfo=timezone.utc),
    )
    early_outcome = _assess(early)
    late_outcome = _assess(late)

    assert early_outcome.trace.evaluation_time == early.evaluation_time
    assert late_outcome.trace.evaluation_time == late.evaluation_time
    assert early_outcome.canonical_digest() != late_outcome.canonical_digest()
