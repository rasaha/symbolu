"""Positive controls: the envelope the chain issued admits exactly the action it was issued for."""

from __future__ import annotations

from risk_authority.api import AUTHORIZATION_ID_PREFIX, derive_authorization_id
from risk_authority.domain.actions import CanonicalAction
from risk_authority.domain.enums import AuthorizationDisposition, GovernanceEventType

from _admission_fixtures import ADMISSION_INSTANT, admission_request

from ugence_cloud_scaling_action_admission import (
    PURPOSE_CAPACITY_ACTION,
    CapacityAdmissionOutcome,
    capacity_action_to_canonical,
)


def test_the_matching_capacity_action_is_admitted(world):
    out = world.admission().admit(admission_request(world))
    assert type(out) is CapacityAdmissionOutcome
    assert out.refusal is None, (out.refusal, out.detail)
    assert out.admitted, out.authorization.reason_codes
    auth = out.authorization
    assert auth.disposition is AuthorizationDisposition.ADMITTED
    assert auth.expires_at == world.envelope.expires_at
    assert auth.authorization_id == derive_authorization_id(
        tenant_id=world.candidate.tenant_id, envelope_id=world.envelope.envelope_id,
        action_digest=out.action.digest)
    assert auth.authorization_id.startswith(AUTHORIZATION_ID_PREFIX)
    assert out.executable is False and auth.executable is False


def test_one_clock_read_and_the_seams_instant(world):
    out = world.admission().admit(admission_request(world))
    assert world.clock.reads == 1 and out.admitted_at == ADMISSION_INSTANT


def test_the_action_is_the_fixed_d2_mapping(world):
    out = world.admission().admit(admission_request(world))
    action = out.action
    expected = capacity_action_to_canonical(world.envelope, world.target_scope)
    assert action == expected
    assert action == CanonicalAction(
        tenant_id=world.envelope.tenant_id, actor_id=world.envelope.subject,
        model_id=world.envelope.model_id, action_type=world.target_scope.action_type,
        target_id=world.target_scope.digest(), purpose=PURPOSE_CAPACITY_ACTION,
        data_classes=(), destination="", amount_minor_units=None, currency="")
    assert action.actor_id == world.envelope.subject == world.candidate.subject_id


def test_re_admission_replays_the_stored_verdict_without_a_second_event(world):
    admission = world.admission()
    first = admission.admit(admission_request(world))
    events = len(world.app.events.for_aggregate(world.candidate.tenant_id, world.envelope.envelope_id))
    again = admission.admit(admission_request(world))
    assert again.replayed and again.admitted
    assert again.authorization.authorization_id == first.authorization.authorization_id
    assert again.authorization.disposition is AuthorizationDisposition.REPLAYED
    assert len(world.app.events.for_aggregate(world.candidate.tenant_id, world.envelope.envelope_id)) == events


def test_the_verdict_is_persisted_and_the_event_emitted(world):
    out = world.admission().admit(admission_request(world))
    stored = world.app.authorizations.get(world.candidate.tenant_id, out.authorization.authorization_id)
    assert stored == out.authorization
    last = world.app.events.for_aggregate(world.candidate.tenant_id, world.envelope.envelope_id)[-1]
    assert last.event_type is GovernanceEventType.ACTION_AUTHORIZED
    assert last.payload_digest == out.action.digest


def test_the_gate_reconciles_against_the_envelope_bindings(world):
    from ugence_cloud_scaling_action_admission import BINDING_KIND_AUTHORIZATION_CANDIDATE, BINDING_KIND_TARGET_SCOPE
    from ugence_cloud_scaling_envelope_issuance import bare_digest
    b = world.envelope.bindings
    assert b.binding_for(BINDING_KIND_TARGET_SCOPE).digest == bare_digest(world.target_scope.digest())
    assert b.binding_for(BINDING_KIND_AUTHORIZATION_CANDIDATE).digest == bare_digest(world.candidate.candidate_digest)
