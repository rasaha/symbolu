"""Registry semantics: exact, append-only, idempotent, tenant-isolated, locked (ADR §15)."""

from __future__ import annotations

import dataclasses
import threading
from dataclasses import replace

import pytest

from _authority_fixtures import (
    T_MID,
    coordinate_of,
    make_authority,
    make_policy,
    registry_snapshot,
)
from ugence_policy_authority.api import (
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


# --------------------------------------------------------------------------- #
# Exact lookup only
# --------------------------------------------------------------------------- #
def test_exact_coordinate_resolution_only():
    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    coordinate = coordinate_of(policy)
    assert authority.registry.get_issued(coordinate) == record
    for component, value in (
        ("policy_id", "x"),
        ("version", "x"),
        ("content_digest", "a" * 64),
        ("policy_family", "READINESS"),
        ("scope", "TENANT"),
    ):
        probe = replace(coordinate, **{component: value})
        assert authority.registry.get_issued(probe) is None, component


def test_a_non_coordinate_lookup_returns_none_rather_than_guessing():
    registry = InMemoryPolicyRegistry()
    for probe in (None, "pol-1", 7, ("pol-1", "1.0.0")):
        assert registry.get_issued(probe) is None
        assert registry.revocations_for(probe) == ()


def test_there_is_no_floating_lookup_of_any_kind():
    registry = InMemoryPolicyRegistry()
    for forbidden in (
        "latest",
        "current",
        "newest",
        "find_by_id",
        "resolve_latest",
        "head",
        "search",
        "query",
    ):
        assert not hasattr(registry, forbidden), forbidden
        assert not hasattr(PolicyRegistry, forbidden), forbidden


def test_append_only_there_is_no_delete_or_update():
    registry = InMemoryPolicyRegistry()
    for forbidden in ("delete", "remove", "update", "replace", "clear", "pop", "overwrite"):
        assert not hasattr(registry, forbidden)
        assert not hasattr(PolicyRegistry, forbidden)


# --------------------------------------------------------------------------- #
# Idempotence and conflict
# --------------------------------------------------------------------------- #
def test_issued_versions_cannot_be_overwritten():
    authority = make_authority()
    policy = make_policy()
    original = authority.issue(policy, record_id="rec-1")
    with pytest.raises(PolicyRegistryConflictError, match="cannot be overwritten"):
        authority.registry.append_issuance(replace(original, record_id="rec-2"))
    assert authority.registry.get_issued(coordinate_of(policy)) == original


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
    twin = IssuedPolicyRecord(
        **{f.name: getattr(record, f.name) for f in dataclasses.fields(record)}
    )
    assert twin is not record
    assert authority.registry.append_issuance(twin) == record
    assert len(authority.registry._issued) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("record_id", "different"),
        ("signature", b"\x02" * 64),
        ("approval_ref", "APPROVAL-EVIL"),
        ("approval_digest", "c" * 64),
        ("issuing_authority_id", "attacker"),
        ("key_id", "other-key"),
    ],
)
def test_any_non_identical_resubmission_is_a_conflict(field, value):
    authority = make_authority()
    policy = make_policy()
    good = authority.issue(policy)
    with pytest.raises(PolicyRegistryConflictError):
        authority.registry.append_issuance(replace(good, **{field: value}))
    assert authority.registry.get_issued(coordinate_of(policy)) == good


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


def test_distinct_versions_of_one_identity_coexist():
    authority = make_authority()
    v1 = make_policy(policy_id="p", version="1.0.0")
    v2 = make_policy(policy_id="p", version="2.0.0")
    authority.issue(v1, record_id="r1")
    authority.issue(v2, record_id="r2")
    assert authority.registry.get_issued(coordinate_of(v1)) is not None
    assert authority.registry.get_issued(coordinate_of(v2)) is not None


# --------------------------------------------------------------------------- #
# Tenant isolation
# --------------------------------------------------------------------------- #
def test_cross_tenant_lookup_is_the_same_typed_miss_as_a_nonexistent_record():
    authority = make_authority()
    policy = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    authority.issue(policy, expected_reference_tenant_id="tenant-a")

    real_but_other_tenant = replace(coordinate_of(policy), tenant_id="tenant-b")
    never_existed = replace(coordinate_of(policy), policy_id="no-such-policy")

    assert authority.registry.get_issued(real_but_other_tenant) is None
    assert authority.registry.get_issued(never_existed) is None
    # Indistinguishable outcomes: both plain ``None``, no exception, no detail.
    assert (
        authority.registry.issued_records_for_identity(
            policy_family="DOMAIN", policy_id="pol-1", scope="TENANT", tenant_id="tenant-b"
        )
        == ()
    )


def test_two_tenants_holding_the_same_policy_id_stay_separate():
    authority = make_authority()
    a = make_policy(scope=PolicyScope.TENANT, tenant_id="t-a", policy_id="shared")
    b = make_policy(scope=PolicyScope.TENANT, tenant_id="t-b", policy_id="shared")
    authority.issue(a, record_id="ra", expected_reference_tenant_id="t-a")
    authority.issue(b, record_id="rb", expected_reference_tenant_id="t-b")
    assert authority.registry.get_issued(coordinate_of(a)) != authority.registry.get_issued(
        coordinate_of(b)
    )


# --------------------------------------------------------------------------- #
# Immutability
# --------------------------------------------------------------------------- #
def test_records_are_deeply_immutable():
    authority = make_authority()
    policy = make_policy(PolicyFamily.READINESS)
    authority.issue(policy)
    fetched = authority.registry.get_issued(coordinate_of(policy))

    with pytest.raises(dataclasses.FrozenInstanceError):
        fetched.record_id = "hijacked"
    with pytest.raises(dataclasses.FrozenInstanceError):
        fetched.coordinate.content_digest = "0" * 64
    with pytest.raises(dataclasses.FrozenInstanceError):
        fetched.policy.metadata.lifecycle_state = None
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
    stored = authority.registry.get_issued(coordinate_of(policy))
    assert len(stored.policy.gates) == 1
    assert authority.resolve(policy.reference).resolved


