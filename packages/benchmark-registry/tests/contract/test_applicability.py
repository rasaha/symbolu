"""Applicability and scope matrices (ADR §15 rows 5-7, §27.1).

§15: "required where applicability depends on it; explicitly ``NOT_APPLICABLE``
otherwise — **never omitted** ... An explicit ``NOT_APPLICABLE`` is a decision on
the record; an omitted field is not."
"""

from __future__ import annotations

import dataclasses
import itertools

import pytest
from ugence_benchmark_registry.api import (
    BenchmarkApplicabilityCoordinate,
    BenchmarkApplicabilityDeclaration,
    BenchmarkContractError,
    BenchmarkRefusalReason,
    BenchmarkScope,
    BenchmarkScopeKind,
    canonical_bytes,
)

import _builders as b

_R = BenchmarkRefusalReason
_D = BenchmarkApplicabilityDeclaration


# --------------------------------------------------------------------------- #
# The 2x2 applicability matrix
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "declaration,value,admissible",
    [
        (_D.APPLICABLE, "EU", True),
        (_D.APPLICABLE, "", False),
        (_D.APPLICABLE, "   ", False),
        (_D.NOT_APPLICABLE, "", True),
        (_D.NOT_APPLICABLE, "EU", False),
    ],
)
def test_the_applicability_matrix(declaration, value, admissible):
    if admissible:
        coordinate = BenchmarkApplicabilityCoordinate(
            declaration=declaration, value=value
        )
        assert coordinate.declaration is declaration
    else:
        with pytest.raises(BenchmarkContractError) as excinfo:
            BenchmarkApplicabilityCoordinate(declaration=declaration, value=value)
        assert excinfo.value.reason in {
            _R.BENCHMARK_APPLICABILITY_INCONSISTENT,
            _R.BENCHMARK_MALFORMED_CONTRACT,
        }


def test_the_two_declarations_produce_different_bytes():
    """A recorded NOT_APPLICABLE is itself digest-bound."""

    applicable = BenchmarkApplicabilityCoordinate.applicable("EU")
    not_applicable = BenchmarkApplicabilityCoordinate.not_applicable()
    assert canonical_bytes(applicable) != canonical_bytes(not_applicable)


def test_there_is_no_third_declaration_and_no_none():
    assert [m.value for m in _D] == ["APPLICABLE", "NOT_APPLICABLE"]
    with pytest.raises(BenchmarkContractError):
        BenchmarkApplicabilityCoordinate(declaration=None, value="")
    with pytest.raises(BenchmarkContractError):
        BenchmarkApplicabilityCoordinate(declaration="APPLICABLE", value="EU")


def test_the_declaration_has_no_default_so_it_cannot_be_omitted():
    fields = {f.name: f for f in dataclasses.fields(BenchmarkApplicabilityCoordinate)}
    assert fields["declaration"].default is dataclasses.MISSING


def test_none_is_not_not_applicable():
    """``None`` and an explicit NOT_APPLICABLE are not interchangeable."""

    with pytest.raises(BenchmarkContractError):
        BenchmarkApplicabilityCoordinate(declaration=_D.APPLICABLE, value=None)
    with pytest.raises(BenchmarkContractError):
        BenchmarkApplicabilityCoordinate(declaration=_D.NOT_APPLICABLE, value=None)


# --------------------------------------------------------------------------- #
# Geography x domain — the full applicability matrix on a real identity
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "geo,dom",
    list(
        itertools.product(
            [
                BenchmarkApplicabilityCoordinate.applicable("EU"),
                BenchmarkApplicabilityCoordinate.not_applicable(),
            ],
            [
                BenchmarkApplicabilityCoordinate.applicable("customer-support"),
                BenchmarkApplicabilityCoordinate.not_applicable(),
            ],
        )
    ),
)
def test_every_geography_domain_combination_is_representable_and_distinct(geo, dom):
    identity = b.identity(coordinate=b.coordinate(geography=geo, domain=dom))
    assert identity.coordinate.geography == geo
    assert identity.coordinate.domain == dom


