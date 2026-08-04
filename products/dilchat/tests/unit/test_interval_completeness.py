"""Interval boundary-completeness tests via a scripted synthetic provider (Workstream B).

A ``ScriptedProvider`` returns Moon longitudes from an explicit function of time, so
we can force exact crossing scenarios and assert the evaluator never skips a
category. This does not exercise real astronomy — it stresses the completeness
algorithm.
"""

from __future__ import annotations

import datetime as dt

import pytest

from ugence_dilchat.astrology.derivation import derive_moon
from ugence_dilchat.astrology.interval import evaluate_interval
from ugence_dilchat.astrology.provider import (
    EphemerisUnavailableError,
    MoonResult,
    Provenance,
)
from ugence_dilchat.astrology.tables import (
    DEGREES_PER_NAKSHATRA,
    DEGREES_PER_PADA,
    DEGREES_PER_RASHI,
)
from ugence_dilchat.domain.enums import FieldStatus

T0 = dt.datetime(2000, 1, 1, 0, 0, tzinfo=dt.UTC)


class ScriptedProvider:
    """Longitude = fn((t - T0) seconds). ``fail_after`` forces a mid-run failure."""

    provider_id = "scripted"
    provider_version = "scripted-1"
    ayanamsa = "lahiri"
    ephemeris_mode = "synthetic"

    def __init__(self, fn, fail_after: int | None = None):
        self._fn = fn
        self._fail_after = fail_after
        self._calls = 0

    def julian_day(self, utc: dt.datetime) -> float:
        return 2451545.0 + (utc - T0).total_seconds() / 86400.0

    def compute_moon(self, utc, *, input_confidence, time_assumption=None) -> MoonResult:
        self._calls += 1
        if self._fail_after is not None and self._calls > self._fail_after:
            raise EphemerisUnavailableError("scripted failure")
        lon = self._fn((utc - T0).total_seconds())
        d = derive_moon(lon)
        prov = Provenance(
            provider_id=self.provider_id, provider_version=self.provider_version,
            ephemeris_mode=self.ephemeris_mode, ayanamsa=self.ayanamsa,
            calculation_timestamp=T0, numerical_precision_class="scripted",
            fallback_used=False, fallback_reason=None, input_confidence=input_confidence,
            provider_kind="SYNTHETIC", synthetic_calculation=True,
        )
        return MoonResult(self.julian_day(utc), d, prov, {})


def _linear(start_deg: float, deg_per_hour: float):
    return lambda secs: start_deg + deg_per_hour * (secs / 3600.0)


def _eval(fn, hours=24.0, fail_after=None):
    prov = ScriptedProvider(fn, fail_after=fail_after)
    return evaluate_interval(
        prov, T0, T0 + dt.timedelta(hours=hours), input_confidence=0.5, exact=False
    )


# --- crossing scenarios ---------------------------------------------------- #
def test_no_crossing_all_stable():
    r = _eval(_linear(5.0, 0.0), hours=6)  # stationary inside pada 2 of nakshatra 0
    assert r.moon_rashi.status is FieldStatus.STABLE
    assert r.moon_nakshatra.status is FieldStatus.STABLE
    assert r.moon_pada.status is FieldStatus.STABLE


def test_one_pada_crossing():
    # Cross the pada boundary at 10.0 deg (nakshatra 0, pada 3->4).
    r = _eval(_linear(9.0, 0.5), hours=6)  # 9 -> 12 deg
    assert r.moon_pada.status is FieldStatus.INDETERMINATE
    assert set(r.moon_pada.possible_values) == {3, 4}
    assert r.moon_nakshatra.status is FieldStatus.STABLE  # still nakshatra 0


def test_several_pada_crossings():
    r = _eval(_linear(0.5, 0.7), hours=24)  # sweeps ~17 deg -> crosses several padas
    assert r.moon_pada.status is FieldStatus.INDETERMINATE
    assert len(r.moon_pada.possible_values) >= 3


