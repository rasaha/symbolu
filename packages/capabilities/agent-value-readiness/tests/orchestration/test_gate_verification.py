"""Stage 2: only independently verified gate results reach the evaluator.

Sanitization is **subtraction**: a rejected result is absent for the evaluator,
never rewritten to a weaker status and never silently accepted. The ratified
GV-3R-b precedence then does the rest, unchanged.
"""

from __future__ import annotations

from datetime import timedelta

from _orchestration_fixtures import (
    ADVISORY,
    MANDATORY,
    PILOT,
    PROD,
    T_MID,
    StubConditionVerifier,
    StubGateVerifier,
    gate,
    gate_result,
    issued_resolver,
    literal_threshold,
    readiness_policy,
    request,
)
from ugence_uvi_policy_contracts.api import PolicyReference, ReadinessTarget

from ugence_agent_value_readiness.api import (
    GateStatus,
    ReadinessAssessmentStatus,
    ReadinessClassification,
    ReadinessInputVerificationStatus,
    ReadinessTrustGapCode,
    assess_readiness,
)

G = ReadinessTrustGapCode
V = ReadinessInputVerificationStatus

TWO_MANDATORY = readiness_policy(
    [gate("m1", MANDATORY), gate("m2", MANDATORY)], policy_id="two-mandatory"
)
ONE_MANDATORY = readiness_policy([gate("m1", MANDATORY)], policy_id="one-mandatory")
WITH_ADVISORY = readiness_policy(
    [gate("m1", MANDATORY), gate("a1", ADVISORY)], policy_id="with-advisory"
)
PILOT_AND_PROD = readiness_policy(
    [gate("m1", MANDATORY), gate("prod-only", MANDATORY, applicability=(PROD,))],
    policy_id="pilot-and-prod",
)
THRESHOLDED = readiness_policy(
    [gate("m1", MANDATORY, threshold=literal_threshold())], policy_id="thresholded"
)


def _assess(req, policy, **kwargs):
    kwargs.setdefault("policy_resolver", issued_resolver(policy))
    kwargs.setdefault("gate_verifier", StubGateVerifier())
    kwargs.setdefault("condition_verifier", StubConditionVerifier())
    return assess_readiness(req, **kwargs)


def _summary(outcome, gate_id):
    return next(s for s in outcome.gate_verifications if s.gate_id == gate_id)


# --------------------------------------------------------------------------- #
# Deny by default
# --------------------------------------------------------------------------- #
def test_no_gate_verifier_configured_admits_nothing():
    req = request(
        policy=ONE_MANDATORY, gate_results=[gate_result(ONE_MANDATORY, "m1", GateStatus.PASS)]
    )
    outcome = _assess(req, ONE_MANDATORY, gate_verifier=None)

    assert outcome.status is ReadinessAssessmentStatus.EVALUATED
    assert outcome.classification is ReadinessClassification.NOT_ASSESSABLE
    assert outcome.trace.admitted_gate_ids == ()
    assert outcome.trace.rejected_gate_ids == ("m1",)
    assert G.GATE_VERIFIER_NOT_CONFIGURED.value in outcome.trust_gap_codes
    assert G.REQUIRED_GATE_RESULT_UNVERIFIED.value in outcome.trust_gap_codes
    assert _summary(outcome, "m1").verification_status is V.NO_VERIFIER_CONFIGURED


def test_an_unverified_pass_cannot_unlock_readiness():
    req = request(
        policy=ONE_MANDATORY, gate_results=[gate_result(ONE_MANDATORY, "m1", GateStatus.PASS)]
    )
    outcome = _assess(
        req,
        ONE_MANDATORY,
        gate_verifier=StubGateVerifier(status=V.EVIDENCE_NOT_VERIFIED),
    )

    assert outcome.classification is ReadinessClassification.NOT_ASSESSABLE
    assert outcome.classification is not ReadinessClassification.DEPLOYMENT_READY
    assert _summary(outcome, "m1").admitted is False


def test_an_unverified_fail_cannot_force_not_ready():
    """A caller-supplied FAIL nobody verified must not influence the tier."""

    req = request(
        policy=ONE_MANDATORY, gate_results=[gate_result(ONE_MANDATORY, "m1", GateStatus.FAIL)]
    )
    outcome = _assess(
        req, ONE_MANDATORY, gate_verifier=StubGateVerifier(status=V.VERIFIER_ERROR)
    )

    # The gate is absent, so the case is incomplete — not NOT_READY.
    assert outcome.classification is ReadinessClassification.NOT_ASSESSABLE


