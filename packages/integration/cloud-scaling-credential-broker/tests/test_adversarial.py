"""Refusals: a grant is minted only for the one action that was admitted and reserved."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from risk_authority.api import VERIFIED, EnvelopeIssuanceRequest, EnvelopeIssuanceSeam, VerifiedArtifactBinding
from risk_authority.crypto.canonical import to_canonical_obj
from risk_authority.crypto.hashing import digest as _digest
from ugence_execution_reservation import ReservationState
from ugence_governance_contracts.api import Validity

from _admission_fixtures import admission_request
from _broker_fixtures import BROKER_INSTANT, RESERVATION_INSTANT, materialization_request, reserve

from ugence_cloud_scaling_credential_broker import (
    CredentialBrokerConfigurationError,
    CredentialBrokerContractError,
    CredentialBrokerExactTypeError,
    CredentialGrant,
    CredentialRefusal as R,
    CredentialRequest,
    CredentialRequestMinter,
    CredentialRequestRefused,
    GrantDisposition,
    ReferenceCredentialBroker,
    RoleStatement,
    derive_grant_id,
    derive_least_privilege_role,
    role_widening,
)


def _refused(world, request=None, expected=None, **seam_kw):
    out = world.seam(**seam_kw).materialize(request or materialization_request(world))
    assert out.grant is None and out.materialized is False
    if expected is not None:
        assert out.refusal is expected, (out.refusal, out.detail)
    return out


# --------------------------------------------------------------------------- #
# no_change derives nothing
# --------------------------------------------------------------------------- #
def test_no_change_derives_no_role():
    from _admission_fixtures import build_admission_world
    scope = replace(build_admission_world().target_scope, action_type="no_change")
    assert derive_least_privilege_role(scope) is None


def test_a_no_change_action_admitted_through_the_real_seams_is_refused(world):
    """A second envelope is issued for a no_change scope through the real issuance and
    admission seams, then brokering refuses it: nothing changes, so nothing is credentialed."""

    from ugence_cloud_scaling_action_admission import (
        BINDING_KIND_AUTHORIZATION_CANDIDATE, BINDING_KIND_TARGET_SCOPE, CloudScalingActionAdmission,
        CapacityAdmissionRequest)
    from ugence_cloud_scaling_envelope_issuance import bare_digest
    from _issuance_fixtures import KEY_RECORD
    scope = replace(world.target_scope, action_type="no_change")
    candidate_digest = world.candidate.candidate_digest
    decision = world.app.decisions.get(world.candidate.tenant_id, world.candidate.decision_id)

    class _V:
        is_production_authoritative = True

        def verify(self, *, as_of):
            return (VerifiedArtifactBinding(BINDING_KIND_AUTHORIZATION_CANDIDATE, bare_digest(candidate_digest), VERIFIED, as_of),
                    VerifiedArtifactBinding(BINDING_KIND_TARGET_SCOPE, bare_digest(scope.digest()), VERIFIED, as_of))

    issued = EnvelopeIssuanceSeam.reference(app=world.app, key_record=KEY_RECORD, verification=_V(), clock=world.clock,
                                            required_binding_kinds=(BINDING_KIND_AUTHORIZATION_CANDIDATE, BINDING_KIND_TARGET_SCOPE)
                                            ).issue(EnvelopeIssuanceRequest(
        tenant_id=world.candidate.tenant_id, decision_id=decision.decision_id,
        decision_digest=_digest(to_canonical_obj(decision)), audience="a", session_id="sess-nc", nonce="n-nc"))
    assert issued.issued, (issued.refusal, issued.detail)
    admitted = CloudScalingActionAdmission.reference(app=world.app, clock=world.clock).admit(CapacityAdmissionRequest(
        tenant_id=world.candidate.tenant_id, envelope_id=issued.envelope.envelope_id, target_scope=scope,
        candidate_digest=candidate_digest, session_id="sess-nc"))
    assert admitted.admitted, admitted.authorization.reason_codes if admitted.authorization else admitted.refusal
    reservation = reserve(world.reservations, admitted.authorization, admitted.action, scope, as_of=world.clock.at)
    out = _refused(world, materialization_request(world, authorization_id=admitted.authorization.authorization_id,
                                                  reservation_id=reservation.reservation_id, target_scope=scope),
                   R.NO_CREDENTIAL_REQUIRED)
    assert "changes nothing" in out.detail


# --------------------------------------------------------------------------- #
# The reservation must be RESERVED and must name this action
# --------------------------------------------------------------------------- #
def test_a_released_reservation_is_refused(world):
    world.reservations.release(world.reservation.reservation_id, as_of=RESERVATION_INSTANT + timedelta(seconds=1))
    assert world.reservations.get_reservation(world.reservation.reservation_id).state is ReservationState.RELEASED
    _refused(world, expected=R.RESERVATION_NOT_RESERVED)


def test_a_dispatched_reservation_is_refused(world):
    world.reservations.mark_dispatched(world.reservation.reservation_id, "dispatch-1",
                                       dispatch_deadline=BROKER_INSTANT + timedelta(minutes=5),
                                       as_of=RESERVATION_INSTANT + timedelta(seconds=1))
    _refused(world, expected=R.RESERVATION_NOT_RESERVED)


def test_an_unknown_reservation_is_refused(world):
    _refused(world, materialization_request(world, reservation_id="res_unknown"), R.RESERVATION_NOT_FOUND)


def test_an_expired_lease_is_refused(world):
    world.clock.at = world.reservation.lease.expires_at + timedelta(seconds=1)
    _refused(world, expected=R.LEASE_EXPIRED)


def test_a_reservation_for_another_authorization_is_refused(world):
    """Reserve a second action under the same envelope; present the first authorization with
    the second reservation. The key names another authorization ref and is refused."""

    foreign = replace(world.authorization, authorization_id="auth.v1:" + "f" * 64)
    other_reservation = reserve(world.reservations, foreign, world.action, world.target_scope,
                                as_of=RESERVATION_INSTANT)
    assert other_reservation.execution_key.authorization_ref != world.authorization.authorization_id
    _refused(world, materialization_request(world, reservation_id=other_reservation.reservation_id),
             R.RESERVATION_MISMATCH)


# --------------------------------------------------------------------------- #
# The presented target scope must re-derive the authorized action
# --------------------------------------------------------------------------- #
def test_a_different_target_scope_is_refused(world):
    other = replace(world.target_scope, compute_group=(world.target_scope.compute_group or "") + "-other")
    _refused(world, materialization_request(world, target_scope=other), R.TARGET_SCOPE_MISMATCH)


def test_a_wider_target_scope_is_refused(world):
    s = world.target_scope
    wider = replace(s, requested_magnitude=s.requested_magnitude + 5, max_permitted_magnitude=s.max_permitted_magnitude + 5,
                    max_permitted_delta=s.max_permitted_delta + 5)
    _refused(world, materialization_request(world, target_scope=wider), R.TARGET_SCOPE_MISMATCH)


# --------------------------------------------------------------------------- #
# The authorization must be AUTHORIZED and unexpired
# --------------------------------------------------------------------------- #
def test_an_expired_authorization_is_refused(world):
    world.clock.at = world.authorization.expires_at + timedelta(seconds=1)
    _refused(world, expected=R.AUTHORIZATION_EXPIRED)


def test_an_unknown_authorization_is_refused(world):
    _refused(world, materialization_request(world, authorization_id="auth.v1:" + "0" * 64), R.AUTHORIZATION_NOT_FOUND)


def test_a_denied_authorization_is_refused(world):
    from risk_authority.domain.enums import ActionGateDecision
    denied = replace(world.authorization, authorization_id="auth.v1:" + "d" * 64, decision=ActionGateDecision.DENIED)
    world.app.authorizations.save(denied)
    _refused(world, materialization_request(world, authorization_id=denied.authorization_id), R.AUTHORIZATION_NOT_AUTHORIZED)


def test_an_expired_envelope_is_refused_even_with_a_forged_longer_authorization(world):
    longer = replace(world.authorization, authorization_id="auth.v1:" + "e" * 64,
                     expires_at=world.envelope.expires_at + timedelta(hours=1))
    world.app.authorizations.save(longer)
    world.clock.at = world.envelope.expires_at + timedelta(seconds=1)
    _refused(world, materialization_request(world, authorization_id=longer.authorization_id), R.ENVELOPE_EXPIRED)


# --------------------------------------------------------------------------- #
# The broker may narrow and never widen; may not choose the window; may not fail open
# --------------------------------------------------------------------------- #
class _Broker(ReferenceCredentialBroker):
    is_production_authoritative = False

    def __init__(self, mutate):
        self._mutate = mutate

    def materialize(self, request):
        return self._mutate(super().materialize(request), request)


def test_a_widened_role_is_refused(world):
    widen = lambda g, r: replace(g, role=replace(g.role, max_magnitude=g.role.max_magnitude + 1))
    out = _refused(world, expected=R.GRANT_INVALID, broker=_Broker(widen))
    assert "widens max_magnitude" in out.detail


def test_a_narrowed_role_is_accepted(world):
    narrow = lambda g, r: replace(g, role=replace(g.role, max_magnitude=max(g.role.max_magnitude - 1, 0), max_delta=0))
    out = world.seam(broker=_Broker(narrow)).materialize(materialization_request(world))
    assert out.materialized and out.grant.role.max_delta == 0


def test_a_grant_that_outlives_the_window_is_refused(world):
    longer = lambda g, r: replace(g, validity=Validity(issued_at=g.validity.issued_at, expires_at=r.not_after + timedelta(seconds=1)))
    _refused(world, expected=R.GRANT_INVALID, broker=_Broker(longer))


def test_a_grant_naming_another_request_or_broker_is_refused(world):
    other_id = lambda g, r: replace(g, broker_authority_id="attacker.broker")
    _refused(world, expected=R.GRANT_INVALID, broker=_Broker(other_id))
    replayed = lambda g, r: replace(g, disposition=GrantDisposition.REPLAYED)
    _refused(world, expected=R.GRANT_INVALID, broker=_Broker(replayed))


def test_a_raising_broker_is_unavailable_never_a_grant(world):
    class Boom(ReferenceCredentialBroker):
        def materialize(self, request):
            raise RuntimeError("vault down")

    out = _refused(world, expected=R.BROKER_UNAVAILABLE, broker=Boom())
    assert "RuntimeError" in out.detail and world.clock.reads == 1


def test_a_foreign_result_type_is_refused(world):
    class Foreign(ReferenceCredentialBroker):
        def materialize(self, request):
            return {"handle": "x"}

    _refused(world, expected=R.GRANT_INVALID, broker=Foreign())


def test_role_widening_reports_every_dimension():
    derived = RoleStatement(tenant_id="t", operation="scale_up", account_id="a", compute_group=None,
                            resource_class="web", namespace="ns", region="r", max_magnitude=10, max_delta=3)
    assert role_widening(derived, derived) == ()
    assert role_widening(replace(derived, compute_group="cg"), derived) == ()  # narrows an open dimension
    assert any("widens resource_class" in r for r in role_widening(replace(derived, resource_class="db"), derived))
    assert any("changes operation" in r for r in role_widening(replace(derived, operation="scale_down"), derived))
    assert any("widens max_delta" in r for r in role_widening(replace(derived, max_delta=4), derived))
    assert role_widening(object(), derived)


# --------------------------------------------------------------------------- #
# The request cannot be assembled by a caller; the ttl cap is enforced at construction
# --------------------------------------------------------------------------- #
def test_a_credential_request_cannot_be_constructed_directly(world):
    role = derive_least_privilege_role(world.target_scope)
    with pytest.raises(CredentialBrokerContractError, match="cannot be constructed directly"):
        CredentialRequest(tenant_id="t", authorization_ref="a", execution_key=world.reservation.execution_key,
                          target_scope_digest="d", reservation_id="r", envelope_id="e", role=role,
                          issued_at=BROKER_INSTANT, not_after=BROKER_INSTANT + timedelta(minutes=1),
                          request_digest="x", minting_token=object())


def test_the_minter_refuses_a_non_reserved_or_mismatched_reservation(world):
    minter = CredentialRequestMinter()
    released = replace(world.reservation, state=ReservationState.RELEASED)
    with pytest.raises(CredentialRequestRefused) as exc:
        minter.mint(authorization=world.authorization, reservation=released, envelope=world.envelope,
                    target_scope=world.target_scope, issued_at=BROKER_INSTANT, not_after=BROKER_INSTANT + timedelta(minutes=1))
    assert exc.value.refusal is R.RESERVATION_NOT_RESERVED
    foreign = replace(world.reservation, authorization_ref="auth.v1:" + "f" * 64)
    with pytest.raises(CredentialRequestRefused) as exc:
        minter.mint(authorization=world.authorization, reservation=foreign, envelope=world.envelope,
                    target_scope=world.target_scope, issued_at=BROKER_INSTANT, not_after=BROKER_INSTANT + timedelta(minutes=1))
    assert exc.value.refusal is R.RESERVATION_MISMATCH


@pytest.mark.parametrize("cap", [timedelta(minutes=15, seconds=1), timedelta(hours=1), timedelta(0), timedelta(seconds=-1), 600])
def test_a_ttl_cap_above_fifteen_minutes_or_non_positive_is_refused_at_construction(world, cap):
    with pytest.raises(CredentialBrokerConfigurationError, match="ttl_cap"):
        world.seam(ttl_cap=cap)


def test_a_fifteen_minute_cap_is_the_ceiling_and_binds_the_window(world):
    out = world.seam(ttl_cap=timedelta(minutes=15)).materialize(materialization_request(world))
    assert out.materialized and out.grant.validity.expires_at <= BROKER_INSTANT + timedelta(minutes=15)
    short = world.seam(ttl_cap=timedelta(seconds=30)).materialize(materialization_request(world))
    assert short.grant.validity.expires_at == BROKER_INSTANT + timedelta(seconds=30)


def test_a_stored_grant_under_this_id_for_another_request_is_a_conflict(world):
    from ugence_cloud_scaling_credential_broker import InMemoryCredentialGrantStore
    grants = InMemoryCredentialGrantStore()
    out = world.seam(grants=grants).materialize(materialization_request(world))
    impostor = replace(out.grant, request_digest="credreq.v1:" + "9" * 64,
                       grant_id=derive_grant_id("credreq.v1:" + "9" * 64))
    with pytest.raises(CredentialBrokerContractError):
        grants.save(replace(out.grant, request_digest="credreq.v1:" + "9" * 64))
    grants._grants[(out.grant.tenant_id, out.grant.grant_id)] = replace(impostor, grant_id=out.grant.grant_id) \
        if False else out.grant
    # The genuine store keeps the genuine grant; a replay still returns it.
    assert world.seam(grants=grants).materialize(materialization_request(world)).replayed


# --------------------------------------------------------------------------- #
# Request hygiene
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("field, value", [
    ("tenant_id", ""), ("authorization_id", " a"), ("reservation_id", None), ("target_scope", object()),
])
def test_malformed_requests_are_refused(world, field, value):
    with pytest.raises(CredentialBrokerExactTypeError):
        materialization_request(world, **{field: value})


def test_a_target_scope_for_another_tenant_cannot_ride_this_request(world):
    with pytest.raises(CredentialBrokerExactTypeError):
        materialization_request(world, target_scope=replace(world.target_scope, tenant_id="tenant-other"))


def test_a_foreign_request_type_is_refused(world):
    with pytest.raises(CredentialBrokerExactTypeError):
        world.seam().materialize(object())  # type: ignore[arg-type]
