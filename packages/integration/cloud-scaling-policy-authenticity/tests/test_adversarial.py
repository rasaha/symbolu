"""Attacks that must be REFUSED, and the exact typed member each must be refused with.

Grouped by which gate does the refusing. Every assertion names a member, never a message
substring: an outcome a caller can only reach by parsing prose is not a typed outcome.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from _policy_fixtures import (
    ONE_SECOND,
    T_AFTER,
    T_BEFORE,
    T_FROM,
    T_MID,
    T_TO,
    ForeignTypePort,
    RaisingPort,
    SubstitutingPort,
    UnresolvedPort,
    issued,
    make_authority,
    make_policy,
    make_signer,
    port_for,
    revoke,
    verifier_for,
)
from ugence_policy_authority.api import (
    DenyAllSignatureVerifier,
    KeyEntitlement,
    PolicyCoordinate,
    PolicyKeyRing,
    PolicyResolutionReason,
)

from ugence_cloud_scaling_policy_authenticity import (
    DenyAllPolicyResolutionPort,
    PolicyAuthenticityOutcome as O,
    PolicyAuthenticityVerifier,
    PolicyAuthorityResolutionPort,
)


def _verify(authority, record, *, as_of=T_MID, tenant=None, verifier=None, **kwargs):
    verifier = verifier or verifier_for(authority)
    return verifier.verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=(
            record.coordinate.tenant_id if tenant is None else tenant
        ),
        as_of=as_of,
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# Temporal validity — "is valid now", judged at the injected instant (D-5B0B-5)
# --------------------------------------------------------------------------- #
@pytest.mark.adversarial
def test_a_revoked_policy_is_refused_at_and_after_the_revocation_instant():
    authority, record = issued()
    revoke(authority, record, revoked_at=T_MID)
    assert _verify(authority, record, as_of=T_MID).outcome is O.REVOKED
    assert _verify(authority, record, as_of=T_MID + ONE_SECOND).outcome is O.REVOKED


@pytest.mark.adversarial
def test_an_instant_before_the_effective_period_is_refused():
    authority, record = issued()
    assert _verify(authority, record, as_of=T_BEFORE).outcome is O.NOT_YET_EFFECTIVE


@pytest.mark.adversarial
def test_an_instant_at_or_after_the_effective_period_is_refused():
    authority, record = issued()
    assert _verify(authority, record, as_of=T_TO).outcome is O.EXPIRED
    assert _verify(authority, record, as_of=T_AFTER).outcome is O.EXPIRED


@pytest.mark.adversarial
def test_the_same_record_yields_different_answers_at_different_instants():
    """The measurement behind D-5B0B-5: authenticity is not a property of the record alone.

    One record, one registry, one key ring, one trust configuration — and three different
    answers. This is why the verified artifact must carry its instant, and why R-2 (whose
    clock supplies it) is load-bearing rather than a formality.
    """

    authority, record = issued()
    assert _verify(authority, record, as_of=T_BEFORE).outcome is O.NOT_YET_EFFECTIVE
    assert _verify(authority, record, as_of=T_MID).outcome is O.VERIFIED
    assert _verify(authority, record, as_of=T_TO).outcome is O.EXPIRED


@pytest.mark.adversarial
def test_revocation_is_absolute_under_the_default_historical_rule():
    """Revoked at ``T_TO - 1s``, and refused even at instants strictly before that.

    ``DENY_ALWAYS`` is the authority's default and the rule the production port pins: a
    revoked version never resolves, at any ``as_of``. The historical exception exists, is
    reachable only under an explicit non-default rule, and is refused here regardless — see
    ``test_historical_refusal.py``.
    """

    authority, record = issued()
    revoke(authority, record, revoked_at=T_TO - ONE_SECOND)
    assert _verify(authority, record, as_of=T_MID).outcome is O.REVOKED
    assert _verify(authority, record, as_of=T_TO - ONE_SECOND).outcome is O.REVOKED


# --------------------------------------------------------------------------- #
# Trust configuration — the D-5B0B-4 option (a) surface
# --------------------------------------------------------------------------- #
@pytest.mark.adversarial
def test_a_policy_verified_under_one_trust_root_is_refused_under_another():
    """Authenticity is an evaluation under configured trust, not a property of the record."""

    authority, record = issued()
    assert _verify(authority, record).outcome is O.VERIFIED

    deny_all = PolicyAuthorityResolutionPort(
        registry=authority.registry,
        signature_verifier=DenyAllSignatureVerifier(),
        adapters=authority.adapters,
    )
    verifier = PolicyAuthenticityVerifier(resolution_port=deny_all)
    assert _verify(authority, record, verifier=verifier).outcome is O.KEY_UNKNOWN


@pytest.mark.adversarial
def test_a_revoked_signing_key_refuses_the_policy_it_previously_signed():
    authority, record = issued()
    revoked_ring = PolicyKeyRing(
        [key.revoke() for key in authority.key_ring.keys.values()]
    )
    port = PolicyAuthorityResolutionPort(
        registry=authority.registry,
        signature_verifier=revoked_ring,
        adapters=authority.adapters,
    )
    verifier = PolicyAuthenticityVerifier(resolution_port=port)
    assert _verify(authority, record, verifier=verifier).outcome is O.KEY_REVOKED


@pytest.mark.adversarial
def test_a_revoke_only_key_cannot_authenticate_an_issued_policy():
    """The entitlement split D-5B0B-4 cites as the second asymmetry, made executable.

    The key is genuine, un-revoked, in window and belongs to the issuing authority. It holds
    ``REVOKE_POLICY`` and not ``ISSUE_POLICY``, and that alone refuses.
    """

    authority, record = issued()
    signer = authority.signer
    revoke_only = PolicyKeyRing(
        [signer.verification_key(entitlements=(KeyEntitlement.REVOKE_POLICY,))]
    )
    port = PolicyAuthorityResolutionPort(
        registry=authority.registry,
        signature_verifier=revoke_only,
        adapters=authority.adapters,
    )
    verifier = PolicyAuthenticityVerifier(resolution_port=port)
    assert _verify(authority, record, verifier=verifier).outcome is O.KEY_NOT_ENTITLED


@pytest.mark.adversarial
def test_a_key_bound_to_another_tenant_cannot_authenticate_this_tenant_s_policy():
    """The tenant asymmetry D-5B0B-4 turns on, made executable.

    A Trusted Evidence Authority trust anchor could not express this refusal at all: its
    record carries no tenant field by ratified refusal. This is the measured reason option
    (a) was ratified over option (b).
    """

    from _policy_fixtures import PolicyScope

    authority = make_authority()
    record = authority.issue(make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-a"))
    foreign_tenant_ring = PolicyKeyRing(
        [
            authority.signer.verification_key(
                entitlements=(KeyEntitlement.ISSUE_POLICY,), tenant_id="tenant-b"
            )
        ]
    )
    port = PolicyAuthorityResolutionPort(
        registry=authority.registry,
        signature_verifier=foreign_tenant_ring,
        adapters=authority.adapters,
    )
    verifier = PolicyAuthenticityVerifier(resolution_port=port)
    result = verifier.verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id="tenant-a",
        as_of=T_MID,
    )
    assert result.outcome is O.KEY_REVOKED  # the authority reports WRONG_TENANT as this


@pytest.mark.adversarial
def test_a_foreign_authority_s_key_of_the_same_id_cannot_stand_in():
    authority, record = issued()
    impostor = make_signer(authority_id="attacker.example", key_id=authority.signer.key_id, seed=9)
    port = PolicyAuthorityResolutionPort(
        registry=authority.registry,
        signature_verifier=PolicyKeyRing([impostor.verification_key()]),
        adapters=authority.adapters,
    )
    verifier = PolicyAuthenticityVerifier(resolution_port=port)
    assert _verify(authority, record, verifier=verifier).outcome is O.KEY_REVOKED


# --------------------------------------------------------------------------- #
# Identity — the coordinate is exact, and the tenant expectation is checked first
# --------------------------------------------------------------------------- #
@pytest.mark.adversarial
def test_an_unregistered_coordinate_is_refused_rather_than_approximated():
    authority, record = issued()
    elsewhere = PolicyCoordinate(
        policy_family=record.coordinate.policy_family,
        policy_id=record.coordinate.policy_id,
        version="9.9.9",
        content_digest=record.coordinate.content_digest,
        scope=record.coordinate.scope,
        tenant_id=record.coordinate.tenant_id,
    )
    result = verifier_for(authority).verify(
        coordinate=elsewhere,
        expected_reference_tenant_id=elsewhere.tenant_id,
        as_of=T_MID,
    )
    assert result.outcome is O.POLICY_NOT_FOUND


@pytest.mark.adversarial
def test_a_tenant_expectation_that_contradicts_the_coordinate_is_refused_before_the_authority_is_asked():
    authority, record = issued()
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id="some-other-tenant",
        as_of=T_MID,
    )
    assert result.outcome is O.TENANT_EXPECTATION_MISMATCH


# --------------------------------------------------------------------------- #
# The port is injected, so the port is not trusted
# --------------------------------------------------------------------------- #
@pytest.mark.adversarial
def test_a_port_that_raises_is_a_refusal_never_a_pass():
    authority, record = issued()
    verifier = PolicyAuthenticityVerifier(resolution_port=RaisingPort())
    assert _verify(authority, record, verifier=verifier).outcome is O.VERIFICATION_UNAVAILABLE


@pytest.mark.adversarial
@pytest.mark.parametrize("payload", [True, "RESOLVED", None, 1, object()])
def test_a_port_that_returns_a_foreign_type_is_refused(payload):
    authority, record = issued()
    verifier = PolicyAuthenticityVerifier(resolution_port=ForeignTypePort(payload=payload))
    assert _verify(authority, record, verifier=verifier).outcome is O.UNSUPPORTED_EXACT_TYPE


@pytest.mark.adversarial
def test_a_port_that_answers_about_a_different_coordinate_is_refused():
    authority, record = issued()
    other = PolicyCoordinate(
        policy_family=record.coordinate.policy_family,
        policy_id="somewhere-else",
        version=record.coordinate.version,
        content_digest=record.coordinate.content_digest,
        scope=record.coordinate.scope,
        tenant_id=record.coordinate.tenant_id,
    )
    port = SubstitutingPort(inner=port_for(authority), substitute_coordinate=other)
    verifier = PolicyAuthenticityVerifier(resolution_port=port)
    assert (
        _verify(authority, record, verifier=verifier).outcome
        is O.RESOLUTION_ANSWERED_ANOTHER_QUESTION
    )


@pytest.mark.adversarial
def test_a_port_that_answers_at_a_different_instant_is_refused():
    authority, record = issued()
    port = SubstitutingPort(
        inner=port_for(authority), substitute_as_of=T_MID + timedelta(days=1)
    )
    verifier = PolicyAuthenticityVerifier(resolution_port=port)
    assert (
        _verify(authority, record, verifier=verifier).outcome
        is O.RESOLUTION_ANSWERED_ANOTHER_QUESTION
    )


@pytest.mark.adversarial
def test_the_deny_all_port_refuses_every_coordinate():
    authority, record = issued()
    verifier = PolicyAuthenticityVerifier(resolution_port=DenyAllPolicyResolutionPort())
    assert _verify(authority, record, verifier=verifier).outcome is O.POLICY_NOT_FOUND


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "reason",
    [r for r in PolicyResolutionReason if r is not PolicyResolutionReason.RESOLVED],
)
def test_every_authority_refusal_reason_reaches_a_distinct_typed_refusal(reason):
    """No authority refusal is silently collapsed, and none of them reaches VERIFIED."""

    authority, record = issued()
    verifier = PolicyAuthenticityVerifier(resolution_port=UnresolvedPort(reason=reason))
    outcome = _verify(authority, record, verifier=verifier).outcome
    assert outcome is not O.VERIFIED
    assert outcome is not O.INDETERMINATE


# --------------------------------------------------------------------------- #
# Exact-type admission
# --------------------------------------------------------------------------- #
@pytest.mark.adversarial
def test_a_naive_instant_is_refused_rather_than_assumed_utc():
    from datetime import datetime

    authority, record = issued()
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=datetime(2026, 6, 1),
    )
    assert result.outcome is O.UNSUPPORTED_EXACT_TYPE


@pytest.mark.adversarial
def test_a_coordinate_look_alike_is_refused_not_adapted():
    class LookAlike:
        policy_family = "domain"
        policy_id = "pol-1"
        version = "1.0.0"
        content_digest = "a" * 64
        scope = "GLOBAL"
        tenant_id = ""

    authority, _record = issued()
    result = verifier_for(authority).verify(
        coordinate=LookAlike(), expected_reference_tenant_id="", as_of=T_MID
    )
    assert result.outcome is O.UNSUPPORTED_EXACT_TYPE


@pytest.mark.adversarial
def test_a_coordinate_subclass_is_refused_not_adapted():
    authority, record = issued()

    class Subclass(PolicyCoordinate):
        pass

    subclassed = Subclass(
        policy_family=record.coordinate.policy_family,
        policy_id=record.coordinate.policy_id,
        version=record.coordinate.version,
        content_digest=record.coordinate.content_digest,
        scope=record.coordinate.scope,
        tenant_id=record.coordinate.tenant_id,
    )
    result = verifier_for(authority).verify(
        coordinate=subclassed,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    assert result.outcome is O.UNSUPPORTED_EXACT_TYPE


@pytest.mark.adversarial
def test_a_candidate_look_alike_is_refused():
    authority, record = issued()
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
        candidate=object(),
    )
    assert result.outcome is O.UNSUPPORTED_EXACT_TYPE


# --------------------------------------------------------------------------- #
# What a verified proof deliberately does NOT establish
# --------------------------------------------------------------------------- #
@pytest.mark.adversarial
def test_a_verified_policy_proof_grants_no_authority():
    authority, record = issued()
    verified = _verify(authority, record).verified_policy
    assert verified.grants_authority is False
    assert verified.historical is False
    assert not hasattr(verified, "envelope")
    assert not hasattr(verified, "credential")
    assert not hasattr(verified, "authorized")
    assert not hasattr(verified, "permitted")


@pytest.mark.adversarial
def test_the_boundary_exposes_no_signer_no_key_and_no_registry():
    """This package holds no trust store. Option (a) delegates; it does not duplicate."""

    import ugence_cloud_scaling_policy_authenticity as pkg

    exported = set(pkg.__all__)
    # Named exactly: substring matching would trip over SUPPORTED_SIGNATURE_ALGORITHMS,
    # which is a closed admission set and not a signing capability.
    forbidden = {
        "SigningKey",
        "PolicyKeyRing",
        "PolicyVerificationKey",
        "Ed25519PolicySigner",
        "InMemoryPolicyRegistry",
        "issue_policy",
        "revoke_policy",
        "resolve_policy",
    }
    assert forbidden.isdisjoint(exported)
    # And nothing exported is callable under a signing name.
    for symbol in exported:
        assert symbol not in {"sign", "mint", "issue", "revoke"}
