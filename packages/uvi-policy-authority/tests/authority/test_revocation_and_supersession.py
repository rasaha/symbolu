"""Policy-version revocation, historical resolution, and supersession (§12, §13)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from _authority_fixtures import (
    ONE_SECOND,
    T_FROM,
    T_MID,
    T_TO,
    make_authority,
    make_policy,
)
from ugence_uvi_policy_authority.api import (
    HistoricalResolutionRule,
    PolicyAuthorityRequestError,
    PolicyRegistryConflictError,
    PolicyResolutionReason,
    PolicyRevocationError,
    PolicyRevocationReasonCode,
    PolicyRevocationRecord,
    SupersessionRule,
    resolve_policy,
    revoke_policy,
)
from ugence_uvi_policy_contracts.api import PolicyFamily, PolicyLifecycleState, PolicyScope

REVOKED_AT = T_MID


def _resolve(authority, reference, *, as_of=T_MID, tenant="", **kwargs):
    return resolve_policy(
        reference=reference,
        expected_tenant_id=tenant,
        as_of=as_of,
        registry=authority.registry,
        signature_verifier=authority.key_ring,
        **kwargs,
    )


def _issued_and_revoked(*, signer=True, revoked_at=REVOKED_AT):
    authority = make_authority()
    policy = make_policy(effective_from=T_FROM, effective_to=None)
    authority.issue(policy)
    revocation = revoke_policy(
        reference=policy.reference,
        revocation_id="rv-1",
        reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
        registry=authority.registry,
        revoked_at=revoked_at,
        signer=authority.signer if signer else None,
    )
    return authority, policy, revocation


# --------------------------------------------------------------------------- #
# The revocation act
# --------------------------------------------------------------------------- #
def test_revocation_binds_the_complete_exact_reference():
    authority, policy, revocation = _issued_and_revoked()
    assert revocation.policy_reference == policy.reference
    assert revocation.policy_reference.content_digest == policy.metadata.content_digest
    assert revocation.revoked_at == REVOKED_AT
    assert revocation.reason_code is PolicyRevocationReasonCode.CONTENT_DEFECT
    assert revocation.signature and revocation.key_id


def test_a_revocation_signature_covers_its_own_payload():
    authority, _, revocation = _issued_and_revoked()
    assert authority.key_ring.verify(
        key_id=revocation.key_id,
        payload=revocation.signing_payload(),
        signature=revocation.signature,
        expected_authority_id=revocation.revoking_authority_id,
        expected_tenant_id=revocation.policy_reference.tenant_id,
        as_of=T_MID,
    ).valid


def test_a_bare_boolean_or_lifecycle_label_cannot_revoke():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)

    with pytest.raises(PolicyAuthorityRequestError):
        revoke_policy(
            reference=policy.reference,
            revocation_id="rv-1",
            reason_code=True,
            registry=authority.registry,
            revoked_at=T_MID,
        )
    with pytest.raises(PolicyAuthorityRequestError):
        revoke_policy(
            reference=policy.reference,
            revocation_id="rv-1",
            reason_code=PolicyLifecycleState.REVOKED,
            registry=authority.registry,
            revoked_at=T_MID,
        )
    assert authority.registry.revocations_for(policy.reference) == ()
    assert _resolve(authority, policy.reference).resolved


def test_setting_the_lifecycle_label_to_revoked_is_not_an_authority_act():
    """A self-declared REVOKED artifact is refused issuance, not silently revoked."""

    from ugence_uvi_policy_authority.api import PolicyIssuanceError

    authority = make_authority()
    with pytest.raises(PolicyIssuanceError):
        authority.issue(make_policy(lifecycle_state=PolicyLifecycleState.REVOKED))
    assert authority.registry._revocations == {}


def test_revoking_a_policy_that_was_never_issued_is_refused():
    authority = make_authority()
    policy = make_policy()
    with pytest.raises(PolicyRevocationError, match="nothing to revoke"):
        revoke_policy(
            reference=policy.reference,
            revocation_id="rv-1",
            reason_code=PolicyRevocationReasonCode.OTHER,
            registry=authority.registry,
            revoked_at=T_MID,
        )


def test_cross_tenant_revocation_is_rejected():
    authority = make_authority()
    policy = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    authority.issue(policy, expected_tenant_id="tenant-a")
    with pytest.raises(PolicyRevocationError, match="[Cc]ross-tenant"):
        revoke_policy(
            reference=policy.reference,
            revocation_id="rv-1",
            reason_code=PolicyRevocationReasonCode.OTHER,
            registry=authority.registry,
            revoked_at=T_MID,
            expected_tenant_id="tenant-b",
        )
    assert _resolve(authority, policy.reference, tenant="tenant-a").resolved


def test_a_replacement_must_share_the_tenant_and_scope():
    authority = make_authority()
    policy = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    authority.issue(policy, expected_tenant_id="tenant-a")
    other_tenant = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-b", version="2.0.0")
    with pytest.raises(PolicyRevocationError, match="same tenant and scope"):
        revoke_policy(
            reference=policy.reference,
            revocation_id="rv-1",
            reason_code=PolicyRevocationReasonCode.REPLACED,
            registry=authority.registry,
            revoked_at=T_MID,
            replacement_reference=other_tenant.reference,
        )


def test_a_naive_revocation_instant_is_refused():
    from datetime import datetime

    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    with pytest.raises(PolicyAuthorityRequestError, match="timezone-aware"):
        revoke_policy(
            reference=policy.reference,
            revocation_id="rv-1",
            reason_code=PolicyRevocationReasonCode.OTHER,
            registry=authority.registry,
            revoked_at=datetime(2026, 6, 1),
        )


# --------------------------------------------------------------------------- #
# Revocation and time
# --------------------------------------------------------------------------- #
def test_resolution_fails_closed_at_and_after_the_revocation_instant():
    authority, policy, _ = _issued_and_revoked()
    for as_of in (REVOKED_AT, REVOKED_AT + ONE_SECOND, T_TO):
        result = _resolve(authority, policy.reference, as_of=as_of)
        assert result.reason is PolicyResolutionReason.REVOKED, as_of


def test_the_default_historical_rule_denies_before_the_revocation_instant():
    authority, policy, _ = _issued_and_revoked()
    result = _resolve(authority, policy.reference, as_of=REVOKED_AT - ONE_SECOND)
    assert result.reason is PolicyResolutionReason.REVOKED
    assert "DENY_ALWAYS" in result.detail


def test_allow_before_revocation_permits_an_explicitly_historical_as_of():
    authority, policy, _ = _issued_and_revoked()
    before = _resolve(
        authority,
        policy.reference,
        as_of=REVOKED_AT - ONE_SECOND,
        historical_resolution=HistoricalResolutionRule.ALLOW_BEFORE_REVOCATION,
    )
    assert before.resolved

    # The instant itself and everything after still fail closed.
    for as_of in (REVOKED_AT, REVOKED_AT + ONE_SECOND):
        assert (
            _resolve(
                authority,
                policy.reference,
                as_of=as_of,
                historical_resolution=HistoricalResolutionRule.ALLOW_BEFORE_REVOCATION,
            ).reason
            is PolicyResolutionReason.REVOKED
        )


def test_an_unverifiable_revocation_still_denies():
    """Revocation fails closed: a bad signature on a revocation does not un-revoke."""

    authority, policy, revocation = _issued_and_revoked(signer=False)
    assert revocation.signature == b""
    assert _resolve(authority, policy.reference).reason is PolicyResolutionReason.REVOKED

    tampered = PolicyRevocationRecord(
        revocation_id="rv-x",
        policy_reference=policy.reference,
        reason_code=PolicyRevocationReasonCode.OTHER,
        revoking_authority_id="whoever",
        revoked_at=REVOKED_AT,
        key_id="k",
        signature_alg="ed25519",
        signature=b"\x00" * 64,
    )
    fresh = make_authority()
    fresh.issue(policy)
    fresh.registry.append_revocation(tampered)
    assert _resolve(fresh, policy.reference).reason is PolicyResolutionReason.REVOKED


def test_revoking_one_version_leaves_another_valid():
    authority = make_authority()
    v1 = make_policy(PolicyFamily.DOMAIN, policy_id="p", version="1.0.0", effective_to=None)
    v2 = make_policy(PolicyFamily.DOMAIN, policy_id="p", version="2.0.0", effective_to=None)
    authority.issue(v1, record_id="r1")
    authority.issue(v2, record_id="r2")

    revoke_policy(
        reference=v1.reference,
        revocation_id="rv-1",
        reason_code=PolicyRevocationReasonCode.REPLACED,
        registry=authority.registry,
        revoked_at=REVOKED_AT,
        replacement_reference=v2.reference,
    )
    assert _resolve(authority, v1.reference).reason is PolicyResolutionReason.REVOKED
    assert _resolve(authority, v2.reference).resolved


def test_revoking_the_same_id_in_another_tenant_does_not_reach_across():
    authority = make_authority()
    a = make_policy(scope=PolicyScope.TENANT, tenant_id="t-a", policy_id="shared", effective_to=None)
    b = make_policy(scope=PolicyScope.TENANT, tenant_id="t-b", policy_id="shared", effective_to=None)
    authority.issue(a, record_id="ra", expected_tenant_id="t-a")
    authority.issue(b, record_id="rb", expected_tenant_id="t-b")

    revoke_policy(
        reference=a.reference,
        revocation_id="rv-a",
        reason_code=PolicyRevocationReasonCode.OTHER,
        registry=authority.registry,
        revoked_at=REVOKED_AT,
        expected_tenant_id="t-a",
    )
    assert _resolve(authority, a.reference, tenant="t-a").reason is PolicyResolutionReason.REVOKED
    assert _resolve(authority, b.reference, tenant="t-b").resolved


def test_key_revocation_and_policy_revocation_stay_distinct():
    authority = make_authority()
    policy = make_policy(effective_to=None)
    record = authority.issue(policy)

    # Revoking the key denies resolution via the key path...
    ring = authority.key_ring.with_key(authority.key_ring.resolve(record.key_id).revoke())
    keyless = resolve_policy(
        reference=policy.reference,
        expected_tenant_id="",
        as_of=T_MID,
        registry=authority.registry,
        signature_verifier=ring,
    )
    assert keyless.reason is PolicyResolutionReason.KEY_REVOKED
    # ...but records no policy-version revocation.
    assert authority.registry.revocations_for(policy.reference) == ()

    # And revoking the policy leaves the key usable for other versions.
    v2 = make_policy(policy_id="pol-1", version="2.0.0", effective_to=None)
    authority.issue(v2, record_id="r2")
    revoke_policy(
        reference=policy.reference,
        revocation_id="rv-1",
        reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
        registry=authority.registry,
        revoked_at=REVOKED_AT,
    )
    assert _resolve(authority, v2.reference).resolved


def test_no_envelope_epoch_concept_is_reused_here():
    """Policy-version revocation does not borrow the Risk Authority's epoch."""

    from ugence_uvi_policy_authority import api, registry, revocation

    for module in (api, registry, revocation):
        source = open(module.__file__).read().lower()
        assert "advance_epoch" not in source
        assert "authority_epoch" not in source
    assert not hasattr(api, "RevocationState")


