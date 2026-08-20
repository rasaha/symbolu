"""The outcome vocabulary is closed, total over the authority's reasons, and fails closed."""

from __future__ import annotations

import pytest

from ugence_policy_authority.api import PolicyResolutionReason

from ugence_cloud_scaling_policy_authenticity import (
    REFUSAL_OUTCOMES,
    RESOLUTION_REASON_OUTCOMES,
    TEMPORAL_OUTCOMES,
    PolicyAuthenticityOutcome as O,
    resolution_reason_outcome,
)


@pytest.mark.invariant
def test_exactly_one_member_is_a_success():
    assert REFUSAL_OUTCOMES == frozenset(m for m in O if m is not O.VERIFIED)
    assert O.VERIFIED not in REFUSAL_OUTCOMES
    assert len(REFUSAL_OUTCOMES) == len(list(O)) - 1


@pytest.mark.invariant
def test_the_reason_mapping_is_total_over_the_authority_s_refusals():
    refusals = {r for r in PolicyResolutionReason if r is not PolicyResolutionReason.RESOLVED}
    assert set(RESOLUTION_REASON_OUTCOMES) == refusals


@pytest.mark.invariant
def test_the_reason_mapping_is_injective_so_no_refusal_is_collapsed_into_another():
    values = list(RESOLUTION_REASON_OUTCOMES.values())
    assert len(set(values)) == len(values)


@pytest.mark.adversarial
def test_no_authority_reason_maps_to_the_success_member():
    assert O.VERIFIED not in set(RESOLUTION_REASON_OUTCOMES.values())
    assert PolicyResolutionReason.RESOLVED not in RESOLUTION_REASON_OUTCOMES
    # Including the success reason itself: a lookup is never a route to VERIFIED.
    assert resolution_reason_outcome(PolicyResolutionReason.RESOLVED) is O.INDETERMINATE


@pytest.mark.adversarial
@pytest.mark.parametrize("unknown", ["RESOLVED", None, 0, object(), "A_FUTURE_REASON"])
def test_an_unrecognised_reason_fails_closed(unknown):
    assert resolution_reason_outcome(unknown) is O.INDETERMINATE
    assert O.INDETERMINATE in REFUSAL_OUTCOMES


@pytest.mark.invariant
def test_the_temporal_outcomes_are_named_because_r2_is_open():
    """R-2: whose clock supplies ``as_of`` is unsettled. These are the members it can move."""

    assert TEMPORAL_OUTCOMES <= REFUSAL_OUTCOMES
    assert O.NOT_YET_EFFECTIVE in TEMPORAL_OUTCOMES
    assert O.EXPIRED in TEMPORAL_OUTCOMES
    assert O.REVOKED in TEMPORAL_OUTCOMES


@pytest.mark.invariant
def test_there_is_no_member_meaning_probably_fine():
    forbidden = ("UNCHECKED", "TRUSTED_TRANSPORT", "ASSUMED", "PROBABLY", "SKIPPED", "WARN")
    for member in O:
        for word in forbidden:
            assert word not in member.value
