"""Construction rules for the agent-constitution artifact.

Every rule here is fail-closed: a refused construction produces no artifact, so a
malformed constitution never reaches the authority to be issued. The field set,
types, requiredness and validation rules are the ratified §2.3 surface
(`ACC-S1-BASE`), exercised field by field.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from _agent_constitution_fixtures import (
    ADAPTER,
    CONSTITUTION_REF,
    DEFAULT_DISPOSITIONS_BOUND,
    DEFAULT_REVIEW_ACTIONS_BOUND,
    DEFAULT_TOOL_SCOPES_BOUND,
    FULL_DISPOSITIONS_BOUND,
    FULL_REVIEW_ACTIONS_BOUND,
    GOVERNED_ROLE_REFS,
    T_FROM,
    T_TO,
    TENANT,
    make_constitution_policy,
)
from ugence_agent_constitution_policy import (
    ADMITTED_CANDIDATE_DISPOSITION_TOKENS,
    ADMITTED_REVIEW_ACTION_TOKENS,
    AGENT_CONSTITUTION_POLICY_FAMILY,
    CONSTITUTION_VOCABULARY_VERSION,
    LIFECYCLE_APPROVED_ACTIVE,
    PLACEHOLDER_CONTENT_DIGEST,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
    AgentConstitutionDuplicateError,
    AgentConstitutionFieldError,
    AgentConstitutionOrderingError,
    AgentConstitutionPolicy,
    AgentConstitutionPolicyError,
    AgentConstitutionPolicyMetadata,
)
from ugence_agentic_proposer import CandidateDisposition, ReviewAction

DISPOSITIONS = sorted(member.value for member in CandidateDisposition)
REVIEW_ACTIONS = sorted(member.value for member in ReviewAction)


def _draft(**kwargs) -> AgentConstitutionPolicy:
    fields = dict(
        metadata=AgentConstitutionPolicyMetadata(
            policy_id="c-1",
            version="1.0.0",
            content_digest=PLACEHOLDER_CONTENT_DIGEST,
            scope=POLICY_SCOPE_TENANT,
            lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
            tenant_id=TENANT,
        ),
        agent_constitution_ref=CONSTITUTION_REF,
        governed_role_refs=GOVERNED_ROLE_REFS,
        permitted_candidate_dispositions_bound=DEFAULT_DISPOSITIONS_BOUND,
        permitted_review_actions_bound=DEFAULT_REVIEW_ACTIONS_BOUND,
        permitted_tool_scopes_bound=DEFAULT_TOOL_SCOPES_BOUND,
    )
    fields.update(kwargs)
    return AgentConstitutionPolicy(**fields)


# --------------------------------------------------------------------------- #
# The whole artifact
# --------------------------------------------------------------------------- #


def test_a_well_formed_constitution_constructs():
    policy = _draft()
    assert policy.agent_constitution_ref == CONSTITUTION_REF
    assert policy.governed_role_refs == GOVERNED_ROLE_REFS
    assert policy.constitution_vocabulary_version == CONSTITUTION_VOCABULARY_VERSION


def test_the_artifact_is_frozen():
    policy = make_constitution_policy()
    with pytest.raises(Exception):
        policy.governed_role_refs = ()


def test_every_construction_error_descends_from_one_root():
    for error in (
        AgentConstitutionFieldError,
        AgentConstitutionOrderingError,
        AgentConstitutionDuplicateError,
    ):
        assert issubclass(error, AgentConstitutionPolicyError)


# --------------------------------------------------------------------------- #
# The signed reference
# --------------------------------------------------------------------------- #


def test_the_reference_must_satisfy_the_c5a_identifier_grammar():
    with pytest.raises(AgentConstitutionFieldError):
        _draft(agent_constitution_ref="has a space")
    with pytest.raises(AgentConstitutionFieldError):
        _draft(agent_constitution_ref="-leading-hyphen")
    with pytest.raises(AgentConstitutionFieldError):
        _draft(agent_constitution_ref="")


def test_the_reference_admits_the_slash_the_identifier_grammar_allows():
    assert (
        _draft(agent_constitution_ref="a/b:c.d-e").agent_constitution_ref == "a/b:c.d-e"
    )


# --------------------------------------------------------------------------- #
# The governed role references
# --------------------------------------------------------------------------- #


def test_an_empty_governed_role_list_is_refused():
    """A constitution that governs nothing is not issuable."""

    with pytest.raises(AgentConstitutionFieldError):
        _draft(governed_role_refs=())


def test_a_duplicate_governed_role_is_refused():
    ref = GOVERNED_ROLE_REFS[0]
    with pytest.raises(AgentConstitutionDuplicateError):
        _draft(governed_role_refs=(ref, ref))


def test_unsorted_governed_roles_are_refused_and_never_reordered():
    unsorted = tuple(reversed(GOVERNED_ROLE_REFS))
    assert list(unsorted) != sorted(unsorted)
    with pytest.raises(AgentConstitutionOrderingError):
        _draft(governed_role_refs=unsorted)


def test_a_governed_role_must_satisfy_the_c5a_identifier_grammar():
    with pytest.raises(AgentConstitutionFieldError):
        _draft(governed_role_refs=("has a space",))


def test_governed_roles_must_be_a_tuple_not_a_list():
    with pytest.raises(AgentConstitutionFieldError):
        _draft(governed_role_refs=list(GOVERNED_ROLE_REFS))


# --------------------------------------------------------------------------- #
# The two closed-vocabulary bounds
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "field", ["permitted_candidate_dispositions_bound", "permitted_review_actions_bound"]
)
def test_an_empty_closed_vocabulary_bound_is_refused(field):
    with pytest.raises(AgentConstitutionFieldError):
        _draft(**{field: ()})


def test_a_token_outside_the_disposition_vocabulary_is_refused():
    with pytest.raises(AgentConstitutionFieldError):
        _draft(permitted_candidate_dispositions_bound=("SOMETHING_ELSE",))


def test_a_token_outside_the_review_action_vocabulary_is_refused():
    with pytest.raises(AgentConstitutionFieldError):
        _draft(permitted_review_actions_bound=("SOMETHING_ELSE",))


def test_a_disposition_token_in_the_review_action_bound_is_refused():
    """The two closed vocabularies never blur into one another."""

    with pytest.raises(AgentConstitutionFieldError):
        _draft(permitted_review_actions_bound=(DISPOSITIONS[0],))


def test_a_duplicate_bound_member_is_refused():
    with pytest.raises(AgentConstitutionDuplicateError):
        _draft(
            permitted_candidate_dispositions_bound=(DISPOSITIONS[0], DISPOSITIONS[0])
        )


def test_an_unsorted_bound_is_refused_and_never_reordered():
    unsorted = (DISPOSITIONS[1], DISPOSITIONS[0])
    with pytest.raises(AgentConstitutionOrderingError):
        _draft(permitted_candidate_dispositions_bound=unsorted)


def test_an_enum_member_is_not_stored_in_place_of_its_string_value():
    """The artifact stays plain stdlib: the projection depends on no enum coercion."""

    with pytest.raises(AgentConstitutionFieldError):
        _draft(permitted_candidate_dispositions_bound=(list(CandidateDisposition)[0],))
    with pytest.raises(AgentConstitutionFieldError):
        _draft(permitted_review_actions_bound=(list(ReviewAction)[0],))


def test_the_maximal_bounds_are_admissible_together():
    policy = _draft(
        permitted_candidate_dispositions_bound=FULL_DISPOSITIONS_BOUND,
        permitted_review_actions_bound=FULL_REVIEW_ACTIONS_BOUND,
    )
    assert (
        set(policy.permitted_candidate_dispositions_bound)
        == ADMITTED_CANDIDATE_DISPOSITION_TOKENS
    )
    assert set(policy.permitted_review_actions_bound) == ADMITTED_REVIEW_ACTION_TOKENS


# --------------------------------------------------------------------------- #
# The open tool-scope bound
# --------------------------------------------------------------------------- #


def test_an_empty_tool_scope_bound_is_admissible():
    """The one bound that may be empty: declared tool scopes default empty."""

    assert _draft(permitted_tool_scopes_bound=()).permitted_tool_scopes_bound == ()


def test_a_tool_scope_must_satisfy_the_c5b_token_grammar():
    with pytest.raises(AgentConstitutionFieldError):
        _draft(permitted_tool_scopes_bound=("has a space",))
    # ``/`` is C5a-only; the tool-scope bound is a Token vocabulary.
    with pytest.raises(AgentConstitutionFieldError):
        _draft(permitted_tool_scopes_bound=("a/b",))


def test_a_duplicate_tool_scope_is_refused():
    with pytest.raises(AgentConstitutionDuplicateError):
        _draft(permitted_tool_scopes_bound=("scope.a", "scope.a"))


def test_unsorted_tool_scopes_are_refused():
    with pytest.raises(AgentConstitutionOrderingError):
        _draft(permitted_tool_scopes_bound=("scope.b", "scope.a"))


def test_the_tool_scope_bound_is_open_any_lawful_token_is_admissible():
    """Bounded by membership, not enumerated: no closed list exists to check."""

    policy = _draft(permitted_tool_scopes_bound=("anything.the-grammar:admits",))
    assert policy.permitted_tool_scopes_bound == ("anything.the-grammar:admits",)


# --------------------------------------------------------------------------- #
# The clause-vocabulary version
# --------------------------------------------------------------------------- #


def test_the_vocabulary_version_is_the_one_fixed_value():
    assert CONSTITUTION_VOCABULARY_VERSION == "ugence.agent-constitution/clauses/v1"
    with pytest.raises(AgentConstitutionFieldError):
        _draft(constitution_vocabulary_version="ugence.agent-constitution/clauses/v2")
    with pytest.raises(AgentConstitutionFieldError):
        _draft(constitution_vocabulary_version="")


# --------------------------------------------------------------------------- #
# The metadata envelope
# --------------------------------------------------------------------------- #


def _metadata(**overrides) -> AgentConstitutionPolicyMetadata:
    fields = dict(
        policy_id="c-1",
        version="1.0.0",
        content_digest=PLACEHOLDER_CONTENT_DIGEST,
        scope=POLICY_SCOPE_TENANT,
        lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
        tenant_id=TENANT,
    )
    fields.update(overrides)
    return AgentConstitutionPolicyMetadata(**fields)


@pytest.mark.parametrize("bad", ["has space", "-leading", "", "a/b"])
def test_policy_id_must_satisfy_the_c5b_token_grammar(bad):
    with pytest.raises(AgentConstitutionFieldError):
        _metadata(policy_id=bad)


@pytest.mark.parametrize("bad", ["has space", "-leading", "", "1/2"])
def test_version_must_satisfy_the_c5b_token_grammar(bad):
    with pytest.raises(AgentConstitutionFieldError):
        _metadata(version=bad)


def test_the_version_is_a_string_never_a_number():
    with pytest.raises(AgentConstitutionFieldError):
        _metadata(version=1)


def test_an_over_long_identifier_is_refused():
    with pytest.raises(AgentConstitutionFieldError):
        _metadata(policy_id="a" * 201)


@pytest.mark.parametrize("bad", ["", "A" * 64, "0" * 63, "z" * 64, 42])
def test_the_content_digest_must_be_lowercase_sha256_hex(bad):
    with pytest.raises(AgentConstitutionFieldError):
        _metadata(content_digest=bad)


def test_an_unknown_scope_is_refused():
    with pytest.raises(AgentConstitutionFieldError):
        _metadata(scope="REGIONAL")


def test_an_unknown_lifecycle_label_is_refused():
    with pytest.raises(AgentConstitutionFieldError):
        _metadata(lifecycle_state="ACTIVE")


def test_scope_and_tenant_are_one_fact():
    with pytest.raises(AgentConstitutionFieldError):
        _metadata(scope=POLICY_SCOPE_GLOBAL, tenant_id=TENANT)
    with pytest.raises(AgentConstitutionFieldError):
        _metadata(scope=POLICY_SCOPE_TENANT, tenant_id="")
    assert _metadata(scope=POLICY_SCOPE_GLOBAL, tenant_id="").tenant_id == ""


def test_a_naive_datetime_is_never_assumed_to_be_utc():
    with pytest.raises(AgentConstitutionFieldError):
        _metadata(effective_from=datetime(2026, 1, 1))


def test_an_empty_effective_interval_is_refused():
    with pytest.raises(AgentConstitutionOrderingError):
        _metadata(effective_from=T_TO, effective_to=T_FROM)
    with pytest.raises(AgentConstitutionOrderingError):
        _metadata(effective_from=T_FROM, effective_to=T_FROM)


def test_an_unbounded_interval_is_admissible():
    assert _metadata(effective_from=None, effective_to=None).effective_from is None


def test_the_policy_family_is_fixed_and_not_an_authored_field():
    metadata = _metadata()
    assert metadata.policy_family == AGENT_CONSTITUTION_POLICY_FAMILY
    with pytest.raises(TypeError):
        AgentConstitutionPolicyMetadata(
            policy_id="c-1",
            version="1.0.0",
            content_digest=PLACEHOLDER_CONTENT_DIGEST,
            scope=POLICY_SCOPE_GLOBAL,
            lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
            policy_family="something.else",
        )


def test_the_metadata_must_be_exactly_this_family_s_envelope():
    class Extended(AgentConstitutionPolicyMetadata):
        pass

    sneaky = Extended(
        policy_id="c-1",
        version="1.0.0",
        content_digest=PLACEHOLDER_CONTENT_DIGEST,
        scope=POLICY_SCOPE_GLOBAL,
        lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
    )
    with pytest.raises(AgentConstitutionFieldError):
        _draft(metadata=sneaky)


# --------------------------------------------------------------------------- #
# The digest binds every body field
# --------------------------------------------------------------------------- #


def test_the_declared_digest_binds_the_body():
    descriptor = ADAPTER.describe(make_constitution_policy())
    assert descriptor.body_digest() == descriptor.declared_content_digest


@pytest.mark.parametrize(
    "overrides",
    [
        dict(agent_constitution_ref="ugence.agent-constitution/tenant-1/other/v1"),
        dict(governed_role_refs=GOVERNED_ROLE_REFS[:1]),
        dict(dispositions_bound=FULL_DISPOSITIONS_BOUND),
        dict(review_actions_bound=FULL_REVIEW_ACTIONS_BOUND),
        dict(tool_scopes_bound=()),
        dict(version="1.0.1"),
        dict(effective_to=datetime(2027, 2, 1, tzinfo=timezone.utc)),
    ],
    ids=[
        "reference",
        "governed-roles",
        "dispositions-bound",
        "review-actions-bound",
        "tool-scopes-bound",
        "version",
        "effective-window",
    ],
)
def test_every_body_field_moves_the_digest(overrides):
    """`[V]` Conditional on the projection: each field is transitively signed."""

    base = ADAPTER.describe(make_constitution_policy()).body_digest()
    other = ADAPTER.describe(make_constitution_policy(**overrides)).body_digest()
    assert base != other
