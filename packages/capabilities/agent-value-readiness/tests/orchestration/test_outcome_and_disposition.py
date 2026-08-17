"""The outcome envelope, its construction invariants, and trust reconciliation.

Two questions are kept apart everywhere: *does a readiness headline exist* and
*what does it say*. The first is the outcome status; the second lives in exactly
one place, the GV-3R-b evaluation result. Nothing else may state, imply or
disagree with it.
"""

from __future__ import annotations

import pytest
from _orchestration_fixtures import (
    ARBITRARY_DIGEST,
    CONDITIONAL,
    MANDATORY,
    StubConditionVerifier,
    StubGateVerifier,
    condition,
    gate,
    gate_result,
    issued_resolver,
    readiness_policy,
    request,
)

from ugence_agent_value_readiness.evaluation.codes import EVALUATOR_FORMULA_VERSION

from ugence_agent_value_readiness.api import (
    READINESS_ORCHESTRATOR_VERSION,
    GateStatus,
    ReadinessAdvisoryCode,
    ReadinessAssessmentError,
    ReadinessAssessmentOutcome,
    ReadinessAssessmentStatus,
    ReadinessTrustAdvisoryState,
    assess_readiness,
)

S = ReadinessTrustAdvisoryState
A = ReadinessAdvisoryCode

POLICY = readiness_policy(
    [gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=True)], policy_id="outcome-policy"
)


def _assess(req, **kwargs):
    kwargs.setdefault("policy_resolver", issued_resolver(POLICY))
    kwargs.setdefault("gate_verifier", StubGateVerifier())
    kwargs.setdefault("condition_verifier", StubConditionVerifier())
    return assess_readiness(req, **kwargs)


def _ready_request(**kwargs):
    return request(
        policy=POLICY,
        gate_results=[
            gate_result(POLICY, "m1", GateStatus.PASS),
            gate_result(POLICY, "c1", GateStatus.PASS),
        ],
        **kwargs,
    )


def _covered_request(**kwargs):
    return request(
        policy=POLICY,
        gate_results=[
            gate_result(POLICY, "m1", GateStatus.PASS),
            gate_result(POLICY, "c1", GateStatus.FAIL),
        ],
        conditions=[condition("cond-1", "c1")],
        **kwargs,
    )


def _by_code(outcome) -> dict:
    return {d.advisory_code: d.state for d in outcome.dispositions}


# --------------------------------------------------------------------------- #
# Versions and identity
# --------------------------------------------------------------------------- #
def test_the_outcome_carries_both_versions_and_neither_replaces_the_other():
    outcome = _assess(_ready_request())

    assert outcome.trace.orchestrator_version == READINESS_ORCHESTRATOR_VERSION
    assert outcome.trace.evaluator_formula_version == EVALUATOR_FORMULA_VERSION
    assert outcome.evaluation.trace.formula_version == EVALUATOR_FORMULA_VERSION
    assert READINESS_ORCHESTRATOR_VERSION == "ugence.readiness-orchestration/v0.1"
    assert EVALUATOR_FORMULA_VERSION == "GV-3R-b.3"


def test_the_trace_binds_the_full_identity_of_the_assessment():
    req = _ready_request()
    outcome = _assess(req)

    assert outcome.trace.assessment_id == req.assessment_id
    assert outcome.trace.tenant_id == req.tenant_id
    assert outcome.trace.subject_id == req.subject_id
    assert outcome.trace.context_digest == req.context_digest
    assert outcome.trace.readiness_policy_ref == req.readiness_policy_ref
    assert outcome.trace.requested_target is req.requested_target
    assert outcome.trace.evaluation_time == req.evaluation_time
    assert outcome.trace.request_digest == req.canonical_digest()


def test_the_evaluation_agrees_with_the_trace_on_every_binding():
    outcome = _assess(_ready_request())
    determination = outcome.evaluation.determination

    assert determination.assessment_id == outcome.trace.assessment_id
    assert determination.tenant_id == outcome.trace.tenant_id
    assert determination.subject_id == outcome.trace.subject_id
    assert determination.readiness_policy_ref == outcome.trace.readiness_policy_ref
    assert determination.requested_target is outcome.trace.requested_target
    assert determination.created_at == outcome.trace.evaluation_time


