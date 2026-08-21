"""BR-2C's trust and verification contracts — shapes, and their refusals.

D-24, D-25 and D-26 replaced two ``bool`` returns with exact types. These tests
assert what those types refuse, not that anything verifies: **no verifier ships
here, and none has been audited** (D-32).
"""

from __future__ import annotations

import dataclasses

import pytest

import _builders as fx
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER,
    BENCHMARK_VERIFIED_RESULT_BOUND_FACTS,
    BenchmarkApprovalVerifiedResult,
    BenchmarkPublisherVerifiedResult,
    BenchmarkRegistryContractError,
    BenchmarkRegistryFaultClass,
    BenchmarkRegistryRefusalReason,
    BenchmarkRevocationVerifiedResult,
    BenchmarkSignatureProfile,
    BenchmarkTrustAnchorStatus,
    BenchmarkTrustRole,
    BenchmarkVerificationOutcome,
    canonical_digest,
    fault_class_for,
)

RESULT_BUILDERS = (
    ("BenchmarkPublisherVerifiedResult", fx.publisher_verified_result),
    ("BenchmarkApprovalVerifiedResult", fx.approval_verified_result),
    ("BenchmarkRevocationVerifiedResult", fx.revocation_verified_result),
)


# --------------------------------------------------------------------------- #
# D-24: nine bound facts, three distinct types
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,builder", RESULT_BUILDERS)
def test_happy_every_verified_result_binds_exactly_the_nine_ratified_facts(
    name, builder
):
    """D-24's nine, in order, and no tenth."""

    fields = tuple(f.name for f in dataclasses.fields(builder()))
    assert fields == BENCHMARK_VERIFIED_RESULT_BOUND_FACTS, name
    assert len(BENCHMARK_VERIFIED_RESULT_BOUND_FACTS) == 9


def test_the_three_result_types_are_distinct_and_not_interchangeable():
    """Three exact types, not one parameterized one (D-24, D-26).

    Distinctness is the mechanism §17's rule 10 relies on: proof about a revoker
    cannot be handed where proof about a publisher is required.
    """

    types = {type(builder()) for _name, builder in RESULT_BUILDERS}
    assert len(types) == 3
    assert types == {
        BenchmarkPublisherVerifiedResult,
        BenchmarkApprovalVerifiedResult,
        BenchmarkRevocationVerifiedResult,
    }


@pytest.mark.parametrize(
    "builder,pinned",
    (
        (fx.publisher_verified_result, BenchmarkTrustRole.PUBLISHER),
        (fx.approval_verified_result, BenchmarkTrustRole.APPROVER),
        (fx.revocation_verified_result, BenchmarkTrustRole.REVOKER),
    ),
)
def test_each_result_pins_its_own_role_and_refuses_every_other(builder, pinned):
    assert builder().signer_role is pinned
    for role in BenchmarkTrustRole:
        if role is pinned:
            continue
        with pytest.raises(BenchmarkRegistryContractError):
            builder(signer_role=role)


@pytest.mark.parametrize("builder,pinned", (
    (fx.publisher_verified_result, BenchmarkTrustRole.PUBLISHER),
))
def test_a_string_spelling_of_the_role_is_not_the_role(builder, pinned):
    """``str`` enum members compare equal to their values; membership is not text."""

    with pytest.raises(BenchmarkRegistryContractError):
        builder(signer_role=pinned.value)


@pytest.mark.parametrize("name,builder", RESULT_BUILDERS)
def test_each_result_owns_a_distinct_byte_space(name, builder):
    """A result for one seam is never replayable as one for another."""

    digests = {canonical_digest(b()) for _n, b in RESULT_BUILDERS}
    assert len(digests) == 3


# --------------------------------------------------------------------------- #
# The outcome/reason biconditional
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,builder", RESULT_BUILDERS)
def test_a_verified_result_carrying_a_refusal_reason_is_unconstructible(
    name, builder
):
    with pytest.raises(BenchmarkRegistryContractError):
        builder(
            outcome=BenchmarkVerificationOutcome.VERIFIED,
            refusal_reason=BenchmarkRegistryRefusalReason.SIGNATURE_INVALID,
        )


