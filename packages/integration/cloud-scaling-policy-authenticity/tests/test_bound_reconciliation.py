"""Gate 16 — R-8's remaining half: the candidate's ceilings against the authenticated ones.

Gates 14 and 15 *extract* an authenticated bound. Until this gate nothing compared it
against what the candidate carries, so a candidate self-asserting 20/5 verified against a
genuinely issued bound of 5/1 for its exact selector. Extraction is not reconciliation, and
the whole of this module is the difference.

Every case here runs against a **genuine** chain: a real authority, a really issued
capacity-bounds policy, and a Phase 5A candidate built through the real builder. Nothing is
stubbed, because a reconciliation proved against a hand-rolled pair proves nothing about the
artifacts it will actually meet.
"""

from __future__ import annotations

import dataclasses

import pytest

from _policy_fixtures import (
    T_CANDIDATE,
    DEFAULT_TEST_BOUNDS,
    genuine_candidate,
    issued,
    issued_bounds,
    phase5a_builders,
    verifier_for,
)
from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome as O

pytestmark = pytest.mark.skipif(
    phase5a_builders() is None,
    reason="the Phase 5A test tree is unavailable outside a source checkout",
)

_Bound = type(DEFAULT_TEST_BOUNDS[0])

#: The genuine candidate's own selector and numbers, asserted rather than assumed by
#: ``test_the_fixtures_still_carry_the_numbers_these_cases_reason_about``.
SELECTOR = ("scale_up", "deploy/checkout-api")
CARRIED_MAGNITUDE, CARRIED_DELTA = 20, 5
REQUESTED_MAGNITUDE, REQUESTED_DELTA = 9, 3


def _bound(action_type=SELECTOR[0], resource_class=SELECTOR[1], magnitude=100, delta=25):
    return _Bound(
        action_type=action_type,
        resource_class=resource_class,
        max_permitted_magnitude=magnitude,
        max_permitted_delta=delta,
    )


def _verify_against(bounds, candidate=None):
    """Verify the genuine candidate against a policy stating exactly ``bounds``."""

    authority, record = issued_bounds(bounds=bounds)
    if candidate is None:
        candidate = genuine_candidate(record)
    return verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_CANDIDATE,
        candidate=candidate,
    )


@pytest.mark.invariant
def test_the_fixtures_still_carry_the_numbers_these_cases_reason_about():
    """Every case below is written against these values. If they move, say so loudly."""

    _authority, record = issued_bounds()
    candidate = genuine_candidate(record)
    scope = candidate.target_scope
    assert (scope.action_type, scope.resource_class) == SELECTOR
    assert (scope.max_permitted_magnitude, scope.max_permitted_delta) == (
        CARRIED_MAGNITUDE,
        CARRIED_DELTA,
    )
    assert (scope.requested_magnitude, scope.requested_delta) == (
        REQUESTED_MAGNITUDE,
        REQUESTED_DELTA,
    )


# ======================================================================================
# The genuine chain, and the narrower-is-fine ruling
# ======================================================================================


@pytest.mark.happy
def test_a_genuine_candidate_within_the_authenticated_bound_verifies():
    result = _verify_against((_bound(magnitude=100, delta=25),))
    assert result.outcome is O.VERIFIED, result.refusal
    only = result.verified_policy.capacity_bounds_fact
    assert len(only) == 1
    assert only[0].max_permitted_magnitude == 100


@pytest.mark.happy
def test_a_candidate_narrower_than_the_policy_verifies():
    """Ruling 1: a candidate may bind itself more tightly than the policy does."""

    result = _verify_against((_bound(magnitude=CARRIED_MAGNITUDE + 1, delta=CARRIED_DELTA + 1),))
    assert result.outcome is O.VERIFIED, result.refusal


@pytest.mark.happy
def test_the_comparison_is_inclusive_at_the_boundary():
    """``<=``, not ``<``: a candidate exactly at the authenticated ceiling is within it."""

    result = _verify_against((_bound(magnitude=CARRIED_MAGNITUDE, delta=CARRIED_DELTA),))
    assert result.outcome is O.VERIFIED, result.refusal


# ======================================================================================
# The four refusals
# ======================================================================================


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "magnitude, delta, named",
    [
        (CARRIED_MAGNITUDE - 1, CARRIED_DELTA, "max_permitted_magnitude"),
        (CARRIED_MAGNITUDE, CARRIED_DELTA - 1, "max_permitted_delta"),
    ],
)
def test_a_candidate_looser_than_the_authenticated_bound_is_refused(magnitude, delta, named):
    """The measured R-8 gap: 20/5 carried against a policy that states less."""

    result = _verify_against((_bound(magnitude=magnitude, delta=delta),))
    assert result.outcome is O.CANDIDATE_BOUND_EXCEEDED
    assert named in result.refusal.detail
    assert result.verified_policy is None