# --------------------------------------------------------------------------- #
# Advisory posture — permanently
# --------------------------------------------------------------------------- #
def test_the_outcome_is_advisory_and_authorizes_nothing():
    outcome = _assess(_ready_request())

    assert outcome.is_advisory is True
    assert outcome.authorizes_deployment is False
    assert outcome.evaluation.authorizes_deployment is False
    assert outcome.trace.is_explanatory_only is True


def test_authorizes_deployment_cannot_be_changed_from_false():
    outcome = _assess(_ready_request())

    with pytest.raises(AttributeError):
        outcome.authorizes_deployment = True
    with pytest.raises(AttributeError):
        object.__setattr__(outcome, "authorizes_deployment", True)
    assert outcome.authorizes_deployment is False


def test_the_outcome_is_frozen():
    outcome = _assess(_ready_request())
    with pytest.raises(Exception):
        outcome.status = ReadinessAssessmentStatus.NOT_EVALUATED


# --------------------------------------------------------------------------- #
# Construction invariants
# --------------------------------------------------------------------------- #
def test_a_not_evaluated_outcome_cannot_carry_an_evaluation_result():
    evaluated = _assess(_ready_request())
    denied = _assess(_ready_request(), policy_resolver=None)

    with pytest.raises(ReadinessAssessmentError):
        ReadinessAssessmentOutcome(
            status=ReadinessAssessmentStatus.NOT_EVALUATED,
            trace=denied.trace,
            evaluation=evaluated.evaluation,
        )


def test_a_not_evaluated_outcome_must_name_a_trust_gap():
    evaluated = _assess(_ready_request())
    with pytest.raises(ReadinessAssessmentError):
        ReadinessAssessmentOutcome(
            status=ReadinessAssessmentStatus.NOT_EVALUATED, trace=evaluated.trace
        )


def test_an_evaluated_outcome_must_carry_exactly_one_evaluation_result():
    evaluated = _assess(_ready_request())
    with pytest.raises(ReadinessAssessmentError):
        ReadinessAssessmentOutcome(
            status=ReadinessAssessmentStatus.EVALUATED, trace=evaluated.trace, evaluation=None
        )


def test_an_outcome_whose_trace_and_evaluation_disagree_is_unconstructible():
    outcome = _assess(_ready_request())
    other = _assess(_ready_request(assessment_id="a-different-assessment"))

    with pytest.raises(ReadinessAssessmentError):
        ReadinessAssessmentOutcome(
            status=ReadinessAssessmentStatus.EVALUATED,
            trace=outcome.trace,
            evaluation=other.evaluation,
        )


def test_an_evaluated_outcome_requires_a_resolved_policy():
    evaluated = _assess(_ready_request())
    denied = _assess(_ready_request(), policy_resolver=None)

    with pytest.raises(ReadinessAssessmentError):
        ReadinessAssessmentOutcome(
            status=ReadinessAssessmentStatus.EVALUATED,
            trace=denied.trace,
            evaluation=evaluated.evaluation,
        )


def test_a_trace_carries_no_classification_field_at_all():
    """A trace/evaluation classification mismatch is unrepresentable."""

    import dataclasses

    from ugence_agent_value_readiness.api import ReadinessAssessmentTrace

    names = {f.name for f in dataclasses.fields(ReadinessAssessmentTrace)}
    assert "classification" not in names
    assert not any("classification" in name for name in names)


def test_an_unresolved_trace_cannot_carry_policy_material():
    import dataclasses

    denied = _assess(_ready_request(), policy_resolver=None)
    with pytest.raises(ReadinessAssessmentError):
        dataclasses.replace(denied.trace, issuance_record_ref="rec-1")
    with pytest.raises(ReadinessAssessmentError):
        dataclasses.replace(denied.trace, resolved_policy_digest=ARBITRARY_DIGEST)


