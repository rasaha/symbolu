# DilChat — Independent Natal-Moon Astronomical Validation (Workstream A)

**Purpose.** Establish astronomical **correctness** (not merely regression stability)
of DilChat's natal-Moon pipeline by comparing it to an **independently-implemented**
astronomy source.

## 1. Independent source

| Field | Value |
|-------|-------|
| Source name | **Astropy** `get_body('moon')`, built-in ephemeris |
| Organization / author | Astropy Project; IAU **SOFA** via **pyerfa** |
| Source version | `astropy==8.0.1`, `pyerfa==2.0.1.5` |
| Calculation method | Geocentric apparent position → `GeocentricTrueEcliptic(equinox=t)` |
| Ephemeris basis | ERFA/IAU-SOFA analytic model — **not** Swiss Ephemeris / pyswisseph |
| Coordinate frame | Geocentric true ecliptic of date |
| Output | Tropical ecliptic longitude (converted to sidereal, §3) |
| Licence | Astropy: BSD-3; ERFA: SOFA-derived permissive |
| Offline | Yes — built-in model, no JPL `.bsp` download required |

**Why this is independent.** Astropy/pyerfa is a wholly separate implementation
lineage (IAU SOFA C library, ported to Python) with no shared code with Swiss
Ephemeris. It is **not** a different UI over the same library, not the DilChat
adapter, and not an AI-generated value. (Skyfield + a JPL `.bsp` was attempted
first but the JPL download is blocked in this environment; Astropy's built-in ERFA
model is used instead and needs no download.)

Generator: [`scripts/generate_independent_reference.py`](../scripts/generate_independent_reference.py)
(requires the `validation` extra: `pip install -e ".[validation,swiss]"`). The
committed test suite does **not** need Astropy — the fixtures carry frozen,
independently-sourced values, validated at runtime against DilChat's Swiss provider.

## 2. Corpus coverage (16 cases, `tests/fixtures/independent_reference_charts.json`)

| ID | Coverage requirement |
|----|----------------------|
| IND-01 | Ordinary birth, India (IST +5:30) |
| IND-02 | Negative UTC offset (America/New_York) |
| IND-03 | Positive non-integer offset (Asia/Kathmandu +5:45) |
| IND-04 | Northern hemisphere (London) |
| IND-05 | Southern hemisphere (Sydney) |
| IND-06 | Historical timezone (Asia/Kolkata 1940, +5:53:20) |
| IND-07 | 23-hour civil day (DST spring-forward), UNKNOWN |
| IND-08 | 25-hour civil day (DST fall-back), UNKNOWN |
| IND-09 | Moon near a rashi boundary |
| IND-10 | Moon near a nakshatra boundary |
| IND-11 | Moon near a pada boundary |
| IND-12 | UNKNOWN time, rashi-stability check |
| IND-13 | UNKNOWN time, nakshatra-ambiguity check |
| IND-14 | APPROXIMATE time straddling a pada boundary |
| IND-15 | Exact input just **before** a nakshatra transition |
| IND-16 | Exact input just **after** a nakshatra transition |

Every case carries the metadata required by the workstream (fixture id, class,
local input, IANA tz, UTC instant/interval, coordinates, source, version,
tropical + sidereal longitude, ayanamsa value, tolerance, rashi/nakshatra/pada or
uncertainty outcome, evidence status). All cases are `VERIFIED_INDEPENDENT`.

## 3. Sidereal conversion (documented, non-conflating)

The **independent** quantity is the **tropical** Moon longitude (Astropy/ERFA). The
sidereal value uses the **identical** Lahiri ayanamsa definition as DilChat — the
Swiss `SE_SIDM_LAHIRI` value at the same instant — so the two implementations are
**not conflated** across different Lahiri epochs/corrections. The sidereal
comparison therefore isolates the pure tropical (astronomical) difference:

```
sidereal_expected = astropy_tropical − ayanamsa(Lahiri, t)
DilChat_sidereal  = swiss_tropical   − ayanamsa(Lahiri, t)
sidereal_diff     = DilChat_sidereal − sidereal_expected  ≡  swiss_tropical − astropy_tropical
```

Ayanamsa values are recorded per case (`ayanamsa_value_deg`).

## 4. Methodology & tolerances

Reported separately (never hiding a longitude discrepancy behind a category match):

- **raw sidereal longitude difference** and **raw tropical longitude difference**
  (both asserted ≤ tolerance);
- **classification agreement** (rashi/nakshatra/pada);
- **timezone-conversion agreement** (the case UTC instants come from the same IANA
  historical tz rules; DilChat tz handling is validated in `test_birthinterval.py`);
- **uncertainty-interval agreement** (interval cases).

| Tolerance | Value | Rationale |
|-----------|-------|-----------|
| Ordinary longitude | 0.02° (72″) | Bounds Moshier-vs-ERFA model difference |
| Near-boundary longitude | 0.01° (36″) | Tighter check on engineered boundary cases |
| Classification (unambiguous) | exact | Away from any boundary |
| Classification (within tol of a boundary) | ±1 adjacent | See §5 |

## 5. Results

- **Point cases (IND-01…06, 09, 10, 11, 15, 16):** DilChat's sidereal **and**
  tropical Moon longitudes agree with the independent Astropy/ERFA values within
  tolerance in **every** case. **Maximum observed sidereal difference = 19.8 arcsec
  (0.0055°).**
- **Classification:** agrees exactly for all cases whose Moon is not within the
  inter-implementation tolerance of a boundary.
- **Boundary finding (IND-10, IND-11):** where the Moon sits within ~0.005° of a
  nakshatra/pada boundary, the two independent implementations legitimately fall on
  **opposite sides** of the boundary (e.g. pada 3 vs 4). The longitudes still agree
  within tolerance; only the discrete category differs by one bucket. This is an
  inherent property of exact boundary classification under finite ephemeris
  precision — **not** a DilChat defect — and it reinforces the interval/uncertainty
  model: near a boundary, a single point classification is not robust, which is
  exactly why DilChat reports `AMBIGUOUS`/`INDETERMINATE` for uncertain inputs.
- **Interval cases (IND-07, 08, 12, 13, 14):** DilChat's interval evaluation
  reproduces the independent uncertainty outcome (STABLE/AMBIGUOUS/INDETERMINATE
  with matching possible-value sets) for the 23-h and 25-h civil days, the UNKNOWN
  rashi/nakshatra checks, and the APPROXIMATE pada-straddle.

Tests: `tests/integration/test_independent_astro.py` — **17 passed** (point +
interval + presence), pyswisseph-only at runtime.

## 6. Limitations / open items

- Astropy's built-in Moon model is analytic (arcsecond-class), not a full JPL DE
  integration; a JPL-DE cross-check (Skyfield + DE440) remains desirable and is
  blocked only by the environment's JPL download restriction. Adding it later would
  further tighten the tropical tolerance below 20″.
- The ayanamsa definition is shared by design (§3); an independent Lahiri-ayanamsa
  derivation is deferred to avoid conflating Lahiri variants.

## 7. Verdict

**INDEPENDENT_ASTRONOMICAL_VALIDATION: PASS (with a documented near-boundary
classification finding).** DilChat's natal-Moon astronomy is independently
corroborated to ≤ 20 arcsec by Astropy/ERFA across 16 coverage cases. The
near-boundary discrete-classification divergence is expected, documented, and
mitigated by the uncertainty model. A JPL-DE cross-check remains an optional future
tightening, not a blocker for astronomical correctness at this precision.
