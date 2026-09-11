"""The Cloudflare Access issuer profile (owner rulings AP3-D1 to AP3-D3,
``ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md`` §20.7), over the in-process issuer.

    CONFORMANCE EVIDENCE ONLY. The issuer here is this suite's own; nothing below is
    validation against Cloudflare, and AP-3 stays PENDING_VALIDATION regardless.

Three things are proven: the profile is selected only by explicit configuration and is
structurally tied to one Access team; under it ``typ`` is exactly ``JWT``, the tenant
is the configured static binding corroborated by the verified email's domain, and the
actor type is the ratified claim-shape mapping; and the ``rfc9068`` profile is
unchanged by any of it.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from ugence_approver_identity_jwt import (
    CLOUDFLARE_ACCESS_PROFILE,
    CLOUDFLARE_ACCESS_TOKEN_TYPE,
    CLOUDFLARE_REQUIRED_CLAIMS,
    ISSUER_PROFILES,
    RFC9068_PROFILE,
    AdapterConfig,
    AdapterConfigurationError,
    JwtApproverIdentityAdapter,
    Refusal,
)
from ugence_governed_review_service import ActorKind
from _issuer import InProcessIssuer
from conftest import NOW, Clock, base_claims

TEAM_ISSUER = "https://ugence.cloudflareaccess.com"
AUD = "24b3008ed1910d53caebbaffb3358aa801bd9dc5cf9f5af8aa7ada87335b12b3"
CERTS = TEAM_ISSUER + "/cdn-cgi/access/certs"
TENANT = "ugence.ai"
DOMAIN = "ugence.ai"
KID = "cf-rsa-1"


@pytest.fixture()
def cf_issuer():
    iss = InProcessIssuer(issuer=TEAM_ISSUER, audience=AUD)
    iss.add_key("RS256", kid=KID)
    iss.start()
    try:
        yield iss
    finally:
        iss.stop()


@pytest.fixture()
def cf_clock():
    return Clock()


def cf_config(source: InProcessIssuer, **over) -> AdapterConfig:
    kwargs = dict(issuer=TEAM_ISSUER, audience=AUD, jwks_url=source.jwks_url,
                  issuer_profile=CLOUDFLARE_ACCESS_PROFILE, bound_tenant=TENANT,
                  verified_email_domain=DOMAIN)
    kwargs.update(over)
    return AdapterConfig(**kwargs)


def human(issuer: InProcessIssuer, **over) -> dict:
    """The human shape of an Access application token for the test principal [I]."""
    claims = {
        "iss": TEAM_ISSUER, "sub": "3b0f6d3e-ap3-test-uuid", "aud": [AUD],
        "email": "ap3-test@ugence.ai", "type": "app", "identity_nonce": "n0nce",
        "iat": int((NOW - timedelta(seconds=60)).timestamp()),
        "exp": int((NOW + timedelta(hours=1)).timestamp()),
    }
    for key, value in over.items():
        if value is None:
            claims.pop(key, None)
        else:
            claims[key] = value
    return claims


def service(issuer: InProcessIssuer, **over) -> dict:
    """The service-token shape: common_name, empty sub, no email [I]."""
    shape = dict(sub="", email=None, common_name="ap3-service-token")
    shape.update(over)
    return human(issuer, **shape)


def adapter_for(issuer, clock, **over) -> JwtApproverIdentityAdapter:
    return JwtApproverIdentityAdapter(cf_config(issuer, **over), clock=clock.datetime)


# --------------------------------------------------------------------------- #
# selection: explicit, structural, and nothing else changes
# --------------------------------------------------------------------------- #
def test_the_profile_vocabulary_is_closed_and_the_default_is_rfc9068(issuer):
    assert ISSUER_PROFILES == (RFC9068_PROFILE, CLOUDFLARE_ACCESS_PROFILE)
    assert CLOUDFLARE_ACCESS_TOKEN_TYPE == "JWT"
    assert CLOUDFLARE_REQUIRED_CLAIMS == ("iss", "aud", "exp", "iat")
    cfg = AdapterConfig(issuer=issuer.issuer, audience=issuer.audience, jwks_url=issuer.jwks_url)
    assert cfg.issuer_profile == RFC9068_PROFILE
    with pytest.raises(AdapterConfigurationError, match="issuer_profile"):
        AdapterConfig(issuer=issuer.issuer, audience=issuer.audience, jwks_url=issuer.jwks_url,
                      issuer_profile="okta")


def test_the_profile_is_tied_to_one_access_team_and_its_certs_endpoint(cf_issuer):
    cf_config(cf_issuer)  # loopback JWKS: accepted outside production, for this harness
    AdapterConfig(issuer=TEAM_ISSUER, audience=AUD, jwks_url=CERTS, production=True,
                  issuer_profile=CLOUDFLARE_ACCESS_PROFILE, bound_tenant=TENANT,
                  verified_email_domain=DOMAIN)
    for bad_issuer in ("https://issuer.test", "https://ugence.cloudflareaccess.com/",
                       "http://ugence.cloudflareaccess.com", "https://ugence.cloudflareaccess.com:443",
                       "https://evil.example/ugence.cloudflareaccess.com",
                       "https://ugence.cloudflareaccess.com.evil.example"):
        with pytest.raises(AdapterConfigurationError, match="cloudflareaccess.com"):
            cf_config(cf_issuer, issuer=bad_issuer)
    for bad_jwks in ("https://other.cloudflareaccess.com/cdn-cgi/access/certs",
                     "https://ugence.cloudflareaccess.com/certs",
                     "https://ugence.cloudflareaccess.com/cdn-cgi/access/certs?x=1"):
        with pytest.raises(AdapterConfigurationError, match="jwks_url exactly"):
            cf_config(cf_issuer, jwks_url=bad_jwks)
    with pytest.raises(AdapterConfigurationError, match="loopback"):
        cf_config(cf_issuer, production=True)


def test_the_profile_carries_its_own_two_mappings_and_refuses_the_ia4_claim_names(cf_issuer, issuer):
    for missing in ("bound_tenant", "verified_email_domain"):
        with pytest.raises(AdapterConfigurationError, match="requires bound_tenant and verified_email_domain"):
            cf_config(cf_issuer, **{missing: None})
    with pytest.raises(AdapterConfigurationError, match="tenant_claim must be unset"):
        cf_config(cf_issuer, tenant_claim="ugence_tenant")
    with pytest.raises(AdapterConfigurationError, match="actor_type_claim must be unset"):
        cf_config(cf_issuer, actor_type_claim="ugence_actor", human_actor_type_value="human")
    for bad_domain in ("Ugence.AI", " ugence.ai", "ugence", "@ugence.ai", "ugence.ai/"):
        with pytest.raises(AdapterConfigurationError, match="verified_email_domain"):
            cf_config(cf_issuer, verified_email_domain=bad_domain)
    with pytest.raises(AdapterConfigurationError, match="bound_tenant must be a typed token"):
        cf_config(cf_issuer, bound_tenant="ugence ai")
    # and the rfc9068 profile never carries the static binding
    with pytest.raises(AdapterConfigurationError, match="cloudflare-access profile only"):
        AdapterConfig(issuer=issuer.issuer, audience=issuer.audience, jwks_url=issuer.jwks_url,
                      bound_tenant=TENANT)


def test_the_rfc9068_profile_is_unchanged(issuer, clock):
    from conftest import config_for

    adapter = JwtApproverIdentityAdapter(config_for(issuer), clock=clock.datetime)
    assert adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1", typ="JWT")).refusal \
        == Refusal.TYP_NOT_ACCESS_TOKEN.value
    ok = adapter.authenticate(issuer.mint(base_claims(issuer), kid="rsa-1"))
    assert ok.authenticated and ok.actor_type is ActorKind.HUMAN and ok.issuer_profile == RFC9068_PROFILE
    assert ok.claims.tenant_claims == ("tenant-a",)
    # an email under any domain changes nothing for rfc9068: it is not read there
    other = adapter.authenticate(issuer.mint(base_claims(issuer, email="x@evil.example"), kid="rsa-1"))
    assert other.authenticated and other.claims.tenant_claims == ("tenant-a",)


# --------------------------------------------------------------------------- #
# AP3-D1: typ JWT, and every other check unchanged
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("typ", [None, "at+jwt", "application/at+jwt", "id_token", "jwt+at", 7, ""])
def test_d1_only_typ_jwt_is_admitted_under_the_profile(cf_issuer, cf_clock, typ):
    adapter = adapter_for(cf_issuer, cf_clock)
    if typ is None:
        # PyJWT writes typ JWT unless the header names a falsy typ, which it then drops:
        # this is the genuinely absent header.
        token = cf_issuer.mint(human(cf_issuer), kid=KID, typ=None, headers={"typ": None})
    elif isinstance(typ, str):
        token = cf_issuer.mint(human(cf_issuer), kid=KID, typ=typ)
    else:
        token = cf_issuer.mint(human(cf_issuer), kid=KID, typ=None, headers={"typ": typ})
    import jwt as pyjwt
    assert pyjwt.get_unverified_header(token).get("typ") == (None if typ in (None, "") else typ)
    assert adapter.authenticate(token).refusal == Refusal.TYP_NOT_PROFILE_TYPE.value


def test_d1_a_well_formed_access_token_is_accepted_and_every_other_gate_still_refuses(cf_issuer, cf_clock):
    adapter = adapter_for(cf_issuer, cf_clock)
    ok = adapter.authenticate(cf_issuer.mint(human(cf_issuer), kid=KID, typ="JWT"))
    assert ok.authenticated and ok.proof == "IDP_AUTHENTICATED"
    assert ok.issuer_profile == CLOUDFLARE_ACCESS_PROFILE
    # typ compared case-insensitively (RFC 7515 §4.1.9)
    assert adapter.authenticate(cf_issuer.mint(human(cf_issuer), kid=KID, typ="jwt")).authenticated
    cases = {
        Refusal.ALG_NOT_PERMITTED: cf_issuer.mint_unsigned(human(cf_issuer), kid=KID, typ="JWT"),
        Refusal.ISSUER_MISMATCH: cf_issuer.mint(human(cf_issuer, iss="https://other.cloudflareaccess.com"),
                                                kid=KID, typ="JWT"),
        Refusal.AUDIENCE_MISMATCH: cf_issuer.mint(human(cf_issuer, aud=["0" * 64]), kid=KID, typ="JWT"),
        Refusal.SIGNATURE_INVALID: cf_issuer.mint(human(cf_issuer), kid=KID, typ="JWT",
                                                  pem=cf_issuer.foreign_pem()),
        Refusal.EXPIRED: cf_issuer.mint(human(cf_issuer, exp=int((NOW - timedelta(seconds=1)).timestamp())),
                                        kid=KID, typ="JWT"),
        Refusal.NOT_YET_VALID: cf_issuer.mint(human(cf_issuer, nbf=int((NOW + timedelta(minutes=5)).timestamp())),
                                              kid=KID, typ="JWT"),
        Refusal.KID_MISSING: cf_issuer.mint(human(cf_issuer), kid=KID, typ="JWT", headers={"kid": ""}),
        Refusal.CLAIM_MISSING: cf_issuer.mint(human(cf_issuer, exp=None), kid=KID, typ="JWT"),
    }
    for expected, token in cases.items():
        assert adapter.authenticate(token).refusal == expected.value, expected
    assert adapter.authenticate(cf_issuer.mint_hmac(human(cf_issuer), kid=KID, typ="JWT")).refusal \
        == Refusal.ALG_NOT_PERMITTED.value
    fetches = cf_issuer.fetches
    unknown = cf_issuer.mint(human(cf_issuer), kid=KID, typ="JWT", headers={"kid": "cf-rsa-never"})
    assert adapter.authenticate(unknown).refusal == Refusal.KEY_UNKNOWN.value
    assert cf_issuer.fetches == fetches + 1


# --------------------------------------------------------------------------- #
# AP3-D2: static tenant binding, corroborated, never derived
# --------------------------------------------------------------------------- #
def test_d2_the_tenant_is_the_configured_binding_corroborated_by_the_email_domain(cf_issuer, cf_clock):
    adapter = adapter_for(cf_issuer, cf_clock)
    ok = adapter.authenticate(cf_issuer.mint(human(cf_issuer), kid=KID, typ="JWT"))
    assert ok.claims.tenant_claims == (TENANT,)
    # the binding is a configured statement: change it and the email domain no longer
    # corroborates it only if the domain changes; the tenant value itself is not derived
    other_binding = adapter_for(cf_issuer, cf_clock, bound_tenant="tenant-42")
    assert other_binding.authenticate(cf_issuer.mint(human(cf_issuer), kid=KID, typ="JWT")).claims.tenant_claims \
        == ("tenant-42",)
    # domain compared case-insensitively after NFC and trimming; the local part as presented
    for email in ("AP3-TEST@UGENCE.AI", "ap3-test@Ugence.Ai", " ap3-test@ugence.ai "):
        got = adapter.authenticate(cf_issuer.mint(human(cf_issuer, email=email), kid=KID, typ="JWT"))
        assert got.authenticated and got.claims.tenant_claims == (TENANT,), email


@pytest.mark.parametrize("email, refusal", [
    ("someone@example.com", Refusal.EMAIL_DOMAIN_MISMATCH),
    ("ap3-test@ugence.ai.evil.example", Refusal.EMAIL_DOMAIN_MISMATCH),
    ("ap3-test@sub.ugence.ai", Refusal.EMAIL_DOMAIN_MISMATCH),
    ("ap3-test@notugence.ai", Refusal.EMAIL_DOMAIN_MISMATCH),
    ("ap3-test@ugence.ai@evil.example", Refusal.CLAIM_MALFORMED),
    ("", Refusal.CLAIM_MALFORMED),
    ("@ugence.ai", Refusal.CLAIM_MALFORMED),
    ("ap3 test@ugence.ai", Refusal.CLAIM_MALFORMED),
    (["ap3-test@ugence.ai"], Refusal.CLAIM_MALFORMED),
])
def test_d2_a_foreign_or_malformed_email_never_binds_the_tenant(cf_issuer, cf_clock, email, refusal):
    adapter = adapter_for(cf_issuer, cf_clock)
    answer = adapter.authenticate(cf_issuer.mint(human(cf_issuer, email=email), kid=KID, typ="JWT"))
    assert answer.authenticated is False and answer.refusal == refusal.value
    assert answer.claims is None


def test_d2_an_absent_email_fails_closed_and_a_wrong_pair_never_reaches_the_binding(cf_issuer, cf_clock):
    adapter = adapter_for(cf_issuer, cf_clock)
    absent = adapter.authenticate(cf_issuer.mint(human(cf_issuer, email=None), kid=KID, typ="JWT"))
    assert absent.refusal == Refusal.ACTOR_SHAPE_AMBIGUOUS.value
    wrong_iss = cf_issuer.mint(human(cf_issuer, iss="https://other.cloudflareaccess.com"), kid=KID, typ="JWT")
    assert adapter.authenticate(wrong_iss).refusal == Refusal.ISSUER_MISMATCH.value
    wrong_aud = cf_issuer.mint(human(cf_issuer, aud=["0" * 64]), kid=KID, typ="JWT")
    assert adapter.authenticate(wrong_aud).refusal == Refusal.AUDIENCE_MISMATCH.value
    # a top-level tenant-looking claim is never read under this profile
    decoy = adapter.authenticate(cf_issuer.mint(human(cf_issuer, ugence_tenant="other"), kid=KID, typ="JWT"))
    assert decoy.claims.tenant_claims == (TENANT,)


# --------------------------------------------------------------------------- #
# AP3-D3: the claim-shape mapping, and nothing inferred from type or sub alone
# --------------------------------------------------------------------------- #
def test_d3_the_human_shape_is_human_and_the_service_shape_is_system_with_no_tenant(cf_issuer, cf_clock):
    adapter = adapter_for(cf_issuer, cf_clock)
    person = adapter.authenticate(cf_issuer.mint(human(cf_issuer), kid=KID, typ="JWT"))
    assert person.actor_type is ActorKind.HUMAN and person.claims.subject == "3b0f6d3e-ap3-test-uuid"
    workload = adapter.authenticate(cf_issuer.mint(service(cf_issuer), kid=KID, typ="JWT"))
    assert workload.authenticated and workload.actor_type is ActorKind.SYSTEM
    assert workload.claims.subject == "ap3-service-token" and workload.claims.tenant_claims == ()
    absent_sub = adapter.authenticate(cf_issuer.mint(service(cf_issuer, sub=None), kid=KID, typ="JWT"))
    assert absent_sub.authenticated and absent_sub.actor_type is ActorKind.SYSTEM


@pytest.mark.parametrize("over", [
    dict(common_name="svc"),                       # human sub+email with a service marker
    dict(sub="", common_name=None),                # empty sub, email, no marker
    dict(sub=None),                                # no sub, email, no marker
    dict(email=None),                              # sub, no email, no marker
    dict(sub="", email=None),                      # nothing at all
    dict(sub="", email=None, common_name=""),      # empty marker
    dict(email=None, common_name="svc"),           # sub and marker
    dict(sub="", common_name="svc"),               # marker and email
    dict(sub=7),                                   # wrong type
    dict(sub="", email=None, common_name=["svc"]), # wrong type
])
def test_d3_every_mixed_or_incomplete_shape_is_refused(cf_issuer, cf_clock, over):
    adapter = adapter_for(cf_issuer, cf_clock)
    answer = adapter.authenticate(cf_issuer.mint(human(cf_issuer, **over), kid=KID, typ="JWT"))
    assert answer.authenticated is False
    assert answer.refusal in (Refusal.ACTOR_SHAPE_AMBIGUOUS.value, Refusal.CLAIM_MALFORMED.value)


def test_d3_type_app_decides_nothing_and_no_ia4_claim_is_read(cf_issuer, cf_clock):
    adapter = adapter_for(cf_issuer, cf_clock)
    for type_value in ("app", "org", None, 7):
        person = adapter.authenticate(cf_issuer.mint(human(cf_issuer, type=type_value), kid=KID, typ="JWT"))
        assert person.actor_type is ActorKind.HUMAN, type_value
        workload = adapter.authenticate(cf_issuer.mint(service(cf_issuer, type=type_value), kid=KID, typ="JWT"))
        assert workload.actor_type is ActorKind.SYSTEM, type_value
    # a service-shaped token cannot promote itself with an IA-4-looking marker claim
    promoted = adapter.authenticate(cf_issuer.mint(service(cf_issuer, ugence_actor="human-sign-in"),
                                                   kid=KID, typ="JWT"))
    assert promoted.actor_type is ActorKind.SYSTEM


def test_the_answer_never_carries_the_token_or_the_email(cf_issuer, cf_clock):
    adapter = adapter_for(cf_issuer, cf_clock)
    token = cf_issuer.mint(human(cf_issuer), kid=KID, typ="JWT")
    for answer in (adapter.authenticate(token),
                   adapter.authenticate(cf_issuer.mint(human(cf_issuer, email="x@evil.example"), kid=KID, typ="JWT"))):
        text = repr(answer)
        for fragment in token.split("."):
            assert fragment not in text
        assert "ugence.ai" not in text.replace(TENANT, "") or "@" not in text
        assert "x@evil.example" not in text
