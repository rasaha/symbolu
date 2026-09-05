"""D-42's key-identifier grammar and D-43's actor-identity grammar, applied.

Both rulings pin one pattern, ``^[a-z0-9](?:[a-z0-9._-]{0,126}[a-z0-9])?$``, and
bind it to key identifiers (D-42) and actor identities (D-43) and to nothing
else: ``applicable_policy_ref`` keeps its ``/`` and ``declared_revocation_reason``
stays free text. Every malformation refuses as ``INDETERMINATE`` (D-42), at
construction, so the confusable class is unrepresentable rather than detected.
"""

from __future__ import annotations

import pytest

import _builders as fx
from ugence_benchmark_registry_authority.api import (
    BenchmarkRegistryContractError,
    BenchmarkRegistryRefusalReason,
)
from ugence_benchmark_registry_authority.contracts._validation import (
    require_actor_identity,
    require_identifier,
    require_key_identifier,
)

GRAMMAR_VALIDATORS = (require_key_identifier, require_actor_identity)

#: Every value in the ratified grammar this suite relies on, plus the edges.
ADMISSIBLE = (
    "a",
    "7",
    "publisher-key-1",
    "approval.key_2",
    "latest",  # D-42: the floating-token ban is deliberately not carried over
    "a" * 128,
    "a" + "-" * 126 + "z",
)

#: One example per malformation class D-42 names, and the near misses.
MALFORMED = (
    "Publisher-Key-1",  # uppercase
    "publisher key 1",  # interior whitespace
    "-publisher-key",  # leading separator
    "publisher-key-",  # trailing separator
    ".",  # a lone separator
    "kеy-1",  # Cyrillic е, NFC-stable and confusable
    "a" * 129,  # one over the bound
    "key/1",  # the path character applicable_policy_ref is allowed
    "key:1",
    "",
)


@pytest.mark.parametrize("value", ADMISSIBLE)
@pytest.mark.parametrize("validator", GRAMMAR_VALIDATORS)
def test_happy_the_ratified_grammar_admits_its_own_language(validator, value):
    assert validator(value, "field") == value


@pytest.mark.parametrize("value", MALFORMED)
@pytest.mark.parametrize("validator", GRAMMAR_VALIDATORS)
def test_every_malformation_refuses_as_indeterminate(validator, value):
    with pytest.raises(BenchmarkRegistryContractError) as caught:
        validator(value, "field")
    assert caught.value.reason is BenchmarkRegistryRefusalReason.INDETERMINATE


@pytest.mark.parametrize("value", [None, 7, b"key", ["key"], True, " key ", "keý"])
@pytest.mark.parametrize("validator", GRAMMAR_VALIDATORS)
def test_the_canonical_string_disciplines_still_apply_first(validator, value):
    with pytest.raises(BenchmarkRegistryContractError) as caught:
        validator(value, "field")
    assert caught.value.reason is BenchmarkRegistryRefusalReason.INDETERMINATE


def test_a_str_subclass_is_refused_even_when_its_text_conforms():
    class Sneaky(str):
        pass

    for validator in GRAMMAR_VALIDATORS:
        with pytest.raises(BenchmarkRegistryContractError):
            validator(Sneaky("publisher-key-1"), "field")


def test_the_bare_identifier_rule_is_untouched():
    """D-42: a separate validator, not a tightening of the shared one."""

    for value in ("benchmark-approval-policy/v1", "Content Defect", "kеy-1"):
        assert require_identifier(value, "field") == value
        for validator in GRAMMAR_VALIDATORS:
            with pytest.raises(BenchmarkRegistryContractError):
                validator(value, "field")


# --------------------------------------------------------------------------- #
# The sites D-42 and D-43 name, and only those
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "builder,field",
    [
        (fx.publisher_envelope, "publisher_key_id"),
        (fx.publisher_envelope, "publisher_identity"),
        (fx.approval_envelope, "approval_authority_key_id"),
        (fx.approval_envelope, "approval_authority_identity"),
        (fx.revocation_envelope, "revoker_key_id"),
        (fx.revocation_envelope, "revoker_identity"),
        (fx.trust_anchor_record, "key_id"),
        (fx.trust_anchor_record, "identity"),
        (fx.trust_anchor_resolution, "key_id"),
        (fx.trust_anchor_resolution, "identity"),
        (fx.publisher_verified_result, "signer_key_id"),
        (fx.publisher_verified_result, "signer_identity"),
        (fx.approval_verified_result, "signer_key_id"),
        (fx.revocation_verified_result, "signer_identity"),
        (fx.submission_record, "declared_registry_authority_identity"),
        (fx.resolution_record, "declared_registry_authority_identity"),
        (fx.historical_record, "declared_registry_authority_identity"),
    ],
)
def test_every_key_identifier_and_actor_identity_field_enforces_the_grammar(
    builder, field
):
    for bad in ("Publisher-Alpha", "publisher alpha", "-x", "kеy-1", "a" * 129):
        with pytest.raises(BenchmarkRegistryContractError) as caught:
            builder(**{field: bad})
        assert caught.value.reason is BenchmarkRegistryRefusalReason.INDETERMINATE


def test_a_homoglyph_pair_can_no_longer_satisfy_actor_separation():
    """D-43's ground: the pair is unrepresentable, so it never reaches the check."""

    with pytest.raises(BenchmarkRegistryContractError):
        fx.approval_envelope(approval_authority_identity="publisher-alphа")  # Cyrillic а
    # The genuine one-character-apart pair still exercises distinctness.
    assert fx.approval_envelope(approval_authority_identity="publisher-alphb")


def test_the_fields_d43_leaves_alone_are_left_alone():
    assert fx.approval_envelope(applicable_policy_ref="benchmark-approval-policy/v1")
    assert fx.approval_envelope(applicable_policy_ref="Policy Ref With Spaces")
    assert fx.revocation_envelope(declared_revocation_reason="Content defect: see ticket #7")


def test_the_pinned_fixture_identities_all_conform_so_no_vector_moved():
    for value in (
        fx.PUBLISHER_IDENTITY, fx.PUBLISHER_KEY_ID, fx.APPROVAL_AUTHORITY_IDENTITY,
        fx.APPROVAL_AUTHORITY_KEY_ID, fx.REGISTRY_AUTHORITY_IDENTITY,
        fx.REVOKER_IDENTITY, fx.REVOKER_KEY_ID,
    ):
        assert require_key_identifier(value, "fixture") == value
