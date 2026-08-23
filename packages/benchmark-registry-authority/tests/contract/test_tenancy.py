"""Tenancy — BR-1's model preserved exactly, and attacked."""

from __future__ import annotations

import dataclasses

import pytest

import _builders as fx
from ugence_benchmark_registry import (
    BenchmarkContractError,
    BenchmarkScope,
    BenchmarkScopeKind,
)
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES,
    BenchmarkRegistryFaultClass,
    BenchmarkRegistryRefusalReason,
    canonical_digest,
)


def test_happy_a_tenant_scoped_chain_constructs():
    assert fx.revocation_event().registration_event.coordinate.scope.kind is (
        BenchmarkScopeKind.TENANT
    )


def test_a_platform_wide_chain_constructs_and_differs():
    envelope = fx.publisher_envelope(
        coordinate=fx.coordinate(scope=BenchmarkScope.platform_wide())
    )
    record = fx.submission_record(publisher_submission_envelope=envelope)
    assert canonical_digest(record) != canonical_digest(fx.submission_record())


def test_a_different_tenant_is_a_different_locator_and_a_different_digest():
    envelope = fx.publisher_envelope(
        coordinate=fx.coordinate(scope=BenchmarkScope.for_tenant("t2"))
    )
    record = fx.submission_record(publisher_submission_envelope=envelope)
    assert canonical_digest(record) != canonical_digest(fx.submission_record())


def test_tenancy_is_never_inferred_or_defaulted():
    """BR-1 refuses a TENANT scope with no tenant and a PLATFORM_WIDE with one."""

    with pytest.raises(BenchmarkContractError):
        BenchmarkScope(kind=BenchmarkScopeKind.TENANT, tenant_id="")
    with pytest.raises(BenchmarkContractError):
        BenchmarkScope(kind=BenchmarkScopeKind.PLATFORM_WIDE, tenant_id="t1")


def test_no_visibility_dimension_is_added_anywhere():
    """No publisher-private, shared-by-policy or visibility field is introduced.

    ``BenchmarkTrustAnchorRecord.public_key_material`` is exempt from the
    ``public_`` token alone, and the collision is **incidental**: this ban is
    about *visibility* — publisher-private, shared-by-policy, public-to-all —
    and "public key" is cryptographic terminology in which "public" names the
    half of a keypair that is not secret, not an audience who may read a
    benchmark. D-25 ratifies the field. The exemption is one token on one field
    of one class; every other token still applies to it, so a
    ``public_visibility`` or ``shared_key_material`` field would still fail.
    """

    banned = ("visibility", "private", "shared", "public_", "acl", "permission")
    for name, builder in fx.PINNED_VECTOR_BUILDERS:
        for f in dataclasses.fields(builder()):
            lowered = f.name.lower()
            for token in banned:
                if (
                    token == "public_"
                    and (name, f.name)
                    == ("BenchmarkTrustAnchorRecord", "public_key_material")
                ):
                    continue
                assert token not in lowered, f.name


def test_no_publisher_dimension_enters_the_locator():
    """The publisher lives on the envelope, one level up — never in the coordinate."""

    coordinate = fx.coordinate()
    names = {f.name for f in dataclasses.fields(coordinate)}
    assert "publisher_id" not in names
    assert "publisher_identity" not in names
    assert len(coordinate.exact_identity) == 9


def test_a_forged_tenant_on_a_frozen_scope_is_refused_at_revalidation():
    from ugence_benchmark_registry_authority.api import (
        BenchmarkRegistryCanonicalizationError,
        canonical_bytes,
    )

    record = fx.submission_record()
    scope = record.publisher_submission_envelope.coordinate.scope
    object.__setattr__(scope, "tenant_id", "")
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(record)


def test_a_cross_tenant_scope_swap_changes_the_digest_rather_than_passing_silently():
    record = fx.submission_record()
    before = canonical_digest(record)
    object.__setattr__(
        record.publisher_submission_envelope.coordinate,
        "scope",
        BenchmarkScope.for_tenant("t2"),
    )
    assert canonical_digest(record) != before


def test_not_found_is_one_member_for_a_miss_and_for_a_denial():
    """§17.6: externally indistinguishable — same code, same shape."""

    assert BenchmarkRegistryRefusalReason.NOT_FOUND.value == "NOT_FOUND"
    assert BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES[
        BenchmarkRegistryRefusalReason.NOT_FOUND
    ] is BenchmarkRegistryFaultClass.READ_NON_DISCLOSURE


def test_there_is_no_separate_not_permitted_member_to_leak_existence():
    names = {r.name for r in BenchmarkRegistryRefusalReason}
    for leaky in ("NOT_PERMITTED", "FORBIDDEN", "UNAUTHORIZED_TENANT", "DENIED"):
        assert leaky not in names


def test_not_admitted_and_not_found_are_distinct_members():
    assert (
        BenchmarkRegistryRefusalReason.NOT_ADMITTED
        is not BenchmarkRegistryRefusalReason.NOT_FOUND
    )
