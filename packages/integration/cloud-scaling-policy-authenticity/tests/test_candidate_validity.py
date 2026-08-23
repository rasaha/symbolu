"""Gate 13 — the candidate must be valid AT the verified instant (5B-2, R-2).

What R-2 turned out to be
--------------------------
The residual was recorded as "whose clock supplies ``as_of``". Measuring it said otherwise:
``as_of`` is already type-checked (naive refused, never assumed UTC) and round-tripped against
the resolution, and the authority already refuses a revoked policy *even at an instant before
its revocation* and one outside its effective window. You cannot resurrect a policy by picking
the moment.

What was open is narrower and sharper: **nothing compared ``as_of`` against the candidate's own
carried validity.** A candidate whose decision expired on 2026-01-01 verified ``VERIFIED`` at
2026-06-01 — five months dead — because the instant was recorded beside the candidate's six
timestamps and never reconciled with them. This suite's own fixtures did exactly that, and
nothing objected, which is the residual demonstrating itself.

The classification is read off the upstream contracts, not inferred
--------------------------------------------------------------------
* ``subject_valid_from``/``subject_valid_until`` — an explicit interval, **inclusive on both
  ends**, matching ``cloud-scaling-risk-integration``'s ``_require_within_validity``
  (``now > valid_until`` / ``now < valid_from``).
* ``decision_expires_at`` — an upper bound, matching Risk Authority's ``now > expires_at``.
* ``subject_asserted_at``, ``decision_evaluated_at``, ``attestation_issued_at`` — occurrence
  instants: moments the candidate asserts already happened.

Matching the upstream comparisons exactly is the point. A boundary that disagreed with the seam
above it about which instants are admissible would be a second opinion, not a second check.
"""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

from _policy_fixtures import (
    T_CANDIDATE,
    T_MID,
    genuine_candidate,
    issued,
    phase5a_builders,
    verifier_for,
)
from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome as O

pytestmark = pytest.mark.skipif(
    phase5a_builders() is None,
    reason="the Phase 5A test tree that builds a genuine candidate is unavailable",
)


def _pair():
    """An authority, its issued record, and a candidate whose coordinate names that policy.

    The candidate must be derived from the record, or gate 11 refuses on the coordinate before
    gate 13 is ever reached and every property below would measure the wrong gate.
    """

    authority, record = issued()
    return authority, record, genuine_candidate(record)


def _verify(candidate, as_of, authority, record):
    return verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=as_of,
        candidate=candidate,
    )


def _with_times(candidate, **overrides):
    """A candidate with timestamps moved and its digest re-derived.

    Built outside Phase 5A's builder on purpose: the builder would refuse some of these, and
    what this gate exists for is a candidate that reached the boundary regardless.
    """

    from ugence_cloud_scaling_authorization_contracts import (
        CapacityAuthorizationCandidate,
        canonical_digest,
    )

    forged = object.__new__(CapacityAuthorizationCandidate)
    for field in dataclasses.fields(candidate):
        object.__setattr__(forged, field.name, getattr(candidate, field.name))
    for name, value in overrides.items():
        object.__setattr__(forged, name, value)
    object.__setattr__(forged, "candidate_digest", canonical_digest(forged.digest_payload()))
    return forged


# ======================================================================================
# The four refusals, each reached on its own
# ======================================================================================
@pytest.mark.adversarial
def test_an_instant_before_the_recommendation_opens_is_refused():
    authority, record, candidate = _pair()
    before = candidate.subject_valid_from_fact - timedelta(seconds=1)
    result = _verify(candidate, before, authority, record)
    assert result.outcome is O.CANDIDATE_RECOMMENDATION_NOT_YET_VALID
    assert result.verified_policy is None


@pytest.mark.adversarial
def test_an_instant_after_the_recommendation_expires_is_refused():
    """The measured residual, inverted: T_MID is five months past this candidate's life."""

    authority, record, candidate = _pair()
    assert T_MID > candidate.subject_valid_until_fact
    result = _verify(candidate, T_MID, authority, record)
    assert result.outcome is O.CANDIDATE_RECOMMENDATION_EXPIRED
    assert result.verified_policy is None