# --------------------------------------------------------------------------- #
# Supersession
# --------------------------------------------------------------------------- #
def test_a_self_declared_superseded_artifact_fails_closed():
    """Proven in test_resolution.py; restated here as the supersession rule."""

    from ugence_uvi_policy_authority.api import PolicyIssuanceError

    with pytest.raises(PolicyIssuanceError):
        make_authority().issue(make_policy(lifecycle_state=PolicyLifecycleState.SUPERSEDED))


def test_supersession_does_not_mutate_or_delete_the_older_record():
    authority = make_authority()
    v1 = make_policy(PolicyFamily.DOMAIN, policy_id="p", version="1.0.0", effective_to=None)
    v2 = make_policy(
        PolicyFamily.DOMAIN,
        policy_id="p",
        version="2.0.0",
        effective_to=None,
        supersedes_ref="p@1.0.0",
    )
    r1 = authority.issue(v1, record_id="r1")
    authority.issue(v2, record_id="r2")

    assert authority.registry.get_issued(v1.reference) == r1
    assert _resolve(authority, v1.reference).resolved
    assert _resolve(authority, v2.reference).resolved


def test_the_default_rule_ignores_an_unstructured_supersedes_ref():
    authority = make_authority()
    v1 = make_policy(PolicyFamily.DOMAIN, policy_id="p", version="1.0.0", effective_to=None)
    v2 = make_policy(
        PolicyFamily.DOMAIN,
        policy_id="p",
        version="2.0.0",
        effective_to=None,
        supersedes_ref="p@1.0.0",
    )
    authority.issue(v1, record_id="r1")
    authority.issue(v2, record_id="r2")
    assert _resolve(authority, v1.reference, supersession=SupersessionRule.SELF_DECLARED_ONLY).resolved


