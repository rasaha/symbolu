"""Unicode NFC and padding are refused at construction, and again at encoding.

ADR §22.4 fixes the two-boundary pattern for naive datetimes — rejected "at the
boundary **and again** at canonicalization". A canonical string is the same kind
of coordinate and gets the same treatment. Neither boundary normalizes.
"""

from __future__ import annotations

import unicodedata

import pytest
from ugence_benchmark_registry.api import (
    BenchmarkApplicabilityCoordinate,
    BenchmarkApprovalReference,
    BenchmarkCanonicalizationError,
    BenchmarkContractError,
    BenchmarkRefusalReason,
    BenchmarkScope,
    canonical_bytes,
)

import _builders as b

_R = BenchmarkRefusalReason

#: "Café" in NFD — a combining acute after a bare ``e``. Distinct bytes from the
#: NFC spelling, and therefore a distinct coordinate.
NFD = "Café"
NFC = "Café"


def test_the_fixture_really_is_non_canonical():
    """The control: NFD and NFC are different strings that normalize together."""

    assert NFD != NFC
    assert unicodedata.normalize("NFC", NFD) == NFC


# --------------------------------------------------------------------------- #
# Construction boundary
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "build",
    [
        lambda v: b.coordinate(benchmark_id=v),
        lambda v: b.coordinate(benchmark_family=v),
        lambda v: BenchmarkScope.for_tenant(v),
        lambda v: BenchmarkApplicabilityCoordinate.applicable(v),
        lambda v: b.measurement(unit=v),
        lambda v: b.measurement(metric_ref=v),
        lambda v: b.source_requirements(source_ref=v),
        lambda v: b.source_requirements(provenance_requirement_refs=(v,)),
        lambda v: BenchmarkApprovalReference(
            approval_ref=v,
            approval_authority_ref="auth",
            approved_content_digest=b.CONTENT_DIGEST,
        ),
        lambda v: b.identity(publisher_id=v),
    ],
)
def test_a_non_nfc_value_is_refused_at_construction(build):
    with pytest.raises(BenchmarkContractError) as excinfo:
        build(NFD)
    assert excinfo.value.reason is _R.BENCHMARK_MALFORMED_CONTRACT


@pytest.mark.parametrize(
    "build",
    [
        lambda v: b.coordinate(benchmark_id=v),
        lambda v: BenchmarkScope.for_tenant(v),
        lambda v: b.measurement(unit=v),
        lambda v: b.identity(publisher_id=v),
    ],
)
def test_the_nfc_spelling_is_accepted(build):
    assert build(NFC) is not None


def test_a_non_nfc_value_is_never_silently_normalized():
    """Refusing keeps the digest a faithful function of what was written."""

    accepted = BenchmarkScope.for_tenant(NFC)
    assert accepted.tenant_id == NFC
    with pytest.raises(BenchmarkContractError):
        BenchmarkScope.for_tenant(NFD)


# --------------------------------------------------------------------------- #
# Padding
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("padded", [" x", "x ", " x ", "\tx", "x\n", " x"])
def test_a_padded_identifier_is_refused_not_trimmed(padded):
    with pytest.raises(BenchmarkContractError):
        b.coordinate(benchmark_id=padded)


@pytest.mark.parametrize("blank", ["", " ", "   ", "\t", "\n"])
def test_an_all_whitespace_identifier_is_refused(blank):
    with pytest.raises(BenchmarkContractError):
        b.coordinate(benchmark_id=blank)


def test_an_all_whitespace_value_is_refused_even_where_empty_is_allowed():
    """``NOT_APPLICABLE`` admits ``""``; it does not admit padding around nothing."""

    assert BenchmarkApplicabilityCoordinate.not_applicable().value == ""
    with pytest.raises(BenchmarkContractError):
        BenchmarkApplicabilityCoordinate(
            declaration=BenchmarkApplicabilityCoordinate.not_applicable().declaration,
            value="   ",
        )


# --------------------------------------------------------------------------- #
# Encoder boundary — defence in depth
# --------------------------------------------------------------------------- #
def test_the_encoder_refuses_a_non_nfc_value_that_arrived_by_another_route():
    scope = BenchmarkScope.for_tenant("tenant-alpha")
    object.__setattr__(scope, "tenant_id", NFD)
    with pytest.raises(BenchmarkCanonicalizationError):
        canonical_bytes(scope)


def test_the_encoder_accepts_the_nfc_spelling_it_refused_in_nfd():
    scope = BenchmarkScope.for_tenant(NFC)
    assert canonical_bytes(scope)


def test_two_spellings_never_share_a_digest_because_one_cannot_exist():
    """Both boundaries refuse NFD, so there is no second spelling to collide."""

    nfc_scope = BenchmarkScope.for_tenant(NFC)
    assert canonical_bytes(nfc_scope)
    with pytest.raises(BenchmarkContractError):
        BenchmarkScope.for_tenant(NFD)


def test_non_ascii_is_preserved_verbatim_in_the_canonical_bytes():
    """``ensure_ascii=False`` — the bytes carry the character, not an escape."""

    scope = BenchmarkScope.for_tenant(NFC)
    assert NFC.encode("utf-8") in canonical_bytes(scope)
    assert b"\\u00e9" not in canonical_bytes(scope)