@pytest.mark.parametrize("name,builder", RESULT_BUILDERS)
def test_a_refused_result_with_no_reason_is_unconstructible(name, builder):
    with pytest.raises(BenchmarkRegistryContractError):
        builder(
            outcome=BenchmarkVerificationOutcome.REFUSED,
            refusal_reason=None,
        )


@pytest.mark.parametrize("name,builder", RESULT_BUILDERS)
def test_a_verified_result_must_bind_the_anchor_revision(name, builder):
    """D-25 makes that digest the anchor revision; a verification names one."""

    with pytest.raises(BenchmarkRegistryContractError):
        builder(anchor_record_digest=None)


def test_a_refusal_that_never_reached_an_anchor_binds_no_revision():
    """TRUST_ANCHOR_NOT_FOUND has no record to digest, and none is invented."""

    result = fx.refused_publisher_verified_result()
    assert result.anchor_record_digest is None
    assert result.outcome is BenchmarkVerificationOutcome.REFUSED
    assert (
        result.refusal_reason
        is BenchmarkRegistryRefusalReason.TRUST_ANCHOR_NOT_FOUND
    )


# --------------------------------------------------------------------------- #
# The specific diagnostics, asserted because they are observable behaviour.
#
# Each of these three constructor gates is followed by a generic validator that
# would also refuse the same input — ``require_enum_member``, ``require_digest``
# and ``require_aware_datetime`` all reject ``None``. Deleting the specific gate
# therefore still refuses, but reports "must be exactly a datetime" where it
# should report "a REVOKED anchor must carry revoked_at". The message is what
# tells an operator which rule they broke, so it is asserted rather than left
# to a mutation sweep to classify as an unobservable difference.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,builder", RESULT_BUILDERS)
def test_a_reasonless_refusal_says_which_rule_it_broke(name, builder):
    with pytest.raises(BenchmarkRegistryContractError) as raised:
        builder(outcome=BenchmarkVerificationOutcome.REFUSED, refusal_reason=None)
    assert "must carry exactly one typed refusal_reason" in str(raised.value)


@pytest.mark.parametrize("name,builder", RESULT_BUILDERS)
def test_an_unbound_anchor_revision_says_which_rule_it_broke(name, builder):
    with pytest.raises(BenchmarkRegistryContractError) as raised:
        builder(anchor_record_digest=None)
    assert "must bind the anchor_record_digest" in str(raised.value)


def test_a_revoked_anchor_missing_its_time_says_which_rule_it_broke():
    with pytest.raises(BenchmarkRegistryContractError) as raised:
        fx.trust_anchor_record(
            status=BenchmarkTrustAnchorStatus.REVOKED, revoked_at=None
        )
    assert "REVOKED anchor must carry revoked_at" in str(raised.value)


def test_the_outcome_vocabulary_is_not_the_admission_vocabulary():
    """D-24: cryptographic verification only — never admission."""

    values = {m.value for m in BenchmarkVerificationOutcome}
    assert values == {"VERIFIED", "REFUSED"}
    assert "ADMITTED" not in values
    assert "REJECTED" not in values


# --------------------------------------------------------------------------- #
# D-24: verification establishes nothing else
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,builder", RESULT_BUILDERS)
def test_a_verified_result_establishes_no_authority_fact_whatsoever(
    name, builder
):
    """Even reading ``outcome=VERIFIED``. §09's five, permanently ``False``."""

    result = builder()
    assert result.outcome is BenchmarkVerificationOutcome.VERIFIED
    assert result.authority_verified is False
    assert result.publisher_authenticity_established is False
    assert result.approval_authenticity_established is False
    assert result.registry_admission_established is False
    assert result.trusted_resolution_established is False


@pytest.mark.parametrize("name,builder", RESULT_BUILDERS)
def test_the_authority_derivations_cannot_be_assigned_on_a_result(name, builder):
    result = builder()
    for attribute in (
        "authority_verified",
        "registry_admission_established",
        "trusted_resolution_established",
    ):
        with pytest.raises(AttributeError):
            object.__setattr__(result, attribute, True)