def test_a_summary_cannot_be_admitted_and_untrusted_at_once():
    import dataclasses

    from ugence_agent_value_readiness.api import ReadinessInputVerificationStatus

    outcome = _assess(_ready_request(), gate_verifier=None)
    rejected = outcome.gate_verifications[0]

    with pytest.raises(ReadinessAssessmentError):
        dataclasses.replace(rejected, admitted=True)
    with pytest.raises(ReadinessAssessmentError):
        dataclasses.replace(
            rejected,
            verification_status=ReadinessInputVerificationStatus.VERIFIED,
            admitted=True,
        )


def test_derived_summaries_are_read_only_views_not_settable_fields():
    import dataclasses

    outcome = _assess(_ready_request())
    field_names = {f.name for f in dataclasses.fields(ReadinessAssessmentOutcome)}

    assert field_names == {"status", "trace", "evaluation"}
    for view in (
        "gate_verifications",
        "condition_verifications",
        "trust_gap_codes",
        "dispositions",
        "classification",
    ):
        assert view not in field_names
        with pytest.raises(AttributeError):
            setattr(outcome, view, ())


def test_a_directly_constructed_outcome_claims_no_authority_provenance():
    """Construction is not orchestration — the same rule the authority states."""

    outcome = _assess(_ready_request())
    forged = ReadinessAssessmentOutcome(
        status=ReadinessAssessmentStatus.EVALUATED,
        trace=outcome.trace,
        evaluation=outcome.evaluation,
    )

    # Structurally identical, and equally powerless: it authorizes nothing, and
    # nothing about it asserts that a boundary was ever consulted.
    assert forged.authorizes_deployment is False
    assert forged.is_advisory is True
    assert forged.canonical_digest() == outcome.canonical_digest()
    assert forged.trace.is_explanatory_only is True


def test_the_outcome_is_not_signed():
    import dataclasses

    outcome = _assess(_ready_request())
    names = {f.name for f in dataclasses.fields(type(outcome.trace))} | {
        f.name for f in dataclasses.fields(ReadinessAssessmentOutcome)
    }
    assert not any("signature" in n or "signed" in n or "key_id" in n for n in names)


# --------------------------------------------------------------------------- #
# Trust-advisory reconciliation
# --------------------------------------------------------------------------- #
def test_every_standing_advisory_receives_an_explicit_disposition():
    outcome = _assess(_ready_request())
    dispositions = _by_code(outcome)

    for code in (
        A.ADVISORY_ONLY_NOT_DEPLOYMENT_AUTHORIZATION,
        A.POLICY_AUTHENTICITY_NOT_VERIFIED,
        A.GATE_STATUS_STRUCTURALLY_SUPPLIED,
        A.EVIDENCE_CLASSIFICATION_PRESERVED,
        A.READINESS_IS_LEADING_INDICATOR_ONLY,
    ):
        assert code.value in dispositions


def test_policy_authenticity_is_resolved_only_by_actual_resolution():
    resolved = _assess(_ready_request())
    denied = _assess(_ready_request(), policy_resolver=None)

    assert (
        _by_code(resolved)[A.POLICY_AUTHENTICITY_NOT_VERIFIED.value]
        is S.RESOLVED_BY_POLICY_RESOLUTION
    )
    assert _by_code(denied)[A.POLICY_AUTHENTICITY_NOT_VERIFIED.value] is S.UNRESOLVED


def test_gate_status_advisory_is_resolved_only_by_gate_verification():
    verified = _assess(_ready_request())
    unverified = _assess(_ready_request(), gate_verifier=None)

    assert (
        _by_code(verified)[A.GATE_STATUS_STRUCTURALLY_SUPPLIED.value]
        is S.RESOLVED_BY_GATE_VERIFICATION
    )
    assert _by_code(unverified)[A.GATE_STATUS_STRUCTURALLY_SUPPLIED.value] is S.UNRESOLVED