def test_the_four_applicability_combinations_have_four_distinct_digests():
    digests = set()
    for geo, dom in itertools.product(
        [
            BenchmarkApplicabilityCoordinate.applicable("EU"),
            BenchmarkApplicabilityCoordinate.not_applicable(),
        ],
        [
            BenchmarkApplicabilityCoordinate.applicable("customer-support"),
            BenchmarkApplicabilityCoordinate.not_applicable(),
        ],
    ):
        digests.add(
            b.identity(
                coordinate=b.coordinate(geography=geo, domain=dom)
            ).canonical_digest()
        )
    assert len(digests) == 4


def test_a_geography_mismatch_is_a_different_benchmark():
    """§15 — an applicability mismatch is a refusal, not an advisory note.

    At BR-1 the structural consequence is that the two are different identities
    with different digests, so a mismatch cannot pass unnoticed. Turning that into
    a resolution refusal is BR-2's.
    """

    eu = b.identity(
        coordinate=b.coordinate(
            geography=BenchmarkApplicabilityCoordinate.applicable("EU")
        )
    )
    us = b.identity(
        coordinate=b.coordinate(
            geography=BenchmarkApplicabilityCoordinate.applicable("US")
        )
    )
    assert eu.canonical_digest() != us.canonical_digest()


# --------------------------------------------------------------------------- #
# Scope (ADR §15 row 5, §27.1)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "kind,tenant,admissible",
    [
        (BenchmarkScopeKind.PLATFORM_WIDE, "", True),
        (BenchmarkScopeKind.PLATFORM_WIDE, "tenant-alpha", False),
        (BenchmarkScopeKind.TENANT, "tenant-alpha", True),
        (BenchmarkScopeKind.TENANT, "", False),
        (BenchmarkScopeKind.TENANT, "   ", False),
    ],
)
def test_the_scope_matrix(kind, tenant, admissible):
    if admissible:
        assert BenchmarkScope(kind=kind, tenant_id=tenant).kind is kind
    else:
        with pytest.raises(BenchmarkContractError) as excinfo:
            BenchmarkScope(kind=kind, tenant_id=tenant)
        assert excinfo.value.reason in {
            _R.BENCHMARK_APPLICABILITY_INCONSISTENT,
            _R.BENCHMARK_MALFORMED_CONTRACT,
        }


def test_platform_wide_is_declared_never_implied():
    assert [m.value for m in BenchmarkScopeKind] == ["PLATFORM_WIDE", "TENANT"]
    platform = BenchmarkScope.platform_wide()
    assert platform.kind is BenchmarkScopeKind.PLATFORM_WIDE
    assert platform.tenant_id == ""


def test_the_scope_kind_has_no_default():
    fields = {f.name: f for f in dataclasses.fields(BenchmarkScope)}
    assert fields["kind"].default is dataclasses.MISSING


def test_a_platform_wide_and_a_tenant_scope_are_different_benchmarks():
    platform = b.identity(
        coordinate=b.coordinate(scope=BenchmarkScope.platform_wide())
    )
    tenant = b.identity()
    assert platform.canonical_digest() != tenant.canonical_digest()


def test_two_tenants_are_different_benchmarks():
    alpha = b.identity()
    beta = b.identity(
        coordinate=b.coordinate(scope=BenchmarkScope.for_tenant("tenant-beta"))
    )
    assert alpha.canonical_digest() != beta.canonical_digest()


def test_declaring_platform_wide_grants_no_cross_tenant_access():
    """§17.6's cross-tenant non-disclosure is a resolution rule, and is BR-2's.

    Asserted structurally: nothing in this package exposes a disclosure,
    permission or visibility decision to read a scope against.
    """

    from ugence_benchmark_registry import api

    banned = ("disclose", "permit", "allow", "visible", "authorize", "entitled",
              "access")
    for name in api.__all__:
        assert not any(token in name.lower() for token in banned), name