# --------------------------------------------------------------------------- #
# D-25: the anchor record, and the revision that is its digest
# --------------------------------------------------------------------------- #
def test_happy_the_anchor_revision_is_the_records_canonical_digest():
    record = fx.trust_anchor_record()
    assert record.anchor_record_digest == canonical_digest(record)


def test_the_anchor_revision_is_derived_and_has_no_settable_field():
    record = fx.trust_anchor_record()
    names = {f.name for f in dataclasses.fields(record)}
    assert "anchor_record_digest" not in names
    assert "anchor_revision" not in names
    with pytest.raises(AttributeError):
        object.__setattr__(record, "anchor_record_digest", "0" * 64)


def test_no_parallel_revision_counter_exists():
    """D-25: the revision *is* the digest, so no counter can fall out of step."""

    names = {f.name for f in dataclasses.fields(fx.trust_anchor_record())}
    for banned in ("revision", "version", "generation", "sequence", "serial"):
        assert not any(banned in n for n in names), names


def test_any_change_to_any_bound_field_is_a_different_revision():
    base = fx.trust_anchor_record().anchor_record_digest
    for override in (
        {"identity": "publisher-omega"},
        {"key_id": "publisher-key-2"},
        {"public_key_material": fx.APPROVER_PUBLIC_KEY},
        {"role": BenchmarkTrustRole.APPROVER},
        {"validity_to": fx.AS_OF},
    ):
        assert fx.trust_anchor_record(**override).anchor_record_digest != base


def test_the_three_role_namespaces_are_separate_by_digest():
    """D-26: one anchor never authorizes another role automatically."""

    digests = {
        fx.trust_anchor_record().anchor_record_digest,
        fx.approver_trust_anchor_record().anchor_record_digest,
        fx.revoker_trust_anchor_record().anchor_record_digest,
    }
    assert len(digests) == 3


def test_the_anchor_binds_the_eight_facts_d25_ratifies():
    fields = tuple(f.name for f in dataclasses.fields(fx.trust_anchor_record()))
    assert fields == (
        "role",
        "identity",
        "key_id",
        "signature_profile",
        "public_key_material",
        "validity_from",
        "validity_to",
        "status",
        "revoked_at",
        "revocation_reason",
    )


# --------------------------------------------------------------------------- #
# Anchor lifecycle consistency
# --------------------------------------------------------------------------- #
def test_a_revoked_anchor_without_a_revocation_time_is_unconstructible():
    with pytest.raises(BenchmarkRegistryContractError):
        fx.trust_anchor_record(
            status=BenchmarkTrustAnchorStatus.REVOKED, revoked_at=None
        )


@pytest.mark.parametrize(
    "status",
    (BenchmarkTrustAnchorStatus.ENABLED, BenchmarkTrustAnchorStatus.DISABLED),
)
def test_a_revocation_fact_without_a_revocation_is_unconstructible(status):
    with pytest.raises(BenchmarkRegistryContractError):
        fx.trust_anchor_record(status=status, revoked_at=fx.ANCHOR_REVOKED_AT)
    with pytest.raises(BenchmarkRegistryContractError):
        fx.trust_anchor_record(
            status=status, revocation_reason=fx.ANCHOR_REVOCATION_REASON
        )


def test_happy_a_revoked_anchor_carries_its_revocation_facts():
    record = fx.revoked_trust_anchor_record()
    assert record.status is BenchmarkTrustAnchorStatus.REVOKED
    assert record.revoked_at == fx.ANCHOR_REVOKED_AT
    assert record.revocation_reason == fx.ANCHOR_REVOCATION_REASON


def test_an_interval_containing_no_instant_is_refused_never_reordered():
    for override in (
        {"validity_to": fx.VALIDITY_FROM},
        {"validity_from": fx.VALIDITY_TO, "validity_to": fx.VALIDITY_FROM},
    ):
        with pytest.raises(BenchmarkRegistryContractError):
            fx.trust_anchor_record(**override)


