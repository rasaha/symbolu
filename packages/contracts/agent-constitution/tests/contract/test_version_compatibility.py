"""Schema compatibility and succession rules, including the required version bump."""

from __future__ import annotations

import fixtures
import pytest

from ugence_agent_constitution import (
    AGENT_CONSTITUTION_V1,
    AGENT_ROLE_MANIFEST_V1,
    ArtifactKind,
    MalformedVersionError,
    SchemaCompatibility,
    SuccessionCompatibility,
    UnknownArtifactKind,
    ValidationOutcome,
    compare_artifact_versions,
    is_semantic_version,
    parse_semantic_version,
    requires_version_bump,
    schema_compatibility,
    succession_compatibility,
    validate_artifact,
    validate_constitution,
)
from ugence_agent_constitution.validation import codes


# -- semantic version parsing --------------------------------------------


@pytest.mark.parametrize("value", ["0.0.0", "1.0.0", "10.20.30"])
def test_release_versions_parse(value):
    assert is_semantic_version(value)


@pytest.mark.parametrize(
    "value", ["1.0", "1.0.0.0", "v1.0.0", "1.0.0-rc1", "1.0.0+build.5", "", "one.0.0"]
)
def test_non_release_versions_are_refused_not_ordered(value):
    """Pre-release and build-metadata ordering is subtle enough that a silent wrong
    answer is likelier than a right one, and this comparison decides supersession."""
    assert not is_semantic_version(value)
    with pytest.raises(MalformedVersionError):
        parse_semantic_version(value)


def test_versions_order_numerically_not_lexically():
    assert compare_artifact_versions("1.10.0", "1.9.0") == 1
    assert compare_artifact_versions("2.0.0", "10.0.0") == -1
    assert compare_artifact_versions("1.2.3", "1.2.3") == 0


# -- schema compatibility -------------------------------------------------


def test_a_known_schema_version_is_supported():
    assert (
        schema_compatibility(ArtifactKind.AGENT_CONSTITUTION, AGENT_CONSTITUTION_V1)
        is SchemaCompatibility.SUPPORTED
    )


def test_an_unseen_schema_version_is_unrecognized_not_rejected():
    assert (
        schema_compatibility(ArtifactKind.AGENT_CONSTITUTION, "agent_constitution.v99")
        is SchemaCompatibility.UNRECOGNIZED
    )


def test_an_unrecognized_schema_version_validates_as_indeterminate_never_valid():
    """A build that has never seen a shape cannot say an artifact in it is well-formed."""
    payload = fixtures.constitution().model_dump()
    payload["schema_version"] = "agent_constitution.v99"
    report = validate_constitution(payload)
    assert report.outcome is ValidationOutcome.INDETERMINATE
    assert report.has_code(codes.SCHEMA_VERSION_UNRECOGNIZED)
    assert not report.is_usable


def test_a_known_shape_read_as_the_wrong_kind_is_invalid_not_indeterminate():
    payload = fixtures.subject().model_dump()
    report = validate_constitution(payload)
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.SCHEMA_VERSION_WRONG_KIND)


def test_an_unknown_artifact_kind_is_a_caller_bug_and_raises():
    with pytest.raises(UnknownArtifactKind):
        schema_compatibility("not_an_artifact_kind", AGENT_CONSTITUTION_V1)


# -- succession -----------------------------------------------------------


def test_a_lineage_root_has_nothing_to_succeed():
    assert (
        succession_compatibility(
            lineage_id="c",
            artifact_version="1.0.0",
            content_digest="sha256:" + "0" * 64,
            predecessor_lineage_id=None,
            predecessor_version=None,
            predecessor_digest=None,
        )
        is SuccessionCompatibility.LINEAGE_ROOT
    )
    assert validate_constitution(fixtures.constitution()).is_usable


def test_a_valid_successor_bumps_its_version_and_changes_its_content():
    base = fixtures.constitution()
    nxt = fixtures.successor(base)
    assert nxt.succeeds(base)
    assert compare_artifact_versions(nxt.artifact_version, base.artifact_version) == 1
    assert nxt.content_digest != base.content_digest
    assert validate_constitution(nxt).is_usable


def test_a_successor_that_reuses_its_predecessors_version_is_invalid():
    """The required version bump. Two artifacts sharing a version are
    indistinguishable to anyone holding a reference to 'that version'."""
    base = fixtures.constitution()
    nxt = fixtures.successor(base, artifact_version=base.artifact_version)
    report = validate_constitution(nxt)
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.SUCCESSION_VERSION_NOT_BUMPED)


def test_a_successor_that_lowers_its_version_is_invalid():
    base = fixtures.constitution(artifact_version="2.0.0")
    nxt = fixtures.successor(base, artifact_version="1.9.9")
    report = validate_constitution(nxt)
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.SUCCESSION_VERSION_NOT_BUMPED)


def test_a_successor_with_unchanged_content_supersedes_nothing():
    base = fixtures.constitution()
    payload = base.model_dump()
    payload.update(
        {"artifact_version": "1.1.0", "predecessor": base.as_ref().model_dump()}
    )
    # Deliberately re-stamp so the digest is correct for the content as written;
    # the point of the rule is content identity, not a stale digest.
    from ugence_agent_constitution import AgentConstitution

    nxt = AgentConstitution.model_validate({**payload, "content_digest": ""})
    nxt = nxt.model_copy(update={"content_digest": base.content_digest})
    report = validate_constitution(nxt)
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.PREDECESSOR_SELF_REFERENCE) or report.has_code(
        codes.SUCCESSION_NO_MATERIAL_CHANGE
    )


def test_a_successor_from_a_different_lineage_is_invalid():
    base = fixtures.constitution()
    nxt = fixtures.successor(base, constitution_id="constitution.some-other-agent")
    report = validate_constitution(nxt)
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.SUCCESSION_LINEAGE_MISMATCH)


def test_an_unorderable_version_makes_succession_undecidable():
    assert (
        succession_compatibility(
            lineage_id="c",
            artifact_version="1.0.0-rc1",
            content_digest="sha256:" + "1" * 64,
            predecessor_lineage_id="c",
            predecessor_version="1.0.0",
            predecessor_digest="sha256:" + "0" * 64,
        )
        is SuccessionCompatibility.UNORDERABLE_VERSION
    )


def test_requires_version_bump_tracks_content_change_only():
    assert requires_version_bump("sha256:" + "0" * 64, "sha256:" + "1" * 64)
    assert not requires_version_bump("sha256:" + "0" * 64, "sha256:" + "0" * 64)


def test_a_malformed_artifact_version_is_invalid_on_a_root_too():
    report = validate_constitution(fixtures.constitution(artifact_version="1.0"))
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.ARTIFACT_VERSION_MALFORMED)


def test_the_manifest_schema_version_is_not_a_constitution_schema_version():
    assert AGENT_ROLE_MANIFEST_V1 != AGENT_CONSTITUTION_V1
    assert (
        schema_compatibility(ArtifactKind.AGENT_ROLE_MANIFEST, AGENT_ROLE_MANIFEST_V1)
        is SchemaCompatibility.SUPPORTED
    )
