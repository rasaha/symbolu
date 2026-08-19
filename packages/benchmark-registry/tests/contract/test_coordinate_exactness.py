"""Exact-only coordinates: a floating reference is unrepresentable (ADR B-8, §17).

ADR B-8: "Floating ``latest``, implicit version selection, and string-parsed
successor guesses are **prohibited in governed evaluation**. A floating reference
must be *unrepresentable* on the trusted path, not merely discouraged."
§17.1-2: "Exact-coordinate lookup only. No ``latest()``, ``current()``, or
newest-version fallback."

These tests assert the *unrepresentable* half. The absence of a resolver is
asserted in ``tests/packaging/test_milestone_boundary.py``; the two together are
what "not merely discouraged" means.
"""

from __future__ import annotations

import dataclasses

import pytest
from ugence_benchmark_registry.api import (
    BenchmarkApplicabilityCoordinate,
    BenchmarkContractError,
    BenchmarkCoordinate,
    BenchmarkRefusalReason,
    BenchmarkScope,
)

import _builders as b

_R = BenchmarkRefusalReason

FLOATING_TOKENS = [
    "latest", "LATEST", "Latest", "current", "CURRENT", "newest", "head",
    "tip", "any", "ANY", "default", "active", "stable", "*", "-", "?",
]

INEXACT_VERSIONS = [
    "latest",
    "1",
    "1.2",
    "1.2.x",
    "1.2.*",
    "^1.2.3",
    "~1.2.3",
    ">=1.2.3",
    "<2.0.0",
    "1.2.3 - 1.4.0",
    "1.2.3 || 1.3.0",
    "v1.2.3",
    "1.02.0",
    "01.2.3",
    "1.2.3.4",
    "",
    " 1.2.3",
    "1.2.3 ",
    # Build metadata (F-3): SemVer 2.0.0 ignores it for precedence, so
    # "1.2.3" and "1.2.3+build" would be two coordinate spellings of one
    # precedence-equivalent version. The governing ADR authorizes no
    # exception, so it is refused, not merely ignored.
    "1.2.3+a",
    "1.2.3+build.7",
    "1.2.3-alpha+build",
    "1.0.0+build.5",
    "1.0.0-alpha.1+exp.sha.5114f85",
]


# --------------------------------------------------------------------------- #
# Floating tokens
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("token", FLOATING_TOKENS)
def test_a_floating_token_is_refused_as_a_benchmark_id(token):
    with pytest.raises(BenchmarkContractError) as excinfo:
        b.coordinate(benchmark_id=token)
    assert excinfo.value.reason in {
        _R.BENCHMARK_COORDINATE_NOT_EXACT,
        _R.BENCHMARK_IDENTITY_COORDINATE_MISSING,
    }


@pytest.mark.parametrize("token", FLOATING_TOKENS)
def test_a_floating_token_is_refused_as_a_family(token):
    with pytest.raises(BenchmarkContractError):
        b.coordinate(benchmark_family=token)


@pytest.mark.parametrize("token", FLOATING_TOKENS)
def test_a_floating_token_is_refused_as_a_tenant(token):
    with pytest.raises(BenchmarkContractError):
        BenchmarkScope.for_tenant(token)


@pytest.mark.parametrize("token", FLOATING_TOKENS)
def test_a_floating_token_is_refused_as_an_applicable_geography(token):
    with pytest.raises(BenchmarkContractError):
        BenchmarkApplicabilityCoordinate.applicable(token)


@pytest.mark.parametrize("token", FLOATING_TOKENS)
def test_a_floating_token_is_refused_as_a_publisher(token):
    with pytest.raises(BenchmarkContractError):
        b.identity(publisher_id=token)


# --------------------------------------------------------------------------- #
# Version exactness
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("version", INEXACT_VERSIONS)
def test_an_inexact_version_is_refused(version):
    with pytest.raises(BenchmarkContractError) as excinfo:
        b.coordinate(benchmark_version=version)
    assert excinfo.value.reason in {
        _R.BENCHMARK_COORDINATE_NOT_EXACT,
        _R.BENCHMARK_IDENTITY_COORDINATE_MISSING,
        _R.BENCHMARK_MALFORMED_CONTRACT,
    }


@pytest.mark.parametrize(
    "version", ["0.0.1", "1.0.0", "1.4.0", "10.20.30", "1.0.0-rc.1", "1.2.3-alpha",
                "1.2.3-alpha.1"]
)
def test_an_exact_semantic_version_is_accepted(version):
    assert b.coordinate(benchmark_version=version).benchmark_version == version


def test_two_spellings_of_one_version_cannot_both_exist():
    """Leading zeroes are refused, so ``1.02.0`` and ``1.2.0`` are not two names
    for one version — the second spelling simply does not exist."""

    assert b.coordinate(benchmark_version="1.2.0")
    with pytest.raises(BenchmarkContractError):
        b.coordinate(benchmark_version="1.02.0")


