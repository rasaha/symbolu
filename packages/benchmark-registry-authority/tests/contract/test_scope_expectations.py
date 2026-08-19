"""Two scope expectations, each admitting exactly one kind, neither authorizing."""

from __future__ import annotations

import pytest

import _builders as fx
from ugence_benchmark_registry import BenchmarkScope
from ugence_benchmark_registry_authority.api import (
    BenchmarkRegistryContractError,
    PlatformRegistryScopeExpectation,
    TenantRegistryScopeExpectation,
    canonical_digest,
)


def test_happy_each_expectation_constructs_from_its_own_kind():
    assert fx.platform_expectation().scope.kind.value == "PLATFORM_WIDE"
    assert fx.tenant_expectation().scope.kind.value == "TENANT"


def test_the_platform_expectation_refuses_a_tenant_scope():
    with pytest.raises(BenchmarkRegistryContractError) as excinfo:
        PlatformRegistryScopeExpectation(scope=BenchmarkScope.for_tenant("t1"))
    assert "PLATFORM_WIDE" in str(excinfo.value)


def test_the_tenant_expectation_refuses_a_platform_scope():
    with pytest.raises(BenchmarkRegistryContractError) as excinfo:
        TenantRegistryScopeExpectation(scope=BenchmarkScope.platform_wide())
    assert "TENANT" in str(excinfo.value)


def test_they_differ_only_in_the_kind_their_constructors_admit():
    import dataclasses

    assert [f.name for f in dataclasses.fields(fx.platform_expectation())] == [
        "scope"
    ]
    assert [f.name for f in dataclasses.fields(fx.tenant_expectation())] == ["scope"]


def test_they_are_different_exact_types_and_cannot_substitute():
    assert type(fx.platform_expectation()) is not type(fx.tenant_expectation())


def test_they_occupy_different_canonical_byte_spaces():
    import json
    from ugence_benchmark_registry_authority.api import canonical_bytes

    a = json.loads(canonical_bytes(fx.platform_expectation()))
    b = json.loads(canonical_bytes(fx.tenant_expectation()))
    assert a["domain"] != b["domain"]
    assert a["type"] != b["type"]


def test_neither_grants_authorization_by_construction():
    assert fx.platform_expectation().authorization_granted is False
    assert fx.tenant_expectation().authorization_granted is False


def test_authorization_granted_cannot_be_set():
    for expectation in (fx.platform_expectation(), fx.tenant_expectation()):
        with pytest.raises(AttributeError):
            object.__setattr__(expectation, "authorization_granted", True)


def test_the_tenant_id_is_derived_through_the_br1_scope():
    expectation = fx.tenant_expectation()
    assert expectation.tenant_id == fx.TENANT_ID
    assert isinstance(type(expectation).tenant_id, property)


def test_no_scope_semantics_are_minted_here():
    """The vocabulary stays BR-1's: the field is a BR-1 BenchmarkScope."""

    assert type(fx.tenant_expectation().scope) is BenchmarkScope


def test_a_different_tenant_is_a_different_expectation_and_digest():
    assert canonical_digest(
        fx.tenant_expectation(scope=BenchmarkScope.for_tenant("t2"))
    ) != canonical_digest(fx.tenant_expectation())


def test_a_duck_typed_scope_is_refused():
    class FakeScope:
        kind = None
        tenant_id = "t1"

    with pytest.raises(BenchmarkRegistryContractError):
        TenantRegistryScopeExpectation(scope=FakeScope())
