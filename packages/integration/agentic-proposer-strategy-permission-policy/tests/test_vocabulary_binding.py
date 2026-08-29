"""One vocabulary, one source of truth, and a policy that can actually be stamped.

Two independent obligations meet here.

**The vocabulary.** The three ratified spellings live in the Agentic Proposer's
``ReasoningStrategy`` and are *imported*, never restated. The assertion that
matters is set equality: if a fourth member were ever ratified, or a spelling
changed, this family's accepted set moves with it and no fork is possible. A
guard that merely listed the three would pass while the two drifted apart.

**The grammar.** A lawfully issued policy's ``policy_id`` and ``version`` are
stamped straight onto ``ProposerAdvisory`` through ``StrategyPolicyResponse``,
whose fields are C5b ``Token``\\ s. A policy that could not satisfy that grammar
would issue, sign and resolve perfectly and then be unusable at the boundary it
exists to serve. Pinned here by constructing the real response shape.
"""

from __future__ import annotations

import pytest
from _strategy_permission_fixtures import (
    STRATEGY_POLICY_REF,
    make_permission_policy,
)
from ugence_agentic_proposer import ReasoningStrategy, StrategyPolicyResponse
from ugence_agentic_proposer_strategy_permission_policy import (
    ADMITTED_STRATEGY_TOKENS,
    STRATEGY_VOCABULARY_VERSION,
    StrategyPermissionFieldError,
    StrategyPermissionPolicy,
)


def test_the_accepted_token_set_equals_the_imported_vocabulary_exactly():
    """Set equality, not containment: neither side may carry a member the other lacks."""

    assert ADMITTED_STRATEGY_TOKENS == {member.value for member in ReasoningStrategy}


def test_the_vocabulary_is_the_three_ratified_spellings():
    assert ADMITTED_STRATEGY_TOKENS == {
        "SINGLE_CANDIDATE_UNREVISED",
        "MULTI_CANDIDATE_UNREVISED",
        "REVISED_ADVISORY",
    }


def test_the_family_defines_no_second_spelling_of_the_vocabulary():
    """A fork is impossible only if there is nothing here to fork from."""

    import pathlib

    src = (
        pathlib.Path(__file__).resolve().parents[1]
        / "src"
        / "ugence_agentic_proposer_strategy_permission_policy"
    )
    for module in sorted(src.glob("*.py")):
        source = module.read_text(encoding="utf-8")
        for member in ReasoningStrategy:
            assert member.value not in source, (
                f"{module.name} restates {member.value!r}; the enum is the single "
                "source of truth and is imported, never copied"
            )


def test_the_vocabulary_version_names_the_vocabulary_it_is_drawn_from():
    assert STRATEGY_VOCABULARY_VERSION == "ugence.agentic-proposer.reasoning-strategy/v1"
    assert make_permission_policy().vocabulary_version == STRATEGY_VOCABULARY_VERSION


# --------------------------------------------------------------------------- #
# C5b — a lawfully issued policy is stampable on the advisory
# --------------------------------------------------------------------------- #


def test_an_issued_policy_s_identity_satisfies_the_response_grammar():
    policy = make_permission_policy()
    response = StrategyPolicyResponse(
        strategy_policy_id=policy.metadata.policy_id,
        strategy_policy_version=policy.metadata.version,
        permitted_strategies=tuple(
            ReasoningStrategy(value) for value in policy.permitted_strategies
        ),
        strategy_policy_ref=policy.strategy_policy_ref,
    )
    assert response.strategy_policy_id == policy.metadata.policy_id
    assert response.strategy_policy_version == policy.metadata.version
    assert isinstance(response.strategy_policy_version, str)
    assert response.strategy_policy_ref == STRATEGY_POLICY_REF


def test_the_family_refuses_an_id_the_response_shape_would_reject():
    """The refusal happens here, not at the advisory boundary.

    ``/`` is admitted by the C5a ``Identifier`` grammar the *reference* uses and
    barred by the C5b ``Token`` grammar the *id* uses. A family that accepted it
    would issue a policy that no advisory could ever carry.
    """

    with pytest.raises(StrategyPermissionFieldError):
        make_permission_policy(policy_id="tenant-1/strategy-permission")

    with pytest.raises(ValueError):
        StrategyPolicyResponse(
            strategy_policy_id="tenant-1/strategy-permission",
            strategy_policy_version="1.0.0",
            permitted_strategies=(ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED,),
            strategy_policy_ref=STRATEGY_POLICY_REF,
        )


def test_the_reference_this_family_signs_satisfies_the_request_grammar():
    """The signed reference and the request's reference share one grammar.

    They must, or the exact-equality check the resolver performs could never
    succeed for a reference a role can actually carry.
    """

    from ugence_agentic_proposer import StrategyPolicyRequest
    from datetime import datetime, timezone

    policy = make_permission_policy()
    request = StrategyPolicyRequest(
        strategy_policy_ref=policy.strategy_policy_ref,
        tenant_id=policy.metadata.tenant_id,
        case_ref="case-1",
        as_of=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    assert request.strategy_policy_ref == policy.strategy_policy_ref


def test_a_permitted_set_maps_onto_enum_members_with_order_preserved():
    policy = make_permission_policy(
        permitted=tuple(sorted(member.value for member in ReasoningStrategy))
    )
    mapped = tuple(ReasoningStrategy(value) for value in policy.permitted_strategies)
    assert [m.value for m in mapped] == list(policy.permitted_strategies)


def test_the_artifact_is_a_plain_stdlib_dataclass():
    """No pydantic model, no enum field: the authority canonicalizes it as-is."""

    import dataclasses

    assert dataclasses.is_dataclass(StrategyPermissionPolicy)
    assert not hasattr(StrategyPermissionPolicy, "model_fields")
    for value in make_permission_policy().permitted_strategies:
        assert type(value) is str