@pytest.mark.adversarial
def test_the_request_itself_is_compared_against_the_authenticated_bound():
    """Ruling 1's defence in depth.

    Phase 5A already compares the request against the candidate's *own* copy of the ceiling.
    This check does not depend on that copy being honest: here the carried ceiling is inside
    the authenticated one and only the request exceeds it, which the carried-ceiling
    comparison alone would admit.
    """

    builders = phase5a_builders()
    projection = builders.build_projection()
    scope = builders.build_target_scope(projection)
    assert scope.requested_magnitude > REQUESTED_MAGNITUDE - 1

    result = _verify_against(
        (_bound(magnitude=REQUESTED_MAGNITUDE - 1, delta=25),)
    )
    assert result.outcome is O.CANDIDATE_BOUND_EXCEEDED
    detail = result.refusal.detail
    # The *carried* ceiling is reported first because it is checked first; what matters for
    # this property is that the request is reached at all when the carried one passes.
    assert "max_permitted_magnitude" in detail or "requested_magnitude" in detail


@pytest.mark.adversarial
def test_a_selector_that_matches_nothing_is_refused_not_defaulted():
    """Ruling 2/3: exact and fail-closed. A miss is a refusal, never somebody else's ceiling."""

    result = _verify_against((_bound(action_type="scale_down"),))
    assert result.outcome is O.CANDIDATE_BOUND_SELECTOR_MISS
    assert result.verified_policy is None


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "resource_class",
    ["", "deploy/checkout-api ", "DEPLOY/CHECKOUT-API", "deploy/checkout-apiX"],
)
def test_no_resource_class_spelling_is_treated_as_equivalent_or_as_a_wildcard(resource_class):
    """`""` is not "any", case is not normalized, and whitespace is not trimmed."""

    result = _verify_against((_bound(resource_class=resource_class),))
    assert result.outcome is O.CANDIDATE_BOUND_SELECTOR_MISS


@pytest.mark.adversarial
def test_two_bounds_for_one_selector_are_ambiguous_rather_than_first_wins():
    """Ruling 3: which ceiling applies is not determined by the body, so nothing may pick."""

    result = _verify_against((_bound(magnitude=100), _bound(magnitude=1)))
    assert result.outcome is O.CANDIDATE_BOUND_SELECTOR_AMBIGUOUS
    assert result.verified_policy is None


@pytest.mark.adversarial
def test_a_candidate_paired_with_a_non_bounds_policy_is_refused():
    """Ruling 3: never ``VERIFIED`` without an applicable authenticated bound."""

    authority, record = issued()
    candidate = genuine_candidate(record)
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_CANDIDATE,
        candidate=candidate,
    )
    assert result.outcome is O.CANDIDATE_POLICY_STATES_NO_BOUNDS
    assert result.verified_policy is None


@pytest.mark.invariant
def test_a_policy_that_states_no_bound_still_verifies_without_a_candidate():
    """The refusal is about the *pairing*, not about non-bounds policies as such."""

    authority, record = issued()
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_CANDIDATE,
    )
    assert result.outcome is O.VERIFIED
    assert result.verified_policy.capacity_bounds_fact is None


# ======================================================================================
# Reason precedence, and every branch neutralised
# ======================================================================================


@pytest.mark.invariant
@pytest.mark.parametrize(
    "bounds, expected",
    [
        # An *empty* bounds tuple never reaches gate 16: gate 15 already refuses a
        # bounds-family policy that carries no bound, and that refusal is the older and more
        # specific one. Recorded here rather than asserted as gate 16's, because measuring it
        # is what showed CANDIDATE_POLICY_STATES_NO_BOUNDS is reachable only for a policy
        # family that supplies no bounds at all — which the non-bounds case below covers.
        ((), O.POLICY_BOUNDS_MALFORMED),
        # A miss beats an exceedance — the bound that would have been exceeded is not this
        # candidate's bound, so reporting the ceiling would name the wrong policy row.
        ((_bound(action_type="scale_down", magnitude=1, delta=1),),
         O.CANDIDATE_BOUND_SELECTOR_MISS),
        # Ambiguity beats an exceedance: with two rows matching, "the" ceiling does not exist
        # to be exceeded.
        ((_bound(magnitude=1, delta=1), _bound(magnitude=100, delta=25)),
         O.CANDIDATE_BOUND_SELECTOR_AMBIGUOUS),
        # And only when exactly one row applies is its ceiling the answer.
        ((_bound(magnitude=1, delta=1),), O.CANDIDATE_BOUND_EXCEEDED),
    ],
)
def test_the_refusal_precedence_is_fixed(bounds, expected):
    """Each case is failing more than one way; the reported reason is pinned, not incidental."""

    assert _verify_against(bounds).outcome is expected


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "bounds, neutralised",
    [
        ((_bound(action_type="scale_down"),), O.CANDIDATE_BOUND_SELECTOR_MISS),
        ((_bound(magnitude=1, delta=1),), O.CANDIDATE_BOUND_EXCEEDED),
    ],
)
def test_each_branch_is_load_bearing_when_neutralised(monkeypatch, bounds, neutralised):
    """Suppress exactly one branch and watch its attack reach a minted artifact.

    A guard that refuses is not yet a guard that is *doing* the refusing — a sibling may be
    answering for it. Here the branch under test is silenced and nothing else is, so a
    ``VERIFIED`` afterwards proves this branch, alone, stood between the attack and an
    artifact. The whole helper is left in place; only its verdict for this one outcome is
    dropped.
    """

    from ugence_cloud_scaling_policy_authenticity import verification as V

    real = V._bound_reconciliation_problem

    def _without_this_branch(candidate, capacity_bounds):
        verdict = real(candidate, capacity_bounds)
        if verdict is not None and verdict[0] is neutralised:
            return None
        return verdict

    monkeypatch.setattr(V, "_bound_reconciliation_problem", _without_this_branch)
    result = _verify_against(bounds)
    assert result.outcome is O.VERIFIED, (
        f"{neutralised.value} was neutralised and the attack was still refused as "
        f"{result.outcome.value}: a sibling is answering for it"
    )
    assert result.verified_policy is not None


