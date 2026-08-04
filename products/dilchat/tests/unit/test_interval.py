"""Interval-evaluation service tests (Area B) using the deterministic fake provider.

The fake provider is a documented synthetic model; these tests exercise the
interval algorithm's status logic and determinism, not astronomical accuracy.
"""

from __future__ import annotations

import datetime as dt

from hypothesis import given, settings
from hypothesis import strategies as st

from ugence_dilchat.astrology.fake import FakeAstrologyProvider
from ugence_dilchat.astrology.interval import evaluate_interval
from ugence_dilchat.domain.enums import FieldStatus, GunaEligibility

P = FakeAstrologyProvider()
T0 = dt.datetime(2000, 1, 1, 0, 0, tzinfo=dt.UTC)


def test_single_instant_is_exact():
    r = evaluate_interval(P, T0, T0, input_confidence=1.0, exact=True)
    assert r.moon_rashi.status is FieldStatus.EXACT
    assert r.moon_nakshatra.status is FieldStatus.EXACT
    assert r.moon_pada.status is FieldStatus.EXACT
    assert r.guna_eligibility is GunaEligibility.ELIGIBLE
    assert r.moon_rashi.value is not None
    assert r.longitude_start == r.longitude_end


def test_full_day_interval_has_ambiguous_fields():
    r = evaluate_interval(P, T0, T0 + dt.timedelta(days=1), input_confidence=0.2, exact=False)
    # The Moon moves ~13 deg/day: nakshatra (13.33 deg) and pada change.
    assert r.moon_nakshatra.status is FieldStatus.AMBIGUOUS
    assert r.moon_pada.status is FieldStatus.INDETERMINATE
    assert r.moon_nakshatra.possible_values is not None
    assert len(r.moon_nakshatra.possible_values) >= 2
    assert r.guna_eligibility is GunaEligibility.INELIGIBLE_AMBIGUOUS_NAKSHATRA


def test_short_interval_can_be_stable():
    r = evaluate_interval(
        P, T0, T0 + dt.timedelta(minutes=2), input_confidence=0.5, exact=False
    )
    # Two minutes -> < 0.03 deg of motion -> all classifications stable.
    assert r.moon_rashi.status is FieldStatus.STABLE
    assert r.moon_pada.status in (FieldStatus.STABLE, FieldStatus.INDETERMINATE)


def test_interval_determinism():
    a = evaluate_interval(P, T0, T0 + dt.timedelta(hours=6), input_confidence=0.5, exact=False)
    b = evaluate_interval(P, T0, T0 + dt.timedelta(hours=6), input_confidence=0.5, exact=False)
    assert a.moon_rashi == b.moon_rashi
    assert a.moon_nakshatra == b.moon_nakshatra
    assert a.trace["nakshatra_indices_seen"] == b.trace["nakshatra_indices_seen"]


def test_possible_values_are_contiguous_traversal_order():
    r = evaluate_interval(P, T0, T0 + dt.timedelta(days=1), input_confidence=0.2, exact=False)
    seen = r.trace["nakshatra_indices_seen"]
    # No category is skipped: consecutive seen indices differ by 1 (mod 27).
    for a, b in zip(seen, seen[1:], strict=False):
        assert (b - a) % 27 == 1


@given(hours=st.integers(min_value=1, max_value=48))
@settings(max_examples=25, deadline=None)
def test_field_statuses_always_valid(hours):
    r = evaluate_interval(
        P, T0, T0 + dt.timedelta(hours=hours), input_confidence=0.3, exact=False
    )
    for f in (r.moon_rashi, r.moon_nakshatra, r.moon_pada):
        if f.value is not None:
            assert f.possible_values is None
        else:
            assert f.possible_values is not None and len(f.possible_values) >= 2