def test_benchmark_and_evidence_authenticity_stay_unresolved_without_a_verifier():
    outcome = _assess(_ready_request(), gate_verifier=None)
    entry = next(
        d
        for d in outcome.dispositions
        if d.advisory_code == A.GATE_STATUS_STRUCTURALLY_SUPPLIED.value
    )
    assert entry.state is S.UNRESOLVED
    assert "benchmark" in entry.detail and "evidence" in entry.detail


def test_condition_advisories_appear_only_when_conditions_were_supplied():
    without = _by_code(_assess(_ready_request()))
    with_conditions = _by_code(_assess(_covered_request()))

    assert A.CONDITION_APPROVAL_AUTHENTICITY_NOT_VERIFIED.value not in without
    assert A.CONDITION_SCOPE_NOT_TENANT_BOUND.value not in without
    assert (
        with_conditions[A.CONDITION_APPROVAL_AUTHENTICITY_NOT_VERIFIED.value]
        is S.RESOLVED_BY_CONDITION_VERIFICATION
    )
    assert (
        with_conditions[A.CONDITION_SCOPE_NOT_TENANT_BOUND.value]
        is S.RESOLVED_BY_CONDITION_VERIFICATION
    )


def test_condition_advisories_stay_unresolved_without_a_condition_verifier():
    outcome = _assess(_covered_request(), condition_verifier=None)
    dispositions = _by_code(outcome)

    assert dispositions[A.CONDITION_APPROVAL_AUTHENTICITY_NOT_VERIFIED.value] is S.UNRESOLVED
    assert dispositions[A.CONDITION_SCOPE_NOT_TENANT_BOUND.value] is S.UNRESOLVED


def test_permanent_boundaries_are_marked_out_of_scope_not_resolved():
    dispositions = _by_code(_assess(_ready_request()))

    assert dispositions[A.ADVISORY_ONLY_NOT_DEPLOYMENT_AUTHORIZATION.value] is S.OUT_OF_SCOPE
    assert dispositions[A.EVIDENCE_CLASSIFICATION_PRESERVED.value] is S.OUT_OF_SCOPE
    assert dispositions[A.READINESS_IS_LEADING_INDICATOR_ONLY.value] is S.OUT_OF_SCOPE


def test_no_advisory_is_ever_deleted_by_orchestration():
    """Every advisory the evaluator emitted is still on the evaluation result."""

    outcome = _assess(_covered_request())
    emitted = set(outcome.evaluation.advisory_codes)
    disposed = set(_by_code(outcome))

    assert emitted <= disposed
    assert A.POLICY_AUTHENTICITY_NOT_VERIFIED.value in emitted
    assert A.GATE_STATUS_STRUCTURALLY_SUPPLIED.value in emitted


def test_a_denied_assessment_leaves_every_verifiable_advisory_unresolved():
    outcome = _assess(_covered_request(), policy_resolver=None)
    dispositions = _by_code(outcome)

    assert dispositions[A.POLICY_AUTHENTICITY_NOT_VERIFIED.value] is S.UNRESOLVED
    assert dispositions[A.GATE_STATUS_STRUCTURALLY_SUPPLIED.value] is S.UNRESOLVED
    assert dispositions[A.CONDITION_APPROVAL_AUTHENTICITY_NOT_VERIFIED.value] is S.UNRESOLVED


# --------------------------------------------------------------------------- #
# The authority's answer and the orchestrator's acceptance are separate facts
# --------------------------------------------------------------------------- #
def test_a_resolution_the_orchestrator_refuses_is_not_accepted():
    """A RESOLVED authority answer that fails an independent recheck is refused.

    The trace reports what the authority said *and*, separately, that this
    assessment did not accept it — so neither statement can be read as the
    other.
    """

    from _orchestration_fixtures import context

    from ugence_policy_authority.api import PolicyResolutionStatus

    # The context binds no readiness policy, so stage 1 resolves and then
    # refuses on the binding recheck.
    outcome = _assess(_ready_request(ctx=context(None)))

    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert outcome.trace.policy_resolution_status is PolicyResolutionStatus.RESOLVED
    assert outcome.trace.policy_resolution_accepted is False
    assert outcome.trace.issuance_record_ref == ""
    assert outcome.trace.resolved_policy_digest == ""