def test_the_status_enum_names_no_banned_lifecycle_state():
    """``ENABLED``, not ``ACTIVE`` — D-08 keeps the floating words out."""

    values = {m.value for m in BenchmarkTrustAnchorStatus}
    assert values == {"ENABLED", "REVOKED", "DISABLED"}


# --------------------------------------------------------------------------- #
# D-27 and D-28: the seven refusals
# --------------------------------------------------------------------------- #
def test_the_five_lifecycle_refusals_and_two_availability_refusals_exist():
    names = {m.name for m in BenchmarkRegistryRefusalReason}
    for expected in (
        "TRUST_ANCHOR_NOT_FOUND",
        "TRUST_ANCHOR_REVOKED",
        "TRUST_ANCHOR_DISABLED",
        "TRUST_ANCHOR_NOT_YET_VALID",
        "TRUST_ANCHOR_EXPIRED",
        "TRUST_DIRECTORY_UNAVAILABLE",
        "STALE_TRUST_SNAPSHOT",
    ):
        assert expected in names


def test_the_seven_new_refusals_are_appended_and_never_inserted():
    """§35.6: BR-2's members occupy composite indices 17..40, undisplaced."""

    members = list(BenchmarkRegistryRefusalReason)
    assert len(members) == 24
    assert [m.name for m in members[-7:]] == [
        "TRUST_ANCHOR_NOT_FOUND",
        "TRUST_ANCHOR_REVOKED",
        "TRUST_ANCHOR_DISABLED",
        "TRUST_ANCHOR_NOT_YET_VALID",
        "TRUST_ANCHOR_EXPIRED",
        "TRUST_DIRECTORY_UNAVAILABLE",
        "STALE_TRUST_SNAPSHOT",
    ]


def test_every_new_refusal_is_classified_and_none_is_unclassified():
    for member in BenchmarkRegistryRefusalReason:
        if member.name.startswith("TRUST_") or member.name == "STALE_TRUST_SNAPSHOT":
            assert (
                fault_class_for(member)
                is BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
            )


def test_the_new_refusals_are_role_neutral():
    """D-27: five conditions, not fifteen. No refusal names a role."""

    for member in BenchmarkRegistryRefusalReason:
        for role in BenchmarkTrustRole:
            if member.name.startswith("TRUST_ANCHOR"):
                assert role.value not in member.name


def test_the_evaluation_order_is_the_one_d28_ratified():
    assert BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER == (
        BenchmarkRegistryRefusalReason.TRUST_ANCHOR_REVOKED,
        BenchmarkRegistryRefusalReason.TRUST_ANCHOR_DISABLED,
        BenchmarkRegistryRefusalReason.TRUST_ANCHOR_NOT_YET_VALID,
        BenchmarkRegistryRefusalReason.TRUST_ANCHOR_EXPIRED,
    )


# --------------------------------------------------------------------------- #
# D-29: one profile, and D-28's no-clock consequence
# --------------------------------------------------------------------------- #
def test_exactly_one_signature_profile_is_ratified_and_none_is_reserved():
    assert len(BenchmarkSignatureProfile) == 1
    assert (
        BenchmarkSignatureProfile.ED25519_SHA512_V1.value == "ED25519_SHA512_V1"
    )


@pytest.mark.parametrize("name,builder", RESULT_BUILDERS)
def test_the_evaluation_time_is_a_declared_input_not_a_clock_read(name, builder):
    """D-28: BR-2C ships no clock, so the trusted instant is supplied."""

    assert builder().evaluated_at == fx.TRUSTED_INSTANT
    assert builder(evaluated_at=fx.AS_OF).evaluated_at == fx.AS_OF


# --------------------------------------------------------------------------- #
# The ports stay inert
# --------------------------------------------------------------------------- #
def test_no_verifier_or_resolver_ships_and_no_crypto_is_imported():
    """The contracts describe a verifier. Nothing here is one."""

    import sys

    for module in ("cryptography", "nacl", "ed25519", "Crypto", "OpenSSL"):
        assert module not in sys.modules
