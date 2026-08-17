"""Phase 4B adversarial suite: fail-closed admission, containment, and the honest boundary.

Every case here must fail closed *before* unauthorized downstream observation, or — where
it is admitted — must be shown to grant nothing. Three groups:

1. **Fail-closed admission.** Malformed, mismatched, expired, masqueraded and smuggled v2
   requests, each proven to be rejected by its own gate with no collaborator reached.
2. **Authority containment.** Even a fully valid v2 request terminates at a non-executable
   risk decision: no envelope, no ActionGate, no execution authority.
3. **Integrity is not authenticity.** The tests that pin what Phase 4B deliberately does
   NOT prove. No test in this file claims authenticity, because none of them establish it.

The happy-path counterpart is ``tests/seam/test_phase4b_seam_admission.py``.
"""

from __future__ import annotations

import ast
import inspect
from datetime import timedelta

import pytest

from risk_authority.api import evaluation_seam as seam_module
from risk_authority.integrations import (
    EVALUATION_REQUEST_SCHEMA_VERSION,
    SeamContractError,
    SubjectBindingValidation,
    SubjectContext,
    SubjectRiskDecision,
    SubjectRiskDisposition,
    SubjectRiskEvaluationRequest,
    SubjectRiskEvaluationRequestV2,
    SubjectRiskNonDecisionReason,
    validate_subject_binding,
)

from ..contract.test_subject_context_contracts import (
    ADR_CONTEXT_DIGEST,
    ADR_SUBJECT_DIGEST,
    FROZEN_V1_DIGEST,
    FROZEN_V2_REQUEST_DIGEST,
    REC_DIGEST,
    adr_binding,
    adr_context,
    v1_request,
    v2_request,
)
from ..seam.test_phase4b_seam_admission import (
    CallLog,
    SpyClock,
    downstream,
    production_seam,
)


# ============================================================ FAIL-CLOSED ADMISSION
def test_a_v2_request_without_a_binding_cannot_be_admitted():
    # subject_context and recommendation_digest are co-required, so the only way to reach
    # the seam without a binding is to omit BOTH. Such a request is behaviorally
    # v1-equivalent in shape but is still a v2 CLASS object, and v2 admission requires a
    # reconcilable binding — it must not be silently treated as a v1 request.
    seam, log = production_seam()
    unbound = SubjectRiskEvaluationRequestV2(
        subject_type="cloud_scaling.capacity_action", subject_id="wl-checkout-api",
        subject_digest=ADR_SUBJECT_DIGEST, tenant_id="tnt-acme",
        requested_purpose="cloud_scaling.capacity_action",
        requested_domain="cloud_scaling",
        requested_scope=v2_request().requested_scope)

    result = seam.evaluate(unbound)
    assert result.disposition is SubjectRiskDisposition.NOT_EVALUATED
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.INVALID_SUBJECT
    assert downstream(log) == []


@pytest.mark.parametrize("bad_digest", [
    "", "sha256:", "sha256:zzzz", "deadbeef", "sha256:" + "F" * 64, "sha256:" + "a" * 63,
    "sha256:" + "a" * 65, None,
])
def test_a_malformed_outer_recommendation_digest_is_refused_at_construction(bad_digest):
    # It never even becomes a request, so it can never reach the seam. A missing digest
    # (None) is refused too, because the context is present and they are co-required.
    with pytest.raises(SeamContractError):
        v2_request(recommendation_digest=bad_digest)


def test_a_context_digest_mismatch_fails_closed_before_resolution():
    # The classic partial tamper: an altered raw context left paired with a stale digest.
    seam, log = production_seam()
    tampered = v2_request(subject_context=SubjectContext.from_dict(
        {**adr_context().to_canonical_dict(), "magnitude_after": 99999}))
    result = seam.evaluate(tampered)
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.INVALID_SUBJECT
    assert "binding:SubjectBindingError" in result.reason_codes
    assert downstream(log) == []


def test_a_subject_digest_mismatch_fails_closed_before_resolution():
    seam, log = production_seam()
    result = seam.evaluate(v2_request(subject_digest="sha256:" + "b" * 64))
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.INVALID_SUBJECT
    assert downstream(log) == []


@pytest.mark.parametrize("field_name,value", [
    ("tenant_id", "tnt-attacker"),
    ("subject_id", "wl-someone-elses-api"),
    ("subject_type", "cloud_scaling.something_else"),
])
def test_an_identity_mismatch_against_the_carried_binding_fails_closed(field_name, value):
    # The binding is reconstructed from the AUTHORITATIVE OUTER fields, so changing any
    # one of them changes the recomputed subject_digest and stops reconciling.
    seam, log = production_seam()
    result = seam.evaluate(v2_request(**{field_name: value}))
    assert result.disposition is SubjectRiskDisposition.NOT_EVALUATED
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.INVALID_SUBJECT
    assert downstream(log) == []


