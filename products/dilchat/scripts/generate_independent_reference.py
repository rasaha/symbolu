#!/usr/bin/env python3
"""Generate INDEPENDENT_REFERENCE_FIXTUREs for natal-Moon validation (Workstream A).

Independence: the tropical Moon longitude is computed with **Astropy** (pyerfa /
IAU-SOFA built-in ephemeris), a separate implementation that does NOT use Swiss
Ephemeris / pyswisseph. The sidereal conversion uses the **identical** Lahiri
ayanamsa definition as DilChat (Swiss ``SE_SIDM_LAHIRI`` value at the instant) so
the two implementations are not conflated — the sidereal comparison therefore
isolates the pure astronomical (tropical) difference, which is reported separately.

Category assignment reuses DilChat's exact Decimal arithmetic (pure math, not
astronomy). This script requires ``astropy`` (extra ``validation``) and
``pyswisseph`` (for the shared ayanamsa constant only). It writes the frozen
fixtures; the committed test suite does NOT need astropy at runtime.

Run:  python scripts/generate_independent_reference.py
"""

from __future__ import annotations

import datetime as dt
import json
import zoneinfo

import numpy as np
import swisseph as swe
from astropy.coordinates import GeocentricTrueEcliptic, get_body, solar_system_ephemeris
from astropy.time import Time

from ugence_dilchat.astrology.derivation import (
    classify_nakshatra,
    classify_pada,
    classify_rashi,
    to_decimal_longitude,
)
from ugence_dilchat.astrology.tables import NAKSHATRA_NAMES, RASHI_NAMES

solar_system_ephemeris.set("builtin")  # ERFA built-in; no external download
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

ASTROPY_VERSION = __import__("astropy").__version__
PYERFA_VERSION = __import__("erfa").__version__
LON_TOL = 0.02        # deg; ordinary tropical-longitude agreement tolerance
BOUNDARY_TOL = 0.01   # deg; near-boundary cases


def _jd_ut(utc: dt.datetime) -> float:
    h = utc.hour + utc.minute / 60 + (utc.second + utc.microsecond / 1e6) / 3600
    return swe.julday(utc.year, utc.month, utc.day, h, swe.GREG_CAL)


def _ayanamsa(utc: dt.datetime) -> float:
    return swe.get_ayanamsa_ut(_jd_ut(utc))


def astropy_tropical_lon(utcs: list[dt.datetime]) -> np.ndarray:
    """Vectorized geocentric true-ecliptic (tropical) Moon longitude, deg [0,360)."""
    t = Time([u.astimezone(dt.UTC).replace(tzinfo=None) for u in utcs], scale="utc")
    moon = get_body("moon", t)
    ecl = moon.transform_to(GeocentricTrueEcliptic(equinox=t))
    return np.asarray(ecl.lon.deg) % 360.0


def sidereal_lon(utc: dt.datetime) -> float:
    trop = float(astropy_tropical_lon([utc])[0])
    return (trop - _ayanamsa(utc)) % 360.0


def classify(sid_lon: float) -> tuple[int, int, int]:
    d = to_decimal_longitude(sid_lon)
    return classify_rashi(d), classify_nakshatra(d), classify_pada(d)


def _local_to_utc(date: dt.date, time: dt.time, tz: str) -> dt.datetime:
    return dt.datetime.combine(date, time, tzinfo=zoneinfo.ZoneInfo(tz)).astimezone(dt.UTC)


