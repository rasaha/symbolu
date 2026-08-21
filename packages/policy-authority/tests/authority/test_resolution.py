"""Trusted resolution: fail-closed order, lifecycle, time, and disclosure (ADR §15, §17)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from _authority_fixtures import (
    ALL_FAMILIES,
    ONE_SECOND,
    T_AFTER,
    T_BEFORE,
    T_FROM,
    T_MID,
    T_TO,
    coordinate_of,
    make_authority,
    make_policy,
    make_signer,
)
from ugence_policy_authority.api import (
    ApprovalVerificationStatus,
    IssuedPolicyRecord,
    PolicyAuthorityRequestError,
    PolicyCoordinate,
    PolicyKeyRing,
    PolicyResolution,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    UnsupportedPolicyArtifactError,
    resolve_policy,
)
from ugence_uvi_policy_contracts.api import (
    PolicyLifecycleState,
    PolicyReference,
    PolicyScope,
)


# --------------------------------------------------------------------------- #
# Happy path and result shape
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("family", ALL_FAMILIES)
def test_a_valid_policy_resolves_by_value_with_its_proof(family):
    authority = make_authority()
    policy = make_policy(family)
    record = authority.issue(policy)

    result = authority.resolve(policy.reference)
    assert result.status is PolicyResolutionStatus.RESOLVED
    assert result.reason is PolicyResolutionReason.RESOLVED
    assert result.policy == policy
    assert result.record == record
    assert result.as_of == T_MID
    assert result.historical is False
    assert result.implies_current_validity is True


def test_resolution_is_deterministic():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    assert (
        len({(r.status, r.reason) for r in (authority.resolve(policy.reference) for _ in range(10))})
        == 1
    )


def test_a_failed_resolution_never_carries_a_policy_or_record():
    authority = make_authority()
    policy = make_policy()
    result = authority.resolve(policy.reference)
    assert result.status is PolicyResolutionStatus.UNRESOLVED
    assert result.reason is PolicyResolutionReason.NOT_FOUND
    assert result.policy is None and result.record is None
    assert result.resolved is False
    assert result.implies_current_validity is False


def test_a_resolution_cannot_be_constructed_with_a_mismatched_status():
    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    coordinate = coordinate_of(policy)

    with pytest.raises(PolicyAuthorityRequestError):
        PolicyResolution(
            status=PolicyResolutionStatus.UNRESOLVED,
            reason=PolicyResolutionReason.EXPIRED,
            requested_coordinate=coordinate,
            as_of=T_MID,
            policy=policy,
            record=record,
        )
    with pytest.raises(PolicyAuthorityRequestError):
        PolicyResolution(
            status=PolicyResolutionStatus.RESOLVED,
            reason=PolicyResolutionReason.RESOLVED,
            requested_coordinate=coordinate,
            as_of=T_MID,
        )
    with pytest.raises(PolicyAuthorityRequestError, match="historical"):
        PolicyResolution(
            status=PolicyResolutionStatus.UNRESOLVED,
            reason=PolicyResolutionReason.REVOKED,
            requested_coordinate=coordinate,
            as_of=T_MID,
            historical=True,
        )


def test_a_constructed_resolution_carries_no_authority_provenance():
    """Constructing a resolved envelope by hand proves nothing about issuance."""

    authority = make_authority()
    policy = make_policy()
    forged_record = IssuedPolicyRecord(
        record_id="forged",
        coordinate=coordinate_of(policy),
        adapter_id="anything",
        policy_type="DomainPolicy",
        policy=policy,
        policy_body_digest=policy.metadata.content_digest,
        issuing_authority_id="attacker",
        key_id="attacker-key",
        signature_alg="ed25519",
        signature=b"\x00" * 64,
        approving_authority_id="attacker-approver",
        approval_ref="APPROVAL-FORGED",
        approval_digest="a" * 64,
        issued_at=T_MID,
    )
    envelope = PolicyResolution(
        status=PolicyResolutionStatus.RESOLVED,
        reason=PolicyResolutionReason.RESOLVED,
        requested_coordinate=coordinate_of(policy),
        as_of=T_MID,
        policy=policy,
        record=forged_record,
    )
    # It constructs — a dataclass is a dataclass. But the authority never
    # produced it, and running the real resolver over the same registry denies.
    assert envelope.resolved
    authority.registry.append_issuance(forged_record)
    assert authority.resolve(policy.reference).reason is PolicyResolutionReason.KEY_UNKNOWN


# --------------------------------------------------------------------------- #
# Exact reference resolution
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "component,value",
    [("policy_id", "other-policy"), ("version", "2.0.0"), ("content_digest", "a" * 64)],
)
def test_any_reference_component_mismatch_is_not_found(component, value):
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    probe = replace(policy.reference, **{component: value})
    assert authority.resolve(probe).reason is PolicyResolutionReason.NOT_FOUND


def test_a_family_mismatch_is_not_found():
    from ugence_uvi_policy_contracts.api import PolicyFamily

    authority = make_authority()
    policy = make_policy(PolicyFamily.DOMAIN)
    authority.issue(policy)
    probe = replace(policy.reference, policy_family=PolicyFamily.READINESS)
    assert authority.resolve(probe).reason is PolicyResolutionReason.NOT_FOUND


def test_a_reference_type_no_adapter_maps_is_refused():
    authority = make_authority()
    with pytest.raises(UnsupportedPolicyArtifactError):
        authority.resolve("pol-1@1.0.0")


def test_input_ordering_cannot_affect_resolution():
    policies = [make_policy(policy_id="p", version=v) for v in ("1.0.0", "2.0.0", "3.0.0")]
    outcomes = []
    for order in (policies, list(reversed(policies)), [policies[1], policies[2], policies[0]]):
        authority = make_authority()
        for p in order:
            authority.issue(p, record_id=f"rec-{p.metadata.version}")
        outcomes.append(
            tuple((authority.resolve(p.reference).status, authority.resolve(p.reference).reason) for p in policies)
        )
    assert len(set(outcomes)) == 1


# --------------------------------------------------------------------------- #
# Digest / signature / key
# --------------------------------------------------------------------------- #
def test_a_hand_assembled_record_fails_closed_at_resolution():
    """Registry retrieval is not trusted resolution."""

    authority = make_authority()
    policy = make_policy()
    forged = IssuedPolicyRecord(
        record_id="forged",
        coordinate=coordinate_of(policy),
        adapter_id="ugence.uvi.policy-family/v1",
        policy_type="DomainPolicy",
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
    assert authority.registry.get_issued(coordinate_of(policy)) is forged
    assert authority.resolve(policy.reference).reason is PolicyResolutionReason.SIGNATURE_INVALID


def test_body_mutation_after_issuance_is_detected():
    """The metadata (and so the coordinate) is untouched, so the digest catches it."""

    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    mutated = replace(record.policy, governed_outcome_unit="inflated")
    object.__setattr__(record, "policy", mutated)

    # The coordinate still matches — only the governed body changed.
    assert coordinate_of(mutated) == coordinate_of(policy)
    assert authority.resolve(policy.reference).reason is (
        PolicyResolutionReason.CONTENT_DIGEST_MISMATCH
    )


def test_a_record_pairing_a_coordinate_with_a_different_artifact_is_detected():
    authority = make_authority()
    a = make_policy(policy_id="a")
    b = make_policy(policy_id="b")
    record = authority.issue(a, record_id="rec-a")
    object.__setattr__(record, "policy", b)
    assert authority.resolve(a.reference).reason is (
        PolicyResolutionReason.ARTIFACT_REFERENCE_MISMATCH
    )


def test_a_record_whose_policy_type_diverges_from_its_descriptor_is_detected():
    """A divergent ``policy_type`` is caught even though every other check passes.

    ``policy_type`` is absent from the issuance signing payload, so the signature
    still verifies over a record that names a different type. The coordinate
    re-derives and both digests match, which is what makes this its own reason
    rather than an ``ARTIFACT_REFERENCE_MISMATCH``.
    """

    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    genuine_payload = record.signing_payload()

    object.__setattr__(record, "policy_type", "not-the-adapters-type")

    # The signature is unaffected: policy_type is not among the signed fields.
    assert record.signing_payload() == genuine_payload

    resolution = authority.resolve(policy.reference)
    assert resolution.status is PolicyResolutionStatus.UNRESOLVED
    assert resolution.reason is PolicyResolutionReason.ARTIFACT_TYPE_MISMATCH
    assert resolution.policy is None


def test_the_policy_type_gate_does_not_fire_for_a_genuine_record():
    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    assert record.policy_type == authority.adapters.describe(policy).policy_type
    assert authority.resolve(policy.reference).status is PolicyResolutionStatus.RESOLVED


def test_a_body_digest_disagreeing_with_the_signed_one_is_detected():
    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    object.__setattr__(record, "policy_body_digest", "c" * 64)
    assert authority.resolve(policy.reference).reason is (
        PolicyResolutionReason.BODY_DIGEST_MISMATCH
    )


def test_a_stored_artifact_no_adapter_claims_fails_closed():
    from dataclasses import dataclass

    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)

    @dataclass(frozen=True)
    class Alien:
        x: int = 1

    object.__setattr__(record, "policy", Alien())
    assert authority.resolve(policy.reference).reason is (
        PolicyResolutionReason.NO_ADAPTER_REGISTERED
    )


def test_an_unknown_or_revoked_key_yields_the_right_reason():
    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)

    assert resolve_policy(
        reference=policy.reference,
        expected_reference_tenant_id="",
        as_of=T_MID,
        registry=authority.registry,
        signature_verifier=PolicyKeyRing(),
        adapters=authority.adapters,
    ).reason is PolicyResolutionReason.KEY_UNKNOWN

    ring = authority.key_ring.with_key(authority.key_ring.resolve(record.key_id).revoke())
    assert resolve_policy(
        reference=policy.reference,
        expected_reference_tenant_id="",
        as_of=T_MID,
        registry=authority.registry,
        signature_verifier=ring,
        adapters=authority.adapters,
    ).reason is PolicyResolutionReason.KEY_REVOKED


# --------------------------------------------------------------------------- #
# Approval re-verification
# --------------------------------------------------------------------------- #
def test_approval_withdrawn_after_issuance_invalidates_resolution():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    assert authority.resolve(policy.reference).resolved

    authority.approval.status = ApprovalVerificationStatus.REVOKED
    assert authority.resolve(
        policy.reference, approval_verifier=authority.approval
    ).reason is PolicyResolutionReason.APPROVAL_PROOF_INVALID


def test_refreshed_approval_still_binding_resolves():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    assert authority.resolve(policy.reference, approval_verifier=authority.approval).resolved


# --------------------------------------------------------------------------- #
# Supersession fails closed at resolution too
# --------------------------------------------------------------------------- #
def test_a_legacy_record_with_unstructured_supersession_fails_closed():
    """Such an artifact cannot be issued; if one is injected, resolution denies."""

    authority = make_authority()
    clean = make_policy()
    record = authority.issue(clean)

    legacy = make_policy(supersedes_ref="p@1.0.0")
    object.__setattr__(record, "policy", legacy)
    object.__setattr__(record, "coordinate", coordinate_of(legacy))
    object.__setattr__(record, "policy_body_digest", legacy.metadata.content_digest)
    authority.registry._issued = {coordinate_of(legacy): record}

    class AlwaysValid:
        def verify(self, **kwargs):
            from ugence_policy_authority.api import KeyVerification, KeyVerificationStatus

            return KeyVerification(status=KeyVerificationStatus.VALID, key_id="k")

    result = resolve_policy(
        reference=legacy.reference,
        expected_reference_tenant_id="",
        as_of=T_MID,
        registry=authority.registry,
        signature_verifier=AlwaysValid(),
        adapters=authority.adapters,
    )
    assert result.reason is PolicyResolutionReason.SUPERSESSION_REFERENCE_UNSUPPORTED
    assert result.policy is None


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "state",
    [
        PolicyLifecycleState.DRAFT,
        PolicyLifecycleState.EXPIRED,
        PolicyLifecycleState.REVOKED,
        PolicyLifecycleState.SUPERSEDED,
    ],
)
def test_every_non_active_lifecycle_state_fails_closed(state):
    authority = make_authority()
    record = authority.issue(make_policy())
    inactive = make_policy(lifecycle_state=state)
    object.__setattr__(record, "policy", inactive)
    object.__setattr__(record, "coordinate", coordinate_of(inactive))
    object.__setattr__(record, "policy_body_digest", inactive.metadata.content_digest)
    authority.registry._issued = {coordinate_of(inactive): record}

    class AlwaysValid:
        def verify(self, **kwargs):
            from ugence_policy_authority.api import KeyVerification, KeyVerificationStatus

            return KeyVerification(status=KeyVerificationStatus.VALID, key_id="k")

    assert resolve_policy(
        reference=inactive.reference,
        expected_reference_tenant_id="",
        as_of=T_MID,
        registry=authority.registry,
        signature_verifier=AlwaysValid(),
        adapters=authority.adapters,
    ).reason is PolicyResolutionReason.LIFECYCLE_NOT_ACTIVE


def test_a_lifecycle_label_cannot_override_time():
    authority = make_authority()
    policy = make_policy(lifecycle_state=PolicyLifecycleState.APPROVED_ACTIVE)
    authority.issue(policy)
    assert authority.resolve(policy.reference, as_of=T_AFTER).reason is (
        PolicyResolutionReason.EXPIRED
    )
    assert authority.resolve(policy.reference, as_of=T_BEFORE).reason is (
        PolicyResolutionReason.NOT_YET_EFFECTIVE
    )


# --------------------------------------------------------------------------- #
# Effective period boundaries
# --------------------------------------------------------------------------- #
def test_effective_from_is_inclusive_and_effective_to_is_exclusive():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    assert authority.resolve(policy.reference, as_of=T_FROM).resolved
    assert authority.resolve(policy.reference, as_of=T_FROM - ONE_SECOND).reason is (
        PolicyResolutionReason.NOT_YET_EFFECTIVE
    )
    assert authority.resolve(policy.reference, as_of=T_TO - ONE_SECOND).resolved
    assert authority.resolve(policy.reference, as_of=T_TO).reason is (
        PolicyResolutionReason.EXPIRED
    )


def test_missing_bounds_are_open_ended():
    authority = make_authority()
    upper = make_policy(effective_to=None)
    authority.issue(upper, record_id="r1")
    for moment in (T_MID, T_AFTER, T_AFTER + timedelta(days=3650)):
        assert authority.resolve(upper.reference, as_of=moment).resolved

    lower = make_policy(policy_id="pol-2", effective_from=None)
    authority.issue(lower, record_id="r2")
    assert authority.resolve(lower.reference, as_of=T_BEFORE).resolved


# --------------------------------------------------------------------------- #
# Tenant / scope disclosure
# --------------------------------------------------------------------------- #
def test_cross_tenant_resolution_fails_closed_without_leakage():
    authority = make_authority()
    policy = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    authority.issue(policy, expected_reference_tenant_id="tenant-a")

    result = authority.resolve(policy.reference, tenant="tenant-b")
    assert result.reason is PolicyResolutionReason.TENANT_SCOPE_MISMATCH
    assert result.policy is None and result.record is None
    assert "tenant-a" not in result.detail
    assert authority.resolve(policy.reference, tenant="tenant-a").resolved


def test_a_global_policy_does_not_resolve_for_a_tenant_request():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    assert authority.resolve(policy.reference, tenant="tenant-a").reason is (
        PolicyResolutionReason.TENANT_SCOPE_MISMATCH
    )


def test_global_scope_uses_the_canonical_empty_tenant_component():
    from ugence_policy_authority.api import GLOBAL_TENANT

    assert GLOBAL_TENANT == ""
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    assert coordinate_of(policy).tenant_id == GLOBAL_TENANT
    assert authority.resolve(policy.reference, tenant=GLOBAL_TENANT).resolved


def test_the_tenant_parameter_checks_declared_identity_not_caller_entitlement():
    """Documented semantics: it compares the reference's tenant, nothing more."""

    import inspect

    from ugence_policy_authority.core import resolution

    assert "expected_reference_tenant_id" in inspect.signature(resolve_policy).parameters
    doc = resolution.__doc__
    assert "declared tenant" in doc
    assert "not the caller's entitlement" in doc


# --------------------------------------------------------------------------- #
# Argument validation
# --------------------------------------------------------------------------- #
def test_a_naive_as_of_is_refused():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    with pytest.raises(PolicyAuthorityRequestError, match="naive datetime"):
        authority.resolve(policy.reference, as_of=datetime(2026, 6, 1))
