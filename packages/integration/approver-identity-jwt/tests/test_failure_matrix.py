"""The adapter ADR's §4 failure surface (IA-1, IA-2, IA-3) over the in-process issuer.

Every refusal is an unauthenticated answer with a reason code; only a key outage is
an exception, and it is the port's ``IdentityUnavailable``. Time is the injected
clock's, never the wall clock's.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ugence_governed_review_service import (
    IDP_AUTHENTICATED,
    ActorKind,
    ApproverIdentityPort,
    IdentityUnavailable,
)

from ugence_approver_identity_jwt import (
    ALGORITHMS,
    AdapterConfig,
    AdapterConfigurationError,
    JwksKeyCache,
    JwtApproverIdentityAdapter,
    KeyRetrievalFailed,
    Refusal,
)

from conftest import NOW, STUDIO_AUDIENCE, Clock, base_claims, config_for


def refused(answer, reason: Refusal) -> bool:
    return (not answer.authenticated and answer.claims is None and answer.actor_id == ""
            and answer.actor_type is ActorKind.SYSTEM and answer.refusal == reason.value)


# --------------------------------------------------------------------------- #
# the port, satisfied
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("alg", ALGORITHMS)
def test_a_well_formed_token_under_each_permitted_algorithm_authenticates(issuer, clock, alg):
    kid = issuer.add_key(alg)
    adapter = JwtApproverIdentityAdapter(config_for(issuer), clock=clock.datetime)
    assert isinstance(adapter, ApproverIdentityPort)
    answer = adapter.authenticate(issuer.mint(base_claims(issuer), kid=kid))
    assert answer.authenticated and answer.proof == IDP_AUTHENTICATED
    assert answer.actor_type is ActorKind.HUMAN and answer.refusal == ""
    assert answer.actor_id == "https%3A%2F%2Fissuer.test|alice"
    c = answer.claims
    assert (c.issuer, c.subject, c.audience) == (issuer.issuer, "alice", issuer.audience)
    assert c.expires_at == datetime.fromtimestamp(base_claims(issuer)["exp"], tz=timezone.utc)
    assert c.tenant_claims == ("tenant-a",) and c.amr == ("pwd", "otp")


def test_the_access_token_type_is_compared_case_insensitively_and_both_forms_are_accepted(
        adapter, issuer):
    for typ in ("at+jwt", "AT+JWT", "application/at+jwt"):
        assert adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1", typ=typ)).authenticated


# --------------------------------------------------------------------------- #
# malformed, oversized, wrong shape
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("proof", ["", "not-a-token", "a.b", "a.b.c", "eyJ.eyJ.sig",
                                   None, 42, b"bytes"])
def test_a_malformed_proof_is_refused_without_touching_the_issuer(adapter, issuer, proof):
    assert refused(adapter.authenticate(proof), Refusal.MALFORMED)
    assert issuer.fetches == 0


def test_an_oversized_proof_is_refused_before_any_parse(issuer, clock):
    adapter = JwtApproverIdentityAdapter(config_for(issuer, max_proof_bytes=64),
                                         clock=clock.datetime)
    token = issuer.mint(base_claims(issuer), kid="rsa-1")
    assert len(token) > 64
    assert refused(adapter.authenticate(token), Refusal.PROOF_TOO_LARGE)
    assert issuer.fetches == 0 and adapter.keys.fetch_count == 0


@pytest.mark.parametrize("make", [
    lambda i: i.mint_unsigned(base_claims(i), kid="rsa-1"),
    lambda i: i.mint_hmac(base_claims(i), kid="rsa-1"),
    lambda i: i.mint(base_claims(i), kid="rsa-1", alg="RS512"),
    lambda i: i.mint(base_claims(i), kid="rsa-1", alg="PS256"),
])
def test_none_hmac_and_every_algorithm_outside_the_allowlist_are_refused(adapter, issuer, make):
    assert refused(adapter.authenticate(make(issuer)), Refusal.ALG_NOT_PERMITTED)
    assert issuer.fetches == 0, "refused from the header alone; no key was fetched"


@pytest.mark.parametrize("typ", [None, "JWT", "id_token", "at-jwt", 7])
def test_a_token_that_is_not_an_access_token_is_refused(adapter, issuer, typ):
    token = issuer.mint(base_claims(issuer), kid="rsa-1", typ=None,
                        headers={} if typ is None else {"typ": typ})
    assert refused(adapter.authenticate(token), Refusal.TYP_NOT_ACCESS_TOKEN)


def test_a_token_without_a_key_id_is_refused(adapter, issuer):
    import jwt as pyjwt
    token = pyjwt.encode(base_claims(issuer), issuer._keys["rsa-1"]["pem"],  # noqa: SLF001
                         algorithm="RS256", headers={"typ": "at+jwt"})
    assert refused(adapter.authenticate(token), Refusal.KID_MISSING)


# --------------------------------------------------------------------------- #
# keys: cache, one refresh, rotation, fail closed
# --------------------------------------------------------------------------- #
def test_keys_are_fetched_once_and_served_from_the_cache(adapter, issuer):
    for _ in range(3):
        assert adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1")).authenticated
    assert issuer.fetches == 1 and adapter.keys.fetch_count == 1


def test_an_unknown_kid_triggers_exactly_one_refresh_then_is_refused(adapter, issuer):
    adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1"))
    forged = issuer.mint(base_claims(issuer), kid="rsa-1", headers={"kid": "ghost"})
    assert refused(adapter.authenticate(forged), Refusal.KEY_UNKNOWN)
    assert issuer.fetches == 2, "one refresh for the unknown kid, no more"
    assert refused(adapter.authenticate(forged), Refusal.KEY_UNKNOWN)
    assert issuer.fetches == 3, "each call may refresh once; none refreshes twice"


def test_rotation_a_new_key_is_picked_up_and_a_withdrawn_key_is_gone_after_refresh(adapter, issuer):
    assert adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1")).authenticated
    new = issuer.add_key("ES256", kid="ec-2")
    assert adapter.authenticate(issuer.mint(base_claims(issuer), kid=new)).authenticated
    assert issuer.fetches == 2
    issuer.unpublish("rsa-1")
    # Still cached: the withdrawn key serves until the next refresh replaces the set.
    assert adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1")).authenticated
    ghost = issuer.mint(base_claims(issuer), kid="ec-2", headers={"kid": "ghost"})
    assert refused(adapter.authenticate(ghost), Refusal.KEY_UNKNOWN)  # forces a refresh
    assert refused(adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1")),
                   Refusal.KEY_UNKNOWN), "replace, never merge: the withdrawn key is gone"
    assert adapter.keys.known_kids == frozenset({"ec-2"})


def test_a_signature_by_a_foreign_key_under_a_published_kid_is_refused(adapter, issuer):
    forged = issuer.mint(base_claims(issuer), kid="rsa-1", pem=issuer.foreign_pem("RS256"))
    assert refused(adapter.authenticate(forged), Refusal.SIGNATURE_INVALID)


def test_a_key_of_the_wrong_type_for_the_named_algorithm_is_refused(adapter, issuer):
    ec_kid = issuer.add_key("ES256")
    # Header says RS256 and names the EC key: PyJWT refuses the key for the algorithm.
    token = issuer.mint(base_claims(issuer), kid=ec_kid, pem=issuer.foreign_pem("RS256"),
                        alg="RS256")
    assert refused(adapter.authenticate(token), Refusal.SIGNATURE_INVALID)


def test_a_key_outage_is_identity_unavailable_never_an_unauthenticated_answer(issuer, clock):
    adapter = JwtApproverIdentityAdapter(config_for(issuer), clock=clock.datetime)
    issuer.fail_next = 1
    with pytest.raises(IdentityUnavailable) as excinfo:
        adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1"))
    assert isinstance(excinfo.value, KeyRetrievalFailed)
    assert "HTTPError" in str(excinfo.value)
    # Recovered issuer: the next call fetches and succeeds.
    assert adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1")).authenticated


def test_a_cached_key_survives_an_outage_but_an_unknown_kid_during_one_fails_closed(
        adapter, issuer):
    assert adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1")).authenticated
    issuer.fail_next = 5
    assert adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1")).authenticated
    with pytest.raises(IdentityUnavailable):
        adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1",
                                         headers={"kid": "ghost"}))


@pytest.mark.parametrize("flag", ["serve_malformed", "serve_symmetric"])
def test_a_malformed_or_symmetric_jwks_is_refused_as_unavailable(issuer, clock, flag):
    setattr(issuer, flag, True)
    adapter = JwtApproverIdentityAdapter(config_for(issuer), clock=clock.datetime)
    with pytest.raises(KeyRetrievalFailed):
        adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1"))
    assert adapter.keys.known_kids == frozenset()


def test_an_unreachable_issuer_is_unavailable(clock, issuer):
    cfg = AdapterConfig(issuer=issuer.issuer, audience=issuer.audience,
                        jwks_url="http://127.0.0.1:9/jwks.json", fetch_timeout_s=0.5)
    adapter = JwtApproverIdentityAdapter(cfg, clock=clock.datetime)
    with pytest.raises(IdentityUnavailable):
        adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1"))


# --------------------------------------------------------------------------- #
# issuer, audience, required claims
# --------------------------------------------------------------------------- #
def test_a_wrong_issuer_is_refused(adapter, issuer):
    token = issuer.mint(base_claims(issuer, iss="https://other.test"), kid="rsa-1")
    assert refused(adapter.authenticate(token), Refusal.ISSUER_MISMATCH)


@pytest.mark.parametrize("aud", [STUDIO_AUDIENCE, [STUDIO_AUDIENCE], ["x", "y"]])
def test_a_token_for_another_audience_including_the_studios_is_refused(adapter, issuer, aud):
    """Row 14, second half: an audience-bound proof for the studio never authenticates
    at the review service."""

    assert refused(adapter.authenticate(issuer.mint(base_claims(issuer, aud=aud), kid="rsa-1")),
                   Refusal.AUDIENCE_MISMATCH)


def test_an_audience_list_that_names_the_service_is_accepted(adapter, issuer):
    token = issuer.mint(base_claims(issuer, aud=[STUDIO_AUDIENCE, issuer.audience]), kid="rsa-1")
    answer = adapter.authenticate(token)
    assert answer.authenticated and answer.claims.audience == issuer.audience


@pytest.mark.parametrize("missing", ["exp", "iat", "sub", "aud", "iss"])
def test_a_missing_required_claim_is_refused(adapter, issuer, missing):
    token = issuer.mint(base_claims(issuer, **{missing: None}), kid="rsa-1")
    assert adapter.authenticate(token).refusal in (
        Refusal.CLAIM_MISSING.value, Refusal.ISSUER_MISMATCH.value, Refusal.AUDIENCE_MISMATCH.value)


@pytest.mark.parametrize("over", [{"sub": ""}, {"sub": 7}, {"exp": "soon"}, {"iat": True},
                                  {"nbf": "now"}])
def test_a_malformed_required_or_time_claim_is_refused(adapter, issuer, over):
    token = issuer.mint(base_claims(issuer, **over), kid="rsa-1")
    assert not adapter.authenticate(token).authenticated


# --------------------------------------------------------------------------- #
# time: the injected clock, never the wall clock
# --------------------------------------------------------------------------- #
def test_expiry_issued_at_and_not_before_are_judged_by_the_injected_clock(issuer, clock):
    adapter = JwtApproverIdentityAdapter(config_for(issuer), clock=clock.datetime)
    fresh = issuer.mint(base_claims(issuer), kid="rsa-1")
    assert adapter.authenticate(fresh).authenticated
    clock.advance(hours=2)
    assert refused(adapter.authenticate(fresh), Refusal.EXPIRED)
    clock.now = NOW
    at_exp = issuer.mint(base_claims(issuer, exp=int(NOW.timestamp())), kid="rsa-1")
    assert refused(adapter.authenticate(at_exp), Refusal.EXPIRED)
    future = issuer.mint(base_claims(issuer, iat=int((NOW + timedelta(minutes=1)).timestamp())),
                         kid="rsa-1")
    assert refused(adapter.authenticate(future), Refusal.ISSUED_IN_FUTURE)
    later = issuer.mint(base_claims(issuer, nbf=int((NOW + timedelta(minutes=5)).timestamp())),
                        kid="rsa-1")
    assert refused(adapter.authenticate(later), Refusal.NOT_YET_VALID)
    clock.advance(minutes=6)
    assert adapter.authenticate(later).authenticated


def test_the_wall_clock_plays_no_part(issuer):
    """A token that expired years ago by the wall clock authenticates when the
    injected clock says it is 2019; the adapter has no clock of its own."""

    then = datetime(2019, 1, 1, tzinfo=timezone.utc)
    adapter = JwtApproverIdentityAdapter(config_for(issuer), clock=lambda: then)
    old = issuer.mint(base_claims(issuer, iat=int(then.timestamp()) - 10,
                                  exp=int(then.timestamp()) + 600,
                                  auth_time=int(then.timestamp()) - 20), kid="rsa-1")
    assert adapter.authenticate(old).authenticated


def test_a_naive_clock_is_a_contract_violation(issuer):
    from ugence_governed_review_service import ContractViolation

    adapter = JwtApproverIdentityAdapter(config_for(issuer), clock=lambda: datetime(2026, 9, 5))
    with pytest.raises(ContractViolation):
        adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1"))


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #
def test_configuration_is_explicit_https_only_outside_the_loopback_exception(issuer):
    with pytest.raises(AdapterConfigurationError):
        AdapterConfig(issuer=issuer.issuer, audience="a", jwks_url="http://idp.example/jwks")
    with pytest.raises(AdapterConfigurationError, match="loopback"):
        config_for(issuer, production=True)  # the test issuer is refused in production
    ok = AdapterConfig(issuer=issuer.issuer, audience="a", jwks_url="https://idp.example/jwks",
                       production=True)
    assert ok.jwks_url.startswith("https://")
    good = dict(issuer=issuer.issuer, audience=issuer.audience, jwks_url=issuer.jwks_url)
    for bad in (dict(issuer=""), dict(audience=" "), dict(jwks_url="https:///nohost"),
                dict(max_proof_bytes=0), dict(fetch_timeout_s=0), dict(tenant_claim=""),
                dict(actor_type_claim=" ", human_actor_type_value="h")):
        with pytest.raises(AdapterConfigurationError):
            AdapterConfig(**dict(good, **bad))


def test_the_adapter_refuses_the_wrong_seams(issuer, clock):
    from ugence_governed_review_service import ContractViolation

    with pytest.raises(ContractViolation):
        JwtApproverIdentityAdapter(object(), clock=clock.datetime)
    with pytest.raises(ContractViolation):
        JwtApproverIdentityAdapter(config_for(issuer), clock="not callable")
    cache = JwksKeyCache(config_for(issuer))
    adapter = JwtApproverIdentityAdapter(config_for(issuer), clock=clock.datetime, keys=cache)
    assert adapter.keys is cache and issuer.fetches == 0, "construction fetches nothing"
