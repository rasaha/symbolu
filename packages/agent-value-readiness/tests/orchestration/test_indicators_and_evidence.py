"""Indicators stay distinct, diagnostic, and evidentially honest.

Orchestration adds a trust boundary; it does not add a requirement. Intelligence,
Capability and Adoption remain three separate families, requirements remain
policy/gate-driven, and no evidence axis is ever elevated on the way through.
"""

from __future__ import annotations

from decimal import Decimal

from _orchestration_fixtures import (
    MANDATORY,
    PROD,
    T_MID,
    TENANT,
    StubConditionVerifier,
    StubGateVerifier,
    claim,
    context,
    gate,
    gate_result,
    indicators,
    issued_resolver,
    readiness_policy,
    request,
)
from ugence_governance_contracts.api import (
    AttestationStatus,
    AttributionStatus,
    SourceBasis,
    TransformationMethod,
    VerificationStatus,
)

from ugence_agent_value_readiness.api import (
    AdvisoryComposite,
    GateStatus,
    ReadinessAssessmentError,
    ReadinessAssessmentRequest,
    ReadinessClassification,
    ReadinessIndicatorClass,
    assess_readiness,
    evaluate_readiness,
)

import pytest

POLICY = readiness_policy([gate("m1", MANDATORY)], policy_id="indicator-policy")


def _assess(req, policy=POLICY, **kwargs):
    kwargs.setdefault("policy_resolver", issued_resolver(policy))
    kwargs.setdefault("gate_verifier", StubGateVerifier())
    kwargs.setdefault("condition_verifier", StubConditionVerifier())
    return assess_readiness(req, **kwargs)


def _ready_request(**kwargs):
    return request(
        policy=POLICY, gate_results=[gate_result(POLICY, "m1", GateStatus.PASS)], **kwargs
    )


# --------------------------------------------------------------------------- #
# Requirements stay gate-driven
# --------------------------------------------------------------------------- #
def test_zero_indicators_with_a_gate_complete_policy_is_still_ready():
    """No global "all three families required" heuristic is reintroduced."""

    outcome = _assess(_ready_request(with_indicators=False))

    assert outcome.classification is ReadinessClassification.DEPLOYMENT_READY
    assert outcome.evaluation.determination.intelligence_results == ()
    assert outcome.evaluation.determination.capability_results == ()
    assert outcome.evaluation.determination.adoption_results == ()


def test_supplying_indicators_changes_nothing_about_the_tier():
    without = _assess(_ready_request(with_indicators=False))
    with_them = _assess(_ready_request(with_indicators=True))

    assert with_them.classification is without.classification
    assert with_them.evaluation.trace.rule_id == without.evaluation.trace.rule_id
    assert with_them.evaluation.reason_codes == without.evaluation.reason_codes


def test_a_favourable_indicator_cannot_rescue_a_verified_mandatory_failure():
    req = request(
        policy=POLICY,
        gate_results=[gate_result(POLICY, "m1", GateStatus.FAIL)],
        with_indicators=True,
    )
    outcome = _assess(req)
    assert outcome.classification is ReadinessClassification.NOT_READY


def test_the_three_indicator_families_stay_distinct():
    intel, cap, ado = indicators()
    assert intel[0].indicator_class is ReadinessIndicatorClass.INTELLIGENCE
    assert cap[0].indicator_class is ReadinessIndicatorClass.CAPABILITY
    assert ado[0].indicator_class is ReadinessIndicatorClass.ADOPTION


# --------------------------------------------------------------------------- #
# Evidence honesty
# --------------------------------------------------------------------------- #
def test_evidence_axes_are_carried_through_unchanged():
    outcome = _assess(_ready_request(with_indicators=True))

    carried = outcome.evaluation.determination.intelligence_results[0].claim
    original = claim("c-int")
    assert carried.source_basis is SourceBasis.REPORTED is original.source_basis
    assert carried.transformation_method is TransformationMethod.DIRECT
    assert carried.attestation_status is AttestationStatus.UNATTESTED
    assert carried.attribution_status is AttributionStatus.NOT_APPLICABLE
    assert carried.verification_status is VerificationStatus.UNVERIFIED


