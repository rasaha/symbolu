"""Signed, authorized, resolution-verified revocation (ADR §14, P-8)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from _authority_fixtures import (
    ONE_SECOND,
    REVOKING_AUTHORITY,
    T_AFTER,
    T_FROM,
    T_MID,
    T_TO,
    coordinate_of,
    make_authority,
    make_policy,
    make_signer,
)
from ugence_policy_authority.api import (
    HistoricalResolutionRule,
    KeyEntitlement,
    PolicyAuthorityRequestError,
    PolicyKeyRing,
    PolicyRegistryConflictError,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    PolicyRevocationError,
    PolicyRevocationReasonCode,
    PolicyRevocationRecord,
    revoke_policy,
    verify_revocation_record,
)
from ugence_uvi_policy_contracts.api import PolicyLifecycleState, PolicyScope

REVOKED_AT = T_MID


def _revoke(authority, policy, *, revocation_id="rv-1", signer=None, **kwargs):
    return revoke_policy(
        reference=kwargs.pop("reference", policy.reference),
        revocation_id=revocation_id,
        reason_code=kwargs.pop("reason_code", PolicyRevocationReasonCode.CONTENT_DEFECT),
        registry=authority.registry,
        adapters=authority.adapters,
        signer=signer or authority.revocation_signer,
        signature_verifier=kwargs.pop("signature_verifier", authority.key_ring),
        revoked_at=kwargs.pop("revoked_at", REVOKED_AT),
        **kwargs,
    )


def _issued_and_revoked(**kwargs):
    authority = make_authority()
    policy = make_policy(effective_from=T_FROM, effective_to=None)
    authority.issue(policy)
    revocation = _revoke(authority, policy, **kwargs)
    return authority, policy, revocation


# --------------------------------------------------------------------------- #
# The revocation act is signed and authorized
# --------------------------------------------------------------------------- #
def test_revocation_binds_the_complete_exact_coordinate():
    authority, policy, revocation = _issued_and_revoked()
    coordinate = coordinate_of(policy)
    assert revocation.coordinate == coordinate
    for component in ("policy_family", "policy_id", "version", "content_digest", "scope", "tenant_id"):
        assert getattr(revocation.coordinate, component) == getattr(coordinate, component)
    assert revocation.revoked_at == REVOKED_AT
    assert revocation.signature and revocation.key_id and revocation.signature_alg


def test_the_revoking_authority_is_the_signer_not_the_issuer():
    authority, _, revocation = _issued_and_revoked()
    assert revocation.revoking_authority_id == REVOKING_AUTHORITY
    assert revocation.revoking_authority_id != authority.signer.authority_id


def test_a_revocation_signer_is_mandatory():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    for bogus in (None, object()):
        with pytest.raises(PolicyAuthorityRequestError, match="mandatory"):
            revoke_policy(
                reference=policy.reference,
                revocation_id="rv-1",
                reason_code=PolicyRevocationReasonCode.OTHER,
                registry=authority.registry,
                adapters=authority.adapters,
                signer=bogus,
                signature_verifier=authority.key_ring,
                revoked_at=T_MID,
            )
    assert authority.registry.revocations_for(coordinate_of(policy)) == ()


def test_a_signature_verifier_is_mandatory():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    with pytest.raises(PolicyAuthorityRequestError, match="mandatory"):
        revoke_policy(
            reference=policy.reference,
            revocation_id="rv-1",
            reason_code=PolicyRevocationReasonCode.OTHER,
            registry=authority.registry,
            adapters=authority.adapters,
            signer=authority.revocation_signer,
            signature_verifier=None,
            revoked_at=T_MID,
        )


def test_an_unsigned_revocation_record_cannot_be_constructed():
    authority, policy, _ = _issued_and_revoked()
    with pytest.raises(PolicyAuthorityRequestError, match="not 'revocation pending'"):
        PolicyRevocationRecord(
            revocation_id="rv-x",
            coordinate=coordinate_of(policy),
            reason_code=PolicyRevocationReasonCode.OTHER,
            revoking_authority_id="whoever",
            key_id="k",
            signature_alg="ed25519",
            signature=b"",
            revoked_at=T_MID,
        )


def test_a_foreign_signer_cannot_revoke_even_with_a_valid_signature():
    """Structurally valid, but the key is not a registered trust anchor."""

    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    foreign = make_signer(authority_id="attacker.authority", key_id="attacker-key", seed=31)

    with pytest.raises(PolicyRevocationError, match="not authorized"):
        _revoke(authority, policy, signer=foreign)
    assert authority.registry.revocations_for(coordinate_of(policy)) == ()
    assert authority.resolve(policy.reference).resolved


def test_an_issue_only_key_cannot_revoke():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    with pytest.raises(PolicyRevocationError, match="NOT_ENTITLED"):
        _revoke(authority, policy, signer=authority.signer)
    assert authority.registry.revocations_for(coordinate_of(policy)) == ()


def test_a_revoked_key_cannot_revoke():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    ring = authority.key_ring.with_key(
        authority.key_ring.resolve(authority.revocation_signer.key_id).revoke()
    )
    with pytest.raises(PolicyRevocationError, match="REVOKED_KEY"):
        _revoke(authority, policy, signature_verifier=ring)


def test_an_unknown_key_cannot_revoke():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    with pytest.raises(PolicyRevocationError, match="UNKNOWN_KEY"):
        _revoke(authority, policy, signature_verifier=PolicyKeyRing())


def test_a_bare_boolean_or_lifecycle_label_cannot_revoke():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    for bogus in (True, PolicyLifecycleState.REVOKED, "REVOKED", 1):
        with pytest.raises(PolicyAuthorityRequestError):
            _revoke(authority, policy, reason_code=bogus)
    assert authority.registry.revocations_for(coordinate_of(policy)) == ()
    assert authority.resolve(policy.reference).resolved


def test_self_labelling_revoked_is_not_an_authority_act():
    from ugence_policy_authority.api import PolicyIssuanceError

    authority = make_authority()
    with pytest.raises(PolicyIssuanceError):
        authority.issue(make_policy(lifecycle_state=PolicyLifecycleState.REVOKED))
    assert authority.registry._revocations == {}


def test_revoking_a_policy_that_was_never_issued_is_refused():
    authority = make_authority()
    with pytest.raises(PolicyRevocationError, match="nothing to revoke"):
        _revoke(authority, make_policy())


def test_cross_tenant_revocation_is_rejected():
    authority = make_authority()
    policy = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    authority.issue(policy, expected_reference_tenant_id="tenant-a")
    with pytest.raises(PolicyRevocationError, match="[Cc]ross-tenant"):
        _revoke(authority, policy, expected_reference_tenant_id="tenant-b")
    assert authority.resolve(policy.reference, tenant="tenant-a").resolved


def test_a_replacement_must_share_the_tenant_and_scope():
    authority = make_authority()
    policy = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    authority.issue(policy, expected_reference_tenant_id="tenant-a")
    other = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-b", version="2.0.0")
    with pytest.raises(PolicyRevocationError, match="same tenant and scope"):
        _revoke(
            authority,
            policy,
            reason_code=PolicyRevocationReasonCode.REPLACED,
            replacement_reference=other.reference,
        )


def test_a_naive_revocation_instant_is_refused():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    with pytest.raises(PolicyAuthorityRequestError, match="naive datetime"):
        _revoke(authority, policy, revoked_at=datetime(2026, 6, 1))


# --------------------------------------------------------------------------- #
# Resolution verifies the revocation before applying it
# --------------------------------------------------------------------------- #
def test_a_valid_revocation_denies_at_and_after_its_instant():
    authority, policy, _ = _issued_and_revoked()
    for as_of in (REVOKED_AT, REVOKED_AT + ONE_SECOND, T_AFTER):
        assert authority.resolve(policy.reference, as_of=as_of).reason is (
            PolicyResolutionReason.REVOKED
        ), as_of


@pytest.mark.parametrize(
    "field,value",
    [
        ("revocation_id", "rv-tampered"),
        ("reason_code", PolicyRevocationReasonCode.KEY_COMPROMISE),
        ("revoking_authority_id", "attacker.authority"),
        ("key_id", "other-key"),
        ("signature_alg", "not-ed25519"),
        ("revoked_at", T_MID + timedelta(seconds=1)),
    ],
)
def test_a_tampered_revocation_fails_closed_as_an_integrity_error(field, value):
    """Not ignored, and not honoured — a typed integrity failure."""

    authority, policy, revocation = _issued_and_revoked()
    tampered = replace(revocation, **{field: value})
    authority.registry._revocations[coordinate_of(policy)] = tampered

    result = authority.resolve(policy.reference, as_of=T_FROM)
    assert result.reason is PolicyResolutionReason.REVOCATION_INTEGRITY_INVALID
    assert result.policy is None, "an unverifiable revocation must not return a live policy"


def test_a_forged_revocation_signature_fails_closed():
    authority, policy, revocation = _issued_and_revoked()
    forged = replace(revocation, signature=b"\x00" * 64)
    authority.registry._revocations[coordinate_of(policy)] = forged
    assert authority.resolve(policy.reference, as_of=T_FROM).reason is (
        PolicyResolutionReason.REVOCATION_INTEGRITY_INVALID
    )


def test_a_revocation_signed_by_an_unentitled_key_fails_closed_at_resolution():
    authority, policy, revocation = _issued_and_revoked()
    # Re-register the revoker's key as issue-only after the fact.
    downgraded = authority.key_ring.with_key(
        replace(
            authority.key_ring.resolve(revocation.key_id),
            entitlements=frozenset({KeyEntitlement.ISSUE_POLICY}),
        )
    )
    from ugence_policy_authority.api import resolve_policy

    result = resolve_policy(
        reference=policy.reference,
        expected_reference_tenant_id="",
        as_of=T_FROM,
        registry=authority.registry,
        signature_verifier=downgraded,
        adapters=authority.adapters,
    )
    assert result.reason is PolicyResolutionReason.REVOCATION_INTEGRITY_INVALID


def test_a_revocation_targeting_another_coordinate_is_rejected():
    authority, policy, revocation = _issued_and_revoked()
    other = make_policy(policy_id="other", effective_to=None)
    verification = verify_revocation_record(
        revocation,
        coordinate=coordinate_of(other),
        signature_verifier=authority.key_ring,
        as_of=T_MID,
    )
    assert not verification.valid
    assert "different policy coordinate" in verification.detail


def test_a_replayed_revocation_from_another_version_does_not_apply():
    authority = make_authority()
    v1 = make_policy(policy_id="p", version="1.0.0", effective_to=None)
    v2 = make_policy(policy_id="p", version="2.0.0", effective_to=None)
    authority.issue(v1, record_id="r1")
    authority.issue(v2, record_id="r2")
    revocation = _revoke(authority, v1)

    # Replay v1's signed revocation under v2's coordinate.
    replayed = replace(revocation, coordinate=coordinate_of(v2))
    authority.registry._revocations[coordinate_of(v2)] = replayed

    assert authority.resolve(v2.reference).reason is (
        PolicyResolutionReason.REVOCATION_INTEGRITY_INVALID
    )
    assert authority.resolve(v1.reference).reason is PolicyResolutionReason.REVOKED


# --------------------------------------------------------------------------- #
# Historical resolution
# --------------------------------------------------------------------------- #
def test_the_default_rule_denies_before_the_revocation_instant():
    authority, policy, _ = _issued_and_revoked()
    result = authority.resolve(policy.reference, as_of=REVOKED_AT - ONE_SECOND)
    assert result.reason is PolicyResolutionReason.REVOKED
    assert "DENY_ALWAYS" in result.detail


def test_allow_before_revocation_discloses_a_historical_answer():
    authority, policy, _ = _issued_and_revoked()
    result = authority.resolve(
        policy.reference,
        as_of=REVOKED_AT - ONE_SECOND,
        historical_resolution=HistoricalResolutionRule.ALLOW_BEFORE_REVOCATION,
    )
    assert result.status is PolicyResolutionStatus.RESOLVED
    assert result.historical is True
    assert result.implies_current_validity is False
    assert result.as_of == REVOKED_AT - ONE_SECOND
    assert "does not imply current validity" in result.detail


def test_a_historical_rule_still_denies_at_and_after_the_instant():
    authority, policy, _ = _issued_and_revoked()
    for as_of in (REVOKED_AT, REVOKED_AT + ONE_SECOND):
        assert authority.resolve(
            policy.reference,
            as_of=as_of,
            historical_resolution=HistoricalResolutionRule.ALLOW_BEFORE_REVOCATION,
        ).reason is PolicyResolutionReason.REVOKED


def test_a_non_historical_resolution_is_never_marked_historical():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    result = authority.resolve(policy.reference)
    assert result.historical is False and result.implies_current_validity is True


def test_an_invalid_historical_rule_is_refused():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    with pytest.raises(PolicyAuthorityRequestError):
        authority.resolve(policy.reference, historical_resolution="ALLOW")


# --------------------------------------------------------------------------- #
# Blast radius and concept separation
# --------------------------------------------------------------------------- #
def test_revoking_one_version_leaves_another_valid():
    authority = make_authority()
    v1 = make_policy(policy_id="p", version="1.0.0", effective_to=None)
    v2 = make_policy(policy_id="p", version="2.0.0", effective_to=None)
    authority.issue(v1, record_id="r1")
    authority.issue(v2, record_id="r2")
    _revoke(authority, v1, reason_code=PolicyRevocationReasonCode.REPLACED,
            replacement_reference=v2.reference)
    assert authority.resolve(v1.reference).reason is PolicyResolutionReason.REVOKED
    assert authority.resolve(v2.reference).resolved


def test_revoking_in_one_tenant_does_not_reach_another():
    authority = make_authority()
    a = make_policy(scope=PolicyScope.TENANT, tenant_id="t-a", policy_id="shared", effective_to=None)
    b = make_policy(scope=PolicyScope.TENANT, tenant_id="t-b", policy_id="shared", effective_to=None)
    authority.issue(a, record_id="ra", expected_reference_tenant_id="t-a")
    authority.issue(b, record_id="rb", expected_reference_tenant_id="t-b")

    # A tenant-scoped revocation needs a key entitled for that tenant.
    _revoke(authority, a, expected_reference_tenant_id="t-a")
    assert authority.resolve(a.reference, tenant="t-a").reason is PolicyResolutionReason.REVOKED
    assert authority.resolve(b.reference, tenant="t-b").resolved


def test_key_revocation_and_policy_revocation_stay_distinct():
    authority = make_authority()
    policy = make_policy(effective_to=None)
    record = authority.issue(policy)

    ring = authority.key_ring.with_key(authority.key_ring.resolve(record.key_id).revoke())
    from ugence_policy_authority.api import resolve_policy

    assert resolve_policy(
        reference=policy.reference,
        expected_reference_tenant_id="",
        as_of=T_MID,
        registry=authority.registry,
        signature_verifier=ring,
        adapters=authority.adapters,
    ).reason is PolicyResolutionReason.KEY_REVOKED
    # ...and records no policy-version revocation.
    assert authority.registry.revocations_for(coordinate_of(policy)) == ()


def test_no_envelope_epoch_concept_is_reused():
    from ugence_policy_authority import api
    from ugence_policy_authority.core import registry, resolution, revocation

    for module in (registry, resolution, revocation):
        source = open(module.__file__).read().lower()
        assert "advance_epoch" not in source
        assert "authority_epoch" not in source
    assert not hasattr(api, "RevocationState")
