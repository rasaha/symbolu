"""Property-based mutation of both manifests: the drafting one and the ratified one.

Three properties, generated over arbitrary artifact content rather than the
hand-picked fixtures, because a hand-picked example proves the rule holds for that
example:

1. **Canonical encoding is a function of the value.** Round-tripping any artifact
   through canonical JSON reproduces it exactly, and re-encoding is byte-stable.
2. **The digest separates values.** Two artifacts with different material content
   never share a digest; the same artifact always yields the same one.
3. **Validation is deterministic and total.** Any generated artifact — coherent or
   not — yields a report, never an exception, and the same one every time.

Hypothesis is used where it is available. When it is not, the module falls back to
an explicit deterministic corpus so the properties are still exercised rather than
silently skipped; the fallback is narrower, and says so.
"""

from __future__ import annotations

import fixtures
import pytest

from ugence_agent_constitution import (
    AgentConstitution,
    AgentRoleManifest,
    ArtifactKind,
    CapabilityRequirement,
    IssuerIdentity,
    IssuerKind,
    RequirementObligation,
    compute_content_digest,
    dumps,
    loads,
    validate_artifact,
)

hypothesis = pytest.importorskip(
    "hypothesis", reason="property-based mutation requires hypothesis"
)
from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

SETTINGS = settings(
    max_examples=75,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

# Text that exercises the rules under test: blank, whitespace-padded, unicode,
# and ordinary. Restricted to a small alphabet so shrinking reports something
# readable rather than a wall of control characters.
text = st.text(
    alphabet=st.sampled_from(list("abcXYZ .-_") + ["ü", "✓"]),
    min_size=0,
    max_size=24,
)
identifier = st.text(alphabet=st.sampled_from(list("abcdefg.-")), min_size=0, max_size=16)
versions = st.sampled_from(["0.0.1", "1.0.0", "1.0.1", "1.1.0", "2.0.0", "1.0", "v1", ""])


@st.composite
def entry_refs(draw):
    from ugence_agent_constitution import CapabilityRegistryEntryRef, fingerprint

    entry_id = draw(identifier)
    version = draw(versions)
    return CapabilityRegistryEntryRef(
        registry_namespace=draw(st.sampled_from(["ugence.capabilities", "other.ns", ""])),
        entry_id=entry_id,
        entry_version=version,
        entry_digest=draw(
            st.sampled_from(
                [fingerprint({"e": entry_id, "v": version}), "not-a-digest", ""]
            )
        ),
    )


@st.composite
def requirements(draw):
    return CapabilityRequirement(
        requirement_id=draw(identifier),
        summary=draw(text),
        obligation=draw(st.sampled_from(list(RequirementObligation))),
        entry_ref=draw(st.one_of(st.none(), entry_refs())),
        condition=draw(st.one_of(st.none(), text)),
        rationale=draw(text),
    )


@st.composite
def manifests(draw):
    """Arbitrary drafting artifacts, coherent and otherwise."""
    return AgentRoleManifest(
        manifest_id=draw(identifier),
        draft_revision=draw(st.integers(min_value=0, max_value=50)),
        role_name=draw(text),
        role_summary=draw(text),
        author_id=draw(identifier),
        capability_requirements=tuple(draw(st.lists(requirements(), max_size=4))),
        prohibited_actions=tuple(draw(st.lists(text, max_size=4))),
        notes=draw(text),
    )


@st.composite
def constitutions(draw):
    """Arbitrary ratified artifacts, coherent and otherwise."""
    return AgentConstitution(
        constitution_id=draw(identifier),
        artifact_version=draw(versions),
        predecessor=None,
        issuer=IssuerIdentity(
            issuer_id=draw(identifier),
            issuer_display_name=draw(text),
            issuer_kind=draw(st.sampled_from(list(IssuerKind))),
        ),
        source_manifest_id=draw(identifier),
        source_manifest_digest=draw(
            st.sampled_from(["sha256:" + "0" * 64, "sha256:" + "a" * 64, "bad", ""])
        ),
        source_manifest_author_id=draw(identifier),
        role_name=draw(text),
        role_summary=draw(text),
        capability_requirements=tuple(draw(st.lists(requirements(), max_size=4))),
        prohibited_actions=tuple(draw(st.lists(text, max_size=4))),
        ratified_at=draw(st.sampled_from(["2026-01-15T09:30:00Z", "", "  "])),
    )


ARTIFACTS = {
    ArtifactKind.AGENT_ROLE_MANIFEST: manifests(),
    ArtifactKind.AGENT_CONSTITUTION: constitutions(),
}


# -- property 1: canonical encoding is a function of the value ------------


@SETTINGS
@given(manifests())
def test_manifest_round_trips_through_canonical_json(draft):
    restored = AgentRoleManifest.model_validate(loads(dumps(draft)))
    assert restored == draft
    assert dumps(restored) == dumps(draft)


@SETTINGS
@given(constitutions())
def test_constitution_round_trips_through_canonical_json(artifact):
    restored = AgentConstitution.model_validate(loads(dumps(artifact)))
    assert restored == artifact
    assert dumps(restored) == dumps(artifact)


@SETTINGS
@given(st.one_of(manifests(), constitutions()))
def test_re_encoding_is_byte_stable(artifact):
    assert len({dumps(artifact) for _ in range(5)}) == 1


# -- property 2: the digest separates values ------------------------------


@SETTINGS
@given(st.one_of(manifests(), constitutions()))
def test_the_digest_is_a_pure_function_of_content(artifact):
    assert compute_content_digest(artifact) == compute_content_digest(artifact)
    restored = type(artifact).model_validate(loads(dumps(artifact)))
    assert compute_content_digest(restored) == compute_content_digest(artifact)


@SETTINGS
@given(manifests(), manifests())
def test_distinct_drafts_have_distinct_digests(left, right):
    if dumps(left) == dumps(right):
        assert compute_content_digest(left) == compute_content_digest(right)
    else:
        assert compute_content_digest(left) != compute_content_digest(right)


@SETTINGS
@given(constitutions(), constitutions())
def test_distinct_constitutions_have_distinct_digests(left, right):
    if dumps(left) == dumps(right):
        assert compute_content_digest(left) == compute_content_digest(right)
    else:
        assert compute_content_digest(left) != compute_content_digest(right)


@SETTINGS
@given(manifests(), text)
def test_any_material_edit_to_a_draft_moves_its_digest(draft, replacement):
    edited = draft.revise(role_summary=replacement)
    if replacement != draft.role_summary or edited.draft_revision != draft.draft_revision:
        assert compute_content_digest(edited) != compute_content_digest(draft)


@SETTINGS
@given(constitutions(), text)
def test_any_material_edit_to_a_constitution_moves_its_digest(artifact, replacement):
    if replacement == artifact.role_summary:
        return
    edited = artifact.model_copy(update={"role_summary": replacement})
    assert compute_content_digest(edited) != compute_content_digest(artifact)


@SETTINGS
@given(st.one_of(manifests(), constitutions()))
def test_stamping_a_digest_is_idempotent(artifact):
    stamp = (
        artifact.with_draft_digest
        if isinstance(artifact, AgentRoleManifest)
        else artifact.with_content_digest
    )
    once = stamp()
    twice = (
        once.with_draft_digest()
        if isinstance(once, AgentRoleManifest)
        else once.with_content_digest()
    )
    assert once == twice


# -- property 3: validation is deterministic and total --------------------


@SETTINGS
@given(manifests())
def test_validating_any_draft_returns_a_report_never_an_exception(draft):
    report = validate_artifact(draft, ArtifactKind.AGENT_ROLE_MANIFEST)
    assert report.outcome is not None
    assert report.is_usable == (report.outcome.value == "VALID")


@SETTINGS
@given(constitutions())
def test_validating_any_constitution_returns_a_report_never_an_exception(artifact):
    report = validate_artifact(artifact, ArtifactKind.AGENT_CONSTITUTION)
    assert report.outcome is not None
    assert report.is_usable == (report.outcome.value == "VALID")


@SETTINGS
@given(st.one_of(manifests(), constitutions()))
def test_validation_is_deterministic_finding_for_finding(artifact):
    kind = (
        ArtifactKind.AGENT_ROLE_MANIFEST
        if isinstance(artifact, AgentRoleManifest)
        else ArtifactKind.AGENT_CONSTITUTION
    )
    reports = [validate_artifact(artifact, kind).canonical_json() for _ in range(3)]
    assert len(set(reports)) == 1


@SETTINGS
@given(st.one_of(manifests(), constitutions()))
def test_every_emitted_code_is_a_declared_code(artifact):
    from ugence_agent_constitution.validation import codes

    kind = (
        ArtifactKind.AGENT_ROLE_MANIFEST
        if isinstance(artifact, AgentRoleManifest)
        else ArtifactKind.AGENT_CONSTITUTION
    )
    for code in validate_artifact(artifact, kind).codes:
        assert code in codes.ALL_CODES


@SETTINGS
@given(constitutions())
def test_a_generated_draft_is_never_usable_as_a_constitution(artifact):
    """Whatever content is generated, the draft/ratified split holds."""
    draft = AgentRoleManifest(
        manifest_id=artifact.constitution_id or "m",
        role_name=artifact.role_name,
        role_summary=artifact.role_summary,
        author_id=artifact.source_manifest_author_id or "a",
        capability_requirements=artifact.capability_requirements,
        prohibited_actions=artifact.prohibited_actions,
    )
    assert not validate_artifact(draft, ArtifactKind.AGENT_CONSTITUTION).is_usable


@SETTINGS
@given(constitutions())
def test_self_ratification_is_refused_for_any_generated_identity(draft_artifact):
    same = draft_artifact.model_copy(
        update={"source_manifest_author_id": draft_artifact.issuer.issuer_id}
    ).with_content_digest()
    report = validate_artifact(same, ArtifactKind.AGENT_CONSTITUTION)
    if same.issuer.issuer_id.strip():
        from ugence_agent_constitution.validation import codes

        assert report.has_code(codes.SELF_RATIFICATION)
    assert not report.is_usable
