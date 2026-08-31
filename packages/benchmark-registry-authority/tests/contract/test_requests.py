"""Requests — an exact locator, no ``as_of`` on the trusted path, no selection."""

from __future__ import annotations

import dataclasses
import json
import pathlib
from datetime import datetime

import pytest

import _builders as fx
from ugence_benchmark_registry import (
    BenchmarkApplicabilityCoordinate,
    BenchmarkContractError,
    BenchmarkCoordinate,
    BenchmarkScope,
)
from ugence_benchmark_registry_authority.api import (
    BenchmarkExactResolutionRequest,
    BenchmarkHistoricalInspectionRequest,
    BenchmarkRegistryContractError,
    PlatformRegistryScopeExpectation,
    TenantRegistryScopeExpectation,
    canonical_bytes,
    canonical_digest,
)

FLOATING_TOKENS = (
    "latest",
    "current",
    "newest",
    "head",
    "tip",
    "any",
    "default",
    "active",
    "stable",
    "*",
    "-",
    "?",
    "LATEST",
    "Latest",
    "ACTIVE",
)

INEXACT_VERSIONS = (
    ">=1.2.3",
    "~1.2.3",
    "^1.2.3",
    "1.2",
    "1",
    "1.2.x",
    "1.2.*",
    "1.2.3+build",
    "1.2.3+20260101",
    "1.02.0",
    "v1.2.3",
    "1.2.3 || 2.0.0",
)


def test_happy_both_requests_construct_from_an_exact_locator():
    assert fx.exact_resolution_request().coordinate == fx.coordinate()
    assert fx.historical_inspection_request().as_of == fx.AS_OF


def test_the_exact_resolution_request_has_no_as_of_at_all():
    """Not optional, not defaulted — absent. There is no parameter to pass."""

    request = fx.exact_resolution_request()
    assert "as_of" not in {f.name for f in dataclasses.fields(request)}
    assert not hasattr(request, "as_of")
    with pytest.raises(TypeError):
        BenchmarkExactResolutionRequest(
            coordinate=fx.coordinate(), as_of=fx.AS_OF
        )


def test_the_historical_request_requires_as_of_and_will_not_default_it():
    with pytest.raises(TypeError):
        BenchmarkHistoricalInspectionRequest(coordinate=fx.coordinate())


def test_a_naive_as_of_is_refused():
    with pytest.raises(BenchmarkRegistryContractError):
        fx.historical_inspection_request(as_of=datetime(2026, 9, 1))


def test_each_request_carries_exactly_one_coordinate_and_no_second_version():
    for builder in (fx.exact_resolution_request, fx.historical_inspection_request):
        request = builder()
        fields = {f.name for f in dataclasses.fields(request)}
        assert sum(1 for f in fields if "version" in f) == 0
        assert request.benchmark_version == fx.BENCHMARK_VERSION
        assert isinstance(type(request).benchmark_version, property)


@pytest.mark.parametrize("token", FLOATING_TOKENS)
def test_no_floating_token_is_constructible_on_any_request(token):
    """Unrepresentable, not merely discouraged — refused by BR-1 at the locator."""

    for field in ("benchmark_id", "benchmark_family", "benchmark_version"):
        with pytest.raises(BenchmarkContractError):
            fx.coordinate(**{field: token})


@pytest.mark.parametrize("version", INEXACT_VERSIONS)
def test_no_range_wildcard_partial_or_build_metadata_version_is_constructible(version):
    with pytest.raises(BenchmarkContractError):
        fx.coordinate(benchmark_version=version)


def test_a_request_cannot_be_built_from_anything_but_an_exact_coordinate():
    for wrong in ("bmk", ("bmk", "fam", "1.2.3"), None, fx.publisher_envelope()):
        with pytest.raises(BenchmarkRegistryContractError):
            BenchmarkExactResolutionRequest(coordinate=wrong)


def test_no_exported_symbol_offers_latest_current_or_selection():
    import ugence_benchmark_registry_authority as pkg

    banned = ("latest", "current", "newest", "select", "resolve_any", "default_")
    for symbol in pkg.__all__:
        lowered = symbol.lower()
        for token in banned:
            assert token not in lowered, symbol


def test_the_package_never_names_the_governance_contracts_reference_type():
    """A ``BenchmarkReference`` names a set, not a coordinate. It is not accepted."""

    src = pathlib.Path(__file__).resolve().parents[2] / "src"
    for path in src.rglob("*.py"):
        text = path.read_text()
        assert "ugence_governance_contracts" not in text.replace(
            "``ugence_governance_contracts.BenchmarkReference``", ""
        ), path.name
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                assert "governance_contracts" not in stripped, path.name


# --------------------------------------------------------------------------- #
# Derived scope expectation
# --------------------------------------------------------------------------- #
def test_the_scope_expectation_is_derived_not_a_constructor_argument():
    for builder in (fx.exact_resolution_request, fx.historical_inspection_request):
        request = builder()
        assert "registry_scope_expectation" not in {
            f.name for f in dataclasses.fields(request)
        }
        assert isinstance(type(request).registry_scope_expectation, property)


def test_a_tenant_locator_derives_the_tenant_expectation():
    request = fx.exact_resolution_request()
    expectation = request.registry_scope_expectation
    assert type(expectation) is TenantRegistryScopeExpectation
    assert expectation.tenant_id == fx.TENANT_ID


def test_a_platform_wide_locator_derives_the_platform_expectation():
    request = fx.exact_resolution_request(
        coordinate=fx.coordinate(scope=BenchmarkScope.platform_wide())
    )
    assert type(request.registry_scope_expectation) is (
        PlatformRegistryScopeExpectation
    )


def test_a_platform_locator_can_never_carry_a_tenant_expectation():
    """There is no constructor argument, so the disagreement is unconstructible."""

    request = fx.exact_resolution_request(
        coordinate=fx.coordinate(scope=BenchmarkScope.platform_wide())
    )
    assert not isinstance(
        request.registry_scope_expectation, TenantRegistryScopeExpectation
    )
    with pytest.raises(TypeError):
        BenchmarkExactResolutionRequest(
            coordinate=fx.coordinate(),
            registry_scope_expectation=fx.platform_expectation(),
        )


def test_both_requests_canonicalize_into_different_byte_spaces():
    a = json.loads(canonical_bytes(fx.exact_resolution_request()))
    b = json.loads(canonical_bytes(fx.historical_inspection_request()))
    assert a["domain"] != b["domain"]
    assert a["type"] != b["type"]


def test_the_as_of_participates_in_the_historical_request_digest():
    assert canonical_digest(
        fx.historical_inspection_request(as_of=fx.VALIDITY_FROM)
    ) != canonical_digest(fx.historical_inspection_request())


def test_a_near_match_locator_is_a_different_request():
    other = fx.exact_resolution_request(
        coordinate=fx.coordinate(
            geography=BenchmarkApplicabilityCoordinate.applicable("us")
        )
    )
    assert canonical_digest(other) != canonical_digest(fx.exact_resolution_request())


def test_the_locator_is_case_sensitive():
    assert canonical_digest(
        fx.exact_resolution_request(coordinate=fx.coordinate(benchmark_id="BMK"))
    ) != canonical_digest(fx.exact_resolution_request())
    assert BenchmarkCoordinate is type(fx.coordinate())
