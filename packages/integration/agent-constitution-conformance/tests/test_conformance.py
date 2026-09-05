"""The §2.3 conformance predicate, proven in both directions (§5.4).

Conforming facts answer ``True``; each of the four clauses violated
independently answers ``False``. Set semantics, order-insensitive; empty
declared tool scopes conform to any bound. The verifier returns a ``bool`` and
nothing else — no artifact on failure, no disposition, no exception for a
non-conforming presentation.
"""

from __future__ import annotations

import pytest
from _constitution_conformance_fixtures import (
    ALL_DISPOSITIONS,
    ALL_REVIEW_ACTIONS,
    DISPOSITIONS_BOUND,
    OTHER_GOVERNED_ROLE_REF,
    REVIEW_ACTIONS_BOUND,
    TOOL_SCOPES_BOUND,
    make_constitution_policy,
    make_facts,
)
from ugence_agent_constitution_conformance import (
    ConstitutionFactsError,
    GovernedRoleFacts,
    role_facts_conform,
)
from ugence_agent_constitution_policy import AgentConstitutionPolicy

POLICY = make_constitution_policy()


# --------------------------------------------------------------------------- #
# True: conforming facts
# --------------------------------------------------------------------------- #


def test_conforming_facts_answer_true():
    assert role_facts_conform(policy=POLICY, facts=make_facts()) is True


def test_the_other_governed_role_conforms_too():
    facts = make_facts(role_contract_ref=OTHER_GOVERNED_ROLE_REF)
    assert role_facts_conform(policy=POLICY, facts=facts) is True


def test_a_strict_subset_of_each_bound_conforms():
    facts = make_facts(
        dispositions=DISPOSITIONS_BOUND[:1],
        review_actions=REVIEW_ACTIONS_BOUND[:1],
        tool_scopes=TOOL_SCOPES_BOUND[:1],
    )
    assert role_facts_conform(policy=POLICY, facts=facts) is True


def test_exact_equality_with_every_bound_conforms():
    facts = make_facts(
        dispositions=DISPOSITIONS_BOUND,
        review_actions=REVIEW_ACTIONS_BOUND,
        tool_scopes=TOOL_SCOPES_BOUND,
    )
    assert role_facts_conform(policy=POLICY, facts=facts) is True


def test_empty_declared_tool_scopes_conform_to_any_bound():
    assert role_facts_conform(policy=POLICY, facts=make_facts(tool_scopes=())) is True
    empty_bound = make_constitution_policy(tool_scopes_bound=())
    assert (
        role_facts_conform(policy=empty_bound, facts=make_facts(tool_scopes=()))
        is True
    )


def test_the_predicate_is_order_insensitive():
    """Set semantics: the same members in any order answer the same."""

    reversed_scopes = tuple(reversed(TOOL_SCOPES_BOUND))
    assert list(reversed_scopes) != sorted(reversed_scopes)
    facts = make_facts(tool_scopes=reversed_scopes)
    assert role_facts_conform(policy=POLICY, facts=facts) is True


# --------------------------------------------------------------------------- #
# False: each clause violated independently
# --------------------------------------------------------------------------- #


def test_a_role_outside_the_signed_role_list_does_not_conform():
    facts = make_facts(role_contract_ref="ugence.roles/tenant-1/ungoverned/v1")
    assert role_facts_conform(policy=POLICY, facts=facts) is False


def test_a_disposition_outside_its_bound_does_not_conform():
    outside = tuple(sorted(set(ALL_DISPOSITIONS) - set(DISPOSITIONS_BOUND)))[:1]
    assert outside, "the fixture bound must be a strict subset for this test"
    facts = make_facts(dispositions=DISPOSITIONS_BOUND + outside)
    assert role_facts_conform(policy=POLICY, facts=facts) is False


def test_a_review_action_outside_its_bound_does_not_conform():
    outside = tuple(sorted(set(ALL_REVIEW_ACTIONS) - set(REVIEW_ACTIONS_BOUND)))[:1]
    assert outside, "the fixture bound must be a strict subset for this test"
    facts = make_facts(review_actions=REVIEW_ACTIONS_BOUND + outside)
    assert role_facts_conform(policy=POLICY, facts=facts) is False


def test_a_tool_scope_outside_its_bound_does_not_conform():
    facts = make_facts(tool_scopes=TOOL_SCOPES_BOUND + ("scope.unbounded",))
    assert role_facts_conform(policy=POLICY, facts=facts) is False


def test_any_declared_scope_fails_an_empty_tool_scope_bound():
    empty_bound = make_constitution_policy(tool_scopes_bound=())
    facts = make_facts(tool_scopes=TOOL_SCOPES_BOUND[:1])
    assert role_facts_conform(policy=empty_bound, facts=facts) is False


def test_a_token_no_enum_contains_does_not_conform():
    """The construction-side half of this claim is proven in test_facts."""

    facts = make_facts(dispositions=("SOMETHING_NO_ENUM_CONTAINS",))
    assert role_facts_conform(policy=POLICY, facts=facts) is False


def test_a_false_answer_is_a_report_not_an_exception_and_mints_nothing():
    facts = make_facts(role_contract_ref="ugence.roles/tenant-1/ungoverned/v1")
    answer = role_facts_conform(policy=POLICY, facts=facts)
    assert answer is False
    assert type(answer) is bool


# --------------------------------------------------------------------------- #
# Input discipline
# --------------------------------------------------------------------------- #


def test_the_verifier_requires_exactly_this_family_s_artifact():
    class Extended(AgentConstitutionPolicy):
        pass

    sneaky = Extended(
        metadata=POLICY.metadata,
        agent_constitution_ref=POLICY.agent_constitution_ref,
        governed_role_refs=POLICY.governed_role_refs,
        permitted_candidate_dispositions_bound=POLICY.permitted_candidate_dispositions_bound,
        permitted_review_actions_bound=POLICY.permitted_review_actions_bound,
        permitted_tool_scopes_bound=POLICY.permitted_tool_scopes_bound,
    )
    with pytest.raises(ConstitutionFactsError):
        role_facts_conform(policy=sneaky, facts=make_facts())


def test_the_verifier_requires_exactly_the_facts_type():
    class ExtendedFacts(GovernedRoleFacts):
        pass

    facts = make_facts()
    sneaky = ExtendedFacts(
        tenant_id=facts.tenant_id,
        role_contract_ref=facts.role_contract_ref,
        declared_candidate_dispositions=facts.declared_candidate_dispositions,
        declared_review_actions=facts.declared_review_actions,
        declared_tool_scopes=facts.declared_tool_scopes,
    )
    with pytest.raises(ConstitutionFactsError):
        role_facts_conform(policy=POLICY, facts=sneaky)
    with pytest.raises(ConstitutionFactsError):
        role_facts_conform(policy=POLICY, facts={"role_contract_ref": "x"})


def test_the_predicate_is_deterministic():
    facts = make_facts()
    answers = {role_facts_conform(policy=POLICY, facts=facts) for _ in range(5)}
    assert answers == {True}


def test_the_tenant_plays_no_part_in_the_predicate():
    """Ratified as role membership plus three subsets; tenant is resolution's."""

    facts = make_facts(tenant_id="tenant-entirely-other")
    assert role_facts_conform(policy=POLICY, facts=facts) is True