def point_case(cid, label, date, time, tz, lat, lon, hemi, tol=LON_TOL, notes=""):
    utc = _local_to_utc(date, time, tz)
    trop = float(astropy_tropical_lon([utc])[0])
    aya = _ayanamsa(utc)
    sid = (trop - aya) % 360.0
    r, n, p = classify(sid)
    return {
        "fixture_id": cid, "fixture_class": "INDEPENDENT_REFERENCE_FIXTURE",
        "evidence_status": "VERIFIED_INDEPENDENT", "label": label,
        "local_birth_input": f"{date}T{time}", "iana_timezone": tz,
        "utc_instant": utc.isoformat(),
        "latitude": lat, "longitude": lon, "hemisphere": hemi,
        "source_name": "Astropy get_body('moon') builtin (ERFA/IAU-SOFA)",
        "source_organization": "Astropy Project / IAU SOFA (via pyerfa)",
        "source_version": f"astropy=={ASTROPY_VERSION}; pyerfa=={PYERFA_VERSION}",
        "calculation_method": "geocentric apparent, GeocentricTrueEcliptic(equinox=t)",
        "ephemeris_basis": "ERFA builtin analytic (independent of Swiss Ephemeris)",
        "coordinate_frame": "geocentric true ecliptic of date",
        "sidereal_or_tropical": "TROPICAL (converted to sidereal below)",
        "expected_tropical_moon_longitude_deg": round(trop, 6),
        "ayanamsa": "lahiri", "ayanamsa_value_deg": round(aya, 6),
        "ayanamsa_source": "Swiss SE_SIDM_LAHIRI (shared definition; documented)",
        "expected_sidereal_moon_longitude_deg": round(sid, 6),
        "longitude_tolerance_deg": tol,
        "expected_rashi": r, "expected_rashi_name": RASHI_NAMES[r],
        "expected_nakshatra": n, "expected_nakshatra_name": NAKSHATRA_NAMES[n],
        "expected_pada": p,
        "uncertainty_outcome": None,
        "reviewer_notes": notes,
    }


