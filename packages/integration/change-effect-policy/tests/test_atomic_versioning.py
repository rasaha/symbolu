"""One version, one digest, three members.

Carries the owner's required proof that **the three-member policy projection is
atomically digest-bound**: changing the protected-registry list, the delegation table or
the mapping coordinate changes the artifact's body digest, so each requires a new
artifact version.

The digest is computed here through the authority's own ``framed_body_digest``, not a
local re-implementation. A test that re-derived the framing would prove that two copies
of my arithmetic agree.
"""

from __future__ import annotations

import copy

import _change_effect_policy_fixtures as fx
from ugence_policy_authority.api import framed_body_digest

from ugence_change_effect_policy import (
    CHANGE_EFFECT_ADAPTER_ID,
    CHANGE_EFFECT_POLICY_TYPE,
    ChangeEffectPolicyFamilyAdapter,
)

ADAPTER = ChangeEffectPolicyFamilyAdapter()


def body_digest(artifact) -> str:
    return framed_body_digest(
        adapter_id=CHANGE_EFFECT_ADAPTER_ID,
        policy_type=CHANGE_EFFECT_POLICY_TYPE,
        projection=ADAPTER.describe(artifact).canonical_projection,
    )


def digest_of_projection(projection) -> str:
    return framed_body_digest(
        adapter_id=CHANGE_EFFECT_ADAPTER_ID,
        policy_type=CHANGE_EFFECT_POLICY_TYPE,
        projection=projection,
    )


# --------------------------------------------------------------------------------------
# All three members are inside the digested body
# --------------------------------------------------------------------------------------


def test_all_three_members_are_present_in_the_projection() -> None:
    projection = ADAPTER.describe(fx.operative_policy()).canonical_projection
    assert "protected_registries" in projection
    assert "delegation_table" in projection
    assert "mapping_coordinate" in projection


def test_changing_the_protected_registry_list_changes_the_digest() -> None:
    baseline = fx.operative_policy()
    entries = list(fx.registries())
    entries[0] = type(entries[0])(
        registry_id=entries[0].registry_id,
        admission_rule=entries[0].admission_rule + " (revised)",
    )
    varied = fx.operative_policy(protected_registries=tuple(entries))
    assert body_digest(varied) != body_digest(baseline)


def test_reordering_the_protected_registry_list_changes_the_digest() -> None:
    """Order is content here, not presentation.

    The list is projected as a sequence, so two orderings are two artifacts. Stated by a
    test because the alternative — a set-like projection where order washed out — is a
    defensible design this one deliberately is not.
    """

    entries = fx.registries()
    reordered = (entries[1], entries[0]) + entries[2:]
    assert body_digest(fx.operative_policy(protected_registries=reordered)) != body_digest(
        fx.operative_policy()
    )


def test_the_delegation_table_participates_in_the_digest() -> None:
    """Shown on the projection, because no artifact with a non-empty table can exist.

    The table is refused at construction, so there is no second artifact to digest. What
    the atomicity claim actually needs is that the *path* is inside the digested body —
    that a table, were one ever admitted, could not change without changing the digest.
    That is what this asserts, and it asserts nothing about a populated table being
    admissible, because it is not.
    """

    projection = ADAPTER.describe(fx.operative_policy()).canonical_projection
    assert projection["delegation_table"] == []

    mutated = copy.deepcopy(projection)
    mutated["delegation_table"] = ["anything at all"]
    assert digest_of_projection(mutated) != digest_of_projection(projection)


def test_changing_the_mapping_coordinate_changes_the_digest() -> None:
    baseline = fx.operative_policy()
    varied = fx.operative_policy(
        mapping_coordinate=fx.mapping_coordinate(version="1.0.1")
    )
    assert body_digest(varied) != body_digest(baseline)


def test_adding_a_mapping_coordinate_changes_the_digest() -> None:
    """Absent and present are two different artifacts, not one artifact in two states."""

    without = fx.policy()
    with_coordinate = fx.policy(mapping_coordinate=fx.mapping_coordinate())
    assert body_digest(with_coordinate) != body_digest(without)


def test_changing_the_mapping_contents_digest_changes_the_artifacts_digest() -> None:
    """The coordinate pins *which* mapping, so a new mapping is a new artifact version.

    This is also what keeps the mapping's separate governance honest: the artifact cannot
    silently start pointing at different mapping content, because pointing elsewhere
    moves its own digest. It remains no claim that the mapping named is sound or ratified.
    """

    baseline = fx.operative_policy()
    varied = fx.operative_policy(
        mapping_coordinate=fx.mapping_coordinate(
            content_digest=fx.digest_of("a different mapping")
        )
    )
    assert body_digest(varied) != body_digest(baseline)


# --------------------------------------------------------------------------------------
# What the projection removes, and how
# --------------------------------------------------------------------------------------


def test_the_declared_content_digest_is_removed_from_the_body() -> None:
    projection = ADAPTER.describe(fx.operative_policy()).canonical_projection
    assert "content_digest" not in projection["metadata"]


def test_the_declared_content_digest_is_removed_rather_than_blanked() -> None:
    """A blanked field would still participate; a sentinel in a digest is a fiction."""

    projection = ADAPTER.describe(fx.operative_policy()).canonical_projection
    assert set(projection["metadata"]) == {
        "policy_id",
        "version",
        "scope",
        "lifecycle_state",
        "tenant_id",
        "supersedes_ref",
        "effective_from",
        "effective_to",
    }


def test_changing_only_the_declared_digest_leaves_the_body_digest_alone() -> None:
    """It is the *claim about* the body, so it cannot be part of the body it claims."""

    baseline = fx.operative_policy()
    restated = fx.operative_policy(
        metadata=fx.metadata(
            lifecycle_state=baseline.metadata.lifecycle_state,
            content_digest=fx.digest_of("a different declared digest"),
        )
    )
    assert body_digest(restated) == body_digest(baseline)


def test_removal_is_by_path_so_the_coordinates_digest_stays_bound() -> None:
    """The discriminating case for "by path, not by name".

    ``content_digest`` appears twice in this artifact: the metadata's declared digest,
    which is removed, and the mapping coordinate's, which must not be. A name-based
    removal would have silently unbound the second, and the artifact could then have been
    repointed at different mapping content without changing its own digest.
    """

    projection = ADAPTER.describe(fx.operative_policy()).canonical_projection
    assert "content_digest" in projection["mapping_coordinate"]
    assert projection["mapping_coordinate"]["content_digest"] == fx.digest_of(
        "mapping-content"
    )


# --------------------------------------------------------------------------------------
# Stability
# --------------------------------------------------------------------------------------


def test_the_digest_is_stable_across_equal_artifacts() -> None:
    assert body_digest(fx.operative_policy()) == body_digest(fx.operative_policy())


def test_the_digest_is_stable_across_repeated_projection() -> None:
    """Projection does not mutate the artifact it reads."""

    artifact = fx.operative_policy()
    first = body_digest(artifact)
    assert body_digest(artifact) == first
    assert artifact.metadata.content_digest == fx.digest_of("baseline-content")


def test_changing_the_pinned_references_changes_the_digest() -> None:
    """CEC-2 pins them explicitly, so they are content too."""

    baseline = fx.operative_policy()
    assert body_digest(
        fx.operative_policy(constitution_ref="ugence.constitution/v2#change-effect")
    ) != body_digest(baseline)
    assert body_digest(
        fx.operative_policy(
            intent_specification_refs=("ugence.intent.recalibration/v2",)
        )
    ) != body_digest(baseline)
