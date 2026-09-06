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
    BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS,
    BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES,
    BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER,
    BENCHMARK_VERIFICATION_REFUSAL_REASONS,
    BENCHMARK_VERIFIED_RESULT_BOUND_FACTS,
    BenchmarkApprovalVerifiedResult,
    BenchmarkPublisherVerifiedResult,
    BenchmarkRegistryContractError,
    BenchmarkRegistryFaultClass,
    BenchmarkRegistryRefusalReason,
    BenchmarkRevocationVerifiedResult,
    BenchmarkSignatureProfile,
    BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES,
    BenchmarkPublisherTrustDirectoryPort,
    BenchmarkRegistryCanonicalizationError,
    BenchmarkTrustAnchorRecord,
    BenchmarkTrustAnchorResolution,
    BenchmarkTrustAnchorStatus,
    BenchmarkTrustRole,
    BenchmarkVerificationOutcome,
    canonical_bytes,
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
def test_no_contract_module_imports_cryptography_and_no_contract_verifies():
    """The contracts describe a verifier. None of them is one.

    The candidate verifier lives in ``verifier.py`` and imports the D-41 pair
    there (D-40 as applied to the candidate rung). The ``contracts`` subpackage
    stays exactly as it was: no cryptographic import, no curve operation, no
    port satisfied. Measured on the import graph rather than ``sys.modules``,
    because the curated surface now legitimately imports the verifier.
    """

    import ast
    import pathlib

    contracts = pathlib.Path(__file__).resolve().parents[2] / "src" / (
        "ugence_benchmark_registry_authority"
    ) / "contracts"
    for path in sorted(contracts.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = {node.module.split(".")[0]}
            else:
                continue
            assert not roots & {"cryptography", "nacl", "ed25519", "Crypto", "OpenSSL"}, (
                path.name, roots
            )
    import ugence_benchmark_registry_authority.contracts as contracts_pkg

    for name in dir(contracts_pkg):
        value = getattr(contracts_pkg, name)
        if isinstance(value, type) and not getattr(value, "_is_protocol", False):
            assert not hasattr(value, "verify_publisher_submission"), name


# --------------------------------------------------------------------------- #
# D-34: the anchor-resolution outcome — record XOR typed refusal
# --------------------------------------------------------------------------- #
def test_the_seam_returns_a_resolution_and_not_an_optional_record():
    """D-34: the annotation itself is the ruling's surface."""

    import typing

    hints = typing.get_type_hints(
        BenchmarkPublisherTrustDirectoryPort.resolve_anchor
    )
    assert hints["return"] is BenchmarkTrustAnchorResolution
    assert typing.get_origin(hints["return"]) is None


def test_happy_a_resolution_carries_the_record_it_resolved():
    resolution = fx.trust_anchor_resolution()
    record = fx.trust_anchor_record()
    assert resolution.anchor == record
    assert resolution.refusal_reason is None
    assert (resolution.role, resolution.identity, resolution.key_id) == (
        record.role,
        record.identity,
        record.key_id,
    )


def test_happy_a_resolution_carries_a_refusal_instead_of_a_record():
    resolution = fx.refused_trust_anchor_resolution()
    assert resolution.anchor is None
    assert (
        resolution.refusal_reason
        is BenchmarkRegistryRefusalReason.TRUST_ANCHOR_NOT_FOUND
    )


def test_a_resolution_carrying_both_a_record_and_a_refusal_is_unconstructible():
    """A resolved refusal. Neither field alone would answer the caller."""

    with pytest.raises(BenchmarkRegistryContractError) as raised:
        fx.trust_anchor_resolution(
            refusal_reason=BenchmarkRegistryRefusalReason.TRUST_ANCHOR_NOT_FOUND
        )
    assert "exactly one of an anchor record" in str(raised.value)


def test_a_resolution_carrying_neither_is_unconstructible():
    """The other direction: the untyped silence D-34 removed."""

    with pytest.raises(BenchmarkRegistryContractError) as raised:
        fx.trust_anchor_resolution(anchor=None, refusal_reason=None)
    assert "exactly one of an anchor record" in str(raised.value)


def test_there_is_no_boolean_success_flag_on_a_resolution():
    """D-24 removed Booleans from these seams; none returns through this one."""

    fields = [f.name for f in dataclasses.fields(BenchmarkTrustAnchorResolution)]
    assert fields == ["role", "identity", "key_id", "anchor", "refusal_reason"]
    for name in fields:
        value = getattr(fx.trust_anchor_resolution(), name)
        assert not isinstance(value, bool), name


def test_neither_half_of_the_exclusive_or_carries_a_default():
    """The unset half is written at every call site, never defaulted."""

    for name in ("anchor", "refusal_reason"):
        field = next(
            f
            for f in dataclasses.fields(BenchmarkTrustAnchorResolution)
            if f.name == name
        )
        assert field.default is dataclasses.MISSING, name
        assert field.default_factory is dataclasses.MISSING, name


@pytest.mark.parametrize(
    "field,value",
    [
        ("role", BenchmarkTrustRole.REVOKER),
        ("identity", "some-other-identity"),
        ("key_id", "some-other-key-id"),
    ],
)
def test_a_resolver_may_not_answer_a_question_it_was_not_asked(field, value):
    """The asked triple and the answered record must agree in all three parts."""

    with pytest.raises(BenchmarkRegistryContractError) as raised:
        fx.trust_anchor_resolution(**{field: value})
    assert "a different" in str(raised.value)
    assert field in str(raised.value)


def test_the_role_is_part_of_the_question_not_inferred_from_the_record():
    """D-26: a shared physical directory never infers the namespace."""

    with pytest.raises(BenchmarkRegistryContractError):
        fx.trust_anchor_resolution(
            anchor=fx.approver_trust_anchor_record(),
            role=BenchmarkTrustRole.PUBLISHER,
        )


@pytest.mark.parametrize(
    "reason",
    [
        BenchmarkRegistryRefusalReason.TRUST_ANCHOR_NOT_FOUND,
        BenchmarkRegistryRefusalReason.TRUST_DIRECTORY_UNAVAILABLE,
    ],
)
def test_the_two_admissible_refusals_are_exactly_the_no_record_conditions(reason):
    """D-28 needs these two separable; a bare None could not tell them apart."""

    assert fx.refused_trust_anchor_resolution(refusal_reason=reason).anchor is None


@pytest.mark.parametrize(
    "reason",
    [
        r
        for r in BenchmarkRegistryRefusalReason
        if r
        not in (
            BenchmarkRegistryRefusalReason.TRUST_ANCHOR_NOT_FOUND,
            BenchmarkRegistryRefusalReason.TRUST_DIRECTORY_UNAVAILABLE,
        )
    ],
)
def test_every_other_refusal_member_is_refused_by_a_resolution(reason):
    """Including all four lifecycle refusals: this seam evaluates nothing."""

    with pytest.raises(BenchmarkRegistryContractError) as raised:
        fx.refused_trust_anchor_resolution(refusal_reason=reason)
    assert "is not one a resolution may carry" in str(raised.value)


def test_the_four_lifecycle_refusals_belong_to_the_verification_seam():
    """D-27's distinctions survive because the resolver never evaluates them."""

    for reason in BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER:
        with pytest.raises(BenchmarkRegistryContractError):
            fx.refused_trust_anchor_resolution(refusal_reason=reason)


def test_a_resolution_returns_a_revoked_anchor_as_it_stands():
    """It filters nothing: the record arrives with its own status intact."""

    revoked = fx.revoked_trust_anchor_record()
    resolution = fx.trust_anchor_resolution(anchor=revoked)
    assert resolution.anchor.status is BenchmarkTrustAnchorStatus.REVOKED
    assert resolution.refusal_reason is None


def test_a_resolution_takes_no_trusted_instant():
    """D-25 and D-27: an instant here would collapse the four distinctions."""

    names = [f.name for f in dataclasses.fields(BenchmarkTrustAnchorResolution)]
    for banned in ("at", "instant", "time", "now"):
        assert not any(banned in n for n in names), banned


def test_only_an_exact_anchor_record_may_be_carried():
    """Not a subclass, and not something that merely looks like one.

    Built directly rather than through the fixture: the fixture reads the triple
    off the record, so it cannot reach the constructor with a non-record.
    """

    record = fx.trust_anchor_record()

    class Subclassed(BenchmarkTrustAnchorRecord):
        pass

    for impostor in (
        object(),
        Subclassed(**dataclasses.asdict(record)),
        dataclasses.asdict(record),
    ):
        with pytest.raises(BenchmarkRegistryContractError):
            BenchmarkTrustAnchorResolution(
                role=record.role,
                identity=record.identity,
                key_id=record.key_id,
                anchor=impostor,
                refusal_reason=None,
            )


def test_a_resolution_establishes_no_authority_even_carrying_a_record():
    """§09's five derivations, on a resolution that did resolve something."""

    resolution = fx.trust_anchor_resolution()
    for prop in BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES:
        assert getattr(resolution, prop) is False, prop


def test_a_resolution_is_not_canonicalizable_and_mints_no_domain():
    """D-34's least obvious clause, asserted rather than assumed.

    Deliberately unsealed: §05 forbids byte space an artifact does not need, and
    D-25 makes the anchor record's own digest the sole anchor revision, so a
    second digest over the resolution carrying it would be a competing identity
    for one fact. The encoder refuses it, which is the enforcement.
    """

    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(fx.trust_anchor_resolution())
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_digest(fx.trust_anchor_resolution())
    assert not hasattr(fx.trust_anchor_resolution(), "anchor_record_digest")


# --------------------------------------------------------------------------- #
# D-35: which refusals a verified result may carry — twelve of the twenty-four
# --------------------------------------------------------------------------- #
#: The nine excluded members that are **registry-state facts**. Named here, not
#: derived, because the point of the list is that a phase §35.1 forbids to ship
#: "any registry state whatsoever" cannot establish any of them, and that claim
#: should be readable rather than computed.
REGISTRY_STATE_REFUSALS = (
    "IDEMPOTENT_DUPLICATE",
    "COORDINATE_SLOT_CONFLICT",
    "DIGEST_ALREADY_BOUND",
    "CONFUSABLE_COORDINATE",
    "LIFECYCLE_CONFLICT",
    "UNAUTHORIZED_TRANSITION",
    "STALE_REGISTRY_SNAPSHOT",
    "STORE_INTEGRITY_INVALID",
    "STORE_UNAVAILABLE",
)

#: The other three exclusions, each on its own ground rather than on registry
#: state: D-10 puts supersession out of BR-2's scope entirely, and D-27 places
#: the non-disclosure collapse at a later external read boundary.
SCOPE_AND_READ_REFUSALS = (
    "UNSUPPORTED_SUPERSESSION",
    "NOT_FOUND",
    "NOT_ADMITTED",
)


def test_happy_the_subset_is_twelve_of_the_twenty_four():
    assert len(BenchmarkRegistryRefusalReason) == 24
    assert len(BENCHMARK_VERIFICATION_REFUSAL_REASONS) == 12
    assert len(set(BENCHMARK_VERIFICATION_REFUSAL_REASONS)) == 12


def test_the_subset_is_derived_from_the_fault_class_map_not_written_out():
    """D-35's load-bearing mechanic, asserted rather than trusted.

    A hand-copied list of twelve is the subtractive option D-35 closed: it must
    be re-edited by hand every time §35.6 appends a member, and an author who
    forgets leaves a ratified member silently inadmissible. Recomputing the
    derivation here from the map means this test fails if someone replaces the
    comprehension with a literal that has since drifted.
    """

    derived = tuple(
        reason
        for reason in BenchmarkRegistryRefusalReason
        if BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES[reason]
        in (
            BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY,
            BenchmarkRegistryFaultClass.INDETERMINATE,
        )
    )
    assert BENCHMARK_VERIFICATION_REFUSAL_REASONS == derived


def test_the_next_appended_member_classifies_itself_in_or_out():
    """Every member has a class, so the derivation can miss none of them.

    D-27 and D-28 require the classification to be total; that totality is what
    makes deriving safe where a literal would not be.
    """

    for reason in BenchmarkRegistryRefusalReason:
        assert reason in BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES, reason.name
        assert (
            reason in BENCHMARK_VERIFICATION_REFUSAL_REASONS
        ) is (
            fault_class_for(reason)
            in (
                BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY,
                BenchmarkRegistryFaultClass.INDETERMINATE,
            )
        ), reason.name


def test_the_subset_preserves_declaration_order():
    """§22.13 sorts refusals by declaration index; a set would lose that."""

    members = list(BenchmarkRegistryRefusalReason)
    positions = [members.index(r) for r in BENCHMARK_VERIFICATION_REFUSAL_REASONS]
    assert positions == sorted(positions)


def test_the_eleven_trust_members_and_indeterminate_are_exactly_the_subset():
    trust = [
        r
        for r in BenchmarkRegistryRefusalReason
        if fault_class_for(r) is BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
    ]
    assert len(trust) == 11
    assert set(BENCHMARK_VERIFICATION_REFUSAL_REASONS) == set(trust) | {
        BenchmarkRegistryRefusalReason.INDETERMINATE
    }


def test_indeterminate_is_in_the_subset_without_being_in_the_trust_class():
    """D-35 rules it in explicitly; the class alone would have excluded it."""

    indeterminate = BenchmarkRegistryRefusalReason.INDETERMINATE
    assert (
        fault_class_for(indeterminate)
        is BenchmarkRegistryFaultClass.INDETERMINATE
    )
    assert (
        fault_class_for(indeterminate)
        is not BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
    )
    assert indeterminate in BENCHMARK_VERIFICATION_REFUSAL_REASONS


@pytest.mark.parametrize("name,builder", RESULT_BUILDERS)
@pytest.mark.parametrize(
    "reason", BENCHMARK_VERIFICATION_REFUSAL_REASONS, ids=lambda r: r.name
)
def test_every_admissible_reason_constructs_on_every_result_type(
    name, builder, reason
):
    result = builder(
        outcome=BenchmarkVerificationOutcome.REFUSED,
        refusal_reason=reason,
        anchor_record_digest=None,
    )
    assert result.refusal_reason is reason
    assert result.outcome is BenchmarkVerificationOutcome.REFUSED


@pytest.mark.parametrize("name,builder", RESULT_BUILDERS)
@pytest.mark.parametrize(
    "reason",
    [
        r
        for r in BenchmarkRegistryRefusalReason
        if r not in BENCHMARK_VERIFICATION_REFUSAL_REASONS
    ],
    ids=lambda r: r.name,
)
def test_every_excluded_reason_is_refused_on_every_result_type(
    name, builder, reason
):
    with pytest.raises(BenchmarkRegistryContractError) as raised:
        builder(
            outcome=BenchmarkVerificationOutcome.REFUSED,
            refusal_reason=reason,
            anchor_record_digest=None,
        )
    assert "is not one a verified result may carry" in str(raised.value)
    assert reason.value in str(raised.value)


def test_the_twelve_excluded_are_exactly_the_nine_plus_three_and_no_others():
    """Both exclusion grounds enumerated, so neither can quietly grow."""

    excluded = {
        r.name
        for r in BenchmarkRegistryRefusalReason
        if r not in BENCHMARK_VERIFICATION_REFUSAL_REASONS
    }
    assert excluded == set(REGISTRY_STATE_REFUSALS) | set(SCOPE_AND_READ_REFUSALS)
    assert len(excluded) == 12


@pytest.mark.parametrize("name", REGISTRY_STATE_REFUSALS)
def test_a_registry_state_refusal_cannot_reach_a_verified_result(name):
    """§35.1: BR-2C ships no storage and no registry state whatsoever."""

    reason = BenchmarkRegistryRefusalReason[name]
    assert fault_class_for(reason) in (
        BenchmarkRegistryFaultClass.IDEMPOTENCE,
        BenchmarkRegistryFaultClass.COORDINATE_CONFLICT,
        BenchmarkRegistryFaultClass.LIFECYCLE_INTEGRITY,
        BenchmarkRegistryFaultClass.STORE_INTEGRITY,
    )
    with pytest.raises(BenchmarkRegistryContractError):
        fx.refused_publisher_verified_result(refusal_reason=reason)


def test_supersession_is_excluded_on_d10_scope_and_not_on_registry_state():
    reason = BenchmarkRegistryRefusalReason.UNSUPPORTED_SUPERSESSION
    assert (
        fault_class_for(reason) is BenchmarkRegistryFaultClass.LIFECYCLE_INTEGRITY
    )
    with pytest.raises(BenchmarkRegistryContractError):
        fx.refused_publisher_verified_result(refusal_reason=reason)


@pytest.mark.parametrize("name", ["NOT_FOUND", "NOT_ADMITTED"])
def test_the_read_vocabulary_never_enters_a_verification_result(name):
    """D-27 puts the non-disclosure collapse at an external read boundary."""

    reason = BenchmarkRegistryRefusalReason[name]
    assert (
        fault_class_for(reason) is BenchmarkRegistryFaultClass.READ_NON_DISCLOSURE
    )
    with pytest.raises(BenchmarkRegistryContractError):
        fx.refused_publisher_verified_result(refusal_reason=reason)


def test_the_four_lifecycle_refusals_stay_admissible_on_a_verified_result():
    """D-27's distinctions land here — this is the seam that evaluates them."""

    for reason in BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER:
        assert reason in BENCHMARK_VERIFICATION_REFUSAL_REASONS
        result = fx.refused_publisher_verified_result(refusal_reason=reason)
        assert result.refusal_reason is reason


def test_the_resolution_seams_two_refusals_are_a_subset_of_the_verification_twelve():
    """D-34's two are among D-35's twelve, so a refusal survives the handoff."""

    for name in ("TRUST_ANCHOR_NOT_FOUND", "TRUST_DIRECTORY_UNAVAILABLE"):
        assert (
            BenchmarkRegistryRefusalReason[name]
            in BENCHMARK_VERIFICATION_REFUSAL_REASONS
        )


def test_this_row_adds_no_member_and_moves_no_refusal_count():
    """D-35 narrows a constructor; §35.6's append-only guarantee is untouched."""

    assert len(BenchmarkRegistryRefusalReason) == 24
    assert len(BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS) == 41
    assert len(BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES) == 24


def test_a_verified_outcome_still_carries_no_reason_at_all():
    """The biconditional's other half is unchanged by the narrowing."""

    for reason in BENCHMARK_VERIFICATION_REFUSAL_REASONS:
        with pytest.raises(BenchmarkRegistryContractError):
            fx.publisher_verified_result(
                outcome=BenchmarkVerificationOutcome.VERIFIED,
                refusal_reason=reason,
            )
