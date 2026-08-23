"""Fingerprints are stable under re-encoding and change on any material edit."""

from __future__ import annotations

import fixtures
import pytest

from ugence_agent_constitution import (
    DIGEST_PREFIX,
    RequirementObligation,
    compute_content_digest,
    digest_scope,
    digests_agree,
    dumps,
    fingerprint,
    is_well_formed_digest,
    loads,
)


def test_fingerprint_shape_is_algorithm_prefixed():
    value = fingerprint({"a": 1})
    assert value.startswith(DIGEST_PREFIX)
    assert is_well_formed_digest(value)


def test_fingerprint_is_stable_across_repeated_calls_and_processes():
    """Pinned literal: a change to this value is a change to every stored digest,
    and must be a deliberate, reviewed migration rather than a silent drift."""
    assert fingerprint({"a": 1, "b": [1, 2]}) == (
        "sha256:8baa73198470c7bb4c3ce142a8fd651affc0310d878bb9bd159e37a573fb4874"
    )
    assert len({fingerprint({"a": 1, "b": [1, 2]}) for _ in range(50)}) == 1


def test_fingerprint_ignores_key_insertion_order():
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})


def test_fingerprint_survives_a_json_round_trip():
    artifact = fixtures.constitution()
    assert fingerprint(loads(dumps(artifact))) == fingerprint(
        loads(dumps(type(artifact).model_validate(loads(dumps(artifact)))))
    )


def test_content_digest_excludes_only_the_digest_field_itself():
    artifact = fixtures.constitution()
    scope = digest_scope(artifact)
    assert "content_digest" not in scope
    assert "role_name" in scope and "issuer" in scope and "capability_requirements" in scope


def test_stamping_a_digest_does_not_change_the_digest():
    """The exclusion rule's whole purpose: stamping is idempotent."""
    artifact = fixtures.constitution()
    assert artifact.with_content_digest().content_digest == artifact.content_digest
    assert digests_agree(artifact.content_digest, artifact)


@pytest.mark.parametrize(
    "field,value",
    [
        ("role_name", "Renamed agent"),
        ("role_summary", "A materially different summary."),
        ("ratified_at", "2026-01-16T09:30:00Z"),
        ("artifact_version", "2.0.0"),
        ("constitution_id", "constitution.other"),
        ("source_manifest_id", "manifest.other"),
        ("source_manifest_author_id", "drafter.other"),
        ("prohibited_actions", ("Something else entirely",)),
    ],
)
def test_a_material_edit_to_any_top_level_field_changes_the_digest(field, value):
    base = fixtures.constitution()
    edited = fixtures.constitution(**{field: value})
    assert edited.content_digest != base.content_digest


def test_a_material_edit_nested_inside_a_requirement_changes_the_digest():
    """Nested content is in scope. A digest that only covered top-level fields
    would let the substance of every obligation change without notice."""
    base = fixtures.constitution()
    edited = fixtures.constitution(
        capability_requirements=(
            fixtures.requirement(summary="Issue a refund of any size whatsoever"),
        )
    )
    assert edited.content_digest != base.content_digest


def test_a_material_edit_to_an_obligation_changes_the_digest():
    base = fixtures.constitution()
    edited = fixtures.constitution(
        capability_requirements=(
            fixtures.requirement(
                obligation=RequirementObligation.CONDITIONAL,
                condition="Only during business hours",
            ),
        )
    )
    assert edited.content_digest != base.content_digest


def test_a_material_edit_to_a_pinned_registry_entry_changes_the_digest():
    base = fixtures.constitution()
    edited = fixtures.constitution(
        capability_requirements=(
            fixtures.requirement(entry_ref=fixtures.entry_ref(version="2.0.0")),
        )
    )
    assert edited.content_digest != base.content_digest


def test_a_material_edit_to_the_issuer_changes_the_digest():
    from ugence_agent_constitution import IssuerIdentity, IssuerKind

    base = fixtures.constitution()
    edited = fixtures.constitution(
        issuer=IssuerIdentity(
            issuer_id="owner.someone-else",
            issuer_display_name="Someone Else",
            issuer_kind=IssuerKind.HUMAN_OWNER,
        )
    )
    assert edited.content_digest != base.content_digest


def test_reordering_requirements_changes_the_digest_because_order_is_authored():
    a, b = fixtures.requirement(), fixtures.requirement(requirement_id="req.escalate")
    first = fixtures.constitution(capability_requirements=(a, b))
    second = fixtures.constitution(capability_requirements=(b, a))
    assert first.content_digest != second.content_digest


def test_digests_agree_rejects_a_declared_digest_that_was_not_recomputed():
    artifact = fixtures.constitution()
    tampered = artifact.model_copy(update={"role_name": "Quietly renamed"})
    assert not digests_agree(tampered.content_digest, tampered)


def test_an_unstamped_artifact_and_a_stamped_one_share_a_digest_scope():
    unstamped = fixtures.constitution(_stamp=False)
    stamped = unstamped.with_content_digest()
    assert compute_content_digest(unstamped) == compute_content_digest(stamped)


def test_manifest_and_constitution_with_the_same_prose_do_not_share_a_digest():
    """Different artifact shapes are different artifacts, even word for word."""
    assert compute_content_digest(fixtures.manifest()) != compute_content_digest(
        fixtures.constitution()
    )