def _sample_sidereal_over_day(date: dt.date, tz: str, step_min=20):
    z = zoneinfo.ZoneInfo(tz)
    start = dt.datetime.combine(date, dt.time(0, 0), tzinfo=z)
    end = dt.datetime.combine(date + dt.timedelta(days=1), dt.time(0, 0), tzinfo=z)
    n = int((end - start).total_seconds() // (step_min * 60)) + 1
    utcs = [start + dt.timedelta(minutes=step_min * i) for i in range(n)]
    utcs = [u for u in utcs if u <= end] + [end]
    trop = astropy_tropical_lon(utcs)
    sids = [(float(trop[i]) - _ayanamsa(utcs[i])) % 360.0 for i in range(len(utcs))]
    return utcs, sids


def _ordered_distinct(vals):
    out = []
    for v in vals:
        if v not in out:
            out.append(v)
    return out


def interval_case(cid, label, date, tz, lat, lon, hemi, notes=""):
    utcs, sids = _sample_sidereal_over_day(date, tz)
    rs = _ordered_distinct([classify(s)[0] for s in sids])
    ns = _ordered_distinct([classify(s)[1] for s in sids])
    ps = _ordered_distinct([classify(s)[2] for s in sids])

    def field(vals, multi):
        return ({"status": "STABLE", "value": vals[0]} if len(vals) == 1
                else {"status": multi, "possible_values": vals})

    z = zoneinfo.ZoneInfo(tz)
    start = dt.datetime.combine(date, dt.time(0, 0), tzinfo=z).astimezone(dt.UTC)
    end = dt.datetime.combine(date + dt.timedelta(days=1), dt.time(0, 0), tzinfo=z).astimezone(dt.UTC)
    return {
        "fixture_id": cid, "fixture_class": "INDEPENDENT_REFERENCE_FIXTURE",
        "evidence_status": "VERIFIED_INDEPENDENT", "label": label,
        "local_birth_input": f"{date} (UNKNOWN time)", "iana_timezone": tz,
        "utc_interval": {"start": start.isoformat(), "end": end.isoformat(),
                         "hours": round((end - start).total_seconds() / 3600, 2)},
        "latitude": lat, "longitude": lon, "hemisphere": hemi,
        "source_name": "Astropy get_body('moon') builtin (ERFA/IAU-SOFA)",
        "source_version": f"astropy=={ASTROPY_VERSION}; pyerfa=={PYERFA_VERSION}",
        "ephemeris_basis": "ERFA builtin analytic (independent of Swiss Ephemeris)",
        "sidereal_or_tropical": "sidereal (Lahiri) via shared ayanamsa",
        "ayanamsa": "lahiri", "birth_time_precision": "UNKNOWN",
        "uncertainty_outcome": {
            "moon_rashi": field(rs, "AMBIGUOUS"),
            "moon_nakshatra": field(ns, "AMBIGUOUS"),
            "moon_pada": field(ps, "INDETERMINATE"),
        },
        "reviewer_notes": notes,
    }


def _boundary_distance(sid: float, step: float) -> float:
    frac = sid % step
    return min(frac, step - frac)


def find_near_boundary(kind: str, year=2001) -> dt.datetime:
    """Find a UTC instant where the sidereal Moon is near a boundary (coarse+fine)."""
    step = {"rashi": 30.0, "nakshatra": 360 / 27, "pada": 360 / 108}[kind]
    base = dt.datetime(year, 1, 1, tzinfo=dt.UTC)
    coarse = [base + dt.timedelta(hours=h) for h in range(0, 24 * 27)]
    trop = astropy_tropical_lon(coarse)
    best_u, best_d = coarse[0], 1e9
    for i, u in enumerate(coarse):
        d = _boundary_distance((float(trop[i]) - _ayanamsa(u)) % 360.0, step)
        if d < best_d:
            best_d, best_u = d, u
    fine = [best_u + dt.timedelta(minutes=m) for m in range(-90, 91, 2)]
    ftrop = astropy_tropical_lon(fine)
    for i, u in enumerate(fine):
        d = _boundary_distance((float(ftrop[i]) - _ayanamsa(u)) % 360.0, step)
        if d < best_d:
            best_d, best_u = d, u
    return best_u


def main() -> None:
    cases = []
    # 1 ordinary India
    cases.append(point_case("IND-01", "Ordinary birth, India (IST +5:30)",
        dt.date(1990, 5, 15), dt.time(14, 30), "Asia/Kolkata", 19.076, 72.8777, "N"))
    # 2 negative UTC offset
    cases.append(point_case("IND-02", "Negative UTC offset (America/New_York)",
        dt.date(1975, 7, 20), dt.time(23, 45), "America/New_York", 40.7128, -74.006, "N"))
    # 3 positive non-integer offset (Nepal +5:45)
    cases.append(point_case("IND-03", "Positive non-integer offset (Asia/Kathmandu +5:45)",
        dt.date(1995, 8, 10), dt.time(10, 0), "Asia/Kathmandu", 27.7172, 85.324, "N"))
    # 4 northern hemisphere (also historical London)
    cases.append(point_case("IND-04", "Northern hemisphere (London)",
        dt.date(1965, 3, 21), dt.time(12, 0), "Europe/London", 51.5074, -0.1278, "N"))
    # 5 southern hemisphere
    cases.append(point_case("IND-05", "Southern hemisphere (Sydney)",
        dt.date(1988, 2, 14), dt.time(9, 0), "Australia/Sydney", -33.8688, 151.2093, "S"))
    # 6 historical timezone (India pre-standardization, Asia/Kolkata +5:53:20)
    cases.append(point_case("IND-06", "Historical timezone (Asia/Kolkata 1940, +5:53:20)",
        dt.date(1940, 1, 1), dt.time(6, 0), "Asia/Kolkata", 22.5726, 88.3639, "N",
        notes="Historical India offset predates the 1942/1945 IST standardization."))
    # 9-11 near boundaries
    for cid, kind, label in [("IND-09", "rashi", "Moon near a rashi boundary"),
                             ("IND-10", "nakshatra", "Moon near a nakshatra boundary"),
                             ("IND-11", "pada", "Moon near a pada boundary")]:
        u = find_near_boundary(kind)
        c = point_case(cid, label, u.date(), u.time().replace(microsecond=0), "UTC",
                       0.0, 0.0, "N", tol=BOUNDARY_TOL,
                       notes=f"Independently located near a {kind} boundary.")
        cases.append(c)
    # 15/16 exact just-before / just-after a nakshatra transition
    ub = find_near_boundary("nakshatra", year=2002)
    before = (ub - dt.timedelta(minutes=20)).replace(microsecond=0)
    after = (ub + dt.timedelta(minutes=20)).replace(microsecond=0)
    cases.append(point_case("IND-15", "Exact input just BEFORE a nakshatra transition",
        before.date(), before.time(), "UTC", 0.0, 0.0, "N", tol=BOUNDARY_TOL))
    cases.append(point_case("IND-16", "Exact input just AFTER a nakshatra transition",
        after.date(), after.time(), "UTC", 0.0, 0.0, "N", tol=BOUNDARY_TOL))
    # 7 23-hour civil day (US spring forward) UNKNOWN
    cases.append(interval_case("IND-07", "23-hour civil day (DST spring-forward), UNKNOWN",
        dt.date(2021, 3, 14), "America/New_York", 40.7128, -74.006, "N"))
    # 8 25-hour civil day (US fall back) UNKNOWN
    cases.append(interval_case("IND-08", "25-hour civil day (DST fall-back), UNKNOWN",
        dt.date(2021, 11, 7), "America/New_York", 40.7128, -74.006, "N"))
    # 12 UNKNOWN with stable rashi (pick a mid-rashi day) / 13 ambiguous nakshatra
    cases.append(interval_case("IND-12", "UNKNOWN time, rashi stability check",
        dt.date(1990, 5, 15), "Asia/Kolkata", 19.076, 72.8777, "N",
        notes="Rashi status determined independently over the civil day."))
    cases.append(interval_case("IND-13", "UNKNOWN time, nakshatra ambiguity check",
        dt.date(1985, 11, 2), "Asia/Kolkata", 28.6139, 77.209, "N",
        notes="Nakshatra status determined independently over the civil day."))
    # 14 APPROXIMATE crossing a pada boundary
    upada = find_near_boundary("pada", year=2003)
    cases.append({
        "fixture_id": "IND-14", "fixture_class": "INDEPENDENT_REFERENCE_FIXTURE",
        "evidence_status": "VERIFIED_INDEPENDENT",
        "label": "APPROXIMATE time straddling a pada boundary",
        "iana_timezone": "UTC",
        "center_utc": upada.replace(microsecond=0).isoformat(),
        "uncertainty_minutes": 60,
        "source_version": f"astropy=={ASTROPY_VERSION}; pyerfa=={PYERFA_VERSION}",
        "ephemeris_basis": "ERFA builtin (independent of Swiss Ephemeris)",
        "birth_time_precision": "APPROXIMATE",
        "uncertainty_outcome": _approx_pada_outcome(upada, 60),
        "reviewer_notes": "Independent samples over the +/-60 min window.",
    })

    out = {
        "fixture_class": "INDEPENDENT_REFERENCE_FIXTURE",
        "status": "VERIFIED_INDEPENDENT",
        "independence_statement":
            "Tropical Moon longitudes computed with Astropy (pyerfa / IAU SOFA builtin "
            "ephemeris), a separate implementation independent of Swiss Ephemeris / "
            "pyswisseph. Sidereal conversion uses the identical Lahiri ayanamsa "
            "definition (Swiss SE_SIDM_LAHIRI) so the two are not conflated; the "
            "comparison isolates the tropical astronomical difference.",
        "generator": "scripts/generate_independent_reference.py",
        "astropy_version": ASTROPY_VERSION, "pyerfa_version": PYERFA_VERSION,
        "swiss_ayanamsa_mode": "SE_SIDM_LAHIRI",
        "generated_note": "Regenerate with the 'validation' extra; committed values are frozen.",
        "cases": cases,
    }
    import pathlib
    p = pathlib.Path(__file__).parent.parent / "tests" / "fixtures" / "independent_reference_charts.json"
    p.write_text(json.dumps(out, indent=2))
    print(f"wrote {len(cases)} INDEPENDENT_REFERENCE cases -> {p}")


def _approx_pada_outcome(center: dt.datetime, minutes: int) -> dict:
    utcs = [center + dt.timedelta(minutes=m) for m in range(-minutes, minutes + 1, 5)]
    trop = astropy_tropical_lon(utcs)
    sids = [(float(trop[i]) - _ayanamsa(utcs[i])) % 360.0 for i in range(len(utcs))]
    rs = _ordered_distinct([classify(s)[0] for s in sids])
    ns = _ordered_distinct([classify(s)[1] for s in sids])
    ps = _ordered_distinct([classify(s)[2] for s in sids])
    return {
        "moon_rashi": {"status": "STABLE", "value": rs[0]} if len(rs) == 1
                      else {"status": "AMBIGUOUS", "possible_values": rs},
        "moon_nakshatra": {"status": "STABLE", "value": ns[0]} if len(ns) == 1
                          else {"status": "AMBIGUOUS", "possible_values": ns},
        "moon_pada": {"status": "STABLE", "value": ps[0]} if len(ps) == 1
                    else {"status": "INDETERMINATE", "possible_values": ps},
    }


if __name__ == "__main__":
    main()
