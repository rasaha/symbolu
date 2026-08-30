"""Gate 13's exact-type re-check — the six carried instants, at the Phase 5B boundary.

Phase 5A admits these six exactly in ``__post_init__``. This package accepts a candidate
object it did not build, and both ``object.__new__`` and ``pickle`` construct one without
running ``__post_init__`` at all. So the upstream admission is not something this boundary
may inherit — it is a property of how a candidate was *built*, and gate 13 is handed one
that may not have been.

Measured before the check existed: for each of the six fields independently, a forged
candidate carrying a single ``datetime`` subclass that lies about the comparison operators
verified ``VERIFIED`` against an instant outside that field's window, while the identical
forgery carrying a plain ``datetime`` was refused with that window's own typed reason.

Every attack value here is hand-built. Nothing passes through ``to_canonical_obj`` — which
is the point: it renders a subclass to exactly the string a plain ``datetime`` produces, so
no digest can see the difference.
"""

from __future__ import annotations

import copy
import datetime as dt
import pickle

import pytest

from _policy_fixtures import (
    T_CANDIDATE,
    genuine_candidate,
    issued_bounds,
    phase5a_builders,
    verifier_for,
)
from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome as O
from ugence_cloud_scaling_policy_authenticity.verification import _CARRIED_INSTANTS

pytestmark = pytest.mark.skipif(
    phase5a_builders() is None,
    reason="the Phase 5A test tree is unavailable outside a source checkout",
)


class _Sneaky(dt.datetime):
    """Never after anything, always before it. The whole attack in four methods."""

    def __gt__(self, other):
        return False

    def __ge__(self, other):
        return True

    def __lt__(self, other):
        return False

    def __le__(self, other):
        return True


#: An instant before ``T_CANDIDATE`` and one after it. Placing a field at the wrong one of
#: these is what makes that field's own window guard the one that should refuse.
_BEFORE = dt.datetime(2026, 1, 1, 0, 5, 0, tzinfo=dt.timezone.utc)
_AFTER = dt.datetime(2026, 1, 1, 0, 7, 0, tzinfo=dt.timezone.utc)

#: For each carried instant, the value that isolates its own guard and the refusal an
#: honest ``datetime`` at that value earns. Asserting the honest reason is what keeps each
#: row measuring its own field rather than some sibling answering for it.
#:
#: Keyed by member name, consulted per production member: the behavioral parametrization
#: below iterates ``_CARRIED_INSTANTS`` itself (guard-coverage ADR §7.2's suite burden,
#: extended to this package by ADR §10), so an instant *added* to production fails here
#: with a ``KeyError`` instead of going silently untested, and an instant *removed* fails
#: the frozen-membership pin at the bottom of this module.
CASE_BY_FIELD = {
    "subject_valid_from_fact": (_AFTER, O.CANDIDATE_RECOMMENDATION_NOT_YET_VALID),
    "subject_valid_until_fact": (_BEFORE, O.CANDIDATE_RECOMMENDATION_EXPIRED),
    "subject_asserted_at_fact": (_AFTER, O.CANDIDATE_FACT_NOT_YET_OCCURRED),
    "decision_evaluated_at_fact": (_AFTER, O.CANDIDATE_FACT_NOT_YET_OCCURRED),
    "decision_expires_at_fact": (_BEFORE, O.CANDIDATE_DECISION_EXPIRED),
    "attestation_issued_at_fact": (_AFTER, O.CANDIDATE_FACT_NOT_YET_OCCURRED),
}


def _forged(candidate, field, value):
    """A candidate carrying ``value`` at ``field``, built past ``__post_init__``.

    ``object.__new__`` is the whole reason this gate exists: it produces a real instance of
    the frozen dataclass without its admission ever running.
    """

    forged = object.__new__(type(candidate))
    for name in candidate.__dataclass_fields__:
        object.__setattr__(forged, name, getattr(candidate, name))
    object.__setattr__(forged, field, value)
    return forged


def _lying(value):
    return _Sneaky(
        value.year,
        value.month,
        value.day,
        value.hour,
        value.minute,
        value.second,
        value.microsecond,
        tzinfo=value.tzinfo,
    )


def _chain():
    authority, record = issued_bounds()
    return authority, record, genuine_candidate(record)


def _verify(candidate, authority, record, as_of=T_CANDIDATE):
    return verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=as_of,
        candidate=candidate,
    )


@pytest.mark.happy
def test_an_exactly_typed_candidate_still_verifies():
    """The repair must not cost the honest chain anything."""

    authority, record, candidate = _chain()
    result = _verify(candidate, authority, record)
    assert result.outcome is O.VERIFIED, result.refusal
    assert result.verified_policy.candidate_digest_fact == candidate.candidate_digest


@pytest.mark.happy
def test_a_forged_but_exactly_typed_candidate_reaches_the_window_guards_unchanged():
    """``object.__new__`` alone is not the defect. Carrying a lying *type* is."""

    authority, record, candidate = _chain()
    rebuilt = _forged(candidate, "subject_valid_from_fact", candidate.subject_valid_from_fact)
    assert _verify(rebuilt, authority, record).outcome is O.VERIFIED


