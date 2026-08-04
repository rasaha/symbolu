"""Independent astronomical validation (Workstream A).

Validates DilChat's Swiss (Moshier) natal-Moon output against frozen
INDEPENDENT_REFERENCE fixtures whose expected values were computed with **Astropy**
(pyerfa / IAU-SOFA), an implementation independent of Swiss Ephemeris. Point cases
check the raw sidereal AND tropical longitude difference (not hidden behind a
category match) plus classification; interval cases check the uncertainty outcome.

Requires only the frozen fixtures + pyswisseph at runtime (no astropy needed).
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib

import pytest

from ugence_dilchat.astrology.interval import evaluate_interval

swisseph = pytest.importorskip("swisseph")
from ugence_dilchat.astrology.swiss import SwissEphemerisProvider  # noqa: E402

_FIX = json.loads(
    (pathlib.Path(__file__).parent.parent / "fixtures" / "independent_reference_charts.json")
    .read_text()
)
_CASES = _FIX["cases"]
_POINT = [c for c in _CASES if c.get("uncertainty_outcome") is None and "utc_instant" in c]
_INTERVAL = [c for c in _CASES if c.get("uncertainty_outcome") is not None]


def test_fixtures_are_independent_and_present():
    assert _FIX["fixture_class"] == "INDEPENDENT_REFERENCE_FIXTURE"
    assert _FIX["status"] == "VERIFIED_INDEPENDENT"
    assert len(_CASES) >= 16
    assert all(c["evidence_status"] == "VERIFIED_INDEPENDENT" for c in _CASES)


@pytest.mark.parametrize("c", _POINT, ids=lambda c: c["fixture_id"])
def test_point_case_matches_independent(c):
    prov = SwissEphemerisProvider(mode="moshier")
    inst = dt.datetime.fromisoformat(c["utc_instant"])
    d = prov.compute_moon(inst, input_confidence=1.0).derivation

    tol = c["longitude_tolerance_deg"]
    # Sidereal difference (normalized to [-180,180)).
    sid_diff = (d.longitude - c["expected_sidereal_moon_longitude_deg"] + 180) % 360 - 180
    # Raw tropical difference — reported explicitly, not hidden by category agreement.
    swiss_tropical = (d.longitude + c["ayanamsa_value_deg"]) % 360
    trop_diff = (c["expected_tropical_moon_longitude_deg"] - swiss_tropical + 180) % 360 - 180

    # Primary independent evidence: the astronomy (longitude) agrees within tolerance.
    assert abs(sid_diff) <= tol, f"{c['fixture_id']} sidereal Δ={sid_diff:.5f}° > {tol}"
    assert abs(trop_diff) <= tol, f"{c['fixture_id']} tropical Δ={trop_diff:.5f}° > {tol}"

    # Classification agreement — but when the Moon sits within the inter-implementation
    # tolerance of a category boundary, the two implementations may legitimately fall on
    # opposite sides. There we require an ADJACENT category (documented boundary finding),
    # otherwise exact equality. This never hides a longitude discrepancy (asserted above).
    _assert_class(d.longitude, 30.0, 12, d.rashi_index, c["expected_rashi"], tol, c["fixture_id"])
    _assert_class(d.longitude, 360 / 27, 27, d.nakshatra_index, c["expected_nakshatra"], tol,
                  c["fixture_id"])
    _assert_class(d.longitude, 360 / 108, 4, d.pada - 1, c["expected_pada"] - 1, tol,
                  c["fixture_id"], pada=True)


def _assert_class(lon, step, cycle, got, exp, tol, fid, pada=False):
    frac = lon % step
    near_boundary = min(frac, step - frac) <= tol
    diff = (got - exp) % cycle
    if near_boundary:
        assert diff in (0, 1, cycle - 1), f"{fid} category off by >1 near boundary"
    else:
        assert diff == 0, f"{fid} category mismatch away from any boundary ({got} != {exp})"


def _cmp_field(got, expected):
    assert got.status.value == expected["status"], (got.status.value, expected)
    if expected["status"] in ("STABLE", "EXACT"):
        assert got.value == expected["value"]
    else:
        assert set(got.possible_values) == set(expected["possible_values"])


@pytest.mark.parametrize("c", _INTERVAL, ids=lambda c: c["fixture_id"])
def test_interval_case_matches_independent(c):
    prov = SwissEphemerisProvider(mode="moshier")
    if "utc_interval" in c:
        start = dt.datetime.fromisoformat(c["utc_interval"]["start"])
        end = dt.datetime.fromisoformat(c["utc_interval"]["end"])
    else:  # APPROXIMATE center ± minutes
        center = dt.datetime.fromisoformat(c["center_utc"])
        u = c["uncertainty_minutes"]
        start, end = center - dt.timedelta(minutes=u), center + dt.timedelta(minutes=u)

    result = evaluate_interval(prov, start, end, input_confidence=0.2, exact=False)
    out = c["uncertainty_outcome"]
    _cmp_field(result.moon_rashi, out["moon_rashi"])
    _cmp_field(result.moon_nakshatra, out["moon_nakshatra"])
    _cmp_field(result.moon_pada, out["moon_pada"])
