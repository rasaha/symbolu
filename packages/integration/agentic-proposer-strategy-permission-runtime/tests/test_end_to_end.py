"""The end-to-end proof: a real policy, a real resolver, a real advisory, real replay.

This is what shows the execution blocker closed. Every piece is genuine — a
strategy-permission policy issued and signed through the shared Policy Authority,
this distribution's concrete resolver, the Agentic Proposer's own ratified
builders, and its six-check replay over the resulting triple.

**What passing here proves.** That the ratified pieces compose: a lawfully issued
and signed policy version can be resolved through configured trust at a caller's
explicit instant, stamped onto an advisory by the proposer's own builder, and
replayed to ``True`` by the proposer's own verifier without either package being
modified.

**What it does not prove, stated because the distinction is the point.** It
establishes **nothing** about private reasoning or chain-of-thought. It does
**not** prove that any declared procedure was *executed*. It establishes no
observable-stage conformance beyond what the advisory's own shape shows — no
component records reasoning stages, so that producer still does not exist. It
creates **no compute authorization and no consequential execution authority**;
those remain with Risk Authority, ActionGate and Decision Authority. And it
cannot establish that this resolver is honest: the reference echo is a
correlation check, and a resolver that wished to mislead would echo back what it
was handed while resolving something else.
"""

from __future__ import annotations

import pytest
import s1_specification_mirror as spec
import ugence_agentic_proposer as ap
from _permission_runtime_fixtures import (
    MULTI,
    POLICY_ID,
    POLICY_VERSION,
    SINGLE,
    STRATEGY_POLICY_REF,
    issued_world,
    make_request,
    make_world,
)

REVISED = ap.ReasoningStrategy.REVISED_ADVISORY


# --------------------------------------------------------------------------- #
# §9.8 — construction with the concrete resolver
# --------------------------------------------------------------------------- #


def test_an_advisory_is_built_with_the_concrete_resolver_and_stamps_the_issued_policy():
    _, policy, _, resolver = issued_world()
    world = make_world(resolver=resolver)
    advisory = world["advisory"]

    assert advisory.strategy_policy_id == policy.metadata.policy_id == POLICY_ID
    assert advisory.strategy_policy_version == policy.metadata.version == POLICY_VERSION
    assert type(advisory.strategy_policy_version) is str
    assert advisory.declared_strategy is SINGLE


def test_the_process_record_derives_its_declaration_from_that_advisory():
    _, _, _, resolver = issued_world()
    world = make_world(resolver=resolver)

    assert world["record"].declared_strategy is world["advisory"].declared_strategy
    assert world["record"].advisory_digest == world["advisory"].advisory_digest


def test_a_strategy_the_issued_policy_does_not_permit_refuses_construction():
    """The refusal is structural: no advisory exists, and no disposition is emitted."""

    _, _, _, resolver = issued_world(permitted=(SINGLE.value,))
    with pytest.raises(ap.CrossContractViolationError):
        make_world(resolver=resolver, declared=REVISED)


def test_the_construction_refusal_names_no_reserved_term_or_disposition():
    """`S2B-D5=A` leaves the operational mapping unruled; nothing here names one."""

    _, _, _, resolver = issued_world(permitted=(SINGLE.value,))
    with pytest.raises(ap.CrossContractViolationError) as excinfo:
        make_world(resolver=resolver, declared=REVISED)

    message = str(excinfo.value).upper()
    for reserved in ap.RESERVED_AUTHORITY_VOCABULARY:
        assert reserved not in message, reserved
    for outcome in ap.TerminalOutcome:
        assert outcome.value not in message, outcome.value
    for disposition in ap.CandidateDisposition:
        assert disposition.value not in message, disposition.value


# --------------------------------------------------------------------------- #
# §9.6 — the echo is a correlation check
# --------------------------------------------------------------------------- #


def test_the_response_echoes_the_request_reference_exactly():
    _, _, _, resolver = issued_world()
    response = resolver.resolve(request=make_request())
    assert response.strategy_policy_ref == STRATEGY_POLICY_REF


def test_a_mis_echoing_resolver_makes_the_builder_refuse():
    """Only a stub can produce this state; a correct resolver cannot."""

    mis_echoing = spec.StubStrategyPolicyResolver(
        echo_ref="some/other/reference", policy_id=POLICY_ID,
        policy_version=POLICY_VERSION)
    with pytest.raises(ap.CrossContractViolationError):
        make_world(resolver=mis_echoing)


def test_the_concrete_resolver_cannot_produce_that_state():
    """It echoes the request's own field, so correlation holds by construction."""

    _, _, _, resolver = issued_world()
    for case_ref in ("case-1", "case-2"):
        request = make_request(case_ref=case_ref)
        assert (
            resolver.resolve(request=request).strategy_policy_ref
            == request.strategy_policy_ref
        )


# --------------------------------------------------------------------------- #
# §9.9 — the six-check replay, positive control then each check independently
# --------------------------------------------------------------------------- #


def _triple():
    _, policy, _, resolver = issued_world()
    response = resolver.resolve(request=make_request())
    world = make_world(resolver=resolver)
    return world, response, policy


def test_the_six_check_replay_passes_on_the_real_triple():
    """The positive control. Without it, every negative below proves nothing."""

    world, response, _ = _triple()
    assert (
        ap.verify_strategy_permission(
            advisory=world["advisory"],
            policy=response,
            role=world["role"],
            process_record=world["record"],
        )
        is True
    )


