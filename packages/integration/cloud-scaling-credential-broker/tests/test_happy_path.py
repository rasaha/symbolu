"""Positive controls: an admitted, reserved capacity action materializes one bounded grant."""

from __future__ import annotations

from datetime import timedelta

from ugence_governance_contracts.api import Validity

from _broker_fixtures import BROKER_INSTANT, materialization_request

from ugence_cloud_scaling_credential_broker import (
    CREDENTIAL_PROFILE,
    DEFAULT_TTL_CAP,
    REFERENCE_BROKER_AUTHORITY_ID,
    CredentialMaterializationOutcome,
    GrantDisposition,
    derive_grant_id,
    derive_least_privilege_role,
)


def test_the_admitted_reserved_action_materializes_a_grant(world):
    out = world.seam().materialize(materialization_request(world))
    assert type(out) is CredentialMaterializationOutcome
    assert out.refusal is None, (out.refusal, out.detail)
    assert out.materialized and not out.replayed and out.executable is False
    grant = out.grant
    assert grant.disposition is GrantDisposition.MATERIALIZED
    assert grant.grant_id == derive_grant_id(out.request_digest)
    assert grant.tenant_id == world.candidate.tenant_id
    assert grant.broker_authority_id == REFERENCE_BROKER_AUTHORITY_ID
    assert grant.credential_profile == CREDENTIAL_PROFILE
    assert grant.handle_ref.startswith("inert:")
    assert grant.executable is False


def test_one_clock_read_and_the_ratified_window(world):
    out = world.seam().materialize(materialization_request(world))
    assert world.clock.reads == 1 and out.materialized_at == BROKER_INSTANT
    v = out.grant.validity
    assert type(v) is Validity and v.issued_at == BROKER_INSTANT
    expected = min(world.authorization.expires_at, world.reservation.lease.expires_at,
                   world.envelope.expires_at, BROKER_INSTANT + DEFAULT_TTL_CAP)
    assert v.expires_at == expected
    assert v.expires_at <= BROKER_INSTANT + timedelta(minutes=15)


def test_the_grant_carries_exactly_the_derived_role(world):
    out = world.seam().materialize(materialization_request(world))
    derived = derive_least_privilege_role(world.target_scope)
    assert out.grant.role == derived
    assert derived.operation == world.target_scope.action_type
    assert derived.account_id == world.target_scope.account_id
    assert derived.max_magnitude == world.target_scope.max_permitted_magnitude
    assert derived.max_delta == world.target_scope.max_permitted_delta


def test_re_materialization_replays_the_stored_grant(world):
    seam = world.seam()
    first = seam.materialize(materialization_request(world))
    again = seam.materialize(materialization_request(world))
    assert again.replayed and again.materialized
    assert again.grant.grant_id == first.grant.grant_id
    assert again.grant.handle_ref == first.grant.handle_ref
    assert again.grant.disposition is GrantDisposition.REPLAYED
    assert again.request_digest == first.request_digest


def test_the_grant_is_persisted_by_derived_id(world):
    from ugence_cloud_scaling_credential_broker import InMemoryCredentialGrantStore
    grants = InMemoryCredentialGrantStore()
    out = world.seam(grants=grants).materialize(materialization_request(world))
    assert grants.get(world.candidate.tenant_id, out.grant.grant_id) == out.grant
