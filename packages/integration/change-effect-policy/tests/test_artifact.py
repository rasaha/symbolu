"""The artifact's shape, and the two refusals that are structural rather than advisory.

Carries two of the owner's nine required proofs: **the delegation table is empty**, and
**an artifact without a valid mapping coordinate cannot be operative**.
"""

from __future__ import annotations

import dataclasses

import pytest

import _change_effect_policy_fixtures as fx
from ugence_change_effect_policy import (
    ACTIVE_LIFECYCLE_STATE,
    ADMITTED_LIFECYCLE_STATES,
    ChangeEffectClassificationPolicy,
    ChangeEffectPolicyFieldError,
    DelegationEntryRefused,
    LIFECYCLE_DRAFT,
    MappingCoordinateRefused,
    OperativeWithoutMappingRefused,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
    PROTECTED_REGISTRY_IDS,
    ProtectedRegistryEntry,
)


# --------------------------------------------------------------------------------------
# The three members
# --------------------------------------------------------------------------------------


def test_artifact_carries_exactly_three_governed_members() -> None:
    """Three members, plus the identity envelope and the two pinned references.

    Pinned as an exact field list because a fourth governed member added without a
    ruling is the failure this asserts against, and an extra field would otherwise ride
    into the digest unremarked.
    """

    names = [f.name for f in dataclasses.fields(ChangeEffectClassificationPolicy)]
    assert names == [
        "metadata",
        "constitution_ref",
        "intent_specification_refs",
        "protected_registries",
        "delegation_table",
        "mapping_coordinate",
    ]


def test_protected_registry_list_is_all_seven_or_refused() -> None:
    partial = fx.registries()[:-1]
    with pytest.raises(ChangeEffectPolicyFieldError):
        fx.policy(protected_registries=partial)


def test_a_registry_named_twice_is_refused() -> None:
    entries = fx.registries()
    duplicated = entries[:-1] + (entries[0],)
    with pytest.raises(ChangeEffectPolicyFieldError):
        fx.policy(protected_registries=duplicated)


def test_an_unknown_registry_is_refused() -> None:
    with pytest.raises(ChangeEffectPolicyFieldError):
        ProtectedRegistryEntry(registry_id="model_weights", admission_rule="whatever")


def test_admission_rule_is_prose_and_nothing_evaluates_it() -> None:
    """The rule is a string for a human. Nothing in the package consumes it.

    If anything did, the artifact would be deciding admission, which is Stage 3 work
    that does not exist.
    """

    entry = fx.registries()[0]
    assert isinstance(entry.admission_rule, str)
    assert not hasattr(entry, "evaluate")
    assert not hasattr(entry, "matches")
    assert not hasattr(entry, "admits")


def test_the_artifact_pins_what_it_applies_under() -> None:
    with pytest.raises(ChangeEffectPolicyFieldError):
        fx.policy(intent_specification_refs=())
    with pytest.raises(ChangeEffectPolicyFieldError):
        fx.policy(constitution_ref="")


# --------------------------------------------------------------------------------------
# Required proof: the delegation table is empty
# --------------------------------------------------------------------------------------


def test_the_shipped_delegation_table_is_empty() -> None:
    assert fx.policy().delegation_table == ()


def test_a_populated_delegation_table_is_refused_not_tolerated() -> None:
    """Ruling: the table is *empty*, not populated with inactive entries.

    Anything at all is refused, because "inactive" is a property a later commit can
    flip, while absent is a property it must add a type to change.
    """

    for offered in (
        ({"delegation_id": "D1", "active": False},),
        ("anything",),
        (object(),),
        ((),),
    ):
        with pytest.raises(DelegationEntryRefused):
            fx.policy(delegation_table=offered)


def test_the_package_offers_no_delegation_entry_type_to_populate_it_with() -> None:
    """The strongest available form of "no delegation entries".

    A caller cannot construct a well-typed entry, because this family defines none. The
    refusal above catches an ill-typed one; this catches the well-typed one that does
    not exist.
    """

    import ugence_change_effect_policy as pkg

    entry_types = [
        name
        for name in pkg.__all__
        if "delegation" in name.lower()
        and isinstance(getattr(pkg, name), type)
        and not issubclass(getattr(pkg, name), BaseException)
    ]
    assert entry_types == []


# --------------------------------------------------------------------------------------
# Required proof: an artifact without a valid mapping coordinate cannot be operative
# --------------------------------------------------------------------------------------


def test_the_initial_shipped_artifact_is_lawful_without_a_coordinate() -> None:
    """Ruling 6: absence is lawful. What it forecloses is operation, not existence."""

    artifact = fx.policy()
    assert artifact.mapping_coordinate is None
    assert artifact.is_operative is False