def test_an_unverified_indeterminate_cannot_influence_the_tier():
    req = request(
        policy=ONE_MANDATORY,
        gate_results=[gate_result(ONE_MANDATORY, "m1", GateStatus.INDETERMINATE)],
    )
    outcome = _assess(
        req,
        ONE_MANDATORY,
        gate_verifier=StubGateVerifier(status=V.THRESHOLD_EVALUATION_NOT_VERIFIED),
    )
    assert outcome.classification is ReadinessClassification.NOT_ASSESSABLE
    assert outcome.evaluation.trace.mandatory_indeterminate_gate_ids == ()


# --------------------------------------------------------------------------- #
# Verified results and the ratified precedence
# --------------------------------------------------------------------------- #
def test_all_verified_passes_produce_the_production_tier():
    req = request(
        policy=TWO_MANDATORY,
        gate_results=[
            gate_result(TWO_MANDATORY, "m1", GateStatus.PASS),
            gate_result(TWO_MANDATORY, "m2", GateStatus.PASS),
        ],
    )
    outcome = _assess(req, TWO_MANDATORY)

    assert outcome.classification is ReadinessClassification.DEPLOYMENT_READY
    assert outcome.trace.admitted_gate_ids == ("m1", "m2")
    assert outcome.trust_gap_codes == ()


def test_all_verified_passes_produce_the_pilot_tier():
    req = request(
        policy=TWO_MANDATORY,
        target=PILOT,
        gate_results=[
            gate_result(TWO_MANDATORY, "m1", GateStatus.PASS, target=PILOT),
            gate_result(TWO_MANDATORY, "m2", GateStatus.PASS, target=PILOT),
        ],
    )
    outcome = _assess(req, TWO_MANDATORY)
    assert outcome.classification is ReadinessClassification.PILOT_READY


def test_a_verified_mandatory_fail_dominates_a_missing_required_gate():
    """FAIL dominance survives sanitization: R1 still precedes R2."""

    req = request(
        policy=TWO_MANDATORY,
        gate_results=[gate_result(TWO_MANDATORY, "m1", GateStatus.FAIL)],
    )
    outcome = _assess(req, TWO_MANDATORY)

    assert outcome.classification is ReadinessClassification.NOT_READY
    assert outcome.evaluation.trace.missing_required_gate_ids == ("m2",)


def test_a_verified_mandatory_fail_dominates_an_unverified_required_gate():
    req = request(
        policy=TWO_MANDATORY,
        gate_results=[
            gate_result(TWO_MANDATORY, "m1", GateStatus.FAIL),
            gate_result(TWO_MANDATORY, "m2", GateStatus.PASS),
        ],
    )
    outcome = _assess(
        req, TWO_MANDATORY, gate_verifier=StubGateVerifier(only_gate_ids=frozenset({"m1"}))
    )

    assert outcome.classification is ReadinessClassification.NOT_READY
    assert outcome.trace.admitted_gate_ids == ("m1",)
    assert outcome.trace.rejected_gate_ids == ("m2",)
    assert G.REQUIRED_GATE_RESULT_UNVERIFIED.value in outcome.trust_gap_codes


def test_a_missing_verified_required_gate_is_not_assessable():
    req = request(
        policy=TWO_MANDATORY,
        gate_results=[gate_result(TWO_MANDATORY, "m1", GateStatus.PASS)],
    )
    outcome = _assess(req, TWO_MANDATORY)
    assert outcome.classification is ReadinessClassification.NOT_ASSESSABLE


def test_an_unverified_advisory_result_can_neither_block_nor_elevate():
    req = request(
        policy=WITH_ADVISORY,
        gate_results=[
            gate_result(WITH_ADVISORY, "m1", GateStatus.PASS),
            gate_result(WITH_ADVISORY, "a1", GateStatus.FAIL),
        ],
    )
    outcome = _assess(
        req, WITH_ADVISORY, gate_verifier=StubGateVerifier(only_gate_ids=frozenset({"m1"}))
    )

    assert outcome.classification is ReadinessClassification.DEPLOYMENT_READY
    # An unverified advisory result is not a required-gate gap.
    assert G.REQUIRED_GATE_RESULT_UNVERIFIED.value not in outcome.trust_gap_codes


def test_a_production_only_gate_stays_diagnostic_during_pilot():
    req = request(
        policy=PILOT_AND_PROD,
        target=PILOT,
        gate_results=[gate_result(PILOT_AND_PROD, "m1", GateStatus.PASS, target=PILOT)],
    )
    outcome = _assess(req, PILOT_AND_PROD)

    assert outcome.classification is ReadinessClassification.PILOT_READY
    assert outcome.evaluation.trace.diagnostic_gate_ids == ("prod-only",)