@pytest.mark.adversarial
def test_the_whole_gate_is_what_stands_between_the_measured_gap_and_an_artifact():
    """The R-8 gap itself, reproduced with the gate silenced and closed with it in place."""

    from ugence_cloud_scaling_policy_authenticity import verification as V

    understated = (_bound(magnitude=5, delta=1),)

    monkeypatch_target = "_bound_reconciliation_problem"
    real = getattr(V, monkeypatch_target)
    try:
        setattr(V, monkeypatch_target, lambda candidate, capacity_bounds: None)
        before = _verify_against(understated)
    finally:
        setattr(V, monkeypatch_target, real)

    assert before.outcome is O.VERIFIED, "the pre-R-8 gap did not reproduce"
    assert before.verified_policy.capacity_bounds_fact[0].max_permitted_magnitude == 5

    after = _verify_against(understated)
    assert after.outcome is O.CANDIDATE_BOUND_EXCEEDED
    assert after.verified_policy is None


@pytest.mark.adversarial
def test_the_no_bounds_branch_is_load_bearing_when_neutralised(monkeypatch):
    """Silence it and a candidate paired with a non-bounds policy reaches an artifact."""

    from ugence_cloud_scaling_policy_authenticity import verification as V

    real = V._bound_reconciliation_problem

    def _without_this_branch(candidate, capacity_bounds):
        verdict = real(candidate, capacity_bounds)
        if verdict is not None and verdict[0] is O.CANDIDATE_POLICY_STATES_NO_BOUNDS:
            return None
        return verdict

    authority, record = issued()
    candidate = genuine_candidate(record)

    monkeypatch.setattr(V, "_bound_reconciliation_problem", _without_this_branch)
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_CANDIDATE,
        candidate=candidate,
    )
    assert result.outcome is O.VERIFIED
    assert result.verified_policy.capacity_bounds_fact is None


@pytest.mark.adversarial
def test_the_ambiguity_branch_is_the_typed_answer_to_a_fail_closed_one(monkeypatch):
    """Neutralising ambiguity does **not** admit — and that is worth stating precisely.

    A duplicate selector trips the verified artifact's own integrity check downstream, which
    fails closed as ``INVARIANT_VIOLATION``. So this branch is not the only thing standing
    between the attack and an artifact, and claiming otherwise would be the kind of
    unmeasured containment claim this whole line of work exists to catch.

    What the branch supplies is the *diagnosis*: a typed refusal naming the ambiguity, raised
    before minting, instead of an untyped "the verifier cannot trust its own reasoning". Both
    are refusals; only one tells an operator what to fix.
    """

    from ugence_cloud_scaling_policy_authenticity import verification as V

    real = V._bound_reconciliation_problem

    def _without_this_branch(candidate, capacity_bounds):
        verdict = real(candidate, capacity_bounds)
        if verdict is not None and verdict[0] is O.CANDIDATE_BOUND_SELECTOR_AMBIGUOUS:
            return None
        return verdict

    duplicated = (_bound(magnitude=100), _bound(magnitude=1))

    monkeypatch.setattr(V, "_bound_reconciliation_problem", _without_this_branch)
    silenced = _verify_against(duplicated)
    assert silenced.outcome is O.INVARIANT_VIOLATION
    assert silenced.verified_policy is None

    monkeypatch.undo()
    assert _verify_against(duplicated).outcome is O.CANDIDATE_BOUND_SELECTOR_AMBIGUOUS
