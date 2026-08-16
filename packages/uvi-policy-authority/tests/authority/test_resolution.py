"""Trusted resolution: lifecycle, effective period, and fail-closed order (§11, §13)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from _authority_fixtures import (
    ALL_FAMILIES,
    ONE_SECOND,
    T_AFTER,
    T_BEFORE,
    T_FROM,
    T_MID,
    T_TO,
    make_authority,
    make_policy,
    make_signer,
)
from ugence_uvi_policy_authority.api import (
    ApprovalVerificationStatus,
    InMemoryPolicyRegistry,
    PolicyAuthorityRequestError,
    PolicyKeyRing,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    resolve_policy,
)
from ugence_uvi_policy_contracts.api import (
    PolicyLifecycleState,
    PolicyReference,
    PolicyScope,
)


def _resolve(authority, reference, *, as_of=T_MID, tenant="", **kwargs):
    return resolve_policy(
        reference=reference,
        expected_tenant_id=tenant,
        as_of=as_of,
        registry=authority.registry,
        signature_verifier=authority.key_ring,
        **kwargs,
    )


@pytest.mark.parametrize("family", ALL_FAMILIES)
def test_a_valid_policy_resolves_by_value_with_its_proof(family):
    authority = make_authority()
    policy = make_policy(family)
    record = authority.issue(policy)

    result = _resolve(authority, policy.reference)
    assert result.status is PolicyResolutionStatus.RESOLVED
    assert result.reason is PolicyResolutionReason.RESOLVED
    assert result.resolved is True
    assert result.policy == policy
    assert result.record == record
    assert result.as_of == T_MID


def test_resolution_is_deterministic():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    results = {
        (r.status, r.reason) for r in (_resolve(authority, policy.reference) for _ in range(10))
    }
    assert len(results) == 1


def test_a_failed_resolution_never_carries_a_policy():
    authority = make_authority()
    policy = make_policy()
    result = _resolve(authority, policy.reference)
    assert result.status is PolicyResolutionStatus.UNRESOLVED
    assert result.reason is PolicyResolutionReason.NOT_FOUND
    assert result.policy is None and result.record is None
    assert result.resolved is False


def test_a_resolution_result_cannot_be_constructed_with_a_mismatched_status():
    from ugence_uvi_policy_authority.api import PolicyResolution

    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)

    with pytest.raises(PolicyAuthorityRequestError):
        PolicyResolution(
            status=PolicyResolutionStatus.UNRESOLVED,
            reason=PolicyResolutionReason.EXPIRED,
            requested_reference=policy.reference,
            as_of=T_MID,
            policy=policy,
            record=record,
        )
    with pytest.raises(PolicyAuthorityRequestError):
        PolicyResolution(
            status=PolicyResolutionStatus.RESOLVED,
            reason=PolicyResolutionReason.RESOLVED,
            requested_reference=policy.reference,
            as_of=T_MID,
        )


# --------------------------------------------------------------------------- #
# Exact reference resolution — no floating lookup
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "component,value",
    [
        ("policy_id", "other-policy"),
        ("version", "2.0.0"),
        ("content_digest", "a" * 64),
    ],
)
def test_any_reference_component_mismatch_is_not_found(component, value):
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    probe = replace(policy.reference, **{component: value})
    assert _resolve(authority, probe).reason is PolicyResolutionReason.NOT_FOUND


def test_a_family_mismatch_is_not_found():
    from ugence_uvi_policy_contracts.api import PolicyFamily

    authority = make_authority()
    policy = make_policy(PolicyFamily.DOMAIN)
    authority.issue(policy)
    probe = replace(policy.reference, policy_family=PolicyFamily.READINESS)
    assert _resolve(authority, probe).reason is PolicyResolutionReason.NOT_FOUND


def test_there_is_no_floating_latest_lookup_in_the_trusted_path():
    """The registry protocol exposes no way to resolve without a digest."""

    from ugence_uvi_policy_authority.api import PolicyRegistry

    registry = InMemoryPolicyRegistry()
    for forbidden in ("latest", "current", "newest", "find_by_id", "resolve_latest", "head"):
        assert not hasattr(registry, forbidden)
        assert not hasattr(PolicyRegistry, forbidden)

    # And a reference cannot even be constructed without a content digest.
    from ugence_uvi_policy_contracts.api import PolicyContractError, PolicyFamily

    with pytest.raises(PolicyContractError):
        PolicyReference(
            policy_id="p", policy_family=PolicyFamily.DOMAIN, version="1", content_digest=""
        )


def test_input_ordering_cannot_affect_resolution():
    from ugence_uvi_policy_contracts.api import PolicyFamily

    policies = [
        make_policy(PolicyFamily.DOMAIN, policy_id="p", version=v)
        for v in ("1.0.0", "2.0.0", "3.0.0")
    ]
    outcomes = []
    for order in (policies, list(reversed(policies)), [policies[1], policies[2], policies[0]]):
        authority = make_authority()
        for i, p in enumerate(order):
            authority.issue(p, record_id=f"rec-{p.metadata.version}")
        outcomes.append(
            tuple(
                (_resolve(authority, p.reference).status, _resolve(authority, p.reference).reason)
                for p in policies
            )
        )
    assert len(set(outcomes)) == 1


# --------------------------------------------------------------------------- #
# Digest / signature / key
# --------------------------------------------------------------------------- #
def test_a_hand_assembled_record_fails_closed_at_resolution():
    """Registry lookup alone is not validity."""

    from ugence_uvi_policy_authority.api import IssuedPolicyRecord

    authority = make_authority()
    policy = make_policy()
    forged = IssuedPolicyRecord(
        record_id="forged",
        policy_reference=policy.reference,
        policy_family=policy.metadata.policy_family,
        policy=policy,
        policy_body_digest=policy.metadata.content_digest,
        issuing_authority_id=authority.signer.authority_id,
        key_id=authority.signer.key_id,
        signature_alg="ed25519",
        signature=b"\x01" * 64,
        approving_authority_id="ugence.governance.policy-approval-board",
        approval_ref="APPROVAL-FORGED",
        approval_digest="b" * 64,
        issued_at=T_MID,
    )
    authority.registry.append_issuance(forged)
    assert authority.registry.get_issued(policy.reference) is forged
    assert _resolve(authority, policy.reference).reason is PolicyResolutionReason.SIGNATURE_INVALID


def test_body_mutation_after_issuance_is_detected():
    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)

    swapped = replace(record.policy, governed_outcome_unit="inflated_unit")
    object.__setattr__(record, "policy", swapped)
    assert _resolve(authority, policy.reference).reason is (
        PolicyResolutionReason.CONTENT_DIGEST_MISMATCH
    )


def test_a_record_pairing_a_reference_with_a_different_artifact_is_detected():
    authority = make_authority()
    a = make_policy(policy_id="a")
    b = make_policy(policy_id="b")
    record = authority.issue(a, record_id="rec-a")
    object.__setattr__(record, "policy", b)
    assert _resolve(authority, a.reference).reason is (
        PolicyResolutionReason.ARTIFACT_REFERENCE_MISMATCH
    )


def test_a_body_digest_that_disagrees_with_the_signed_one_is_detected():
    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    object.__setattr__(record, "policy_body_digest", "c" * 64)
    assert _resolve(authority, policy.reference).reason is (
        PolicyResolutionReason.BODY_DIGEST_MISMATCH
    )


def test_an_unknown_key_yields_key_unknown():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    result = resolve_policy(
        reference=policy.reference,
        expected_tenant_id="",
        as_of=T_MID,
        registry=authority.registry,
        signature_verifier=PolicyKeyRing(),
    )
    assert result.reason is PolicyResolutionReason.KEY_UNKNOWN


def test_a_revoked_key_yields_key_revoked():
    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    ring = authority.key_ring.with_key(authority.key_ring.resolve(record.key_id).revoke())
    result = resolve_policy(
        reference=policy.reference,
        expected_tenant_id="",
        as_of=T_MID,
        registry=authority.registry,
        signature_verifier=ring,
    )
    assert result.reason is PolicyResolutionReason.KEY_REVOKED


# --------------------------------------------------------------------------- #
# Approval re-verification at resolution time
# --------------------------------------------------------------------------- #
def test_approval_withdrawn_after_issuance_invalidates_resolution():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    assert _resolve(authority, policy.reference).resolved

    authority.approval.status = ApprovalVerificationStatus.REVOKED
    result = _resolve(authority, policy.reference, approval_verifier=authority.approval)
    assert result.reason is PolicyResolutionReason.APPROVAL_PROOF_INVALID


def test_refreshed_approval_still_binding_resolves():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    assert _resolve(authority, policy.reference, approval_verifier=authority.approval).resolved


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "state,expected",
    [
        (PolicyLifecycleState.DRAFT, PolicyResolutionReason.LIFECYCLE_NOT_ACTIVE),
        (PolicyLifecycleState.EXPIRED, PolicyResolutionReason.LIFECYCLE_NOT_ACTIVE),
        (PolicyLifecycleState.REVOKED, PolicyResolutionReason.LIFECYCLE_NOT_ACTIVE),
        (PolicyLifecycleState.SUPERSEDED, PolicyResolutionReason.SUPERSEDED),
    ],
)
def test_every_non_active_lifecycle_state_fails_closed(state, expected):
    """These artifacts cannot be *issued*, so they are placed directly."""

    authority = make_authority()
    active = make_policy()
    record = authority.issue(active)
    inactive = make_policy(lifecycle_state=state)
    object.__setattr__(record, "policy", inactive)
    object.__setattr__(record, "policy_reference", inactive.reference)
    object.__setattr__(record, "policy_body_digest", inactive.metadata.content_digest)
    authority.registry._issued = {inactive.reference: record}

    # The signature no longer covers this reference, so verification must be
    # bypassed to isolate the lifecycle rule.
    class AlwaysValid:
        def verify(self, **kwargs):
            from ugence_uvi_policy_authority.api import KeyVerification, KeyVerificationStatus

            return KeyVerification(status=KeyVerificationStatus.VALID, key_id="k")

    result = resolve_policy(
        reference=inactive.reference,
        expected_tenant_id="",
        as_of=T_MID,
        registry=authority.registry,
        signature_verifier=AlwaysValid(),
    )
    assert result.reason is expected


def test_a_lifecycle_label_cannot_override_time():
    """APPROVED_ACTIVE does not make an out-of-window policy resolvable."""

    authority = make_authority()
    policy = make_policy(lifecycle_state=PolicyLifecycleState.APPROVED_ACTIVE)
    authority.issue(policy)
    assert policy.metadata.lifecycle_state is PolicyLifecycleState.APPROVED_ACTIVE
    assert _resolve(authority, policy.reference, as_of=T_AFTER).reason is (
        PolicyResolutionReason.EXPIRED
    )
    assert _resolve(authority, policy.reference, as_of=T_BEFORE).reason is (
        PolicyResolutionReason.NOT_YET_EFFECTIVE
    )


# --------------------------------------------------------------------------- #
# Effective period boundaries
# --------------------------------------------------------------------------- #
def test_effective_from_is_inclusive():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    assert _resolve(authority, policy.reference, as_of=T_FROM).resolved
    assert _resolve(authority, policy.reference, as_of=T_FROM - ONE_SECOND).reason is (
        PolicyResolutionReason.NOT_YET_EFFECTIVE
    )


def test_effective_to_is_exclusive():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    assert _resolve(authority, policy.reference, as_of=T_TO - ONE_SECOND).resolved
    assert _resolve(authority, policy.reference, as_of=T_TO).reason is (
        PolicyResolutionReason.EXPIRED
    )


def test_a_missing_upper_bound_is_open_ended():
    authority = make_authority()
    policy = make_policy(effective_to=None)
    authority.issue(policy)
    for moment in (T_MID, T_AFTER, T_AFTER + timedelta(days=3650)):
        assert _resolve(authority, policy.reference, as_of=moment).resolved


def test_a_missing_lower_bound_is_open_ended():
    authority = make_authority()
    policy = make_policy(effective_from=None)
    authority.issue(policy)
    assert _resolve(authority, policy.reference, as_of=T_BEFORE).resolved


# --------------------------------------------------------------------------- #
# Tenant / scope
# --------------------------------------------------------------------------- #
def test_cross_tenant_resolution_fails_closed_without_leakage():
    authority = make_authority()
    policy = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    authority.issue(policy, expected_tenant_id="tenant-a")

    result = _resolve(authority, policy.reference, tenant="tenant-b")
    assert result.reason is PolicyResolutionReason.TENANT_SCOPE_MISMATCH
    assert result.policy is None and result.record is None
    # Nothing in the result reveals that a record exists under tenant-a.
    assert "tenant-a" not in result.detail

    assert _resolve(authority, policy.reference, tenant="tenant-a").resolved


def test_a_global_policy_does_not_resolve_for_a_tenant_request():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    assert _resolve(authority, policy.reference, tenant="tenant-a").reason is (
        PolicyResolutionReason.TENANT_SCOPE_MISMATCH
    )


def test_two_tenants_holding_the_same_policy_id_stay_separate():
    authority = make_authority()
    a = make_policy(scope=PolicyScope.TENANT, tenant_id="t-a", policy_id="shared")
    b = make_policy(scope=PolicyScope.TENANT, tenant_id="t-b", policy_id="shared")
    authority.issue(a, record_id="ra", expected_tenant_id="t-a")
    authority.issue(b, record_id="rb", expected_tenant_id="t-b")

    assert _resolve(authority, a.reference, tenant="t-a").resolved
    assert _resolve(authority, b.reference, tenant="t-b").resolved
    assert _resolve(authority, a.reference, tenant="t-b").reason is (
        PolicyResolutionReason.TENANT_SCOPE_MISMATCH
    )


# --------------------------------------------------------------------------- #
# Argument validation
# --------------------------------------------------------------------------- #
def test_a_naive_as_of_is_refused():
    from datetime import datetime

    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    with pytest.raises(PolicyAuthorityRequestError, match="timezone-aware"):
        _resolve(authority, policy.reference, as_of=datetime(2026, 6, 1))


def test_a_non_reference_is_refused():
    authority = make_authority()
    with pytest.raises(PolicyAuthorityRequestError):
        _resolve(authority, "pol-1@1.0.0")