@pytest.mark.adversarial
@pytest.mark.parametrize("field", _CARRIED_INSTANTS)
def test_a_lying_instant_cannot_satisfy_its_own_window(field):
    """Each of the six, one at a time, with the honest control that proves it is not vacuous.

    Parametrized over the production tuple, so the six cannot drift from what the gate
    actually iterates; ``CASE_BY_FIELD`` supplies each member's isolating value and reason.
    """

    value, honest_reason = CASE_BY_FIELD[field]
    authority, record, candidate = _chain()

    # Control: the same forgery carrying a plain ``datetime`` earns this field's own refusal.
    plain = _verify(_forged(candidate, field, value), authority, record)
    assert plain.outcome is honest_reason, plain.refusal
    assert plain.verified_policy is None

    # The attack: identical, except the type.
    lying = _verify(_forged(candidate, field, _lying(value)), authority, record)
    assert lying.outcome is O.CANDIDATE_FACT_NOT_EXACT_INSTANT, lying.refusal
    assert field in lying.refusal.detail
    assert lying.verified_policy is None


@pytest.mark.adversarial
def test_all_six_lying_at_once_are_refused_and_the_first_is_named():
    """The audit's original shape: every carried instant a lie, and nothing minted."""

    authority, record, candidate = _chain()
    forged = candidate
    for field in _CARRIED_INSTANTS:
        forged = _forged(forged, field, _lying(CASE_BY_FIELD[field][0]))

    result = _verify(forged, authority, record)
    assert result.outcome is O.CANDIDATE_FACT_NOT_EXACT_INSTANT
    assert result.verified_policy is None
    # Named in declaration order, so the diagnosis is stable rather than dict-ordered.
    assert "subject_valid_from_fact" in result.refusal.detail


@pytest.mark.adversarial
def test_no_digest_can_see_the_difference():
    """Why the type is the only place it survives: the canonical rendering is identical."""

    from ugence_policy_authority.api import to_canonical_obj

    honest = _BEFORE
    assert to_canonical_obj(_lying(honest)) == to_canonical_obj(honest)


@pytest.mark.adversarial
@pytest.mark.parametrize("route", ["pickle", "deepcopy"])
def test_the_other_routes_past_post_init_are_refused_too(route):
    """``object.__new__`` is not the only way in, so the gate is not written against it."""

    authority, record, candidate = _chain()
    forged = _forged(candidate, "decision_expires_at_fact", _lying(_BEFORE))
    revived = pickle.loads(pickle.dumps(forged)) if route == "pickle" else copy.deepcopy(forged)

    assert type(revived.decision_expires_at_fact) is _Sneaky, "the route lost the subclass"
    result = _verify(revived, authority, record)
    assert result.outcome is O.CANDIDATE_FACT_NOT_EXACT_INSTANT
    assert result.verified_policy is None


@pytest.mark.invariant
def test_the_carried_instant_membership_is_frozen():
    """The independent half of deriving from production (guard-coverage ADR §10).

    Parametrizing over ``_CARRIED_INSTANTS`` means an added member is exercised (or fails
    ``CASE_BY_FIELD`` loudly) — but it also means a member *removed* from production would
    silently remove its test. This pin names the exact expected six, so membership can
    shrink only by failing here, and the disclosed multiplicity of ``verification.py:1026``
    stays re-derivable: one static site, six carried-instant invariants.
    """

    assert _CARRIED_INSTANTS == (
        "subject_valid_from_fact",
        "subject_valid_until_fact",
        "subject_asserted_at_fact",
        "decision_evaluated_at_fact",
        "decision_expires_at_fact",
        "attestation_issued_at_fact",
    )
    assert tuple(CASE_BY_FIELD) == _CARRIED_INSTANTS, (
        "every production member has exactly one isolating case, in declaration order"
    )


@pytest.mark.invariant
def test_the_typing_check_precedes_the_window_checks_and_does_not_reorder_them():
    """Precedence: typing first, then the four validity refusals in their existing order."""

    authority, record, candidate = _chain()

    # Failing typing *and* a window at once reports the typing, because a value that lies
    # about `<` and `>` cannot be caught by comparing it.
    both = _forged(candidate, "subject_valid_until_fact", _lying(_BEFORE))
    assert _verify(both, authority, record).outcome is O.CANDIDATE_FACT_NOT_EXACT_INSTANT

    # And among exactly-typed candidates the existing order is untouched: a candidate whose
    # recommendation expired *and* whose decision expired still reports the recommendation.
    expired_both = _forged(candidate, "subject_valid_until_fact", _BEFORE)
    expired_both = _forged(expired_both, "decision_expires_at_fact", _BEFORE)
    assert _verify(expired_both, authority, record).outcome is (
        O.CANDIDATE_RECOMMENDATION_EXPIRED
    )