def test_an_evaluated_outcome_requires_an_accepted_resolution_not_merely_a_resolved_one():
    from _orchestration_fixtures import context

    evaluated = _assess(_ready_request())
    refused = _assess(_ready_request(ctx=context(None)))

    with pytest.raises(ReadinessAssessmentError):
        ReadinessAssessmentOutcome(
            status=ReadinessAssessmentStatus.EVALUATED,
            trace=refused.trace,
            evaluation=evaluated.evaluation,
        )


def test_acceptance_and_policy_material_are_the_same_fact_stated_twice():
    import dataclasses

    outcome = _assess(_ready_request())

    # Accepted but stripped of its material, or material without acceptance:
    # both are unrepresentable.
    with pytest.raises(ReadinessAssessmentError):
        dataclasses.replace(outcome.trace, issuance_record_ref="")
    with pytest.raises(ReadinessAssessmentError):
        dataclasses.replace(outcome.trace, policy_resolution_accepted=False)


# --------------------------------------------------------------------------- #
# A misconfigured boundary is never quieter than an absent one
# --------------------------------------------------------------------------- #
def test_a_malformed_gate_verifier_is_a_gap_even_with_no_gate_results():
    from ugence_agent_value_readiness.api import ReadinessTrustGapCode

    class Broken:
        verify_gate_result = "not callable"

    outcome = _assess(request(policy=POLICY), gate_verifier=Broken())
    assert ReadinessTrustGapCode.GATE_VERIFIER_MALFORMED_RESULT.value in outcome.trust_gap_codes


def test_a_malformed_condition_verifier_is_a_gap_even_with_no_verifiable_input():
    from ugence_agent_value_readiness.api import ReadinessTrustGapCode

    class Broken:
        verify_condition = None

    outcome = _assess(_covered_request(), condition_verifier=Broken())
    assert (
        ReadinessTrustGapCode.CONDITION_VERIFIER_MALFORMED_RESULT.value
        in outcome.trust_gap_codes
    )


# --------------------------------------------------------------------------- #
# A disposition is resolved only when nothing of its kind went unverified
# --------------------------------------------------------------------------- #
def test_one_unverified_gate_result_leaves_the_gate_advisory_open():
    from _orchestration_fixtures import StubGateVerifier

    outcome = _assess(
        _ready_request(), gate_verifier=StubGateVerifier(only_gate_ids=frozenset({"m1"}))
    )
    entry = next(
        d
        for d in outcome.dispositions
        if d.advisory_code == A.GATE_STATUS_STRUCTURALLY_SUPPLIED.value
    )
    assert outcome.trace.admitted_gate_ids == ("m1",)
    assert outcome.trace.rejected_gate_ids == ("c1",)
    assert entry.state is S.UNRESOLVED
    assert "1 of 2" in entry.detail


def test_one_unverified_condition_leaves_the_condition_advisories_open():
    from _orchestration_fixtures import StubConditionVerifier, condition as _condition

    request_with_two = request(
        policy=POLICY,
        gate_results=[
            gate_result(POLICY, "m1", GateStatus.PASS),
            gate_result(POLICY, "c1", GateStatus.FAIL),
        ],
        conditions=[_condition("cond-1", "c1"), _condition("cond-2", "c1")],
    )
    outcome = _assess(
        request_with_two,
        condition_verifier=StubConditionVerifier(only_condition_ids=frozenset({"cond-1"})),
    )
    dispositions = _by_code(outcome)

    assert outcome.trace.admitted_condition_ids == ("cond-1",)
    assert outcome.trace.rejected_condition_ids == ("cond-2",)
    assert dispositions[A.CONDITION_APPROVAL_AUTHENTICITY_NOT_VERIFIED.value] is S.UNRESOLVED
    assert dispositions[A.CONDITION_SCOPE_NOT_TENANT_BOUND.value] is S.UNRESOLVED