# --------------------------------------------------------------------------- #
# Binding rechecks the orchestrator performs itself
# --------------------------------------------------------------------------- #
def test_a_gate_result_bound_to_another_policy_is_rejected():
    other = readiness_policy([gate("m1", MANDATORY)], policy_id="another-policy")
    borrowed = gate_result(ONE_MANDATORY, "m1", GateStatus.PASS, policy_ref=other.reference)
    req = request(policy=ONE_MANDATORY, gate_results=[borrowed])
    outcome = _assess(req, ONE_MANDATORY)

    assert G.GATE_RESULT_POLICY_REFERENCE_MISMATCH.value in outcome.trust_gap_codes
    assert outcome.trace.admitted_gate_ids == ()


def test_a_gate_result_for_another_target_is_rejected():
    req = request(
        policy=ONE_MANDATORY,
        target=PROD,
        gate_results=[gate_result(ONE_MANDATORY, "m1", GateStatus.PASS, target=PILOT)],
    )
    outcome = _assess(req, ONE_MANDATORY)
    assert G.GATE_RESULT_TARGET_MISMATCH.value in outcome.trust_gap_codes


def test_a_gate_absent_from_the_resolved_policy_is_rejected():
    """The RESOLVED policy — not the caller's — is the gate inventory."""

    richer = readiness_policy(
        [gate("m1", MANDATORY), gate("ghost", MANDATORY)], policy_id="richer"
    )
    ghost = gate_result(richer, "ghost", GateStatus.PASS, policy_ref=ONE_MANDATORY.reference)
    req = request(
        policy=ONE_MANDATORY,
        gate_results=[gate_result(ONE_MANDATORY, "m1", GateStatus.PASS), ghost],
    )
    outcome = _assess(req, ONE_MANDATORY)

    assert G.GATE_RESULT_GATE_NOT_IN_RESOLVED_POLICY.value in outcome.trust_gap_codes
    assert outcome.trace.admitted_gate_ids == ("m1",)


def test_a_redefined_gate_body_is_rejected():
    """A gate that is not canonically identical to the resolved one is refused."""

    tampered_policy = readiness_policy(
        [gate("m1", ADVISORY)], policy_id="one-mandatory-tampered"
    )
    tampered = gate_result(
        tampered_policy, "m1", GateStatus.PASS, policy_ref=ONE_MANDATORY.reference
    )
    req = request(policy=ONE_MANDATORY, gate_results=[tampered])
    outcome = _assess(req, ONE_MANDATORY)

    assert G.GATE_RESULT_GATE_BODY_MISMATCH.value in outcome.trust_gap_codes
    assert outcome.trace.admitted_gate_ids == ()


def test_duplicate_results_for_one_gate_reject_every_copy():
    """A conflict is never resolved by choosing one copy."""

    req = request(
        policy=ONE_MANDATORY,
        gate_results=[
            gate_result(ONE_MANDATORY, "m1", GateStatus.PASS),
            gate_result(ONE_MANDATORY, "m1", GateStatus.FAIL),
        ],
    )
    outcome = _assess(req, ONE_MANDATORY)

    assert G.GATE_RESULT_DUPLICATE.value in outcome.trust_gap_codes
    assert outcome.trace.admitted_gate_ids == ()
    assert outcome.classification is ReadinessClassification.NOT_ASSESSABLE


# --------------------------------------------------------------------------- #
# Rechecking what the verifier returned
# --------------------------------------------------------------------------- #
def test_a_verifier_that_raises_fails_closed():
    req = request(
        policy=ONE_MANDATORY, gate_results=[gate_result(ONE_MANDATORY, "m1", GateStatus.PASS)]
    )
    outcome = _assess(req, ONE_MANDATORY, gate_verifier=StubGateVerifier(raises=True))

    assert G.GATE_VERIFIER_ERROR.value in outcome.trust_gap_codes
    assert outcome.trace.admitted_gate_ids == ()


def test_a_verifier_returning_a_foreign_object_fails_closed():
    req = request(
        policy=ONE_MANDATORY, gate_results=[gate_result(ONE_MANDATORY, "m1", GateStatus.PASS)]
    )
    outcome = _assess(
        req, ONE_MANDATORY, gate_verifier=StubGateVerifier(returns_foreign_object=True)
    )

    assert G.GATE_VERIFIER_MALFORMED_RESULT.value in outcome.trust_gap_codes
    assert outcome.trace.admitted_gate_ids == ()


