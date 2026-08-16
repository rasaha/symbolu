"""Registry semantics: append-only, exact, idempotent, tenant-isolated (§9)."""

from __future__ import annotations

import dataclasses
from dataclasses import replace

import pytest

from _authority_fixtures import (
    T_MID,
    make_authority,
    make_policy,
    registry_snapshot,
)
from ugence_uvi_policy_authority.api import (
    InMemoryPolicyRegistry,
    IssuedPolicyRecord,
    PolicyRegistry,
    PolicyRegistryConflictError,
    PolicyRevocationReasonCode,
    revoke_policy,
)
from ugence_uvi_policy_contracts.api import PolicyFamily, PolicyScope


def test_the_in_memory_registry_satisfies_the_protocol():
    assert isinstance(InMemoryPolicyRegistry(), PolicyRegistry)


def test_exact_reference_resolution_only():
    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    assert authority.registry.get_issued(policy.reference) == record
    for component, value in (
        ("policy_id", "x"),
        ("version", "x"),
        ("content_digest", "a" * 64),
    ):
        assert authority.registry.get_issued(replace(policy.reference, **{component: value})) is None


def test_a_non_reference_lookup_returns_none_rather_than_guessing():
    registry = InMemoryPolicyRegistry()
    for probe in (None, "pol-1", 7, ("pol-1", "1.0.0")):
        assert registry.get_issued(probe) is None
        assert registry.revocations_for(probe) == ()


def test_issued_versions_cannot_be_overwritten():
    authority = make_authority()
    policy = make_policy()
    original = authority.issue(policy, record_id="rec-1")

    tampered = replace(original, record_id="rec-2")
    with pytest.raises(PolicyRegistryConflictError, match="cannot be overwritten"):
        authority.registry.append_issuance(tampered)
    assert authority.registry.get_issued(policy.reference) == original


def test_byte_identical_resubmission_is_idempotent():
    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    for _ in range(5):
        assert authority.registry.append_issuance(record) == record
    assert len(authority.registry._issued) == 1


def test_a_reconstructed_but_canonically_identical_record_is_idempotent():
    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    twin = IssuedPolicyRecord(**{f.name: getattr(record, f.name) for f in dataclasses.fields(record)})
    assert twin is not record
    assert authority.registry.append_issuance(twin) == record
    assert len(authority.registry._issued) == 1


def test_conflicting_identity_version_reuse_is_rejected():
    authority = make_authority()
    a = make_policy(PolicyFamily.DOMAIN, policy_id="p", version="1.0.0")
    b = make_policy(
        PolicyFamily.DOMAIN,
        policy_id="p",
        version="1.0.0",
        overrides={"governed_outcome_unit": "other"},
    )
    authority.issue(a, record_id="ra")
    with pytest.raises(PolicyRegistryConflictError):
        authority.issue(b, record_id="rb")
    assert len(authority.registry._issued) == 1


def test_duplicate_registration_cannot_replace_a_valid_record():
    authority = make_authority()
    policy = make_policy()
    good = authority.issue(policy)
    evil = replace(good, signature=b"\x02" * 64, approval_ref="APPROVAL-EVIL")
    with pytest.raises(PolicyRegistryConflictError):
        authority.registry.append_issuance(evil)
    assert authority.registry.get_issued(policy.reference) == good


def test_append_only_there_is_no_delete_or_update():
    registry = InMemoryPolicyRegistry()
    for forbidden in ("delete", "remove", "update", "replace", "clear", "pop", "overwrite"):
        assert not hasattr(registry, forbidden)
        assert not hasattr(PolicyRegistry, forbidden)


def test_cross_tenant_lookup_returns_typed_not_found_without_leakage():
    authority = make_authority()
    policy = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    authority.issue(policy, expected_tenant_id="tenant-a")

    probe = replace(policy.reference, tenant_id="tenant-b")
    assert authority.registry.get_issued(probe) is None
    assert (
        authority.registry.issued_records_for_identity(
            policy_id=policy.metadata.policy_id,
            policy_family=policy.metadata.policy_family,
            scope=PolicyScope.TENANT,
            tenant_id="tenant-b",
        )
        == ()
    )