def test_the_strict_rule_returns_a_typed_deferred_status_and_never_guesses():
    """The contracts cannot express which exact version a successor replaces."""

    authority = make_authority()
    v1 = make_policy(PolicyFamily.DOMAIN, policy_id="p", version="1.0.0", effective_to=None)
    v2 = make_policy(
        PolicyFamily.DOMAIN,
        policy_id="p",
        version="2.0.0",
        effective_to=None,
        supersedes_ref="p@1.0.0",
    )
    authority.issue(v1, record_id="r1")
    authority.issue(v2, record_id="r2")

    result = _resolve(
        authority,
        v1.reference,
        supersession=SupersessionRule.STRICT_UNDETERMINED_ON_SUCCESSOR,
    )
    assert result.reason is PolicyResolutionReason.SUPERSESSION_UNDETERMINED
    assert result.policy is None
    assert "do not carry enough information" in result.detail
    # The older record is untouched.
    assert authority.registry.get_issued(v1.reference) is not None


def test_the_strict_rule_does_not_fire_without_a_successor():
    authority = make_authority()
    v1 = make_policy(PolicyFamily.DOMAIN, policy_id="p", version="1.0.0", effective_to=None)
    authority.issue(v1, record_id="r1")
    assert _resolve(
        authority, v1.reference, supersession=SupersessionRule.STRICT_UNDETERMINED_ON_SUCCESSOR
    ).resolved


def test_supersession_does_not_reach_across_tenants():
    authority = make_authority()
    a1 = make_policy(scope=PolicyScope.TENANT, tenant_id="t-a", policy_id="p", version="1.0.0", effective_to=None)
    b2 = make_policy(
        scope=PolicyScope.TENANT,
        tenant_id="t-b",
        policy_id="p",
        version="2.0.0",
        effective_to=None,
        supersedes_ref="p@1.0.0",
    )
    authority.issue(a1, record_id="ra", expected_tenant_id="t-a")
    authority.issue(b2, record_id="rb", expected_tenant_id="t-b")
    assert _resolve(
        authority,
        a1.reference,
        tenant="t-a",
        supersession=SupersessionRule.STRICT_UNDETERMINED_ON_SUCCESSOR,
    ).resolved


def test_an_invalid_supersession_rule_is_refused():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    with pytest.raises(PolicyAuthorityRequestError):
        _resolve(authority, policy.reference, supersession="STRICT")
    with pytest.raises(PolicyAuthorityRequestError):
        _resolve(authority, policy.reference, historical_resolution="ALLOW")
