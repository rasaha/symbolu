"""Every member of every authority-flag loop, exercised individually.

Guard-coverage ADR §7.2, ruled at ratification: a guard inside ``for flag in
_AUTHORITY_FLAGS:`` is inventoried as **one** static guard site with a recorded semantic
multiplicity, not unrolled into one scored site per flag — *and the suite must exercise
every member*. That second half is not decoration. One mutation neutralises the whole
loop, so a kill proves only that at least one member is tested; if six of seven were
inert, the sweep would report the site KILLED and nothing would contradict it. The
discrimination burden falls here, which is §6's within-class criterion applied to a loop
rather than to an exception class.

So each test below forces exactly one flag ``True`` on an otherwise genuine object and
asserts the refusal **names that flag**. Naming it is the discriminating half: a test
that only asserted "some invariant fired" would pass for a loop that had collapsed to its
first member.

The flag tuples are read from the modules rather than transcribed. They differ — 7, 6, 8
and 9 members across the four loops — and a transcribed list would silently stop covering
a member the day one is added, which is the exact failure this module exists to prevent.
"""

from __future__ import annotations

import copy

import pytest

from ugence_cloud_scaling_risk_integration import authenticity as _authenticity
from ugence_cloud_scaling_risk_integration import outcomes as _outcomes
from ugence_cloud_scaling_risk_integration import projection as _projection
from ugence_cloud_scaling_risk_integration.errors import (
    NonExecutableInvariantError,
    ProjectionError,
    RecommendationAuthenticityError,
)

from ugence_cloud_scaling_risk_integration import CloudScalingRiskAdapter

from conftest import build_recommendation, fixed_clock, reference_seam, INSIDE_WINDOW


def _forged(instance, flag: str):
    """A copy of ``instance`` with one flag forced ``True``, bypassing its constructor.

    ``dataclasses.replace`` would re-run the very ``__post_init__`` under test, so the
    refusal would come from the constructor rather than from the guard the test is
    aiming at — and for a ``SubjectRiskDecision`` it would come from Risk Authority's own
    invariant, in a different distribution. ``object.__setattr__`` on a copy is how a
    forged token actually arrives: the flags have no setter, and a compromised or
    duck-typed producer does not need one.
    """

    forged = copy.copy(instance)
    object.__setattr__(forged, flag, True)
    return forged


@pytest.fixture(scope="module")
def genuine_recommendation():
    return build_recommendation()


@pytest.fixture(scope="module")
def genuine_token(genuine_recommendation):
    """Authenticated against the recommendation's own independent digest.

    Supplied explicitly because the object form carries no ``evidence_digest`` and the
    package fails closed rather than recomputing a digest and comparing it to itself.
    """

    return _authenticity.authenticate_controller_output(
        genuine_recommendation,
        expected_recommendation_digest=genuine_recommendation.digest(),
    )


@pytest.fixture(scope="module")
def genuine_projection(genuine_token):
    return _projection.project_recommendation(genuine_token)


@pytest.fixture(scope="module")
def genuine_outcome(genuine_recommendation):
    """A real ``RISK_DECISION`` outcome, carrying a real ``SubjectRiskDecision``.

    Built through the reference seam rather than assembled, so the decision the
    ``_DECISION_FLAGS`` loop reads is the one Risk Authority actually returns.
    """

    adapter = CloudScalingRiskAdapter(
        seam=reference_seam(INSIDE_WINDOW), clock=fixed_clock(INSIDE_WINDOW)
    )
    outcome = adapter.evaluate(
        genuine_recommendation,
        expected_recommendation_digest=genuine_recommendation.digest(),
    )
    assert outcome.status is _outcomes.AdapterOutcomeStatus.RISK_DECISION, outcome.detail
    return outcome


# --- the four loops, one test per member -------------------------------------------


@pytest.mark.parametrize("flag", _outcomes._AUTHORITY_FLAGS)
def test_every_outcome_authority_flag_is_refused(flag, genuine_outcome):
    """``outcomes.py:118`` — 7 members, multiplicity 7 (guard-coverage ADR §7.2)."""

    forged = _forged(genuine_outcome, flag)
    with pytest.raises(NonExecutableInvariantError) as exc:
        type(forged).__post_init__(forged)
    assert flag in str(exc.value), (
        f"the loop refused, but not for {flag!r}: a kill on this one static site must be "
        "attributable to the member under test, not to whichever member fires first"
    )


@pytest.mark.parametrize("flag", _outcomes._DECISION_FLAGS)
def test_every_decision_flag_is_refused(flag, genuine_outcome):
    """``outcomes.py:136`` — 6 members. Not named by ADR §7.2, and a loop-guard all the
    same: the adapter re-asserts Risk Authority's own flags on the decision it is handed,
    because a duck-typed or compromised seam is exactly what that guard exists for."""

    forged = copy.copy(genuine_outcome)
    object.__setattr__(forged, "decision", _forged(genuine_outcome.decision, flag))
    with pytest.raises(NonExecutableInvariantError) as exc:
        type(forged).__post_init__(forged)
    assert flag in str(exc.value)


@pytest.mark.parametrize("flag", _projection._AUTHORITY_FLAGS)
def test_every_projection_authority_flag_is_refused(flag, genuine_projection):
    """``projection.py:127`` — **9** members, so multiplicity 9. Guard-coverage ADR §7.2
    records this loop as multiplicity 7; that is the count of ``outcomes.py``'s tuple,
    not this one's. The number is measured here rather than assumed."""

    forged = _forged(genuine_projection, flag)
    with pytest.raises(ProjectionError) as exc:
        type(forged).__post_init__(forged)
    assert flag in str(exc.value)


@pytest.mark.parametrize("flag", _authenticity._AUTHORITY_FLAGS)
def test_every_authenticated_token_authority_flag_is_refused(flag, genuine_token):
    """``authenticity.py:267`` — 8 members. Also unnamed by ADR §7.2."""

    forged = _forged(genuine_token, flag)
    with pytest.raises(RecommendationAuthenticityError) as exc:
        _authenticity._assert_no_authority_fields(forged, "an authenticated recommendation")
    assert flag in str(exc.value)


# --- the multiplicities themselves, so the inventory's numbers stay re-derivable -----


def test_the_recorded_multiplicities_are_what_the_source_says():
    """The guard inventory records a multiplicity per loop site, read from these tuples.

    Pinned here so a flag added to one of them fails a test that names the site, rather
    than silently widening what one static guard decides while its recorded multiplicity
    stays where it was.
    """

    assert len(_outcomes._AUTHORITY_FLAGS) == 7
    assert len(_outcomes._DECISION_FLAGS) == 6
    assert len(_authenticity._AUTHORITY_FLAGS) == 8
    assert len(_projection._AUTHORITY_FLAGS) == 9
