"""Stage 3: only independently verified controls compensate a concern.

A compensating control is the one thing that can turn an unresolved conditional
concern into readiness, so it is the input most worth forging. Nothing here
accepts a control because it is *shaped* correctly: coverage requires the
resolved policy to mark the exact concern compensable, the control to be active
at the evaluation instant, and a configured verifier to attest its identity,
approval authority, approval evidence, owner/monitoring obligations and its
tenant / subject / context binding.
"""

from __future__ import annotations

from datetime import timedelta

from _orchestration_fixtures import (
    ARBITRARY_DIGEST,
    CONDITIONAL,
    MANDATORY,
    T_AFTER,
    T_FROM,
    T_LATER,
    T_MID,
    StubConditionVerifier,
    StubGateVerifier,
    condition,
    gate,
    gate_result,
    issued_resolver,
    readiness_policy,
    request,
)
from ugence_uvi_policy_contracts.api import PolicyReference, ReadinessTarget

from ugence_agent_value_readiness.api import (
    ConditionStatus,
    GateStatus,
    ReadinessClassification,
    ReadinessInputVerificationStatus,
    ReadinessTrustGapCode,
    assess_readiness,
)

G = ReadinessTrustGapCode
V = ReadinessInputVerificationStatus

COMPENSABLE = readiness_policy(
    [
        gate("m1", MANDATORY),
        gate("c1", CONDITIONAL, compensable=True),
        gate("c2", CONDITIONAL, compensable=True),
    ],
    policy_id="compensable",
)
NOT_COMPENSABLE = readiness_policy(
    [gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=False)],
    policy_id="not-compensable",
)
MANDATORY_ONLY = readiness_policy([gate("m1", MANDATORY)], policy_id="mandatory-only")


def _assess(req, policy, **kwargs):
    kwargs.setdefault("policy_resolver", issued_resolver(policy))
    kwargs.setdefault("gate_verifier", StubGateVerifier())
    kwargs.setdefault("condition_verifier", StubConditionVerifier())
    return assess_readiness(req, **kwargs)


def _unresolved_case(policy=COMPENSABLE, *, conditions=(), gates=None):
    """All mandatory gates PASS; ``c1`` is an unresolved conditional concern."""

    gates = (
        gates
        if gates is not None
        else [
            gate_result(policy, "m1", GateStatus.PASS),
            gate_result(policy, "c1", GateStatus.FAIL),
            gate_result(policy, "c2", GateStatus.PASS),
        ]
    )
    return request(policy=policy, gate_results=gates, conditions=conditions)


def _summary(outcome, condition_id):
    return next(s for s in outcome.condition_verifications if s.condition_id == condition_id)


# --------------------------------------------------------------------------- #
# The verified-coverage path, and its absence
# --------------------------------------------------------------------------- #
def test_a_verified_active_condition_compensates_the_exact_eligible_concern():
    outcome = _assess(_unresolved_case(conditions=[condition("cond-1", "c1")]), COMPENSABLE)

    assert outcome.classification is ReadinessClassification.READY_WITH_CONDITIONS
    assert outcome.trace.admitted_condition_ids == ("cond-1",)
    assert outcome.evaluation.trace.accepted_condition_ids == ("cond-1",)


def test_no_condition_verifier_configured_provides_no_coverage():
    outcome = _assess(
        _unresolved_case(conditions=[condition("cond-1", "c1")]),
        COMPENSABLE,
        condition_verifier=None,
    )

    assert outcome.classification is ReadinessClassification.NOT_READY
    assert G.CONDITION_VERIFIER_NOT_CONFIGURED.value in outcome.trust_gap_codes
    assert outcome.trace.admitted_condition_ids == ()
    assert _summary(outcome, "cond-1").verification_status is V.NO_VERIFIER_CONFIGURED