@pytest.mark.parametrize("unknown_field", [
    "tenant_id", "subject_id", "policy_id", "risk_outcome", "control_results",
    "executable", "cloud_provider",
])
def test_an_unknown_context_field_is_refused_and_never_normalized_away(unknown_field):
    payload = {**adr_context().to_canonical_dict(), unknown_field: "x"}
    with pytest.raises(SeamContractError):
        SubjectContext.from_dict(payload)


def test_a_smuggled_context_mutation_is_caught_by_revalidation():
    # A frozen-dataclass bypass: the instance is mutated after construction, so its own
    # digest no longer matches what the request committed to.
    seam, log = production_seam()
    smuggled = v2_request()
    object.__setattr__(smuggled.subject_context, "environment", "attacker-controlled")
    result = seam.evaluate(smuggled)
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.INVALID_SUBJECT
    assert downstream(log) == []


@pytest.mark.parametrize("expired_by", [
    timedelta(microseconds=1), timedelta(minutes=1), timedelta(days=365),
])
def test_an_expired_subject_validity_window_fails_closed_at_every_scale(expired_by):
    log = CallLog()
    valid_until = adr_context().subject_valid_until
    seam, _ = production_seam(log=log, clock=SpyClock(log, valid_until + expired_by))
    result = seam.evaluate(v2_request())
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.EXPIRED_SUBJECT
    assert downstream(log) == []


def test_the_last_instant_of_the_validity_window_is_still_admitted():
    # The boundary is inclusive; proving the expiry gate is not merely always-on.
    log = CallLog()
    valid_until = adr_context().subject_valid_until
    seam, _ = production_seam(log=log, clock=SpyClock(log, valid_until))
    result = seam.evaluate(v2_request())
    assert result.non_decision_reason is not SubjectRiskNonDecisionReason.EXPIRED_SUBJECT


# ============================================================ AUTHORITY CONTAINMENT
def test_a_fully_valid_v2_request_never_reaches_the_envelope_issuer():
    seam, _ = production_seam()
    calls = []
    seam._app.issue_envelope = lambda *a, **k: calls.append("envelope")  # type: ignore
    result = seam.evaluate(v2_request())
    assert result.disposition is SubjectRiskDisposition.RISK_PASSED
    assert calls == []


def test_a_fully_valid_v2_request_never_reaches_actiongate():
    seam, _ = production_seam()
    calls = []
    seam._app.authorize_action = lambda *a, **k: calls.append("actiongate")  # type: ignore
    seam.evaluate(v2_request())
    assert calls == []


def test_every_execution_flag_stays_false_on_the_serialized_v2_decision():
    seam, _ = production_seam()
    serialized = seam.evaluate(v2_request()).to_canonical_dict()
    for flag in ("authorization_performed", "envelope_issued", "actiongate_invoked",
                 "actuation_performed", "effect_verified", "executable"):
        assert serialized[flag] is False, flag


@pytest.mark.parametrize("flag", [
    "authorization_performed", "envelope_issued", "actiongate_invoked",
    "actuation_performed", "effect_verified", "executable",
])
def test_a_forged_execution_flag_on_a_v2_decision_is_rejected_not_normalized(flag):
    seam, _ = production_seam()
    payload = seam.evaluate(v2_request()).to_canonical_dict()
    payload[flag] = True
    with pytest.raises(SeamContractError):
        SubjectRiskDecision.from_dict(payload)


@pytest.mark.parametrize("forbidden", [
    "policy_id", "workflow_ir_id", "control_results", "control_status", "risk_outcome",
    "risk_decision", "envelope", "signing_key", "credential", "execution_instruction",
])
def test_the_v2_request_has_no_authority_bearing_field_to_forge(forbidden):
    assert forbidden not in SubjectRiskEvaluationRequestV2.__dataclass_fields__


def _executable_module_source(module) -> str:
    """The module's source with every docstring stripped and comments dropped.

    Prose describing what the seam does *not* do must not be able to satisfy — or to
    fail — an assertion about what it does. ``ast.unparse`` discards comments, and the
    walk below removes module/class/function docstrings."""

    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:]
    return ast.unparse(tree)


def test_the_seam_never_gained_an_execution_surface_in_phase_4b():
    source = _executable_module_source(seam_module)
    for token in ("issue_envelope", "authorize_action", "ActionGate", "kubernetes",
                  "boto3", "credential"):
        assert token not in source, token