# --------------------------------------------------------------------------- #
# Wildcard, range and query characters
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("char", ["*", "?", "%", "^", "~", ">", "<", "|", ",",
                                  "[", "]", "{", "}"])
def test_a_query_character_anywhere_is_refused(char):
    with pytest.raises(BenchmarkContractError) as excinfo:
        b.coordinate(benchmark_id=f"bmk-{char}-x")
    assert excinfo.value.reason is _R.BENCHMARK_COORDINATE_NOT_EXACT


# --------------------------------------------------------------------------- #
# Partial coordinates
# --------------------------------------------------------------------------- #
def test_no_coordinate_field_carries_a_default():
    """A partial coordinate must not be constructible at all."""

    for field in dataclasses.fields(BenchmarkCoordinate):
        assert field.default is dataclasses.MISSING, field.name
        assert field.default_factory is dataclasses.MISSING, field.name


@pytest.mark.parametrize(
    "field", [f.name for f in dataclasses.fields(BenchmarkCoordinate)]
)
def test_a_partial_coordinate_cannot_be_constructed(field):
    kwargs = {
        f.name: getattr(b.coordinate(), f.name)
        for f in dataclasses.fields(BenchmarkCoordinate)
    }
    kwargs.pop(field)
    with pytest.raises(TypeError):
        BenchmarkCoordinate(**kwargs)


@pytest.mark.parametrize(
    "field", ["benchmark_id", "benchmark_family", "benchmark_version"]
)
def test_a_blank_coordinate_component_is_refused(field):
    with pytest.raises(BenchmarkContractError):
        b.coordinate(**{field: ""})
    with pytest.raises(BenchmarkContractError):
        b.coordinate(**{field: "   "})


# --------------------------------------------------------------------------- #
# There is no way to ask for "the newest"
# --------------------------------------------------------------------------- #
def test_no_public_symbol_offers_latest_or_current_selection():
    import ugence_benchmark_registry as pkg
    from ugence_benchmark_registry import api

    banned = ("latest", "current", "newest", "resolve", "lookup", "find",
              "search", "select", "register", "publish", "revoke", "supersede")
    for module in (pkg, api):
        for name in module.__all__:
            lowered = name.lower()
            for token in banned:
                assert token not in lowered, (module.__name__, name)


def test_no_contract_method_offers_latest_or_current_selection():
    """No *callable* selects a version; enum members are vocabulary, not code.

    ``BenchmarkLifecycleState.REGISTERED`` names a state the ADR §29 lifecycle
    ratifies; naming a state is not performing a registration. The scan is for
    behaviour, so enum types are excluded by type rather than by exception, and
    their members are pinned in ``test_lifecycle.py``.
    """

    import enum

    from ugence_benchmark_registry import api

    banned = ("latest", "current", "newest", "resolve", "lookup", "find_",
              "register", "publish", "revoke", "supersede")
    # ``unresolved_reason`` / ``trusted_resolution_performed`` are the honest
    # *negative* answers: they exist to say resolution did **not** happen. A
    # capability named after the thing it refuses to do is the opposite of the
    # defect this scan looks for, so both are exempted by exact name.
    exempt = {"unresolved_reason", "trusted_resolution_performed"}
    for name in api.__all__:
        obj = getattr(api, name)
        if not isinstance(obj, type) or issubclass(obj, enum.Enum):
            continue
        for attribute in dir(obj):
            if attribute.startswith("__") or attribute in exempt:
                continue
            if not callable(getattr(obj, attribute, None)) and not isinstance(
                getattr(obj, attribute, None), property
            ):
                continue
            lowered = attribute.lower()
            for token in banned:
                assert token not in lowered, (name, attribute)


# --------------------------------------------------------------------------- #
# Case sensitivity — no approximation
# --------------------------------------------------------------------------- #
def test_coordinates_are_case_sensitive():
    """A near-match is a different coordinate, never the same one.

    §17 admits exact-coordinate lookup only; case-insensitive approximation
    would make two distinct benchmarks share one name.
    """

    lower = b.coordinate(benchmark_id="bmk-alpha")
    upper = b.coordinate(benchmark_id="BMK-ALPHA")
    assert lower != upper
    assert lower.canonical_digest() != upper.canonical_digest()


def test_a_whitespace_padded_coordinate_is_refused_not_trimmed():
    with pytest.raises(BenchmarkContractError) as excinfo:
        b.coordinate(benchmark_id=" bmk-alpha")
    assert excinfo.value.reason is _R.BENCHMARK_MALFORMED_CONTRACT
    with pytest.raises(BenchmarkContractError):
        b.coordinate(benchmark_id="bmk-alpha ")


def test_the_exact_identity_tuple_covers_every_coordinate_component():
    coordinate = b.coordinate()
    assert coordinate.exact_identity == (
        "bmk-support-resolution-time",
        "operational-efficiency",
        "1.4.0",
        "TENANT",
        "tenant-alpha",
        "APPLICABLE",
        "EU",
        "APPLICABLE",
        "customer-support",
    )