def test_an_unverified_active_condition_cannot_compensate():
    outcome = _assess(
        _unresolved_case(conditions=[condition("cond-1", "c1")]),
        COMPENSABLE,
        condition_verifier=StubConditionVerifier(status=V.APPROVAL_NOT_VERIFIED),
    )

    assert outcome.classification is ReadinessClassification.NOT_READY
    assert G.CONDITION_NOT_VERIFIED.value in outcome.trust_gap_codes


def test_a_rejected_condition_stays_visible_with_a_stable_reason():
    outcome = _assess(
        _unresolved_case(conditions=[condition("cond-1", "c1")]),
        COMPENSABLE,
        condition_verifier=None,
    )

    summary = _summary(outcome, "cond-1")
    assert summary.admitted is False
    assert summary.trust_gap_codes == (G.CONDITION_NOT_VERIFIED.value,)
    assert summary.source_gate_or_finding_ref == "c1"
    assert outcome.trace.rejected_condition_ids == ("cond-1",)


# --------------------------------------------------------------------------- #
# Lifecycle and the half-open window at the evaluation instant
# --------------------------------------------------------------------------- #
def test_an_inactive_lifecycle_status_provides_no_coverage():
    for status in (
        ConditionStatus.PROPOSED,
        ConditionStatus.EXPIRED,
        ConditionStatus.REVOKED,
        ConditionStatus.SATISFIED,
    ):
        outcome = _assess(
            _unresolved_case(conditions=[condition("cond-1", "c1", status=status)]),
            COMPENSABLE,
        )
        assert outcome.classification is ReadinessClassification.NOT_READY, status
        assert G.CONDITION_NOT_ACTIVE_AT_EVALUATION_TIME.value in outcome.trust_gap_codes


def test_a_not_yet_effective_condition_provides_no_coverage():
    outcome = _assess(
        _unresolved_case(conditions=[condition("cond-1", "c1", effective_from=T_LATER)]),
        COMPENSABLE,
    )
    assert outcome.classification is ReadinessClassification.NOT_READY
    assert G.CONDITION_NOT_ACTIVE_AT_EVALUATION_TIME.value in outcome.trust_gap_codes


def test_an_elapsed_window_provides_no_coverage():
    outcome = _assess(
        _unresolved_case(
            conditions=[condition("cond-1", "c1", effective_to=T_MID)]
        ),
        COMPENSABLE,
    )
    # Half-open: effective_to == evaluation_time is already outside.
    assert outcome.classification is ReadinessClassification.NOT_READY


def test_an_expired_condition_provides_no_coverage():
    outcome = _assess(
        _unresolved_case(conditions=[condition("cond-1", "c1", expiry=T_MID)]), COMPENSABLE
    )
    assert outcome.classification is ReadinessClassification.NOT_READY


def test_the_verifier_is_never_consulted_for_an_inactive_control():
    verifier = StubConditionVerifier()
    _assess(
        _unresolved_case(
            conditions=[condition("cond-1", "c1", status=ConditionStatus.REVOKED)]
        ),
        COMPENSABLE,
        condition_verifier=verifier,
    )
    assert verifier.calls == []


# --------------------------------------------------------------------------- #
# Eligibility of the concern itself
# --------------------------------------------------------------------------- #
def test_a_mandatory_concern_is_never_compensable():
    """D-6: no control, verified or not, waives a mandatory failure."""

    req = request(
        policy=MANDATORY_ONLY,
        gate_results=[gate_result(MANDATORY_ONLY, "m1", GateStatus.FAIL)],
        conditions=[condition("cond-1", "m1")],
    )
    outcome = _assess(req, MANDATORY_ONLY)

    assert outcome.classification is ReadinessClassification.NOT_READY
    assert G.CONDITION_CONCERN_NOT_CONDITIONAL.value in outcome.trust_gap_codes
    assert outcome.trace.admitted_condition_ids == ()


