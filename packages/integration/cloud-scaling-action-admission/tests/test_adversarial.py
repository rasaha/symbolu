"""Attacks the gate must refuse: the action must be the one the envelope was issued for."""

from __future__ import annotations

from dataclasses import replace

import pytest

from risk_authority.api import ActionAdmissionRefusal as R
from risk_authority.domain.actions import CanonicalAction
from risk_authority.domain.enums import ActionGateDecision
from risk_authority.domain.envelope import ArtifactBinding
from risk_authority.integrations.actiongate import RuntimeIdentity
from ugence_cloud_scaling_authorization_contracts import ExecutionTargetScope

from _admission_fixtures import ADMISSION_INSTANT, admission_request

from ugence_cloud_scaling_action_admission import (
    BINDING_KIND_AUTHORIZATION_CANDIDATE,
    BINDING_KIND_TARGET_SCOPE,
    ActionAdmissionContractError,
    ActionAdmissionExactTypeError,
    CapacityActionGate,
    CapacityAdmissionRequest,
    capacity_action_to_canonical,
    capacity_bounds_violations,
)


def _denied(world, request=None, **kw):
    out = world.admission().admit(request or admission_request(world, **kw))
    assert out.refusal is None and not out.admitted and out.authorization is not None
    assert out.authorization.decision is ActionGateDecision.DENIED
    return out.authorization.reason_codes


def _scope(world, **over) -> ExecutionTargetScope:
    return replace(world.target_scope, **over)


# --------------------------------------------------------------------------- #
# The presented artifacts must be the bound ones
# --------------------------------------------------------------------------- #
def test_a_wider_magnitude_is_refused(world):
    s = world.target_scope
    wider = _scope(world, requested_magnitude=s.requested_magnitude + 5,
                   max_permitted_magnitude=s.max_permitted_magnitude + 5,
                   max_permitted_delta=s.max_permitted_delta + 5)
    reasons = _denied(world, target_scope=wider)
    assert any("not the one the envelope binds" in r for r in reasons)


def test_a_different_target_scope_is_refused(world):
    other = _scope(world, compute_group=(world.target_scope.compute_group or "") + "-other")
    reasons = _denied(world, target_scope=other)
    assert any("target scope" in r for r in reasons)


def test_a_different_action_type_is_refused(world):
    s = world.target_scope
    flipped = "scale_down" if s.action_type != "scale_down" else "scale_up"
    reasons = _denied(world, target_scope=_scope(world, action_type=flipped))
    assert any("not the one the envelope binds" in r for r in reasons)


def test_a_different_candidate_digest_is_refused(world):
    reasons = _denied(world, candidate_digest="sha256:" + "c" * 64)
    assert any("candidate digest" in r for r in reasons)


def test_a_forged_binding_breaks_the_signature_and_is_refused_in_the_kernel(world):
    other = _scope(world, compute_group=(world.target_scope.compute_group or "") + "-forged")
    from ugence_cloud_scaling_envelope_issuance import bare_digest
    bindings = tuple(
        ArtifactBinding(BINDING_KIND_TARGET_SCOPE, bare_digest(other.digest()))
        if b.kind == BINDING_KIND_TARGET_SCOPE else b
        for b in world.envelope.bindings.artifact_bindings)
    forged = replace(world.envelope, bindings=replace(world.envelope.bindings, artifact_bindings=bindings))
    world.app.envelopes._envelopes[(forged.tenant_id, forged.envelope_id)] = forged
    out = world.admission().admit(admission_request(world, target_scope=other))
    assert out.refusal is R.ENVELOPE_INVALID and out.authorization is None
    assert "signature" in out.detail.lower()


def test_an_envelope_without_the_bindings_is_denied_by_the_gate(world):
    stripped = replace(world.envelope, bindings=replace(world.envelope.bindings, artifact_bindings=()))
    gate = CapacityActionGate(target_scope=world.target_scope, candidate_digest=world.candidate.candidate_digest)
    action = capacity_action_to_canonical(stripped, world.target_scope)
    verdict = gate.authorize(
        authorization_id="auth.v1:" + "0" * 64, envelope=stripped, action=action,
        identity=RuntimeIdentity(action.tenant_id, action.actor_id, action.model_id, "s"),
        key_ring=world.app._key_ring, revocation_state=world.app.revocation, now=ADMISSION_INSTANT)
    assert verdict.decision is ActionGateDecision.DENIED
    assert any("binds no execution target scope" in r for r in verdict.reason_codes)
    assert any("binds no authorization candidate" in r for r in verdict.reason_codes)


# --------------------------------------------------------------------------- #
# Identity and shape
# --------------------------------------------------------------------------- #
def _gate_verdict(world, action, identity=None, **gate_kw):
    gate = CapacityActionGate(target_scope=gate_kw.pop("target_scope", world.target_scope),
                              candidate_digest=gate_kw.pop("candidate_digest", world.candidate.candidate_digest))
    identity = identity or RuntimeIdentity(action.tenant_id, action.actor_id, action.model_id, "s")
    return gate.authorize(authorization_id="auth.v1:" + "0" * 64, envelope=world.envelope, action=action,
                          identity=identity, key_ring=world.app._key_ring,
                          revocation_state=world.app.revocation, now=ADMISSION_INSTANT)