# ================================================ INTEGRITY IS NOT AUTHENTICITY
def test_admission_does_not_verify_the_recommendation_digest_against_anything():
    # The seam holds no recommendation, no reconstructor and no resolver for one, so it
    # cannot possibly check that recommendation_digest corresponds to a real
    # CapacityActionRecommendation. Recording that absence is the point: an absent check
    # must stay visibly absent rather than be simulated by a placeholder.
    source = _executable_module_source(seam_module)
    for token in ("CapacityActionRecommendation", "recommendation_resolver",
                  "verify_recommendation", "authenticate"):
        assert token not in source, token


def test_an_arbitrary_recommendation_digest_is_admitted_when_self_consistent():
    # A digest of all-9s corresponds to no recommendation that has ever existed, yet a
    # self-consistent request carrying it is admitted. This is the documented Phase 4B
    # boundary: BINDING INTEGRITY, never source authenticity. The Cloud Scaling adapter
    # remains responsible for reconstructing the real recommendation and requiring
    # rec.digest() equality before a request enters the trusted path.
    fake_rec = "sha256:" + "9" * 64
    binding = adr_binding().__class__(
        tenant_id="tnt-acme", subject_id="wl-checkout-api",
        subject_type="cloud_scaling.capacity_action",
        recommendation_digest=fake_rec, context_digest=ADR_CONTEXT_DIGEST)
    request = v2_request(recommendation_digest=fake_rec, subject_digest=binding.digest())

    seam, _ = production_seam()
    result = seam.evaluate(request)
    assert result.non_decision_reason is not SubjectRiskNonDecisionReason.INVALID_SUBJECT
    # Admitted — and still non-executable, which is the guarantee that does hold.
    assert result.executable is False


def test_the_validator_still_grants_nothing_when_the_seam_calls_it():
    validation = validate_subject_binding(v2_request())
    assert isinstance(validation, SubjectBindingValidation)
    assert (validation.policy_resolved, validation.risk_evaluated,
            validation.authority_granted, validation.envelope_issued,
            validation.actiongate_invoked, validation.actuation_performed,
            validation.effect_verified, validation.executable) == (False,) * 8


def test_a_validation_cannot_carry_a_context_that_disagrees_with_its_digest():
    # The context handed to a subject-aware resolver is bound to the digest that was
    # reconciled, so a validation claiming one context while carrying another is refused.
    with pytest.raises(SeamContractError):
        SubjectBindingValidation(
            tenant_id="tnt-acme", subject_id="wl-checkout-api",
            subject_type="cloud_scaling.capacity_action",
            recommendation_digest=REC_DIGEST, context_digest=ADR_CONTEXT_DIGEST,
            subject_digest=ADR_SUBJECT_DIGEST, binding=adr_binding(),
            context=SubjectContext.from_dict(
                {**adr_context().to_canonical_dict(), "environment": "staging"}))


# ============================================================ V1 PRESERVATION
def test_the_frozen_v1_request_digest_is_unchanged_by_phase_4b():
    assert v1_request().digest() == FROZEN_V1_DIGEST


def test_the_frozen_v2_request_digest_is_unchanged_by_phase_4b():
    # Phase 4B changes seam ADMISSION, not the v2 contract, so the Phase 4A frozen
    # identity must survive untouched.
    assert v2_request().digest() == FROZEN_V2_REQUEST_DIGEST


def test_v1_serialization_gains_no_v2_or_phase_4b_field():
    canonical = v1_request().to_canonical_dict()
    for absent in ("subject_context", "recommendation_digest", "subject_binding",
                   "context_digest"):
        assert absent not in canonical, absent
    assert canonical["schema_version"] == EVALUATION_REQUEST_SCHEMA_VERSION


def test_v1_is_still_not_accepted_by_the_v2_binding_validator():
    with pytest.raises(SeamContractError):
        validate_subject_binding(v1_request())


def test_v1_and_v2_remain_unrelated_types_after_the_seam_widening():
    assert not isinstance(v2_request(), SubjectRiskEvaluationRequest)
    assert not issubclass(SubjectRiskEvaluationRequestV2, SubjectRiskEvaluationRequest)


def test_the_v1_non_decision_reasons_are_unchanged():
    # Phase 4B adds exactly one member and renames/removes none, so no existing consumer
    # of the taxonomy can break.
    existing = {
        "UNSUPPORTED_SCHEMA_VERSION", "INVALID_SUBJECT", "EXPIRED_SUBJECT",
        "NO_AUTHORITATIVE_POLICY", "AMBIGUOUS_POLICY", "EXPIRED_POLICY",
        "MISSING_TRUSTED_EVIDENCE_PROVIDER", "EVALUATOR_UNAVAILABLE",
        "AUTHORITY_UNAVAILABLE", "SCOPE_BINDING_FAILED", "TENANT_SCOPE_MISMATCH",
    }
    names = {member.name for member in SubjectRiskNonDecisionReason}
    assert existing <= names
    assert names - existing == {"CALLER_SUPPLIED_EVALUATION_TIME"}