def test_a_conditional_gate_the_policy_does_not_mark_compensable_is_refused():
    req = request(
        policy=NOT_COMPENSABLE,
        gate_results=[
            gate_result(NOT_COMPENSABLE, "m1", GateStatus.PASS),
            gate_result(NOT_COMPENSABLE, "c1", GateStatus.FAIL),
        ],
        conditions=[condition("cond-1", "c1")],
    )
    outcome = _assess(req, NOT_COMPENSABLE)

    assert outcome.classification is ReadinessClassification.NOT_READY
    assert G.CONDITION_CONCERN_NOT_COMPENSABLE.value in outcome.trust_gap_codes


def test_a_condition_naming_a_gate_the_resolved_policy_lacks_is_refused():
    outcome = _assess(
        _unresolved_case(conditions=[condition("cond-1", "not-a-gate")]), COMPENSABLE
    )
    assert G.CONDITION_CONCERN_NOT_IN_RESOLVED_POLICY.value in outcome.trust_gap_codes
    assert outcome.classification is ReadinessClassification.NOT_READY


def test_a_condition_covering_the_wrong_gate_cannot_unlock_readiness():
    """A control over ``c2`` does not compensate the unresolved ``c1``."""

    outcome = _assess(_unresolved_case(conditions=[condition("cond-1", "c2")]), COMPENSABLE)
    assert outcome.classification is not ReadinessClassification.READY_WITH_CONDITIONS
    assert outcome.classification is ReadinessClassification.NOT_ASSESSABLE


def test_duplicate_condition_ids_reject_every_copy():
    outcome = _assess(
        _unresolved_case(
            conditions=[condition("cond-1", "c1"), condition("cond-1", "c2")]
        ),
        COMPENSABLE,
    )
    assert G.CONDITION_DUPLICATE.value in outcome.trust_gap_codes
    assert outcome.trace.admitted_condition_ids == ()
    assert outcome.classification is ReadinessClassification.NOT_READY


# --------------------------------------------------------------------------- #
# Rechecking what the condition verifier returned
# --------------------------------------------------------------------------- #
def test_a_condition_verifier_that_raises_fails_closed():
    outcome = _assess(
        _unresolved_case(conditions=[condition("cond-1", "c1")]),
        COMPENSABLE,
        condition_verifier=StubConditionVerifier(raises=True),
    )
    assert G.CONDITION_VERIFIER_ERROR.value in outcome.trust_gap_codes
    assert outcome.classification is ReadinessClassification.NOT_READY


def test_a_condition_verifier_returning_a_foreign_object_fails_closed():
    outcome = _assess(
        _unresolved_case(conditions=[condition("cond-1", "c1")]),
        COMPENSABLE,
        condition_verifier=StubConditionVerifier(returns_foreign_object=True),
    )
    assert G.CONDITION_VERIFIER_MALFORMED_RESULT.value in outcome.trust_gap_codes


def test_a_non_callable_condition_verifier_fails_closed():
    class Broken:
        verify_condition = None

    outcome = _assess(
        _unresolved_case(conditions=[condition("cond-1", "c1")]),
        COMPENSABLE,
        condition_verifier=Broken(),
    )
    assert G.CONDITION_VERIFIER_MALFORMED_RESULT.value in outcome.trust_gap_codes


def test_an_attestation_naming_a_different_condition_is_rejected():
    outcome = _assess(
        _unresolved_case(conditions=[condition("cond-1", "c1")]),
        COMPENSABLE,
        condition_verifier=StubConditionVerifier(overrides={"condition_id": "cond-other"}),
    )
    assert G.CONDITION_IDENTITY_MISMATCH.value in outcome.trust_gap_codes


def test_an_attestation_carrying_a_different_condition_digest_is_rejected():
    outcome = _assess(
        _unresolved_case(conditions=[condition("cond-1", "c1")]),
        COMPENSABLE,
        condition_verifier=StubConditionVerifier(
            overrides={"condition_digest": ARBITRARY_DIGEST}
        ),
    )
    assert G.CONDITION_DIGEST_MISMATCH.value in outcome.trust_gap_codes