@pytest.mark.parametrize("field, value, reason", [
    ("actor_id", "someone-else", "actor does not match envelope subject"),
    ("model_id", "another-model", "model does not match envelope binding"),
    ("action_type", "coordinated", "does not equal the target scope"),
    ("action_type", "delete_everything", "not a canonical capacity action"),
    ("purpose", "CUSTOMER_REFUND_REVIEW", "not the capacity purpose"),
    ("target_id", "sha256:" + "d" * 64, "not the presented target scope digest"),
    ("data_classes", ("CUSTOMER_PII",), "no data classes"),
    ("destination", "external://x", "no data classes"),
    ("amount_minor_units", 1, "no data classes"),
])
def test_an_action_that_is_not_the_mapped_one_is_denied(world, field, value, reason):
    action = replace(capacity_action_to_canonical(world.envelope, world.target_scope), **{field: value})
    verdict = _gate_verdict(world, action)
    assert verdict.decision is ActionGateDecision.DENIED
    assert any(reason in r for r in verdict.reason_codes), verdict.reason_codes


def test_a_runtime_identity_that_disagrees_is_denied(world):
    action = capacity_action_to_canonical(world.envelope, world.target_scope)
    verdict = _gate_verdict(world, action, identity=RuntimeIdentity(action.tenant_id, "other", action.model_id, "s"))
    assert verdict.decision is ActionGateDecision.DENIED
    assert any("runtime identity" in r for r in verdict.reason_codes)


def test_a_required_condition_left_unsatisfied_is_denied(world):
    from risk_authority.domain.envelope import EnvelopeConditions
    conditioned = replace(world.envelope, conditions=EnvelopeConditions(required_conditions=("HUMAN_APPROVAL",)))
    action = capacity_action_to_canonical(conditioned, world.target_scope)
    gate = CapacityActionGate(target_scope=world.target_scope, candidate_digest=world.candidate.candidate_digest)
    kw = dict(authorization_id="auth.v1:" + "0" * 64, envelope=conditioned, action=action,
              identity=RuntimeIdentity(action.tenant_id, action.actor_id, action.model_id, "s"),
              key_ring=world.app._key_ring, revocation_state=world.app.revocation, now=ADMISSION_INSTANT)
    assert gate.authorize(**kw).decision is ActionGateDecision.DENIED
    assert gate.authorize(**kw, satisfied_conditions=frozenset({"HUMAN_APPROVAL"})).decision is ActionGateDecision.AUTHORIZED


# --------------------------------------------------------------------------- #
# The kernel still stands in front of the gate
# --------------------------------------------------------------------------- #
def test_a_session_mismatch_is_refused_before_the_gate(world):
    out = world.admission().admit(admission_request(world, session_id="other-session"))
    assert out.refusal is R.ENVELOPE_INVALID and out.authorization is None


def test_a_revoked_envelope_is_refused_before_the_gate(world):
    world.app.revocation.advance_epoch(world.candidate.tenant_id)
    out = world.admission().admit(admission_request(world))
    assert out.refusal is R.ENVELOPE_INVALID


def test_an_unknown_envelope_is_refused_with_one_clock_read(world):
    out = world.admission().admit(admission_request(world, envelope_id="rae_999999"))
    assert out.refusal is R.ENVELOPE_NOT_FOUND and out.action is None and world.clock.reads == 1


def test_the_clock_is_read_once_on_a_denial_too(world):
    _denied(world, candidate_digest="sha256:" + "c" * 64)
    assert world.clock.reads == 1


# --------------------------------------------------------------------------- #
# Mapping and bounds
# --------------------------------------------------------------------------- #
def test_the_mapping_refuses_foreign_types_and_another_tenant(world):
    with pytest.raises(ActionAdmissionExactTypeError):
        capacity_action_to_canonical(object(), world.target_scope)
    with pytest.raises(ActionAdmissionExactTypeError):
        capacity_action_to_canonical(world.envelope, object())
    with pytest.raises(ActionAdmissionContractError):
        capacity_action_to_canonical(world.envelope, _scope(world, tenant_id="tenant-other"))


def test_bounds_violations_are_reported_even_when_the_scope_type_did_not_refuse_them():
    from types import SimpleNamespace as NS
    assert capacity_bounds_violations(NS(requested_magnitude=5, magnitude_before=3,
                                         max_permitted_magnitude=10, max_permitted_delta=5)) == ()
    assert any("exceeds permitted maximum" in r for r in capacity_bounds_violations(
        NS(requested_magnitude=11, magnitude_before=3, max_permitted_magnitude=10, max_permitted_delta=50)))
    assert any("exceeds permitted delta" in r for r in capacity_bounds_violations(
        NS(requested_magnitude=9, magnitude_before=3, max_permitted_magnitude=10, max_permitted_delta=2)))
    assert capacity_bounds_violations(NS(requested_magnitude="9", magnitude_before=3,
                                         max_permitted_magnitude=10, max_permitted_delta=2))


# --------------------------------------------------------------------------- #
# Request hygiene
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("field, value", [
    ("tenant_id", ""), ("session_id", " s"), ("envelope_id", None), ("candidate_digest", "abc"),
    ("target_scope", object()), ("satisfied_conditions", ["x"]),
])
def test_malformed_requests_are_refused(world, field, value):
    with pytest.raises(ActionAdmissionExactTypeError):
        admission_request(world, **{field: value})


def test_a_target_scope_for_another_tenant_cannot_ride_this_request(world):
    with pytest.raises(ActionAdmissionExactTypeError):
        admission_request(world, target_scope=_scope(world, tenant_id="tenant-other"))


def test_a_foreign_request_type_is_refused(world):
    with pytest.raises(ActionAdmissionExactTypeError):
        world.admission().admit(object())  # type: ignore[arg-type]
