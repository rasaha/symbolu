"""A draft is not a constitution, and nobody ratifies their own draft.

These two rules are why the drafting artifact and the ratified artifact are
separate types rather than one type with a ``ratified`` flag. A flag is a field
somebody sets; a type is a thing somebody has to construct.
"""

from __future__ import annotations

import fixtures
import pytest
from pydantic import ValidationError

from ugence_agent_constitution import (
    AGENT_CONSTITUTION_V1,
    AGENT_ROLE_MANIFEST_V1,
    AgentConstitution,
    AgentRoleManifest,
    ArtifactKind,
    ConformanceSubject,
    ValidationOutcome,
    is_ratified_constitution,
    validate_artifact,
    validate_constitution,
)
from ugence_agent_constitution.validation import codes


# -- a draft is not a constitution ---------------------------------------


def test_a_manifest_payload_read_as_a_constitution_is_refused_by_name():
    report = validate_constitution(fixtures.manifest().model_dump())
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.DRAFT_IS_NOT_A_CONSTITUTION)
    assert not report.is_usable


def test_a_manifest_instance_read_as_a_constitution_is_refused_the_same_way():
    """Both routes into validation take the same path and cannot diverge."""
    report = validate_artifact(fixtures.manifest(), ArtifactKind.AGENT_CONSTITUTION)
    assert report.has_code(codes.DRAFT_IS_NOT_A_CONSTITUTION)


def test_a_manifest_is_never_ratified_and_never_authority_bearing():
    assert AgentRoleManifest.is_ratified is False
    assert AgentRoleManifest.carries_authority is False
    draft = fixtures.manifest()
    assert draft.is_ratified is False
    assert draft.carries_authority is False


def test_is_ratified_constitution_rejects_a_draft_carrying_constitutional_content():
    """A draft with every field a constitution has is still not a constitution:
    ratification is an act recorded by producing a different artifact."""
    assert is_ratified_constitution(fixtures.constitution()) is True
    assert is_ratified_constitution(fixtures.manifest()) is False


def test_is_ratified_constitution_rejects_a_duck_typed_impostor():
    class _Impostor:
        is_ratified = True
        schema_version = AGENT_CONSTITUTION_V1
        constitution_id = "constitution.refund-agent"

    assert is_ratified_constitution(_Impostor()) is False


def test_is_ratified_constitution_rejects_a_constitution_that_does_not_validate():
    """Being the right type is necessary, not sufficient."""
    assert is_ratified_constitution(fixtures.constitution(role_name="")) is False


def test_a_manifest_cannot_be_relabelled_into_a_constitution_by_schema_version():
    payload = fixtures.manifest().model_dump()
    payload["schema_version"] = AGENT_CONSTITUTION_V1
    report = validate_constitution(payload)
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.SCHEMA_STRUCTURE_INVALID)


def test_a_manifest_validates_perfectly_well_as_what_it_actually_is():
    report = validate_artifact(fixtures.manifest(), ArtifactKind.AGENT_ROLE_MANIFEST)
    assert report.is_usable


# -- drafts are immutable values, revised by copy-on-write ---------------


def test_a_draft_instance_cannot_be_mutated_in_place():
    draft = fixtures.manifest()
    with pytest.raises(ValidationError):
        draft.role_name = "Renamed"


def test_revising_a_draft_yields_a_new_artifact_and_advances_the_revision():
    draft = fixtures.manifest()
    revised = draft.revise(role_summary="A materially different summary.")
    assert revised is not draft
    assert draft.role_summary != revised.role_summary
    assert revised.draft_revision == draft.draft_revision + 1


def test_revising_clears_the_stale_digest_so_no_draft_carries_the_wrong_one():
    draft = fixtures.manifest()
    revised = draft.revise(notes="second pass")
    assert revised.draft_digest == ""
    assert revised.with_draft_digest().draft_digest != draft.draft_digest


def test_the_revision_counter_is_not_a_caller_set_field():
    with pytest.raises(ValueError):
        fixtures.manifest().revise(draft_revision=99)


def test_a_constitution_instance_cannot_be_mutated_in_place():
    artifact = fixtures.constitution()
    with pytest.raises(ValidationError):
        artifact.role_name = "Quietly renamed"


# -- self-ratification ----------------------------------------------------


def test_an_issuer_ratifying_their_own_draft_is_refused():
    report = validate_constitution(
        fixtures.constitution(source_manifest_author_id=fixtures.ISSUER_ID)
    )
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.SELF_RATIFICATION)
    assert not report.is_usable


def test_self_ratification_is_caught_despite_surrounding_whitespace():
    """Comparing raw strings would let ``"owner.board "`` slip past."""
    report = validate_constitution(
        fixtures.constitution(source_manifest_author_id=fixtures.ISSUER_ID + " ")
    )
    assert report.has_code(codes.SELF_RATIFICATION)


def test_an_independent_issuer_is_accepted():
    assert validate_constitution(fixtures.constitution()).is_usable


def test_two_blank_identities_are_not_reported_as_self_ratification():
    """Blank fields are already reported as missing; calling that self-ratification
    on top would be a second, misleading finding about the same defect."""
    report = validate_constitution(fixtures.constitution(source_manifest_author_id=""))
    assert report.has_code(codes.MANDATORY_FIELD_MISSING)
    assert not report.has_code(codes.SELF_RATIFICATION)


# -- what this package explicitly does not do ----------------------------


def test_no_artifact_claims_to_make_an_authority_decision():
    assert AgentConstitution.makes_authority_decision is False
    assert AgentConstitution.is_signed is False


def test_no_conformance_evaluation_exists_in_this_build():
    assert ConformanceSubject.conformance_evaluated is False
    assert validate_artifact(
        fixtures.subject(), ArtifactKind.CONFORMANCE_SUBJECT
    ).is_usable


def test_the_two_schema_identities_are_distinct_constants():
    assert AGENT_ROLE_MANIFEST_V1 != AGENT_CONSTITUTION_V1