def test_an_attestation_covering_a_second_concern_is_rejected():
    """One control covers exactly one concern; identity ambiguity is refused."""

    for override in (
        {"covered_gate_id": "c2"},
        {"source_gate_or_finding_ref": "c2"},
        {"gate_digest": ARBITRARY_DIGEST},
    ):
        outcome = _assess(
            _unresolved_case(conditions=[condition("cond-1", "c1")]),
            COMPENSABLE,
            condition_verifier=StubConditionVerifier(overrides=override),
        )
        assert G.CONDITION_SOURCE_REFERENCE_MISMATCH.value in outcome.trust_gap_codes, override
        assert outcome.classification is ReadinessClassification.NOT_READY, override


def test_every_returned_condition_coordinate_is_rechecked():
    other_ref = PolicyReference(
        policy_id="elsewhere",
        policy_family=COMPENSABLE.reference.policy_family,
        version="1.0.0",
        content_digest=ARBITRARY_DIGEST,
    )
    for override in (
        {"readiness_policy_ref": other_ref},
        {"tenant_id": "another-tenant"},
        {"subject_id": "another-subject"},
        {"context_digest": ARBITRARY_DIGEST},
        {"requested_target": ReadinessTarget.PILOT},
        {"verified_at": T_MID + timedelta(seconds=1)},
        {"effective_from": T_AFTER},
        {"effective_to": T_AFTER},
        {"expiry": T_AFTER},
    ):
        outcome = _assess(
            _unresolved_case(conditions=[condition("cond-1", "c1")]),
            COMPENSABLE,
            condition_verifier=StubConditionVerifier(overrides=override),
        )
        assert G.CONDITION_VERIFICATION_BINDING_MISMATCH.value in outcome.trust_gap_codes, (
            override
        )
        assert outcome.trace.admitted_condition_ids == (), override


def test_an_attestation_missing_an_approval_proof_is_rejected():
    for override in (
        {"approval_authority_verified": False},
        {"approval_evidence_verified": False},
        {"owner_and_monitoring_verified": False},
    ):
        outcome = _assess(
            _unresolved_case(conditions=[condition("cond-1", "c1")]),
            COMPENSABLE,
            condition_verifier=StubConditionVerifier(overrides=override),
        )
        assert G.CONDITION_APPROVAL_NOT_VERIFIED.value in outcome.trust_gap_codes, override
        assert outcome.classification is ReadinessClassification.NOT_READY, override


def test_a_verifier_establishing_a_non_active_status_provides_no_coverage():
    outcome = _assess(
        _unresolved_case(conditions=[condition("cond-1", "c1")]),
        COMPENSABLE,
        condition_verifier=StubConditionVerifier(
            overrides={"verified_status": ConditionStatus.REVOKED}
        ),
    )
    assert G.CONDITION_NOT_VERIFIED.value in outcome.trust_gap_codes
    assert outcome.classification is ReadinessClassification.NOT_READY


def test_the_verifier_receives_the_complete_binding_it_must_attest():
    verifier = StubConditionVerifier()
    req = _unresolved_case(conditions=[condition("cond-1", "c1")])
    _assess(req, COMPENSABLE, condition_verifier=verifier)

    (verification_request,) = verifier.calls
    resolved_gate = {g.gate_id: g for g in COMPENSABLE.gates}["c1"]
    assert verification_request.covered_gate_id == "c1"
    assert verification_request.gate_digest == resolved_gate.canonical_digest()
    assert verification_request.tenant_id == req.tenant_id
    assert verification_request.subject_id == req.subject_id
    assert verification_request.context_digest == req.context_digest
    assert verification_request.evaluation_time == T_MID
    assert verification_request.approving_authority_ref == "authority-1"
    assert verification_request.accountable_owner == "owner-1"
    assert verification_request.monitoring_requirement == "weekly override-rate review"
    assert verification_request.evidence_refs == ("ev-cond-1",)
    assert verification_request.effective_from == T_FROM