def test_nakshatra_and_pada_cross_together():
    # The nakshatra boundary at 40/3 deg is ALSO a pada boundary (pada 4->1).
    r = _eval(_linear(DEGREES_PER_NAKSHATRA - 1.0, 0.5), hours=6)
    assert r.moon_nakshatra.status is FieldStatus.AMBIGUOUS
    assert set(r.moon_nakshatra.possible_values) == {0, 1}
    assert r.moon_pada.status is FieldStatus.INDETERMINATE


def test_one_rashi_crossing():
    r = _eval(_linear(DEGREES_PER_RASHI - 1.0, 0.5), hours=6)  # cross 30 deg
    assert r.moon_rashi.status is FieldStatus.AMBIGUOUS
    assert set(r.moon_rashi.possible_values) == {0, 1}


def test_wrap_360_to_0_crosses_rashi_nakshatra_pada():
    # At 0 deg a rashi, nakshatra AND pada boundary coincide; force a 359->1 wrap.
    r = _eval(_linear(359.0, 0.5), hours=6)
    assert set(r.moon_rashi.possible_values) == {11, 0}
    assert set(r.moon_nakshatra.possible_values) == {26, 0}
    assert r.moon_pada.status is FieldStatus.INDETERMINATE


def test_boundary_exactly_at_interval_start_is_half_open():
    # Half-open [start, end): a boundary exactly at start belongs to the HIGHER
    # category; moving up from 10.0, the Moon stays in pada 4 for all of [10, 13.33).
    r = _eval(_linear(10.0, 0.5), hours=6)
    assert r.moon_pada.status is FieldStatus.STABLE
    assert r.moon_pada.value == 4


def test_crossing_exactly_at_interval_end():
    # Reaches the pada boundary (10.0) exactly at the end instant (closed sampling
    # conservatively includes the endpoint category).
    r = _eval(_linear(7.0, 0.5), hours=6)  # 7 -> 10 over 6h
    assert r.moon_pada.status is FieldStatus.INDETERMINATE
    assert set(r.moon_pada.possible_values) >= {3}


def test_two_boundaries_between_coarse_samples_are_caught():
    # Fast motion: 15 deg/hour -> a raw 30-min step spans 7.5 deg (> 2 padas).
    # Densification must still catch every crossed pada.
    r = _eval(_linear(0.1, 15.0), hours=1)  # sweeps ~15 deg in 1h
    assert r.moon_pada.status is FieldStatus.INDETERMINATE
    # 0.1 -> ~15.1 deg spans padas covering nakshatra 0 (4 padas) into nakshatra 1.
    assert len(r.moon_pada.possible_values) >= 4
    # No category skipped: nakshatra possible set is contiguous.
    ns = r.trace["nakshatra_indices_seen"]
    for a, b in zip(ns, ns[1:], strict=False):
        assert (b - a) % 27 == 1


def test_provider_failure_propagates():
    with pytest.raises(EphemerisUnavailableError):
        _eval(_linear(0.0, 13.0), hours=24, fail_after=3)


def test_non_monotonic_path_rejected():
    # A backward jump violates the prograde precondition -> explicit failure.
    def zigzag(secs):
        h = secs / 3600.0
        return 100.0 + (5.0 * h if h < 3 else 5.0 * (6 - h))  # up then down
    with pytest.raises(EphemerisUnavailableError):
        _eval(zigzag, hours=6)


def test_determinism_and_trace_has_transitions():
    a = _eval(_linear(0.5, 0.7), hours=24)
    b = _eval(_linear(0.5, 0.7), hours=24)
    assert a.moon_nakshatra == b.moon_nakshatra
    assert a.trace["nakshatra_indices_seen"] == b.trace["nakshatra_indices_seen"]
    assert len(a.trace["pada_values_seen"]) >= 2  # transitions recorded


def test_stable_not_marked_ambiguous_and_ambiguous_not_collapsed():
    stable = _eval(_linear(5.0, 0.0), hours=6)
    assert stable.moon_nakshatra.status is FieldStatus.STABLE
    assert stable.moon_nakshatra.value == 0
    amb = _eval(_linear(DEGREES_PER_PADA * 0 + 9.0, 0.5), hours=6)
    assert amb.moon_pada.possible_values is not None
    assert amb.moon_pada.value is None  # not collapsed to a single value
