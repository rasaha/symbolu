"""Issuance ordering, instrumented side effects, and the injected clock (ADR §11)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from _authority_fixtures import (
    ALL_FAMILIES,
    APPROVING_AUTHORITY,
    ISSUING_AUTHORITY,
    T_AFTER,
    T_FROM,
    T_MID,
    T_TO,
    RecordingRegistry,
    RecordingSigner,
    approval_evidence,
    coordinate_of,
    make_authority,
    make_policy,
    registry_snapshot,
)
from ugence_policy_authority.api import (
    AUTHORITY_PROTOCOL,
    AUTHORITY_PROTOCOL_VERSION,
    SUPERSESSION_REFERENCE_UNSUPPORTED,
    AdapterRegistry,
    ApprovalVerificationStatus,
    DenyAllApprovalVerifier,
    IssuedPolicyRecord,
    PolicyApprovalError,
    PolicyAuthorityRequestError,
    PolicyDigestMismatchError,
    PolicyIssuanceError,
    PolicyRegistryConflictError,
    UnsupportedPolicyArtifactError,
    UnsupportedSupersessionError,
    default_uvi_adapters,
    issue_policy,
)
from ugence_uvi_policy_contracts.api import PolicyFamily, PolicyLifecycleState, PolicyScope


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("family", ALL_FAMILIES)
def test_every_supported_family_issues(family):
    authority = make_authority()
    policy = make_policy(family)
    record = authority.issue(policy)

    assert isinstance(record, IssuedPolicyRecord)
    assert record.coordinate == coordinate_of(policy)
    assert record.coordinate.policy_family == family.value
    assert record.policy_body_digest == policy.metadata.content_digest
    assert record.issuing_authority_id == ISSUING_AUTHORITY
    assert record.approving_authority_id == APPROVING_AUTHORITY
    assert record.issued_at == T_MID
    assert record.authority_protocol == AUTHORITY_PROTOCOL
    assert record.authority_protocol_version == AUTHORITY_PROTOCOL_VERSION
    assert authority.registry.get_issued(record.coordinate) == record


def test_issuance_is_byte_for_byte_deterministic_on_retry():
    from ugence_policy_authority.core.canonical import canonical_bytes

    policy = make_policy(PolicyFamily.DOMAIN)
    a = make_authority().issue(policy)
    b = make_authority().issue(policy)
    assert a.signature == b.signature
    assert canonical_bytes(a.signing_payload()) == canonical_bytes(b.signing_payload())


# --------------------------------------------------------------------------- #
# Instrumented ordering: no collaborator runs before its stage
# --------------------------------------------------------------------------- #
def _instrumented(**overrides):
    authority = make_authority()
    signer = RecordingSigner(inner=authority.signer)
    registry = RecordingRegistry(inner=authority.registry)
    kwargs = dict(
        policy=make_policy(),
        record_id="rec-1",
        approval=approval_evidence(),
        approval_verifier=authority.approval,
        signer=signer,
        registry=registry,
        adapters=authority.adapters,
        issued_at=T_MID,
    )
    kwargs.update(overrides)
    return authority, signer, registry, kwargs


@pytest.mark.parametrize(
    "stage,mutate",
    [
        ("structure", lambda k, a: k.update(record_id="")),
        ("structure_approval_type", lambda k, a: k.update(approval=True)),
        ("structure_naive_clock", lambda k, a: k.update(issued_at=datetime(2026, 6, 1))),
        ("family", lambda k, a: k.update(policy=object())),
        ("tenant", lambda k, a: k.update(expected_reference_tenant_id="somebody-else")),
        ("supersession", lambda k, a: k.update(policy=make_policy(supersedes_ref="p@1"))),
        (
            "digest",
            lambda k, a: k.update(
                policy=replace(
                    k["policy"], metadata=replace(k["policy"].metadata, content_digest="a" * 64)
                )
            ),
        ),
    ],
)
def test_no_collaborator_is_invoked_before_its_stage(stage, mutate):
    """Approval verifier, signer and registry are all untouched by an early failure."""

    authority, signer, registry, kwargs = _instrumented()
    mutate(kwargs, authority)

    with pytest.raises(Exception):
        issue_policy(**kwargs)

    assert authority.approval.calls == [], f"{stage}: approval verifier was invoked"
    assert signer.calls == [], f"{stage}: signer was invoked"
    assert registry.appends == [], f"{stage}: registry was mutated"


def test_the_signer_is_not_invoked_when_approval_fails():
    authority, signer, registry, kwargs = _instrumented()
    authority.approval.status = ApprovalVerificationStatus.REJECTED

    with pytest.raises(PolicyApprovalError):
        issue_policy(**kwargs)

    assert len(authority.approval.calls) == 1
    assert signer.calls == []
    assert registry.appends == []


def test_the_registry_is_not_mutated_when_signing_fails():
    class BrokenSigner(RecordingSigner):
        def sign(self, payload):
            self.calls.append(payload)
            raise RuntimeError("HSM unavailable")

    authority, _, registry, kwargs = _instrumented()
    broken = BrokenSigner(inner=authority.signer)
    kwargs["signer"] = broken

    with pytest.raises(RuntimeError):
        issue_policy(**kwargs)

    assert len(broken.calls) == 1
    assert registry.appends == []
    assert len(registry.inner._issued) == 0


def test_a_signer_returning_no_material_does_not_mutate_the_registry():
    from ugence_policy_authority.api import PolicySigningError

    class EmptySigner(RecordingSigner):
        def sign(self, payload):
            self.calls.append(payload)
            return b""

    authority, _, registry, kwargs = _instrumented()
    kwargs["signer"] = EmptySigner(inner=authority.signer)

    with pytest.raises(PolicySigningError):
        issue_policy(**kwargs)
    assert registry.appends == []


def test_the_registry_is_unchanged_after_a_failure_at_every_stage():
    authority = make_authority()
    authority.issue(make_policy(PolicyFamily.GEOGRAPHY, policy_id="seeded"), record_id="seed")
    before = registry_snapshot(authority.registry)

    policy = make_policy(PolicyFamily.DOMAIN)
    failures = [
        dict(policy={"not": "a policy"}),
        dict(policy=make_policy(PolicyFamily.DOMAIN, supersedes_ref="prior")),
        dict(
            policy=replace(policy, metadata=replace(policy.metadata, content_digest="b" * 64))
        ),
        dict(policy=make_policy(PolicyFamily.DOMAIN, lifecycle_state=PolicyLifecycleState.DRAFT)),
        dict(issued_at=T_AFTER),
        dict(issued_at=datetime(2026, 6, 1)),
    ]
    for override in failures:
        kwargs = dict(policy=policy, record_id="should-not-persist")
        kwargs.update(override)
        with pytest.raises(Exception):
            authority.issue(**kwargs)
        assert registry_snapshot(authority.registry) == before, override

    authority.approval.status = ApprovalVerificationStatus.EXPIRED
    with pytest.raises(PolicyApprovalError):
        authority.issue(policy, record_id="should-not-persist")
    assert registry_snapshot(authority.registry) == before


# --------------------------------------------------------------------------- #
# Supersession — v0.1 rejects a non-empty unstructured reference
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "supersedes_ref,should_issue",
    [
        ("", True),
        ("   ", True),
        ("\t\n  \r", True),
        ("p@1.0.0", False),
        ("prior-version", False),
        ("  padded  ", False),
        ("../../etc/passwd", False),
        ("*", False),
        ("latest", False),
        ("{\"policy_id\": \"p\"}", False),
    ],
)
def test_the_supersession_truth_table(supersedes_ref, should_issue):
    """Emptiness is exactly ``supersedes_ref.strip()``."""

    authority = make_authority()
    policy = make_policy(supersedes_ref=supersedes_ref)

    if should_issue:
        record = authority.issue(policy)
        assert record.coordinate.policy_id == "pol-1"
    else:
        with pytest.raises(UnsupportedSupersessionError) as exc:
            authority.issue(policy)
        assert SUPERSESSION_REFERENCE_UNSUPPORTED in str(exc.value)
        assert len(authority.registry._issued) == 0


def test_supersession_rejection_precedes_every_collaborator():
    authority, signer, registry, kwargs = _instrumented(
        policy=make_policy(supersedes_ref="p@1.0.0")
    )
    with pytest.raises(UnsupportedSupersessionError):
        issue_policy(**kwargs)
    assert authority.approval.calls == []
    assert signer.calls == []
    assert registry.appends == []


def test_supersession_rejection_does_not_affect_unrelated_versions():
    """Blast radius: rejecting one artifact leaves the identity usable."""

    authority = make_authority()
    good = make_policy(policy_id="p", version="1.0.0")
    authority.issue(good, record_id="r1")

    with pytest.raises(UnsupportedSupersessionError):
        authority.issue(
            make_policy(policy_id="p", version="2.0.0", supersedes_ref="p@1.0.0"),
            record_id="r2",
        )

    assert authority.resolve(good.reference).resolved
    # And a clean v2 still issues afterwards.
    clean_v2 = make_policy(policy_id="p", version="2.0.0")
    authority.issue(clean_v2, record_id="r2")
    assert authority.resolve(clean_v2.reference).resolved


def test_no_permissive_supersession_posture_survives():
    from ugence_policy_authority import api

    for banned in ("SupersessionRule", "SELF_DECLARED_ONLY", "SUPERSESSION_UNDETERMINED"):
        assert banned not in api.__all__, banned
        assert not hasattr(api, banned), banned


# --------------------------------------------------------------------------- #
# Approval
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
            adapters=authority.adapters,
            issued_at=T_MID,
        )
    assert len(authority.registry._issued) == 0


@pytest.mark.parametrize(
    "status",
    [s for s in ApprovalVerificationStatus if s is not ApprovalVerificationStatus.APPROVED],
)
def test_every_non_approved_status_fails_closed(status):
    authority = make_authority()
    authority.approval.status = status
    with pytest.raises(PolicyApprovalError):
        authority.issue(make_policy())


def test_a_boolean_a_name_or_a_label_is_not_approval_evidence():
    authority = make_authority()
    for bogus in (None, True, APPROVING_AUTHORITY, 1, {"approved": True}):
        with pytest.raises(PolicyAuthorityRequestError):
            issue_policy(
                policy=make_policy(),
                record_id="rec-1",
                approval=bogus,
                approval_verifier=authority.approval,
                signer=authority.signer,
                registry=authority.registry,
                adapters=authority.adapters,
                issued_at=T_MID,
            )


def test_a_duck_typed_approval_evidence_stand_in_is_rejected():
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class FakeEvidence:
        approval_ref: str = "APPROVAL-FAKE"
        approval_digest: str = "0" * 64
        approving_authority_id: str = APPROVING_AUTHORITY

    authority = make_authority()
    with pytest.raises(PolicyAuthorityRequestError, match="ApprovalEvidenceRef"):
        issue_policy(
            policy=make_policy(),
            record_id="rec-1",
            approval=FakeEvidence(),
            approval_verifier=authority.approval,
            signer=authority.signer,
            registry=authority.registry,
            adapters=authority.adapters,
            issued_at=T_MID,
        )


def test_the_authority_cannot_approve_its_own_policy():
    authority = make_authority()
    authority.approval.approving_authority_id = ISSUING_AUTHORITY
    with pytest.raises(PolicyApprovalError, match="cannot approve its own policy"):
        authority.issue(
            make_policy(), evidence=approval_evidence(approving_authority_id=ISSUING_AUTHORITY)
        )


def test_a_verification_binding_a_different_policy_is_rejected():
    authority = make_authority()
    other = make_policy(PolicyFamily.GEOGRAPHY, policy_id="other")
    authority.approval.override_coordinate = coordinate_of(other)
    with pytest.raises(PolicyApprovalError, match="different policy coordinate"):
        authority.issue(make_policy(PolicyFamily.DOMAIN))


def test_a_verification_binding_a_different_body_digest_is_rejected():
    authority = make_authority()
    authority.approval.override_body_digest = "c" * 64
    with pytest.raises(PolicyApprovalError, match="different policy body digest"):
        authority.issue(make_policy())


def test_an_approval_outside_its_validity_period_fails_closed():
    authority = make_authority()
    authority.approval.approved_from = T_FROM
    authority.approval.approved_to = T_FROM + timedelta(days=1)
    with pytest.raises(PolicyApprovalError, match="expired"):
        authority.issue(make_policy(), issued_at=T_MID)

    authority = make_authority()
    authority.approval.approved_from = T_TO
    with pytest.raises(PolicyApprovalError, match="not yet effective"):
        authority.issue(make_policy(), issued_at=T_MID)


def test_a_verifier_returning_a_fabricated_object_is_rejected():
    class Nonsense:
        def verify_approval(self, **kwargs):
            return True

    class DuckTyped:
        """Looks like an ApprovalVerification but is not one."""

        verified = True

        def verify_approval(self, *, coordinate, policy_body_digest, approval, as_of):
            fake = type("V", (), {})()
            fake.verified = True
            fake.status = ApprovalVerificationStatus.APPROVED
            fake.coordinate = coordinate
            fake.policy_body_digest = policy_body_digest
            fake.approving_authority_id = approval.approving_authority_id
            fake.approval_ref = approval.approval_ref
            fake.approval_digest = approval.approval_digest
            fake.verified_at = as_of
            fake.approved_from = None
            fake.approved_to = None
            fake.detail = ""
            return fake

    authority = make_authority()
    for verifier in (Nonsense(), DuckTyped()):
        with pytest.raises(PolicyApprovalError, match="must return an ApprovalVerification"):
            issue_policy(
                policy=make_policy(),
                record_id="rec-1",
                approval=approval_evidence(),
                approval_verifier=verifier,
                signer=authority.signer,
                registry=authority.registry,
                adapters=authority.adapters,
                issued_at=T_MID,
            )


# --------------------------------------------------------------------------- #
# Family recognition
# --------------------------------------------------------------------------- #
def test_an_unsupported_dataclass_cannot_be_issued():
    from dataclasses import dataclass

    from ugence_uvi_policy_contracts.api import PolicyArtifactMetadata

    @dataclass(frozen=True)
    class RogueMultiplierPolicy:
        metadata: PolicyArtifactMetadata
        roi_multiplier: int = 10

    with pytest.raises(UnsupportedPolicyArtifactError):
        make_authority().issue(RogueMultiplierPolicy(metadata=make_policy().metadata))


def test_a_subclass_of_a_supported_family_cannot_be_issued():
    from ugence_uvi_policy_contracts.api import DomainPolicy

    class ExtendedDomainPolicy(DomainPolicy):
        pass

    policy = make_policy(PolicyFamily.DOMAIN)
    with pytest.raises(UnsupportedPolicyArtifactError):
        make_authority().issue(
            ExtendedDomainPolicy(
                metadata=policy.metadata, governed_outcome_unit=policy.governed_outcome_unit
            )
        )


def test_runtime_type_and_declared_family_must_agree():
    from ugence_policy_authority.api import UviPolicyFamilyAdapter

    policy = make_policy(PolicyFamily.DOMAIN)
    object.__setattr__(policy, "metadata", make_policy(PolicyFamily.READINESS).metadata)
    assert type(policy).__name__ == "DomainPolicy"
    with pytest.raises(UnsupportedPolicyArtifactError, match="declares family"):
        UviPolicyFamilyAdapter().describe(policy)


# --------------------------------------------------------------------------- #
# Lifecycle and effective period at the explicit instant
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
def test_only_an_active_lifecycle_may_be_issued(state):
    with pytest.raises(PolicyIssuanceError, match="only an active lifecycle"):
        make_authority().issue(make_policy(lifecycle_state=state))


def test_a_policy_whose_window_already_elapsed_cannot_be_issued():
    with pytest.raises(PolicyIssuanceError, match="already elapsed"):
        make_authority().issue(make_policy(), issued_at=T_AFTER)


def test_a_future_dated_policy_is_issuable_but_not_yet_resolvable():
    from ugence_policy_authority.api import PolicyResolutionReason

    authority = make_authority()
    policy = make_policy(effective_from=T_TO, effective_to=None)
    assert authority.issue(policy, issued_at=T_MID).issued_at == T_MID
    assert authority.resolve(policy.reference, as_of=T_MID).reason is (
        PolicyResolutionReason.NOT_YET_EFFECTIVE
    )


# --------------------------------------------------------------------------- #
# The clock is injected and read once
# --------------------------------------------------------------------------- #
def test_issuance_reads_exactly_one_caller_supplied_instant():
    authority = make_authority()
    record = authority.issue(make_policy(), issued_at=T_MID)
    assert record.issued_at == T_MID
    (_, _, _, seen_as_of), = authority.approval.calls
    assert seen_as_of == T_MID


def test_a_naive_issuance_instant_is_refused():
    with pytest.raises(PolicyAuthorityRequestError, match="naive datetime"):
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
    assert authority.issue(policy, record_id="rec-1") == authority.issue(policy, record_id="rec-1")
    assert len(authority.registry._issued) == 1


def test_conflicting_same_version_issuance_is_rejected():
    authority = make_authority()
    a = make_policy(PolicyFamily.DOMAIN, policy_id="p", version="1.0.0")
    b = make_policy(
        PolicyFamily.DOMAIN,
        policy_id="p",
        version="1.0.0",
        overrides={"governed_outcome_unit": "different_unit"},
    )
    authority.issue(a, record_id="rec-a")
    with pytest.raises(PolicyRegistryConflictError, match="cannot be reused"):
        authority.issue(b, record_id="rec-b")


def test_a_differing_record_id_for_the_same_coordinate_is_a_conflict():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy, record_id="rec-1")
    with pytest.raises(PolicyRegistryConflictError, match="cannot be overwritten"):
        authority.issue(policy, record_id="rec-2")


def test_tenant_scoped_issuance_binds_the_tenant():
    authority = make_authority()
    policy = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    record = authority.issue(policy, expected_reference_tenant_id="tenant-a")
    assert record.coordinate.tenant_id == "tenant-a"
    with pytest.raises(PolicyAuthorityRequestError, match="expected reference tenant"):
        authority.issue(
            policy, record_id="rec-2", expected_reference_tenant_id="tenant-b"
        )


def test_a_malformed_dependency_is_refused_before_anything_else():
    authority = make_authority()
    for bad in (
        {"approval_verifier": object()},
        {"signer": object()},
        {"registry": object()},
        {"adapters": object()},
        {"record_id": ""},
    ):
        kwargs = dict(
            policy=make_policy(),
            record_id="rec-1",
            approval=approval_evidence(),
            approval_verifier=authority.approval,
            signer=authority.signer,
            registry=authority.registry,
            adapters=authority.adapters,
            issued_at=T_MID,
        )
        kwargs.update(bad)
        with pytest.raises(PolicyAuthorityRequestError):
            issue_policy(**kwargs)
    assert len(authority.registry._issued) == 0
