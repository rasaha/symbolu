"""Adversarial/negative conformance for the v2 subject-context layer (Phase 4A).

Every case here must **fail closed**: a typed ``SeamContractError`` (or its
``SubjectBindingError`` subclass), never a silently-accepted value, never a
successful validation, and never anything authority-bearing.

The ADR requires negative coverage of at least 2x the happy path; the happy-path
counterpart is ``tests/contract/test_subject_context_contracts.py``.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from risk_authority.domain import Scope
from risk_authority.integrations import (
    EVALUATION_REQUEST_SCHEMA_VERSION,
    SeamContractError,
    SubjectBinding,
    SubjectBindingError,
    SubjectBindingValidation,
    SubjectContext,
    SubjectRiskEvaluationRequestV2,
    validate_subject_binding,
)

from ..contract.test_subject_context_contracts import (
    ADR_CONTEXT_DIGEST,
    ADR_SUBJECT_DIGEST,
    REC_DIGEST,
    T0,
    adr_binding,
    adr_context,
    v1_request,
    v2_request,
)

# ADR §5.3 tamper demonstration: `environment: prod -> staging` with a stale digest.
TAMPERED_CONTEXT_DIGEST = "sha256:7d0c44ea7a501417f3cb0f454ceaa70eabbc4c65587d547066470d2796e88164"
TAMPERED_SUBJECT_DIGEST = "sha256:24875cdc6ff29904bd83ad012b62fae93f97ca2531703ee261c0de8cd6744ab9"


def context_dict(**overrides) -> dict:
    data = adr_context().to_canonical_dict()
    data.update(overrides)
    return data


def binding_dict(**overrides) -> dict:
    data = adr_binding().to_canonical_dict()
    data.update(overrides)
    return data


def tampered_context() -> SubjectContext:
    return SubjectContext(
        action_type="scale_up",
        subject_asserted_at=T0,
        subject_valid_from=T0,
        subject_valid_until=T0 + timedelta(minutes=15),
        environment="staging",  # the altered fact
        region="eu-west-1",
        zone=None,
        compute_group="cluster-7",
        resource_class="web",
        magnitude_before=6,
        magnitude_after=9,
    )


# --- unknown / surplus fields -------------------------------------------------------


def test_context_rejects_an_unknown_field():
    with pytest.raises(SeamContractError):
        SubjectContext.from_dict(context_dict(subject_id="wl-checkout-api"))


def test_binding_rejects_an_unknown_field():
    with pytest.raises(SeamContractError):
        SubjectBinding.from_dict(binding_dict(evidence_references=[]))


def test_v2_request_rejects_a_surplus_field():
    data = v2_request().to_canonical_dict()
    data["extra_field"] = "x"
    with pytest.raises(SeamContractError):
        SubjectRiskEvaluationRequestV2.from_dict(data)


@pytest.mark.parametrize("field_name", [
    "policy_id", "control_status", "control_results", "risk_class", "risk_decision",
    "authorization_envelope", "envelope_id", "execution_instruction", "executable",
    "credential", "signing_key",
])
def test_context_rejects_authority_bearing_field_names(field_name):
    # There is no field through which a caller can supply policy, control status,
    # authorization or execution: the closed field set excludes them structurally.
    with pytest.raises(SeamContractError):
        SubjectContext.from_dict(context_dict(**{field_name: "PASS"}))


@pytest.mark.parametrize("field_name", ["policy_id", "control_status", "envelope_id", "executable"])
def test_v2_request_rejects_authority_bearing_field_names(field_name):
    data = v2_request().to_canonical_dict()
    data[field_name] = "PASS"
    with pytest.raises(SeamContractError):
        SubjectRiskEvaluationRequestV2.from_dict(data)


def test_context_requires_an_explicit_schema_version():
    data = context_dict()
    del data["schema_version"]
    with pytest.raises(SeamContractError):
        SubjectContext.from_dict(data)


def test_binding_requires_every_anchor():
    data = binding_dict()
    del data["recommendation_digest"]
    with pytest.raises(SeamContractError):
        SubjectBinding.from_dict(data)


def test_v2_request_requires_an_explicit_schema_version():
    data = v2_request().to_canonical_dict()
    del data["schema_version"]
    with pytest.raises(SeamContractError):
        SubjectRiskEvaluationRequestV2.from_dict(data)


# --- wrong / cross-schema tags ------------------------------------------------------


@pytest.mark.parametrize("bad_tag", [
    "risk-subject-context-2", "risk-subject-binding-1",
    "risk-subject-evaluation-request-1", "", "RISK-SUBJECT-CONTEXT-1",
])
def test_context_rejects_a_foreign_schema_tag(bad_tag):
    with pytest.raises(SeamContractError):
        SubjectContext.from_dict(context_dict(schema_version=bad_tag))


@pytest.mark.parametrize("bad_tag", ["risk-subject-context-1", "risk-subject-binding-2", ""])
def test_binding_rejects_a_foreign_schema_tag(bad_tag):
    with pytest.raises(SeamContractError):
        SubjectBinding.from_dict(binding_dict(schema_version=bad_tag))


@pytest.mark.parametrize("bad_tag", [EVALUATION_REQUEST_SCHEMA_VERSION, "risk-subject-context-1", ""])
def test_v2_request_rejects_a_foreign_schema_tag(bad_tag):
    data = v2_request().to_canonical_dict()
    data["schema_version"] = bad_tag
    with pytest.raises(SeamContractError):
        SubjectRiskEvaluationRequestV2.from_dict(data)


# --- malformed / substituted digests ------------------------------------------------


@pytest.mark.parametrize("bad_digest", [
    "sha256:abc", "abc", "", "sha256:" + "1" * 63, "sha256:" + "1" * 65,
    "sha256:" + "G" * 64, "sha256:" + "A" * 64, "sha512:" + "1" * 64, "SHA256:" + "1" * 64,
])
def test_binding_rejects_a_malformed_recommendation_digest(bad_digest):
    with pytest.raises(SeamContractError):
        SubjectBinding.from_dict(binding_dict(recommendation_digest=bad_digest))


@pytest.mark.parametrize("bad_digest", ["sha256:abc", "", "not-a-digest"])
def test_binding_rejects_a_malformed_context_digest(bad_digest):
    with pytest.raises(SeamContractError):
        SubjectBinding.from_dict(binding_dict(context_digest=bad_digest))


def test_v2_request_rejects_a_malformed_subject_digest():
    with pytest.raises(SeamContractError):
        v2_request(subject_digest="sha256:abc")


def test_v2_request_rejects_a_malformed_recommendation_digest():
    with pytest.raises(SeamContractError):
        v2_request(recommendation_digest="not-a-digest")


def test_cross_schema_digest_substitution_fails_closed():
    # A context_digest presented in the subject_digest slot never reconciles: the two
    # objects embed different schema tags, so their canonical bytes cannot collide.
    assert ADR_CONTEXT_DIGEST != ADR_SUBJECT_DIGEST
    with pytest.raises(SubjectBindingError):
        validate_subject_binding(v2_request(subject_digest=ADR_CONTEXT_DIGEST))


def test_binding_digest_slot_substitution_changes_the_subject_digest():
    substituted = SubjectBinding.from_dict(binding_dict(context_digest=ADR_SUBJECT_DIGEST))
    assert substituted.digest() != ADR_SUBJECT_DIGEST


def test_a_request_digest_is_never_accepted_as_a_subject_digest():
    with pytest.raises(SubjectBindingError):
        validate_subject_binding(v2_request(subject_digest=v2_request().digest()))


# --- float / bool magnitude attacks -------------------------------------------------


@pytest.mark.parametrize("field_name", ["magnitude_before", "magnitude_after"])
@pytest.mark.parametrize("bad_value", [6.0, 0.5, -3.5, float("inf")])
def test_context_rejects_a_float_magnitude(field_name, bad_value):
    with pytest.raises(SeamContractError):
        SubjectContext.from_dict(context_dict(**{field_name: bad_value}))


@pytest.mark.parametrize("field_name", ["magnitude_before", "magnitude_after"])
@pytest.mark.parametrize("bad_value", [True, False])
def test_context_rejects_a_bool_magnitude(field_name, bad_value):
    # bool is an int subclass in Python: True must never canonicalize as a magnitude.
    with pytest.raises(SeamContractError):
        SubjectContext.from_dict(context_dict(**{field_name: bad_value}))


@pytest.mark.parametrize("bad_value", ["6", [6], {"v": 6}])
def test_context_rejects_a_non_integer_magnitude(bad_value):
    with pytest.raises(SeamContractError):
        SubjectContext.from_dict(context_dict(magnitude_before=bad_value))


# --- timestamps ---------------------------------------------------------------------


def test_context_rejects_a_naive_timestamp():
    with pytest.raises(SeamContractError):
        SubjectContext(
            action_type="scale_up",
            subject_asserted_at=datetime(2026, 8, 13, 4, 0, 0),  # no tzinfo
            subject_valid_from=T0,
            subject_valid_until=T0 + timedelta(minutes=15),
        )


def test_context_rejects_a_non_utc_offset():
    plus_two = timezone(timedelta(hours=2))
    with pytest.raises(SeamContractError):
        SubjectContext(
            action_type="scale_up",
            subject_asserted_at=datetime(2026, 8, 13, 6, 0, 0, tzinfo=plus_two),
            subject_valid_from=T0,
            subject_valid_until=T0 + timedelta(minutes=15),
        )


@pytest.mark.parametrize("bad_ts", [
    "2026-08-13T04:00:00Z", "2026-08-13 04:00:00.000000Z", "2026-08-13T04:00:00.000000+00:00",
    "2026-08-13T04:00:00.000000", "not-a-timestamp", "",
])
def test_context_rejects_a_malformed_timestamp_string(bad_ts):
    with pytest.raises((SeamContractError, ValueError)):
        SubjectContext.from_dict(context_dict(subject_asserted_at=bad_ts))


def test_context_rejects_a_non_datetime_timestamp():
    with pytest.raises(SeamContractError):
        SubjectContext(
            action_type="scale_up",
            subject_asserted_at=1_755_000_000,
            subject_valid_from=T0,
            subject_valid_until=T0,
        )


def test_v2_request_rejects_a_naive_evaluation_time():
    with pytest.raises(SeamContractError):
        v2_request(evaluation_time=datetime(2026, 8, 13, 4, 0, 0))


# --- temporal ordering --------------------------------------------------------------


def test_context_rejects_assertion_before_the_validity_window():
    with pytest.raises(SeamContractError):
        SubjectContext(
            action_type="scale_up",
            subject_asserted_at=T0 - timedelta(seconds=1),
            subject_valid_from=T0,
            subject_valid_until=T0 + timedelta(minutes=15),
        )


def test_context_rejects_assertion_after_the_validity_window():
    with pytest.raises(SeamContractError):
        SubjectContext(
            action_type="scale_up",
            subject_asserted_at=T0 + timedelta(minutes=16),
            subject_valid_from=T0,
            subject_valid_until=T0 + timedelta(minutes=15),
        )


def test_context_rejects_an_inverted_validity_window():
    with pytest.raises(SeamContractError):
        SubjectContext(
            action_type="scale_up",
            subject_asserted_at=T0,
            subject_valid_from=T0 + timedelta(minutes=15),
            subject_valid_until=T0 - timedelta(minutes=15),
        )


# --- action_type --------------------------------------------------------------------


def test_context_rejects_a_missing_action_type():
    data = context_dict()
    del data["action_type"]
    with pytest.raises(SeamContractError):
        SubjectContext.from_dict(data)


@pytest.mark.parametrize("bad_action", ["", " scale_up", "scale_up ", "scale_up\n"])
def test_context_rejects_a_non_canonical_action_type(bad_action):
    with pytest.raises(SeamContractError):
        SubjectContext.from_dict(context_dict(action_type=bad_action))


@pytest.mark.parametrize("bad_action", [None, 7, True, ["scale_up"]])
def test_context_rejects_a_non_string_action_type(bad_action):
    with pytest.raises(SeamContractError):
        SubjectContext.from_dict(context_dict(action_type=bad_action))


def test_context_rejects_a_non_nfc_normalized_string():
    # NFD "e" + combining acute; the canonicalizer would silently NFC it, changing the
    # bytes the digest freezes, so it is rejected instead.
    with pytest.raises(SeamContractError):
        SubjectContext.from_dict(context_dict(environment="éu-prod"))


# --- missing vs named ---------------------------------------------------------------


def test_missing_optional_string_is_distinct_from_the_empty_string():
    absent = SubjectContext.from_dict(context_dict(environment=None))
    named_empty = SubjectContext.from_dict(context_dict(environment=""))
    assert absent.digest() != named_empty.digest()


def test_missing_magnitude_is_distinct_from_zero():
    absent = SubjectContext.from_dict(context_dict(magnitude_before=None))
    zero = SubjectContext.from_dict(context_dict(magnitude_before=0))
    assert absent.digest() != zero.digest()


def test_every_named_optional_change_moves_the_context_digest():
    for name, value in (("environment", "staging"), ("region", "us-east-1"),
                        ("zone", "az-1"), ("compute_group", "cluster-8"),
                        ("resource_class", "worker"), ("magnitude_before", 7),
                        ("magnitude_after", 10)):
        assert SubjectContext.from_dict(context_dict(**{name: value})).digest() != ADR_CONTEXT_DIGEST


# --- immutability -------------------------------------------------------------------


@pytest.mark.parametrize("target,attr", [
    ("context", "environment"), ("context", "magnitude_after"), ("context", "schema_version"),
    ("binding", "tenant_id"), ("binding", "context_digest"),
    ("request", "tenant_id"), ("request", "subject_digest"),
])
def test_contracts_are_frozen_against_mutation(target, attr):
    obj = {"context": adr_context(), "binding": adr_binding(), "request": v2_request()}[target]
    with pytest.raises(FrozenInstanceError):
        setattr(obj, attr, "mutated")


def test_validation_result_is_frozen():
    result = validate_subject_binding(v2_request())
    with pytest.raises(FrozenInstanceError):
        result.subject_digest = "sha256:" + "0" * 64


# --- layered-commitment tampering ---------------------------------------------------


def test_adr_tamper_fixture_digests_reproduce():
    tampered = tampered_context()
    assert tampered.digest() == TAMPERED_CONTEXT_DIGEST
    assert adr_binding(context_digest=TAMPERED_CONTEXT_DIGEST).digest() == TAMPERED_SUBJECT_DIGEST


def test_altered_raw_context_with_a_stale_subject_digest_fails_closed():
    # The exact ADR §5.3 tamper demonstration: the resolver never sees "staging".
    with pytest.raises(SubjectBindingError):
        validate_subject_binding(v2_request(subject_context=tampered_context()))


@pytest.mark.parametrize("name,value", [
    ("environment", "staging"), ("region", "us-east-1"), ("zone", "az-9"),
    ("compute_group", "cluster-99"), ("resource_class", "gpu"),
    ("magnitude_before", 1), ("magnitude_after", 9999), ("action_type", "scale_down"),
])
def test_any_altered_context_fact_with_a_stale_digest_fails_closed(name, value):
    altered = SubjectContext.from_dict(context_dict(**{name: value}))
    with pytest.raises(SubjectBindingError):
        validate_subject_binding(v2_request(subject_context=altered))


# --- binding-anchor substitution ----------------------------------------------------


def test_tenant_substitution_fails_closed():
    with pytest.raises(SubjectBindingError):
        validate_subject_binding(v2_request(tenant_id="tnt-evil"))


def test_subject_substitution_fails_closed():
    with pytest.raises(SubjectBindingError):
        validate_subject_binding(v2_request(subject_id="wl-billing-api"))


def test_subject_type_substitution_fails_closed():
    with pytest.raises(SubjectBindingError):
        validate_subject_binding(v2_request(subject_type="cloud_scaling.other_action"))


def test_recommendation_digest_substitution_fails_closed():
    with pytest.raises(SubjectBindingError):
        validate_subject_binding(v2_request(recommendation_digest="sha256:" + "9" * 64))


def test_a_context_bound_to_another_tenants_binding_fails_closed():
    foreign = SubjectBinding(
        tenant_id="tnt-evil", subject_id="wl-checkout-api",
        subject_type="cloud_scaling.capacity_action",
        recommendation_digest=REC_DIGEST, context_digest=ADR_CONTEXT_DIGEST)
    with pytest.raises(SubjectBindingError):
        validate_subject_binding(v2_request(subject_digest=foreign.digest()))


# --- validator input guards ---------------------------------------------------------


def test_validator_rejects_a_v1_request_with_no_conversion():
    with pytest.raises(SubjectBindingError):
        validate_subject_binding(v1_request())


@pytest.mark.parametrize("bogus", [None, "request", 42, {"schema_version": "risk-subject-evaluation-request-2"}])
def test_validator_rejects_a_non_v2_object(bogus):
    with pytest.raises(SubjectBindingError):
        validate_subject_binding(bogus)


def test_validator_rejects_a_v2_request_carrying_no_context():
    bare = SubjectRiskEvaluationRequestV2(
        subject_type="x", subject_id="s", subject_digest="sha256:" + "0" * 64,
        tenant_id="t", requested_purpose="p", requested_domain="d",
        requested_scope=Scope(purposes=("p",)))
    with pytest.raises(SubjectBindingError):
        validate_subject_binding(bare)


def test_v2_request_rejects_a_context_without_a_recommendation_digest():
    with pytest.raises(SeamContractError):
        v2_request(recommendation_digest=None)


def test_v2_request_rejects_a_recommendation_digest_without_a_context():
    with pytest.raises(SeamContractError):
        v2_request(subject_context=None)


def test_v2_request_rejects_a_non_context_object_in_the_context_slot():
    with pytest.raises(SeamContractError):
        v2_request(subject_context={"schema_version": "risk-subject-context-1"})


def test_validator_catches_a_context_mutated_through_the_frozen_bypass():
    # object.__setattr__ can bypass frozen dataclasses; the validator re-parses the
    # context from its own canonical form rather than trusting the instance.
    smuggled = adr_context()
    object.__setattr__(smuggled, "schema_version", "risk-subject-context-99")
    with pytest.raises(SeamContractError):
        validate_subject_binding(v2_request(subject_context=smuggled))


# --- authority boundary -------------------------------------------------------------


def test_a_successful_validation_grants_nothing():
    result = validate_subject_binding(v2_request())
    assert (result.policy_resolved, result.risk_evaluated, result.authority_granted,
            result.envelope_issued, result.actiongate_invoked, result.actuation_performed,
            result.effect_verified, result.executable) == (False,) * 8


@pytest.mark.parametrize("flag", [
    "policy_resolved", "risk_evaluated", "authority_granted", "envelope_issued",
    "actiongate_invoked", "actuation_performed", "effect_verified", "executable",
])
def test_a_forged_authority_flag_is_rejected_not_normalized(flag):
    with pytest.raises(SeamContractError):
        SubjectBindingValidation(
            tenant_id="t", subject_id="s", subject_type="x",
            recommendation_digest=REC_DIGEST, context_digest=ADR_CONTEXT_DIGEST,
            subject_digest=ADR_SUBJECT_DIGEST, binding=adr_binding(), **{flag: True})