def test_a_non_callable_verifier_fails_closed():
    class Broken:
        verify_gate_result = "not callable"

    req = request(
        policy=ONE_MANDATORY, gate_results=[gate_result(ONE_MANDATORY, "m1", GateStatus.PASS)]
    )
    outcome = _assess(req, ONE_MANDATORY, gate_verifier=Broken())
    assert G.GATE_VERIFIER_MALFORMED_RESULT.value in outcome.trust_gap_codes


def test_a_verifier_that_verifies_a_different_status_is_rejected():
    req = request(
        policy=ONE_MANDATORY, gate_results=[gate_result(ONE_MANDATORY, "m1", GateStatus.FAIL)]
    )
    outcome = _assess(
        req,
        ONE_MANDATORY,
        gate_verifier=StubGateVerifier(overrides={"verified_status": GateStatus.PASS}),
    )

    assert G.GATE_RESULT_VERIFIED_STATUS_MISMATCH.value in outcome.trust_gap_codes
    assert outcome.trace.admitted_gate_ids == ()


def test_every_returned_coordinate_is_rechecked_independently():
    from _orchestration_fixtures import ARBITRARY_DIGEST

    req = request(
        policy=ONE_MANDATORY, gate_results=[gate_result(ONE_MANDATORY, "m1", GateStatus.PASS)]
    )
    other_ref = PolicyReference(
        policy_id="elsewhere",
        policy_family=ONE_MANDATORY.reference.policy_family,
        version="1.0.0",
        content_digest=ARBITRARY_DIGEST,
    )
    for override in (
        {"gate_id": "another-gate"},
        {"gate_digest": ARBITRARY_DIGEST},
        {"readiness_policy_ref": other_ref},
        {"tenant_id": "another-tenant"},
        {"subject_id": "another-subject"},
        {"context_digest": ARBITRARY_DIGEST},
        {"requested_target": ReadinessTarget.PILOT},
        {"verified_at": T_MID + timedelta(seconds=1)},
    ):
        outcome = _assess(
            req, ONE_MANDATORY, gate_verifier=StubGateVerifier(overrides=override)
        )
        assert G.GATE_RESULT_VERIFICATION_BINDING_MISMATCH.value in outcome.trust_gap_codes, (
            override
        )
        assert outcome.trace.admitted_gate_ids == (), override


def test_a_verified_answer_must_cover_the_evidence_the_result_cites():
    req = request(
        policy=ONE_MANDATORY,
        gate_results=[
            gate_result(ONE_MANDATORY, "m1", GateStatus.PASS, evidence_refs=("ev-1",))
        ],
    )
    outcome = _assess(
        req, ONE_MANDATORY, gate_verifier=StubGateVerifier(overrides={"evidence_verified": False})
    )

    assert G.GATE_RESULT_SUPPORTING_VERIFICATION_INCOMPLETE.value in outcome.trust_gap_codes
    assert outcome.trace.admitted_gate_ids == ()


def test_a_verified_answer_must_cover_the_threshold_evaluation():
    req = request(
        policy=THRESHOLDED, gate_results=[gate_result(THRESHOLDED, "m1", GateStatus.PASS)]
    )
    outcome = _assess(
        req,
        THRESHOLDED,
        gate_verifier=StubGateVerifier(overrides={"threshold_evaluation_verified": False}),
    )

    assert G.GATE_RESULT_SUPPORTING_VERIFICATION_INCOMPLETE.value in outcome.trust_gap_codes
    assert outcome.trace.admitted_gate_ids == ()


def test_the_verifier_is_handed_the_resolved_gate_not_the_callers_copy():
    verifier = StubGateVerifier()
    req = request(
        policy=ONE_MANDATORY, gate_results=[gate_result(ONE_MANDATORY, "m1", GateStatus.PASS)]
    )
    _assess(req, ONE_MANDATORY, gate_verifier=verifier)

    (verification_request,) = verifier.calls
    resolved_gate = {g.gate_id: g for g in ONE_MANDATORY.gates}["m1"]
    assert verification_request.policy_gate == resolved_gate
    assert verification_request.gate_digest == resolved_gate.canonical_digest()
    assert verification_request.evaluation_time == T_MID
    assert verification_request.tenant_id == req.tenant_id
    assert verification_request.subject_id == req.subject_id
    assert verification_request.context_digest == req.context_digest