def test_check_1_a_different_stamped_identity_fails_replay():
    world, response, _ = _triple()
    broken = response.model_copy(update={"strategy_policy_id": "other-policy"})
    assert (
        ap.verify_strategy_permission(
            advisory=world["advisory"], policy=broken, role=world["role"],
            process_record=world["record"])
        is False
    )


def test_check_1b_a_different_stamped_version_fails_replay():
    world, response, _ = _triple()
    broken = response.model_copy(update={"strategy_policy_version": "9.9.9"})
    assert (
        ap.verify_strategy_permission(
            advisory=world["advisory"], policy=broken, role=world["role"],
            process_record=world["record"])
        is False
    )


def test_check_2_a_role_naming_another_reference_fails_replay():
    world, response, _ = _triple()
    other_role = world["role"].model_copy(
        update={"strategy_policy_ref": "some/other/reference"})
    assert (
        ap.verify_strategy_permission(
            advisory=world["advisory"], policy=response, role=other_role,
            process_record=world["record"])
        is False
    )


def test_check_3_an_empty_permitted_set_fails_replay():
    """The state the response shape admits on purpose, and this family never issues."""

    world, response, _ = _triple()
    broken = response.model_copy(update={"permitted_strategies": ()})
    assert (
        ap.verify_strategy_permission(
            advisory=world["advisory"], policy=broken, role=world["role"],
            process_record=world["record"])
        is False
    )


def test_check_4_a_declaration_outside_the_permitted_set_fails_replay():
    world, response, _ = _triple()
    broken = response.model_copy(update={"permitted_strategies": (REVISED,)})
    assert (
        ap.verify_strategy_permission(
            advisory=world["advisory"], policy=broken, role=world["role"],
            process_record=world["record"])
        is False
    )


def test_check_5_a_record_bound_to_another_advisory_fails_replay():
    world, response, _ = _triple()
    other_world, _, _ = _triple()
    assert (
        ap.verify_strategy_permission(
            advisory=world["advisory"], policy=response, role=world["role"],
            process_record=other_world["record"].model_copy(
                update={"advisory_digest": "0" * 64}))
        is False
    )


def test_check_6_a_declaration_the_shape_does_not_yield_fails_replay():
    """`§9.10` — and construction still succeeds, because check 6 is replay-only."""

    _, _, _, resolver = issued_world(permitted=(SINGLE.value, MULTI.value))
    response = resolver.resolve(request=make_request())
    world = make_world(resolver=resolver, candidate_count=2, declared=SINGLE)

    # Construction succeeded: a two-candidate advisory declaring the single-candidate
    # token is constructible, and only replay reports the mismatch.
    assert world["advisory"].declared_strategy is SINGLE
    assert len(world["advisory"].candidates) == 2
    assert (
        ap.verify_strategy_permission(
            advisory=world["advisory"], policy=response, role=world["role"],
            process_record=world["record"])
        is False
    )


# --------------------------------------------------------------------------- #
# §9.10 — a shape-derived strategy outside the permitted set
# --------------------------------------------------------------------------- #


def test_a_shape_derived_strategy_outside_the_permitted_set_fails_replay():
    """Issued permitting only the single-candidate token; the shape yields the other."""

    _, policy, _, resolver = issued_world(permitted=(SINGLE.value,))
    response = resolver.resolve(request=make_request())
    world = make_world(resolver=resolver, candidate_count=2, declared=SINGLE)

    assert policy.permitted_strategies == (SINGLE.value,)
    assert (
        ap.verify_strategy_permission(
            advisory=world["advisory"], policy=response, role=world["role"],
            process_record=world["record"])
        is False
    )


def test_the_both_permitted_variant_isolates_check_6_from_check_4():
    """With both members permitted, check 4 passes and only check 6 can fail.

    Without this variant the failure above would be ambiguous: it could be check 4
    reporting an unpermitted declaration rather than check 6 reporting a shape
    mismatch. Here the declaration is permitted, so the ``False`` is check 6's
    alone — and the positive control below shows the same world passes once the
    declaration matches the shape.
    """

    _, _, _, resolver = issued_world(permitted=(SINGLE.value, MULTI.value))
    response = resolver.resolve(request=make_request())

    mismatched = make_world(resolver=resolver, candidate_count=2, declared=SINGLE)
    assert SINGLE in response.permitted_strategies
    assert (
        ap.verify_strategy_permission(
            advisory=mismatched["advisory"], policy=response, role=mismatched["role"],
            process_record=mismatched["record"])
        is False
    )

    matched = make_world(resolver=resolver, candidate_count=2, declared=MULTI)
    assert (
        ap.verify_strategy_permission(
            advisory=matched["advisory"], policy=response, role=matched["role"],
            process_record=matched["record"])
        is True
    )


# --------------------------------------------------------------------------- #
# The limits, asserted rather than only written down
# --------------------------------------------------------------------------- #


def test_replay_emits_no_disposition_and_returns_only_a_bool():
    """`False` is not a denial, and this boundary maps it to no outcome."""

    world, response, _ = _triple()
    broken = response.model_copy(update={"permitted_strategies": ()})
    outcome = ap.verify_strategy_permission(
        advisory=world["advisory"], policy=broken, role=world["role"],
        process_record=world["record"])
    assert outcome is False
    assert type(outcome) is bool


def test_nothing_in_this_proof_records_a_reasoning_stage():
    """`[G]` No component records observable reasoning stages; none is invented here."""

    world, _, _ = _triple()
    for artifact in (world["advisory"], world["record"]):
        fields = set(type(artifact).model_fields)
        for absent in ("reasoning_stages", "stages", "chain_of_thought", "trace"):
            assert absent not in fields