def test_identity_listing_is_order_independent():
    versions = ("3.0.0", "1.0.0", "2.0.0")
    listings = []
    for order in (versions, tuple(reversed(versions))):
        authority = make_authority()
        for v in order:
            authority.issue(make_policy(policy_id="p", version=v), record_id=f"rec-{v}")
        listings.append(
            tuple(
                r.coordinate.version
                for r in authority.registry.issued_records_for_identity(
                    policy_family="DOMAIN", policy_id="p", scope="GLOBAL", tenant_id=""
                )
            )
        )
    assert listings[0] == listings[1] == ("1.0.0", "2.0.0", "3.0.0")


# --------------------------------------------------------------------------- #
# Concurrency — process-local only, but real
# --------------------------------------------------------------------------- #
def _race(target, threads=16):
    barrier = threading.Barrier(threads)
    results: list = []
    errors: list = []

    def run(index):
        barrier.wait()
        try:
            results.append(target(index))
        except Exception as exc:  # noqa: BLE001 - the point is to collect them
            errors.append(exc)

    workers = [threading.Thread(target=run, args=(i,)) for i in range(threads)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    return results, errors


def test_concurrent_identical_issuance_produces_exactly_one_stored_record():
    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    authority.registry._issued.clear()
    authority.registry._issued_bytes.clear()
    authority.registry._identity_slots.clear()

    results, errors = _race(lambda _: authority.registry.append_issuance(record))

    assert not errors, errors
    assert len(authority.registry._issued) == 1
    assert all(r == record for r in results)


def test_concurrent_conflicting_issuance_produces_one_winner_and_typed_conflicts():
    authority = make_authority()
    # 16 distinct bodies competing for the same identity slot.
    policies = [
        make_policy(
            policy_id="p", version="1.0.0", overrides={"governed_outcome_unit": f"unit-{i}"}
        )
        for i in range(16)
    ]
    records = []
    for i, policy in enumerate(policies):
        fresh = make_authority()
        records.append(fresh.issue(policy, record_id=f"rec-{i}"))

    results, errors = _race(lambda i: authority.registry.append_issuance(records[i]))

    assert len(results) == 1, "more than one writer won the slot"
    assert len(errors) == 15
    assert all(isinstance(e, PolicyRegistryConflictError) for e in errors)
    assert len(authority.registry._issued) == 1


def test_revocation_racing_resolution_does_not_corrupt_state():
    authority = make_authority()
    policy = make_policy(effective_to=None)
    authority.issue(policy)

    outcomes: list = []
    errors: list = []
    barrier = threading.Barrier(2)

    def revoke():
        barrier.wait()
        try:
            revoke_policy(
                reference=policy.reference,
                revocation_id="rv-1",
                reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
                registry=authority.registry,
                adapters=authority.adapters,
                signer=authority.revocation_signer,
                signature_verifier=authority.key_ring,
                revoked_at=T_MID,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def resolve():
        barrier.wait()
        for _ in range(50):
            try:
                outcomes.append(authority.resolve(policy.reference).reason)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

    threads = [threading.Thread(target=revoke), threading.Thread(target=resolve)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    # Every observation is one of the two consistent states — never a torn one.
    from ugence_policy_authority.api import PolicyResolutionReason

    assert set(outcomes) <= {PolicyResolutionReason.RESOLVED, PolicyResolutionReason.REVOKED}
    assert len(authority.registry._revocations) == 1
    assert authority.resolve(policy.reference).reason is PolicyResolutionReason.REVOKED


def test_the_registry_holds_a_lock_and_does_not_claim_more_than_process_local():
    registry = InMemoryPolicyRegistry()
    assert isinstance(registry._lock, type(threading.RLock()))

    import ugence_policy_authority.core.registry as module

    doc = module.__doc__.lower()
    assert "process-local" in doc
    assert "not production persistence" in doc
    # It must not claim durability or distribution.
    assert "durab" in doc  # only as a disclaimer
    assert "no durability" in doc


# --------------------------------------------------------------------------- #
# Revocation storage
# --------------------------------------------------------------------------- #
def test_revocations_are_append_only_and_conflict_aware():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)

    def revoke(revocation_id, reason):
        return revoke_policy(
            reference=policy.reference,
            revocation_id=revocation_id,
            reason_code=reason,
            registry=authority.registry,
            adapters=authority.adapters,
            signer=authority.revocation_signer,
            signature_verifier=authority.key_ring,
            revoked_at=T_MID,
        )

    first = revoke("rv-1", PolicyRevocationReasonCode.CONTENT_DEFECT)
    assert revoke("rv-1", PolicyRevocationReasonCode.CONTENT_DEFECT) == first
    assert len(authority.registry._revocations) == 1

    with pytest.raises(PolicyRegistryConflictError, match="[Cc]onflicting"):
        revoke("rv-2", PolicyRevocationReasonCode.KEY_COMPROMISE)
    assert authority.registry.revocations_for(coordinate_of(policy)) == (first,)


def test_append_requires_the_right_record_types():
    registry = InMemoryPolicyRegistry()
    with pytest.raises(PolicyRegistryConflictError):
        registry.append_issuance({"looks": "like a record"})
    with pytest.raises(PolicyRegistryConflictError):
        registry.append_revocation({"looks": "like a revocation"})
