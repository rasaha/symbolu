"""Two refusal vocabularies, provably disjoint, BR-1's frozen prefix in order."""

from __future__ import annotations

import pytest

from ugence_benchmark_registry import (
    BR1_BENCHMARK_REFUSAL_REASONS,
    BenchmarkRefusalReason,
)
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS,
    BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES,
    BENCHMARK_REGISTRY_REFUSAL_REASONS,
    BenchmarkRegistryContractError,
    BenchmarkRegistryFaultClass,
    BenchmarkRegistryRefusalReason,
    fault_class_for,
)

REQUIRED_MEMBERS = (
    "IDEMPOTENT_DUPLICATE",
    "COORDINATE_SLOT_CONFLICT",
    "DIGEST_ALREADY_BOUND",
    "CONFUSABLE_COORDINATE",
    "LIFECYCLE_CONFLICT",
    "UNAUTHORIZED_TRANSITION",
    "UNSUPPORTED_SUPERSESSION",
    "STALE_REGISTRY_SNAPSHOT",
    "STORE_INTEGRITY_INVALID",
    "STORE_UNAVAILABLE",
    "NO_TRUST_ANCHOR_CONFIGURED",
    "PUBLISHER_UNTRUSTED",
    "SIGNATURE_INVALID",
    "APPROVAL_UNVERIFIED",
    "NOT_FOUND",
    "NOT_ADMITTED",
    "INDETERMINATE",
)


def test_happy_every_ratified_member_exists():
    names = {r.name for r in BenchmarkRegistryRefusalReason}
    assert set(REQUIRED_MEMBERS) <= names


def test_the_br1_enum_is_not_modified_or_extended():
    assert len(BenchmarkRefusalReason) == 17
    assert frozenset(BenchmarkRefusalReason) == BR1_BENCHMARK_REFUSAL_REASONS


def test_the_composite_prefix_is_br1_declaration_order_not_frozenset_order():
    prefix = BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS[: len(BenchmarkRefusalReason)]
    assert prefix == tuple(BenchmarkRefusalReason)


def test_the_composite_prefix_and_the_frozen_set_cannot_drift():
    prefix = BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS[: len(BenchmarkRefusalReason)]
    assert frozenset(prefix) == BR1_BENCHMARK_REFUSAL_REASONS


def test_the_composite_suffix_is_br2_declaration_order():
    suffix = BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS[len(BenchmarkRefusalReason) :]
    assert suffix == tuple(BenchmarkRegistryRefusalReason)


def test_br2_members_never_displace_a_br1_index():
    for index, member in enumerate(BenchmarkRefusalReason):
        assert BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS[index] is member


def test_the_two_vocabularies_share_no_member():
    assert not (
        set(BenchmarkRefusalReason) & set(BenchmarkRegistryRefusalReason)
    )


def test_the_two_vocabularies_share_no_value():
    br1 = {r.value for r in BenchmarkRefusalReason}
    br2 = {r.value for r in BenchmarkRegistryRefusalReason}
    assert not (br1 & br2)


def test_no_alias_exists_in_either_direction():
    """No lookup helper accepts one vocabulary and returns the other's member."""

    for member in BenchmarkRefusalReason:
        with pytest.raises(BenchmarkRegistryContractError):
            fault_class_for(member)


def test_a_bare_string_spelling_of_a_br2_member_is_not_classified():
    with pytest.raises(BenchmarkRegistryContractError):
        fault_class_for("NOT_FOUND")


def test_the_fault_class_mapping_is_total_over_the_br2_enum():
    assert set(BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES) == set(
        BenchmarkRegistryRefusalReason
    )
    for member in BenchmarkRegistryRefusalReason:
        assert isinstance(fault_class_for(member), BenchmarkRegistryFaultClass)


def test_exactly_seven_fault_classes_exist_and_all_are_used():
    assert len(BenchmarkRegistryFaultClass) == 7
    used = set(BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES.values())
    assert used == set(BenchmarkRegistryFaultClass)


def test_every_unknown_condition_fails_closed():
    assert fault_class_for(
        BenchmarkRegistryRefusalReason.INDETERMINATE
    ) is BenchmarkRegistryFaultClass.INDETERMINATE


def test_the_fault_class_mapping_is_immutable():
    with pytest.raises(TypeError):
        BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES[
            BenchmarkRegistryRefusalReason.NOT_FOUND
        ] = BenchmarkRegistryFaultClass.IDEMPOTENCE


def test_every_member_is_a_refusal_including_the_idempotent_one():
    """IDEMPOTENT_DUPLICATE reports that nothing new was registered."""

    assert (
        fault_class_for(BenchmarkRegistryRefusalReason.IDEMPOTENT_DUPLICATE)
        is BenchmarkRegistryFaultClass.IDEMPOTENCE
    )
    names = {r.name for r in BenchmarkRegistryRefusalReason}
    for success_word in ("OK", "SUCCESS", "ADMITTED_OK", "RESOLVED", "VALID"):
        assert success_word not in names


def test_the_reason_sets_are_the_expected_sizes():
    assert len(BENCHMARK_REGISTRY_REFUSAL_REASONS) == 24
    assert len(BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS) == 41


def test_no_br2_member_is_prefixed_benchmark_like_a_br1_member():
    for member in BenchmarkRegistryRefusalReason:
        assert not member.value.startswith("BENCHMARK_")