def test_a_verified_gate_result_does_not_elevate_the_claims_axes():
    """Gate verification proves the gate, never the evidence classification."""

    outcome = _assess(_ready_request(with_indicators=True))
    for group in (
        outcome.evaluation.determination.intelligence_results,
        outcome.evaluation.determination.capability_results,
        outcome.evaluation.determination.adoption_results,
    ):
        for result in group:
            assert result.claim.source_basis is SourceBasis.REPORTED
            assert result.claim.verification_status is VerificationStatus.UNVERIFIED
            assert result.claim.attribution_status is AttributionStatus.NOT_APPLICABLE


def _request_with_indicators(intelligence):
    return ReadinessAssessmentRequest(
        assessment_id="a",
        tenant_id=TENANT,
        subject_id="a1",
        context=context(POLICY),
        readiness_policy_ref=POLICY.reference,
        requested_target=PROD,
        evaluation_time=T_MID,
        intelligence_results=intelligence,
    )


def test_indicators_must_keep_their_exact_tenant_and_subject_binding():
    intel, _, _ = indicators(tenant="another-tenant", subject="another-subject")
    with pytest.raises(ReadinessAssessmentError):
        _request_with_indicators(intel)


def test_an_indicator_bound_to_another_context_is_refused():
    intel, _, _ = indicators(context_id="a-different-context")
    with pytest.raises(ReadinessAssessmentError):
        _request_with_indicators(intel)


# --------------------------------------------------------------------------- #
# The advisory composite stays inert
# --------------------------------------------------------------------------- #
def _composite(score):
    return AdvisoryComposite(
        method_id="m",
        method_version="1",
        score=Decimal(score),
        scale_min=Decimal("0"),
        scale_max=Decimal("1"),
        component_result_refs=("ir1",),
    )


def test_the_composite_cannot_move_the_tier_in_either_direction():
    low = _assess(_ready_request(composite=_composite("0")))
    high = _assess(_ready_request(composite=_composite("1")))

    assert low.classification is high.classification is ReadinessClassification.DEPLOYMENT_READY
    assert low.evaluation.trace.rule_id == high.evaluation.trace.rule_id
    assert low.evaluation.reason_codes == high.evaluation.reason_codes


def test_a_maximal_composite_cannot_rescue_a_mandatory_failure():
    req = request(
        policy=POLICY,
        gate_results=[gate_result(POLICY, "m1", GateStatus.FAIL)],
        composite=_composite("1"),
    )
    outcome = _assess(req)
    assert outcome.classification is ReadinessClassification.NOT_READY


def test_the_composite_is_carried_through_unchanged():
    outcome = _assess(_ready_request(composite=_composite("0.5")))
    assert outcome.evaluation.determination.advisory_composite == _composite("0.5")
    assert outcome.evaluation.trace.advisory_composite_carried is True


# --------------------------------------------------------------------------- #
# The evaluator remains independently usable
# --------------------------------------------------------------------------- #
def test_the_standalone_evaluator_needs_no_orchestration_configuration():
    """GV-3R-b keeps working with no resolver, verifier or authority wiring."""

    from ugence_agent_value_readiness.api import ReadinessEvaluationCase

    case = ReadinessEvaluationCase(
        case_id="standalone",
        tenant_id=TENANT,
        subject_id="a1",
        context=context(POLICY),
        readiness_policy=POLICY,
        readiness_policy_ref=POLICY.reference,
        requested_target=PROD,
        gate_results=(gate_result(POLICY, "m1", GateStatus.PASS),),
    )
    result = evaluate_readiness(case, evaluation_time=T_MID)

    assert result.classification is ReadinessClassification.DEPLOYMENT_READY
    assert result.authorizes_deployment is False


def test_orchestration_reproduces_the_standalone_classification_exactly():
    """The orchestrator adds a boundary, never a second algorithm."""

    from ugence_agent_value_readiness.api import ReadinessEvaluationCase

    case = ReadinessEvaluationCase(
        case_id="assessment-1",
        tenant_id=TENANT,
        subject_id="a1",
        context=context(POLICY),
        readiness_policy=POLICY,
        readiness_policy_ref=POLICY.reference,
        requested_target=PROD,
        gate_results=(gate_result(POLICY, "m1", GateStatus.PASS),),
    )
    standalone = evaluate_readiness(case, evaluation_time=T_MID)
    orchestrated = _assess(_ready_request())

    assert orchestrated.evaluation.canonical_digest() == standalone.canonical_digest()