def test_an_active_lifecycle_state_without_a_coordinate_is_refused() -> None:
    with pytest.raises(OperativeWithoutMappingRefused):
        fx.policy(metadata=fx.metadata(lifecycle_state=ACTIVE_LIFECYCLE_STATE))


def test_every_non_operative_lifecycle_state_admits_an_absent_coordinate() -> None:
    """The refusal is aimed at the operative state alone, not at lifecycle generally."""

    for state in sorted(ADMITTED_LIFECYCLE_STATES - {ACTIVE_LIFECYCLE_STATE}):
        artifact = fx.policy(metadata=fx.metadata(lifecycle_state=state))
        assert artifact.is_operative is False


def test_is_operative_is_the_conjunction_of_two_fields_it_already_carries() -> None:
    """Exhaustive over the matrix, so the property is read off rather than asserted.

    ``is_operative`` consults no registry and no trust configuration. An artifact that
    reports ``True`` is still inert: nothing here resolves it, and nothing acts on it.
    """

    for state in sorted(ADMITTED_LIFECYCLE_STATES):
        for coordinate in (None, fx.mapping_coordinate()):
            if coordinate is None and state == ACTIVE_LIFECYCLE_STATE:
                continue  # refused above; there is no such artifact to ask
            artifact = fx.policy(
                metadata=fx.metadata(lifecycle_state=state), mapping_coordinate=coordinate
            )
            expected = state == ACTIVE_LIFECYCLE_STATE and coordinate is not None
            assert artifact.is_operative is expected


def test_a_refused_artifact_never_exists_to_be_read() -> None:
    """The refusal is in ``__post_init__``, so there is no half-built artifact.

    A validator called after construction would leave a window in which an operative
    artifact with no mapping existed and could be handed on.
    """

    with pytest.raises(OperativeWithoutMappingRefused):
        fx.policy(metadata=fx.metadata(lifecycle_state=ACTIVE_LIFECYCLE_STATE))
    # And the same metadata is fine for a non-operative artifact, so the refusal is
    # about the pair, not about the metadata being malformed.
    assert fx.policy(metadata=fx.metadata(lifecycle_state=LIFECYCLE_DRAFT)) is not None


# --------------------------------------------------------------------------------------
# Identity envelope
# --------------------------------------------------------------------------------------


def test_policy_family_is_a_property_not_a_settable_field() -> None:
    field_names = {f.name for f in dataclasses.fields(fx.metadata())}
    assert "policy_family" not in field_names
    assert fx.metadata().policy_family == "change_effect.classification_policy"


def test_scope_and_tenant_are_one_fact() -> None:
    with pytest.raises(ChangeEffectPolicyFieldError):
        fx.metadata(scope=POLICY_SCOPE_GLOBAL, tenant_id="acme")
    with pytest.raises(ChangeEffectPolicyFieldError):
        fx.metadata(scope=POLICY_SCOPE_TENANT, tenant_id="")
    assert fx.metadata(scope=POLICY_SCOPE_TENANT, tenant_id="acme").tenant_id == "acme"


def test_a_truncated_content_digest_is_refused() -> None:
    with pytest.raises(ChangeEffectPolicyFieldError):
        fx.metadata(content_digest=fx.digest_of("x")[:32])


def test_a_naive_effectivity_instant_is_refused() -> None:
    import datetime as dt

    with pytest.raises(ChangeEffectPolicyFieldError):
        fx.metadata(effective_from=dt.datetime(2026, 1, 1))


def test_an_empty_effectivity_interval_is_refused() -> None:
    import datetime as dt

    instant = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    with pytest.raises(ChangeEffectPolicyFieldError):
        fx.metadata(effective_from=instant, effective_to=instant)


def test_the_artifact_is_frozen() -> None:
    artifact = fx.policy()
    with pytest.raises(dataclasses.FrozenInstanceError):
        artifact.delegation_table = ({"D1": True},)  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        artifact.mapping_coordinate = fx.mapping_coordinate()  # type: ignore[misc]


def test_the_seven_registry_ids_are_pinned() -> None:
    assert PROTECTED_REGISTRY_IDS == (
        "subject_classes",
        "governance_roles",
        "observables",
        "context_predicates",
        "constraint_inputs",
        "identity_links",
        "obligated_actions",
    )


def test_a_mapping_coordinate_must_be_the_repository_coordinate_type() -> None:
    """Ruling 3: no reduced ad-hoc reference carrying only version and digest."""

    class ReducedReference:
        version = "1.0.0"
        content_digest = fx.digest_of("mapping-content")

    with pytest.raises(MappingCoordinateRefused):
        fx.policy(mapping_coordinate=ReducedReference())