@pytest.mark.adversarial
def test_an_expired_decision_is_refused_independently_of_the_recommendation_window():
    """A live recommendation can carry a dead decision, so the two are checked separately.

    The fixture's decision outlives its recommendation, so the ordering cannot be reached by
    choosing an instant — the candidate has to state it.
    """

    authority, record, candidate = _pair()
    assert candidate.decision_expires_at_fact > candidate.subject_valid_until_fact, (
        "the fixture's decision outlives its recommendation; this test exists because that "
        "makes the decision bound unreachable by instant choice alone"
    )
    short = _with_times(
        candidate,
        decision_expires_at_fact=candidate.decision_evaluated_at_fact + timedelta(seconds=1),
    )
    assert T_CANDIDATE <= short.subject_valid_until_fact, "still inside the recommendation"
    assert T_CANDIDATE > short.decision_expires_at_fact, "but past the decision"
    result = _verify(short, T_CANDIDATE, authority, record)
    assert result.outcome is O.CANDIDATE_DECISION_EXPIRED
    assert result.verified_policy is None


@pytest.mark.adversarial
def test_an_instant_before_the_decision_was_evaluated_is_refused():
    """A determination cannot be about a moment before the evidence it rests on existed."""

    authority, record, candidate = _pair()
    between = candidate.decision_evaluated_at_fact - timedelta(seconds=1)
    assert between >= candidate.subject_valid_from_fact, "inside the recommendation window"
    result = _verify(candidate, between, authority, record)
    assert result.outcome is O.CANDIDATE_FACT_NOT_YET_OCCURRED
    assert "decision_evaluated_at_fact" in result.refusal.detail


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "name", ["subject_asserted_at_fact", "decision_evaluated_at_fact", "attestation_issued_at_fact"]
)
def test_every_occurrence_fact_is_enforced_not_just_the_first(name):
    """Each of the three on its own, so none can be dropped without a test noticing."""

    authority, record, candidate = _pair()
    moved = _with_times(candidate, **{name: T_CANDIDATE + timedelta(seconds=1)})
    result = _verify(moved, T_CANDIDATE, authority, record)
    assert result.outcome is O.CANDIDATE_FACT_NOT_YET_OCCURRED
    assert name in result.refusal.detail


# ======================================================================================
# The boundaries, which must agree with the seam above
# ======================================================================================
@pytest.mark.invariant
def test_the_recommendation_window_is_inclusive_at_its_close():
    """``now > valid_until`` upstream, so ``== valid_until`` is admissible here too."""

    authority, record, candidate = _pair()
    assert _verify(candidate, candidate.subject_valid_until_fact, authority, record).outcome is O.VERIFIED


@pytest.mark.invariant
def test_an_occurrence_instant_is_inclusive_at_its_own_moment():
    authority, record, candidate = _pair()
    at = candidate.decision_evaluated_at_fact
    assert _verify(candidate, at, authority, record).outcome is O.VERIFIED


@pytest.mark.happy
def test_an_instant_inside_every_constraint_verifies():
    authority, record, candidate = _pair()
    result = _verify(candidate, T_CANDIDATE, authority, record)
    assert result.outcome is O.VERIFIED
    assert result.verified_policy.resolved_as_of_fact == T_CANDIDATE


@pytest.mark.invariant
def test_the_gate_is_silent_when_no_candidate_accompanies_the_determination():
    """Gate 13 reconciles a candidate. With none supplied there is nothing to reconcile."""

    authority, record = issued()
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    assert result.outcome is O.VERIFIED


@pytest.mark.invariant
def test_the_four_refusals_are_distinct_members():
    """One generic 'stale' outcome would tell a reader to go looking for the wrong thing."""

    members = {
        O.CANDIDATE_RECOMMENDATION_NOT_YET_VALID,
        O.CANDIDATE_RECOMMENDATION_EXPIRED,
        O.CANDIDATE_DECISION_EXPIRED,
        O.CANDIDATE_FACT_NOT_YET_OCCURRED,
    }
    assert len(members) == 4
    from ugence_cloud_scaling_policy_authenticity import REFUSAL_OUTCOMES

    assert members <= REFUSAL_OUTCOMES
