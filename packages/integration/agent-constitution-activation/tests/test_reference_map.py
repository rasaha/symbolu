"""`ACC-IA-3` — entries derive from an issued record, and from nothing else.

The function's signature is half the proof: there is no parameter through which
a caller could hand it an entry, a key, a coordinate or a role list. These
tests prove the other half — what is derived, what is refused, and that a
conflicting or malformed prior map fails closed before anything merges.
"""

from __future__ import annotations

import dataclasses

import pytest
from _activation_fixtures import (
    GLOBAL_TENANT,
    GOVERNED_ROLE_REF,
    T_ISSUE,
    coordinate_of,
    make_first_constitution,
    make_world,
)
from ugence_agent_constitution_activation import (
    ActivationRequestError,
    ReferenceMapConflictError,
    ReferenceMapDerivationError,
    populate_reference_map,
)
from ugence_policy_authority.api import PolicyCoordinate


@pytest.fixture(scope="module")
def issued():
    world = make_world()
    policy, receipt = world.issue_first_constitution()
    record = world.registry.get_issued(receipt.coordinate)
    return world, policy, record


def test_one_entry_derives_per_governed_role_reference(issued):
    world, policy, record = issued
    mapping = populate_reference_map(record=record, adapters=world.root._adapters)
    assert dict(mapping) == {
        (GLOBAL_TENANT, GOVERNED_ROLE_REF): record.coordinate
    }


def test_a_multi_role_constitution_yields_one_entry_each(issued):
    world, _, _ = issued
    other_ref = "ugence.roles/ugence/other-governed/v1"
    # A distinct version: the module-scoped registry already holds 1.0.0, and a
    # version identity is never reusable with different content.
    policy = make_first_constitution(
        governed_role_refs=tuple(sorted((GOVERNED_ROLE_REF, other_ref))),
        version="1.1.0",
    )
    receipt = world.root.issue_constitution(
        policy=policy,
        record_id="rec-two-roles",
        approval=world.evidence,
        issued_at=T_ISSUE,
    )
    record = world.registry.get_issued(receipt.coordinate)
    mapping = populate_reference_map(record=record, adapters=world.root._adapters)
    assert set(mapping) == {
        (GLOBAL_TENANT, GOVERNED_ROLE_REF),
        (GLOBAL_TENANT, other_ref),
    }
    assert set(mapping.values()) == {record.coordinate}


def test_the_returned_mapping_is_read_only_and_detached(issued):
    world, _, record = issued
    existing = {}
    mapping = populate_reference_map(
        record=record, adapters=world.root._adapters, existing=existing
    )
    with pytest.raises(TypeError):
        mapping[(GLOBAL_TENANT, "injected")] = record.coordinate
    assert existing == {}, "the caller's mapping was mutated"


def test_a_loose_policy_is_not_a_record(issued):
    world, policy, _ = issued
    with pytest.raises(ActivationRequestError):
        populate_reference_map(record=policy, adapters=world.root._adapters)


def test_a_record_carrying_another_family_is_refused(issued):
    world, _, record = issued
    alien = dataclasses.replace(record, policy=object())
    with pytest.raises(ReferenceMapDerivationError):
        populate_reference_map(record=alien, adapters=world.root._adapters)


def test_a_record_whose_halves_disagree_yields_nothing(issued):
    """The re-derivation check: a coordinate that does not equal the carried
    artifact's derived coordinate is refused, digest component included."""

    world, _, record = issued
    other = make_first_constitution(
        tool_scopes_bound=("invoice.read",)
    )
    swapped = dataclasses.replace(record, policy=other)
    with pytest.raises(ReferenceMapDerivationError):
        populate_reference_map(record=swapped, adapters=world.root._adapters)


def test_an_identical_existing_entry_is_idempotent(issued):
    world, _, record = issued
    first = populate_reference_map(record=record, adapters=world.root._adapters)
    second = populate_reference_map(
        record=record, adapters=world.root._adapters, existing=first
    )
    assert dict(second) == dict(first)


def test_a_conflicting_existing_entry_fails_closed(issued):
    world, _, record = issued
    conflicting = dataclasses.replace(record.coordinate, version="9.9.9")
    existing = {(GLOBAL_TENANT, GOVERNED_ROLE_REF): conflicting}
    with pytest.raises(ReferenceMapConflictError):
        populate_reference_map(
            record=record, adapters=world.root._adapters, existing=existing
        )
    assert existing[(GLOBAL_TENANT, GOVERNED_ROLE_REF)] == conflicting


def test_unrelated_existing_entries_are_carried_unchanged(issued):
    world, _, record = issued
    unrelated_key = ("tenant-9", "ugence.roles/tenant-9/some-role/v1")
    unrelated = dataclasses.replace(record.coordinate, tenant_id="tenant-9",
                                    scope="TENANT")
    mapping = populate_reference_map(
        record=record,
        adapters=world.root._adapters,
        existing={unrelated_key: unrelated},
    )
    assert mapping[unrelated_key] == unrelated
    assert mapping[(GLOBAL_TENANT, GOVERNED_ROLE_REF)] == record.coordinate


@pytest.mark.parametrize(
    "existing",
    [
        {("only-one-component",): None},
        {("a", "b", "c"): None},
        {(1, "role"): None},
        {("t", "role"): "not-a-coordinate"},
        "not-a-mapping",
    ],
    ids=["short-key", "long-key", "non-str-key", "non-coordinate-value", "non-mapping"],
)
def test_a_malformed_prior_map_is_refused_before_any_merge(issued, existing):
    world, _, record = issued
    if isinstance(existing, dict):
        existing = {
            key: (record.coordinate if value is None else value)
            for key, value in existing.items()
        }
    with pytest.raises(ActivationRequestError):
        populate_reference_map(
            record=record, adapters=world.root._adapters, existing=existing
        )


def test_the_derived_map_feeds_the_resolver_without_translation(issued):
    """The derived mapping is exactly the shape the conformance resolver's
    constructor validates — proven by constructing one over it."""

    world, policy, record = issued
    mapping = populate_reference_map(record=record, adapters=world.root._adapters)
    resolver = world.root.constitution_resolver(reference_map=mapping)
    assert dict(resolver.reference_map) == dict(mapping)
    assert type(record.coordinate) is PolicyCoordinate
    assert coordinate_of(policy) == record.coordinate
