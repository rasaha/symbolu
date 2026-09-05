"""IA-4, the explicit claim mapping (adapter ADR §3): nothing has a default, HUMAN is
an exact configured match, assurance is recorded and never enforced, and the answer
records which claim supplied ``authenticated_at``."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from ugence_governed_review_service import (
    ActorKind,
    authentication_reference,
    subject_reference,
)

from ugence_approver_identity_jwt import (
    AdapterConfigurationError,
    JwtApproverIdentityAdapter,
    Refusal,
)

from conftest import ACTOR_CLAIM, HUMAN_VALUE, NOW, TENANT_CLAIM, base_claims, config_for


# --------------------------------------------------------------------------- #
# tenant
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("value, expected", [
    ("tenant-a", ("tenant-a",)),
    (["tenant-a"], ("tenant-a",)),
    (["tenant-a", "tenant-b"], ("tenant-a", "tenant-b")),
    ([], ()),
    (None, ()),
])
def test_the_configured_tenant_claim_is_carried_as_presented(adapter, issuer, value, expected):
    token = issuer.mint(base_claims(issuer, **{TENANT_CLAIM: value}), kid="rsa-1")
    answer = adapter.authenticate(token)
    assert answer.authenticated and answer.claims.tenant_claims == expected


@pytest.mark.parametrize("value", [7, "", [""], ["a", 1], {"id": "t"}])
def test_a_malformed_tenant_claim_is_refused(adapter, issuer, value):
    token = issuer.mint(base_claims(issuer, **{TENANT_CLAIM: value}), kid="rsa-1")
    assert adapter.authenticate(token).refusal == Refusal.CLAIM_MALFORMED.value


def test_without_a_configured_tenant_claim_no_tenant_is_ever_recorded(issuer, clock):
    adapter = JwtApproverIdentityAdapter(config_for(issuer, tenant_claim=None), clock=clock.datetime)
    for value in ("tenant-a", ["tenant-a"]):
        token = issuer.mint(base_claims(issuer, **{TENANT_CLAIM: value}), kid="rsa-1")
        assert adapter.authenticate(token).claims.tenant_claims == ()


# --------------------------------------------------------------------------- #
# actor type: an exact configured match, never an inference
# --------------------------------------------------------------------------- #
def test_human_is_exactly_the_configured_claim_equal_to_the_configured_value(adapter, issuer):
    assert adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1")).actor_type \
        is ActorKind.HUMAN
    for value in (HUMAN_VALUE.upper(), HUMAN_VALUE + " ", "human", True, 1, [HUMAN_VALUE], None):
        token = issuer.mint(base_claims(issuer, **{ACTOR_CLAIM: value}), kid="rsa-1")
        answer = adapter.authenticate(token)
        assert answer.authenticated and answer.actor_type is ActorKind.SYSTEM, value


def test_human_is_never_inferred_from_sub_client_id_amr_or_auth_time(adapter, issuer):
    # Every human-looking signal present, the configured claim absent: SYSTEM.
    looks_human = base_claims(issuer, **{ACTOR_CLAIM: None}, client_id="service-42",
                              amr=["pwd", "otp", "mfa"],
                              auth_time=int((NOW - timedelta(minutes=1)).timestamp()))
    assert adapter.authenticate(issuer.mint(looks_human, kid="rsa-1")).actor_type is ActorKind.SYSTEM
    # Every signal absent or service-like, the configured claim matching: HUMAN.
    looks_service = base_claims(issuer, sub="service-42", client_id="service-42", amr=None,
                                auth_time=None, acr=None)
    assert adapter.authenticate(issuer.mint(looks_service, kid="rsa-1")).actor_type is ActorKind.HUMAN


def test_without_actor_configuration_every_subject_is_system(issuer, clock):
    adapter = JwtApproverIdentityAdapter(
        config_for(issuer, actor_type_claim=None, human_actor_type_value=None), clock=clock.datetime)
    answer = adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1"))
    assert answer.authenticated and answer.actor_type is ActorKind.SYSTEM
    with pytest.raises(AdapterConfigurationError, match="together"):
        config_for(issuer, human_actor_type_value=None)
    with pytest.raises(AdapterConfigurationError, match="together"):
        config_for(issuer, actor_type_claim=None)


# --------------------------------------------------------------------------- #
# assurance: recorded, never enforced (ID-5)
# --------------------------------------------------------------------------- #
def test_acr_and_amr_are_recorded_as_asserted_and_empty_when_absent(adapter, issuer):
    full = adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1"))
    assert (full.claims.acr, full.claims.amr) == ("urn:example:loa2", ("pwd", "otp"))
    bare = adapter.authenticate(issuer.mint(base_claims(issuer, acr=None, amr=None), kid="rsa-1"))
    assert bare.authenticated and (bare.claims.acr, bare.claims.amr) == ("", ())
    for over in ({"amr": "pwd"}, {"amr": ["pwd", 1]}, {"acr": 2}):
        token = issuer.mint(base_claims(issuer, **over), kid="rsa-1")
        assert adapter.authenticate(token).refusal == Refusal.CLAIM_MALFORMED.value


# --------------------------------------------------------------------------- #
# authenticated_at: auth_time, else the required iat, and which is recorded
# --------------------------------------------------------------------------- #
def test_authenticated_at_comes_from_auth_time_else_iat_and_the_source_is_recorded(adapter, issuer):
    claims = base_claims(issuer)
    with_auth_time = adapter.authenticate(issuer.mint(claims, kid="rsa-1"))
    assert with_auth_time.authenticated_at_source == "auth_time"
    assert with_auth_time.claims.authenticated_at \
        == datetime.fromtimestamp(claims["auth_time"], tz=timezone.utc)
    without = adapter.authenticate(issuer.mint(base_claims(issuer, auth_time=None), kid="rsa-1"))
    assert without.authenticated_at_source == "iat"
    assert without.claims.authenticated_at == datetime.fromtimestamp(claims["iat"], tz=timezone.utc)
    bad = adapter.authenticate(issuer.mint(base_claims(issuer, auth_time="yesterday"), kid="rsa-1"))
    assert bad.refusal == Refusal.CLAIM_MALFORMED.value


# --------------------------------------------------------------------------- #
# the references the service records (ID-2)
# --------------------------------------------------------------------------- #
def test_the_subject_and_authentication_references_follow_from_the_claims_not_the_token(
        adapter, issuer):
    a = adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1"))
    ec = issuer.add_key("ES256")
    b = adapter.authenticate(issuer.mint(base_claims(issuer), kid=ec))
    assert a.actor_id == b.actor_id == subject_reference(a.claims)
    assert authentication_reference(a.claims) == authentication_reference(b.claims), \
        "same claims under two keys and two signatures: one reference"
    c = adapter.authenticate(issuer.mint(base_claims(issuer, jti="jti-0002"), kid="rsa-1"))
    assert authentication_reference(c.claims) != authentication_reference(a.claims)
    assert a.claims.proof_id_digest == "sha256:" + hashlib.sha256(b"jti-0001").hexdigest()
    none = adapter.authenticate(issuer.mint(base_claims(issuer, jti=None), kid="rsa-1"))
    assert none.authenticated and none.claims.proof_id_digest == ""
    assert adapter.authenticate(issuer.mint(base_claims(issuer, jti=5), kid="rsa-1")).refusal \
        == Refusal.CLAIM_MALFORMED.value
