"""Construction rules for the presented-role-facts input shape (§5.1).

Fail-closed: a refused construction produces no facts object, so nothing
malformed ever reaches the predicate to be subset-tested.
"""

from __future__ import annotations

import dataclasses

import pytest
from _constitution_conformance_fixtures import ROLE_REF, TENANT, make_facts
from ugence_agent_constitution_conformance import (
    ConstitutionFactsError,
    GovernedRoleFacts,
)


def test_well_formed_facts_construct():
    facts = make_facts()
    assert facts.tenant_id == TENANT
    assert facts.role_contract_ref == ROLE_REF


def test_the_facts_are_frozen():
    facts = make_facts()
    with pytest.raises(Exception):
        facts.role_contract_ref = "ugence.roles/other/v1"


def test_the_facts_are_a_plain_stdlib_dataclass():
    assert dataclasses.is_dataclass(GovernedRoleFacts)
    assert not hasattr(GovernedRoleFacts, "model_fields")


def test_the_tenant_may_be_the_canonical_empty_string():
    """A role governed by a GLOBAL-scope constitution carries the empty tenant."""

    assert make_facts(tenant_id="").tenant_id == ""


def test_the_role_reference_must_satisfy_the_c5a_identifier_grammar():
    with pytest.raises(ConstitutionFactsError):
        make_facts(role_contract_ref="has a space")
    with pytest.raises(ConstitutionFactsError):
        make_facts(role_contract_ref="-leading-hyphen")
    with pytest.raises(ConstitutionFactsError):
        make_facts(role_contract_ref="")


def test_the_role_reference_admits_the_slash_the_grammar_allows():
    assert make_facts(role_contract_ref="a/b:c.d-e").role_contract_ref == "a/b:c.d-e"


@pytest.mark.parametrize(
    "field", ["dispositions", "review_actions"], ids=["dispositions", "review-actions"]
)
def test_a_closed_surface_declaration_must_be_non_empty(field):
    """The declaring surface these mirror requires non-empty declarations."""

    with pytest.raises(ConstitutionFactsError):
        make_facts(**{field: ()})


def test_declared_tool_scopes_may_be_empty():
    assert make_facts(tool_scopes=()).declared_tool_scopes == ()


def test_a_duplicate_declared_member_is_refused():
    with pytest.raises(ConstitutionFactsError):
        make_facts(tool_scopes=("scope.a", "scope.a"))


def test_a_declared_member_must_be_exactly_a_str():
    with pytest.raises(ConstitutionFactsError):
        make_facts(tool_scopes=(b"scope.a",))


def test_a_declared_set_must_be_a_tuple_not_a_list():
    with pytest.raises(ConstitutionFactsError):
        make_facts(tool_scopes=["scope.a"])


def test_a_declared_member_must_satisfy_the_c5b_token_grammar():
    with pytest.raises(ConstitutionFactsError):
        make_facts(tool_scopes=("has a space",))
    # ``/`` is C5a-only; declared tokens are held to the Token grammar.
    with pytest.raises(ConstitutionFactsError):
        make_facts(tool_scopes=("a/b",))


def test_declared_sets_are_order_insensitive_at_construction():
    """The predicate is set semantics; presented facts need not be sorted."""

    unsorted = ("scope.b", "scope.a")
    assert make_facts(tool_scopes=unsorted).declared_tool_scopes == unsorted


def test_an_over_long_reference_is_refused():
    with pytest.raises(ConstitutionFactsError):
        make_facts(role_contract_ref="a" * 201)


def test_a_declared_token_outside_its_enum_is_stated_not_refused():
    """Presentation is not vocabulary: the predicate answers False for it.

    A token no enum contains can never sit inside a signed closed bound, so the
    honest answer is a report of non-conformance, not a refusal to state the
    facts. The predicate half of this claim is proven in test_conformance.
    """

    facts = make_facts(dispositions=("SOMETHING_NO_ENUM_CONTAINS",))
    assert facts.declared_candidate_dispositions == ("SOMETHING_NO_ENUM_CONTAINS",)