def test_records_are_deeply_immutable_by_value():
    authority = make_authority()
    policy = make_policy(PolicyFamily.READINESS)
    record = authority.issue(policy)
    fetched = authority.registry.get_issued(policy.reference)

    with pytest.raises(dataclasses.FrozenInstanceError):
        fetched.record_id = "hijacked"
    with pytest.raises(dataclasses.FrozenInstanceError):
        fetched.policy_reference.content_digest = "0" * 64
    with pytest.raises(dataclasses.FrozenInstanceError):
        fetched.policy.metadata.lifecycle_state = None
    assert isinstance(fetched.policy.gates, tuple)
    with pytest.raises(TypeError):
        fetched.policy.gates[0] = None
    assert isinstance(fetched.signature, bytes)


def test_a_caller_owned_collection_cannot_reach_a_stored_record():
    from ugence_uvi_policy_contracts.api import (
        GateCategory,
        PolicyGate,
        ReadinessTarget,
        RequirementClass,
    )

    gates = [
        PolicyGate(
            gate_id="g1",
            category=GateCategory.SAFETY,
            requirement_class=RequirementClass.MANDATORY,
            applicability=(ReadinessTarget.PILOT,),
        )
    ]
    authority = make_authority()
    policy = make_policy(PolicyFamily.READINESS, overrides={"gates": gates})
    authority.issue(policy)
    before = registry_snapshot(authority.registry)

    gates.clear()
    gates.append("garbage")
    assert registry_snapshot(authority.registry) == before
    assert len(authority.registry.get_issued(policy.reference).policy.gates) == 1


def test_mutating_the_returned_key_ring_mapping_does_not_change_the_ring():
    authority = make_authority()
    original = dict(authority.key_ring.keys)
    replacement = authority.key_ring.with_key(
        authority.key_ring.resolve(authority.signer.key_id).revoke()
    )
    assert dict(authority.key_ring.keys) == original
    assert replacement is not authority.key_ring


def test_identity_listing_is_order_independent():
    policies = [
        make_policy(PolicyFamily.DOMAIN, policy_id="p", version=v)
        for v in ("3.0.0", "1.0.0", "2.0.0")
    ]
    listings = []
    for order in (policies, list(reversed(policies))):
        authority = make_authority()
        for p in order:
            authority.issue(p, record_id=f"rec-{p.metadata.version}")
        listings.append(
            tuple(
                r.policy_reference.version
                for r in authority.registry.issued_records_for_identity(
                    policy_id="p",
                    policy_family=PolicyFamily.DOMAIN,
                    scope=PolicyScope.GLOBAL,
                    tenant_id="",
                )
            )
        )
    assert listings[0] == listings[1] == ("1.0.0", "2.0.0", "3.0.0")


def test_revocations_are_append_only_and_conflict_aware():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)

    first = revoke_policy(
        reference=policy.reference,
        revocation_id="rv-1",
        reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
        registry=authority.registry,
        revoked_at=T_MID,
    )
    # Identical repeat is idempotent.
    again = revoke_policy(
        reference=policy.reference,
        revocation_id="rv-1",
        reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
        registry=authority.registry,
        revoked_at=T_MID,
    )
    assert first == again
    assert len(authority.registry._revocations) == 1

    # A conflicting revocation is rejected.
    with pytest.raises(PolicyRegistryConflictError, match="[Cc]onflicting"):
        revoke_policy(
            reference=policy.reference,
            revocation_id="rv-2",
            reason_code=PolicyRevocationReasonCode.KEY_COMPROMISE,
            registry=authority.registry,
            revoked_at=T_MID,
        )
    assert authority.registry.revocations_for(policy.reference) == (first,)


def test_append_requires_the_right_record_types():
    registry = InMemoryPolicyRegistry()
    with pytest.raises(PolicyRegistryConflictError):
        registry.append_issuance({"looks": "like a record"})
    with pytest.raises(PolicyRegistryConflictError):
        registry.append_revocation({"looks": "like a revocation"})
