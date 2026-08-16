"""Issuance ordering, side effects, and the injected clock (GV-2C-b §10)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from _authority_fixtures import (
    ALL_FAMILIES,
    APPROVING_AUTHORITY,
    ISSUING_AUTHORITY,
    T_AFTER,
    T_FROM,
    T_MID,
    T_TO,
    RecordingSigner,
    approval_evidence,
    make_authority,
    make_policy,
    make_signer,
    registry_snapshot,
)
from ugence_uvi_policy_authority.api import (
    AUTHORITY_PROTOCOL,
    AUTHORITY_PROTOCOL_VERSION,
    ApprovalVerificationStatus,
    DenyAllApprovalVerifier,
    InMemoryPolicyRegistry,
    IssuedPolicyRecord,
    PolicyApprovalError,
    PolicyAuthorityRequestError,
    PolicyDigestMismatchError,
    PolicyIssuanceError,
    PolicyRegistryConflictError,
    UnsupportedPolicyFamilyError,
    issue_policy,
)
from ugence_uvi_policy_contracts.api import (
    PolicyFamily,
    PolicyLifecycleState,
    PolicyScope,
)


# --------------------------------------------------------------------------- #
# Happy path, every supported family
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("family", ALL_FAMILIES)
def test_every_supported_family_issues(family):
    authority = make_authority()
    policy = make_policy(family)
    record = authority.issue(policy)

    assert isinstance(record, IssuedPolicyRecord)
    assert record.policy_family is family
    assert record.policy_reference == policy.reference
    assert record.policy_body_digest == policy.metadata.content_digest
    assert record.issuing_authority_id == ISSUING_AUTHORITY
    assert record.approving_authority_id == APPROVING_AUTHORITY
    assert record.issued_at == T_MID
    assert record.authority_protocol == AUTHORITY_PROTOCOL
    assert record.authority_protocol_version == AUTHORITY_PROTOCOL_VERSION
    assert authority.registry.get_issued(policy.reference) == record


def test_issuance_is_byte_for_byte_deterministic():
    from ugence_uvi_policy_authority.canonical import canonical_bytes

    policy = make_policy(PolicyFamily.DOMAIN)
    a = make_authority().issue(policy)
    b = make_authority().issue(policy)
    assert canonical_bytes(a) == canonical_bytes(b)
    assert a.signature == b.signature


# --------------------------------------------------------------------------- #
# Ordering: nothing happens before the stage that authorizes it
# --------------------------------------------------------------------------- #
def test_signer_is_not_called_when_approval_fails():
    authority = make_authority()
    signer = RecordingSigner(inner=authority.signer)
    authority.approval.status = ApprovalVerificationStatus.REJECTED

    with pytest.raises(PolicyApprovalError):
        issue_policy(
            policy=make_policy(),
            record_id="rec-1",
            approval=approval_evidence(),
            approval_verifier=authority.approval,
            signer=signer,
            registry=authority.registry,
            issued_at=T_MID,
        )
    assert signer.calls == []


def test_approval_verifier_is_not_called_after_an_earlier_structural_failure():
    """Family, identity and digest checks all precede approval verification."""

    authority = make_authority()

    # (a) unsupported artifact type
    with pytest.raises(UnsupportedPolicyFamilyError):
        authority.issue(object())
    assert authority.approval.calls == []

    # (b) digest that does not bind the body
    policy = make_policy()
    forged = replace(policy, metadata=replace(policy.metadata, content_digest="a" * 64))
    with pytest.raises(PolicyDigestMismatchError):
        authority.issue(forged)
    assert authority.approval.calls == []

    # (c) naive (non-tz-aware) issuance instant
    with pytest.raises(PolicyAuthorityRequestError):
        authority.issue(policy, issued_at=datetime(2026, 6, 1))
    assert authority.approval.calls == []

    # (d) tenant mismatch
    with pytest.raises(PolicyAuthorityRequestError):
        authority.issue(policy, expected_tenant_id="someone-else")
    assert authority.approval.calls == []

    # Only a fully structural-clean request reaches the verifier.
    authority.issue(policy)
    assert len(authority.approval.calls) == 1


def test_approval_precedes_the_lifecycle_and_effective_period_stage():
    """A DRAFT artifact with failing approval reports the approval failure first."""

    authority = make_authority()
    authority.approval.status = ApprovalVerificationStatus.REJECTED
    draft = make_policy(lifecycle_state=PolicyLifecycleState.DRAFT)
    with pytest.raises(PolicyApprovalError):
        authority.issue(draft)


@pytest.mark.parametrize(
    "stage_setup",
    [
        "unsupported_type",
        "digest_mismatch",
        "approval_rejected",
        "approval_self",
        "lifecycle_draft",
        "already_expired",
        "naive_clock",
    ],
)
def test_registry_is_unchanged_after_a_failure_at_every_stage(stage_setup):
    authority = make_authority()
    # Seed one valid record so the snapshot is non-trivial.
    seeded = make_policy(PolicyFamily.GEOGRAPHY, policy_id="seeded")
    authority.issue(seeded, record_id="seed")
    before = registry_snapshot(authority.registry)

    policy = make_policy(PolicyFamily.DOMAIN)
    kwargs = {}
    if stage_setup == "unsupported_type":
        policy = {"not": "a policy"}
    elif stage_setup == "digest_mismatch":
        policy = replace(policy, metadata=replace(policy.metadata, content_digest="b" * 64))
    elif stage_setup == "approval_rejected":
        authority.approval.status = ApprovalVerificationStatus.EXPIRED
    elif stage_setup == "approval_self":
        authority.approval.approving_authority_id = ISSUING_AUTHORITY
    elif stage_setup == "lifecycle_draft":
        policy = make_policy(PolicyFamily.DOMAIN, lifecycle_state=PolicyLifecycleState.REVOKED)
    elif stage_setup == "already_expired":
        kwargs["issued_at"] = T_AFTER
    elif stage_setup == "naive_clock":
        kwargs["issued_at"] = datetime(2026, 6, 1)

    with pytest.raises(Exception):
        authority.issue(policy, record_id="should-not-persist", **kwargs)

    assert registry_snapshot(authority.registry) == before


# --------------------------------------------------------------------------- #
# Approval is required, and cannot be faked
# --------------------------------------------------------------------------- #
def test_the_shipped_default_verifier_denies():
    authority = make_authority()
    with pytest.raises(PolicyApprovalError):
        issue_policy(
            policy=make_policy(),
            record_id="rec-1",
            approval=approval_evidence(),
            approval_verifier=DenyAllApprovalVerifier(),
            signer=authority.signer,
            registry=authority.registry,
            issued_at=T_MID,
        )
    assert registry_snapshot(authority.registry) == ((), ())


@pytest.mark.parametrize(
    "status",
    [s for s in ApprovalVerificationStatus if s is not ApprovalVerificationStatus.APPROVED],
)
def test_every_non_approved_status_fails_closed(status):
    authority = make_authority()
    authority.approval.status = status
    with pytest.raises(PolicyApprovalError):
        authority.issue(make_policy())


def test_missing_approval_evidence_is_a_request_error():
    authority = make_authority()
    for bogus in (None, True, "ugence.governance.policy-approval-board", 1):
        with pytest.raises(PolicyAuthorityRequestError):
            issue_policy(
                policy=make_policy(),
                record_id="rec-1",
                approval=bogus,
                approval_verifier=authority.approval,
                signer=authority.signer,
                registry=authority.registry,
                issued_at=T_MID,
            )


def test_the_authority_cannot_approve_its_own_policy():
    authority = make_authority()
    authority.approval.approving_authority_id = ISSUING_AUTHORITY
    with pytest.raises(PolicyApprovalError, match="cannot approve its own policy"):
        authority.issue(make_policy(), evidence=approval_evidence(
            approving_authority_id=ISSUING_AUTHORITY
        ))


def test_a_verification_binding_a_different_policy_is_rejected():
    authority = make_authority()
    other = make_policy(PolicyFamily.GEOGRAPHY, policy_id="other")
    authority.approval.override_reference = other.reference
    with pytest.raises(PolicyApprovalError, match="different policy reference"):
        authority.issue(make_policy(PolicyFamily.DOMAIN))


def test_a_verification_binding_a_different_body_digest_is_rejected():
    authority = make_authority()
    authority.approval.override_body_digest = "c" * 64
    with pytest.raises(PolicyApprovalError, match="different policy body digest"):
        authority.issue(make_policy())


def test_an_expired_approved_period_fails_closed():
    authority = make_authority()
    authority.approval.approved_from = T_FROM
    authority.approval.approved_to = T_FROM + timedelta(days=1)
    with pytest.raises(PolicyApprovalError, match="expired"):
        authority.issue(make_policy(), issued_at=T_MID)


def test_an_approval_not_yet_effective_fails_closed():
    authority = make_authority()
    authority.approval.approved_from = T_TO
    with pytest.raises(PolicyApprovalError, match="not yet effective"):
        authority.issue(make_policy(), issued_at=T_MID)


def test_a_verifier_returning_something_else_is_rejected():
    class Nonsense:
        def verify_approval(self, **kwargs):
            return True

    authority = make_authority()
    with pytest.raises(PolicyApprovalError, match="must return an ApprovalVerification"):
        issue_policy(
            policy=make_policy(),
            record_id="rec-1",
            approval=approval_evidence(),
            approval_verifier=Nonsense(),
            signer=authority.signer,
            registry=authority.registry,
            issued_at=T_MID,
        )


# --------------------------------------------------------------------------- #
# Family / identity validation
# --------------------------------------------------------------------------- #
def test_an_unsupported_dataclass_cannot_be_issued():
    from dataclasses import dataclass

    from ugence_uvi_policy_contracts.api import PolicyArtifactMetadata

    @dataclass(frozen=True)
    class RogueMultiplierPolicy:
        metadata: PolicyArtifactMetadata
        roi_multiplier: int = 10

    policy = make_policy()
    rogue = RogueMultiplierPolicy(metadata=policy.metadata)
    with pytest.raises(UnsupportedPolicyFamilyError):
        make_authority().issue(rogue)


def test_a_subclass_of_a_supported_family_cannot_be_issued():
    from ugence_uvi_policy_contracts.api import DomainPolicy

    class ExtendedDomainPolicy(DomainPolicy):
        pass

    policy = make_policy(PolicyFamily.DOMAIN)
    sneaky = ExtendedDomainPolicy(
        metadata=policy.metadata, governed_outcome_unit=policy.governed_outcome_unit
    )
    with pytest.raises(UnsupportedPolicyFamilyError):
        make_authority().issue(sneaky)


def test_runtime_type_and_declared_family_must_agree():
    """The contracts enforce this; the authority re-checks it independently.

    The contract constructor already rejects a family/type disagreement, so the
    mismatch is forced past it here — precisely the case the authority must not
    rely on someone else having caught.
    """

    from ugence_uvi_policy_authority.families import require_supported_policy

    policy = make_policy(PolicyFamily.DOMAIN)
    readiness_meta = make_policy(PolicyFamily.READINESS).metadata
    object.__setattr__(policy, "metadata", readiness_meta)

    assert type(policy).__name__ == "DomainPolicy"
    with pytest.raises(UnsupportedPolicyFamilyError, match="declares family"):
        require_supported_policy(policy)

    with pytest.raises(UnsupportedPolicyFamilyError):
        make_authority().issue(policy)


# --------------------------------------------------------------------------- #
# Lifecycle and effective period at issuance time
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
def test_only_approved_active_may_be_issued(state):
    with pytest.raises(PolicyIssuanceError, match="only APPROVED_ACTIVE is issuable"):
        make_authority().issue(make_policy(lifecycle_state=state))


def test_a_policy_whose_window_already_elapsed_cannot_be_issued():
    with pytest.raises(PolicyIssuanceError, match="already elapsed"):
        make_authority().issue(make_policy(), issued_at=T_AFTER)


def test_a_future_dated_policy_is_issuable_but_not_yet_resolvable():
    """Issuance-time checks do not replace resolution-time checks."""

    from ugence_uvi_policy_authority.api import PolicyResolutionReason, resolve_policy

    authority = make_authority()
    policy = make_policy(effective_from=T_TO, effective_to=None)
    record = authority.issue(policy, issued_at=T_MID)
    assert record.issued_at == T_MID

    result = resolve_policy(
        reference=policy.reference,
        expected_tenant_id="",
        as_of=T_MID,
        registry=authority.registry,
        signature_verifier=authority.key_ring,
    )
    assert result.reason is PolicyResolutionReason.NOT_YET_EFFECTIVE


# --------------------------------------------------------------------------- #
# The clock is injected
# --------------------------------------------------------------------------- #
def test_issuance_reads_exactly_one_caller_supplied_instant():
    """Every timestamp on the record and in the signature derives from issued_at."""

    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy, issued_at=T_MID)

    assert record.issued_at == T_MID
    # The approval verifier saw the same instant, and nothing else.
    (_, _, _, seen_as_of), = authority.approval.calls
    assert seen_as_of == T_MID


def test_a_naive_datetime_is_refused():
    with pytest.raises(PolicyAuthorityRequestError, match="timezone-aware"):
        make_authority().issue(make_policy(), issued_at=datetime(2026, 6, 1))


def test_two_issuances_at_different_instants_differ_only_by_that_instant():
    policy = make_policy()
    a = make_authority().issue(policy, issued_at=T_MID)
    b = make_authority().issue(policy, issued_at=T_MID + timedelta(seconds=1))
    assert a.signature != b.signature
    assert a.policy_body_digest == b.policy_body_digest


# --------------------------------------------------------------------------- #
# Registry interaction
# --------------------------------------------------------------------------- #
def test_duplicate_identical_issuance_is_idempotent():
    authority = make_authority()
    policy = make_policy()
    first = authority.issue(policy, record_id="rec-1")
    second = authority.issue(policy, record_id="rec-1")
    assert first == second
    assert len(authority.registry._issued) == 1


def test_conflicting_same_version_issuance_is_rejected():
    """Same id/family/version/scope/tenant, different content."""

    authority = make_authority()
    a = make_policy(PolicyFamily.DOMAIN, policy_id="p", version="1.0.0")
    b = make_policy(
        PolicyFamily.DOMAIN,
        policy_id="p",
        version="1.0.0",
        overrides={"governed_outcome_unit": "different_unit"},
    )
    authority.issue(a, record_id="rec-a")
    assert a.reference != b.reference
    with pytest.raises(PolicyRegistryConflictError, match="cannot be reused"):
        authority.issue(b, record_id="rec-b")


def test_a_differing_record_id_for_the_same_reference_is_a_conflict():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy, record_id="rec-1")
    with pytest.raises(PolicyRegistryConflictError, match="cannot be overwritten"):
        authority.issue(policy, record_id="rec-2")


def test_distinct_versions_of_one_policy_coexist():
    authority = make_authority()
    v1 = make_policy(PolicyFamily.DOMAIN, policy_id="p", version="1.0.0")
    v2 = make_policy(PolicyFamily.DOMAIN, policy_id="p", version="2.0.0")
    authority.issue(v1, record_id="r1")
    authority.issue(v2, record_id="r2")
    assert authority.registry.get_issued(v1.reference) is not None
    assert authority.registry.get_issued(v2.reference) is not None


def test_tenant_scoped_issuance_binds_the_tenant():
    authority = make_authority()
    policy = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    record = authority.issue(policy, expected_tenant_id="tenant-a")
    assert record.policy_reference.tenant_id == "tenant-a"
    with pytest.raises(PolicyAuthorityRequestError, match="does not match the expected tenant"):
        authority.issue(policy, record_id="rec-2", expected_tenant_id="tenant-b")


def test_a_malformed_dependency_is_refused_before_anything_else():
    authority = make_authority()
    for bad_kwargs in (
        {"approval_verifier": object()},
        {"signer": object()},
        {"registry": object()},
        {"record_id": ""},
    ):
        kwargs = dict(
            policy=make_policy(),
            record_id="rec-1",
            approval=approval_evidence(),
            approval_verifier=authority.approval,
            signer=authority.signer,
            registry=authority.registry,
            issued_at=T_MID,
        )
        kwargs.update(bad_kwargs)
        with pytest.raises(PolicyAuthorityRequestError):
            issue_policy(**kwargs)
