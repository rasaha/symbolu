"""Two closed vocabularies, one source of truth each, and one open bound.

`ACC-S1-BASE` ratified the imported proposer enums as the single source of truth
for the closed-vocabulary bounds. The assertion that matters is set equality: if
a member were ever added to either ratified enum, or a spelling changed, this
family's accepted sets move with it and no fork is possible. A guard that merely
listed the members would pass while the two drifted apart.

The tool-scope bound is deliberately different: an **open** vocabulary, bounded
by the C5b ``Token`` grammar and by membership at the conformance boundary, not
enumerated — because a governed role's declared tool scopes are open tokens that
default empty.
"""

from __future__ import annotations

import pathlib

import pytest
from _agent_constitution_fixtures import make_constitution_policy
from ugence_agent_constitution_policy import (
    ADMITTED_CANDIDATE_DISPOSITION_TOKENS,
    ADMITTED_REVIEW_ACTION_TOKENS,
    CONSTITUTION_VOCABULARY_VERSION,
    AgentConstitutionFieldError,
    AgentConstitutionPolicy,
)
from ugence_agentic_proposer import CandidateDisposition, ReviewAction


def test_the_disposition_token_set_equals_the_imported_vocabulary_exactly():
    """Set equality, not containment: neither side may carry a member the other lacks."""

    assert ADMITTED_CANDIDATE_DISPOSITION_TOKENS == {
        member.value for member in CandidateDisposition
    }


def test_the_review_action_token_set_equals_the_imported_vocabulary_exactly():
    assert ADMITTED_REVIEW_ACTION_TOKENS == {member.value for member in ReviewAction}


def test_the_two_closed_vocabularies_do_not_overlap():
    """A token can never be lawful in both bounds at once."""

    assert not ADMITTED_CANDIDATE_DISPOSITION_TOKENS & ADMITTED_REVIEW_ACTION_TOKENS


def test_the_family_defines_no_second_spelling_of_either_vocabulary():
    """A fork is impossible only if there is nothing here to fork from."""

    src = (
        pathlib.Path(__file__).resolve().parents[1]
        / "src"
        / "ugence_agent_constitution_policy"
    )
    members = list(CandidateDisposition) + list(ReviewAction)
    for module in sorted(src.glob("*.py")):
        source = module.read_text(encoding="utf-8")
        for member in members:
            assert member.value not in source, (
                f"{module.name} restates {member.value!r}; the enum is the single "
                "source of truth and is imported, never copied"
            )


def test_the_vocabulary_version_names_the_clause_vocabulary_it_is_drawn_from():
    assert CONSTITUTION_VOCABULARY_VERSION == "ugence.agent-constitution/clauses/v1"
    assert (
        make_constitution_policy().constitution_vocabulary_version
        == CONSTITUTION_VOCABULARY_VERSION
    )


def test_a_bound_member_maps_onto_its_enum_with_order_preserved():
    policy = make_constitution_policy(
        dispositions_bound=tuple(sorted(m.value for m in CandidateDisposition)),
        review_actions_bound=tuple(sorted(m.value for m in ReviewAction)),
    )
    dispositions = tuple(
        CandidateDisposition(value)
        for value in policy.permitted_candidate_dispositions_bound
    )
    actions = tuple(
        ReviewAction(value) for value in policy.permitted_review_actions_bound
    )
    assert [m.value for m in dispositions] == list(
        policy.permitted_candidate_dispositions_bound
    )
    assert [m.value for m in actions] == list(policy.permitted_review_actions_bound)


def test_a_review_action_is_not_admitted_into_the_disposition_bound():
    """Cross-vocabulary members are refused even though both satisfy the grammar."""

    with pytest.raises(AgentConstitutionFieldError):
        make_constitution_policy(
            dispositions_bound=tuple(sorted(m.value for m in ReviewAction))
        )


def test_the_tool_scope_bound_is_grammar_bounded_not_enumerated():
    """Any lawful C5b Token is admissible; no closed list exists to consult."""

    policy = make_constitution_policy(tool_scopes_bound=("a.b:c-d", "zz.99"))
    assert policy.permitted_tool_scopes_bound == ("a.b:c-d", "zz.99")


def test_the_artifact_is_a_plain_stdlib_dataclass():
    """No pydantic model, no enum field: the authority canonicalizes it as-is."""

    import dataclasses

    assert dataclasses.is_dataclass(AgentConstitutionPolicy)
    assert not hasattr(AgentConstitutionPolicy, "model_fields")
    policy = make_constitution_policy()
    for values in (
        policy.governed_role_refs,
        policy.permitted_candidate_dispositions_bound,
        policy.permitted_review_actions_bound,
        policy.permitted_tool_scopes_bound,
    ):
        for value in values:
            assert type(value) is str
