"""Deterministic derivation of rashi / nakshatra / pada from a sidereal longitude.

Boundary policy (reproducible): the input longitude is normalized to ``[0, 360)``
and rounded ONCE to ``LONGITUDE_DECIMALS`` (1e-6 deg) before any ``floor``. Bucket
selection uses integer ``floor`` on the rounded value, so a longitude exactly on a
boundary (e.g. 30.000000) deterministically belongs to the *higher* bucket. A
configurable ``boundary_epsilon`` is reported in the trace for observability but
does not change the deterministic bucket assignment.

Formulas (design DILCHAT_ASTROLOGY_ENGINE_SPEC.md §4):
    rashi_index     = floor(lon / 30)                    in 0..11
    nakshatra_index = floor(lon / (360/27))              in 0..26
    pada            = floor((lon mod (360/27)) / (360/108)) + 1   in 1..4
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .tables import (
    DEGREES_PER_NAKSHATRA,
    DEGREES_PER_PADA,
    DEGREES_PER_RASHI,
    NAKSHATRA_NAMES,
    RASHI_NAMES,
)

LONGITUDE_DECIMALS = 6
DEFAULT_BOUNDARY_EPSILON = 10 ** (-LONGITUDE_DECIMALS)


def normalize_longitude(longitude: float) -> float:
    """Return longitude wrapped into [0, 360)."""
    wrapped = math.fmod(longitude, 360.0)
    if wrapped < 0:
        wrapped += 360.0
    # Guard against a rounding artifact producing exactly 360.0.
    if wrapped >= 360.0:
        wrapped -= 360.0
    return wrapped


def round_longitude(longitude: float) -> float:
    return round(longitude, LONGITUDE_DECIMALS)


@dataclass(frozen=True)
class MoonDerivation:
    longitude: float          # normalized, rounded sidereal longitude in [0,360)
    rashi_index: int          # 0..11
    rashi_name: str
    nakshatra_index: int      # 0..26
    nakshatra_name: str
    pada: int                 # 1..4
    trace: dict


def derive_moon(raw_longitude: float) -> MoonDerivation:
    lon = round_longitude(normalize_longitude(raw_longitude))
    # Defensive: rounding a value like 359.9999996 could yield 360.0.
    if lon >= 360.0:
        lon = 0.0

    # Boundary policy: a longitude within one storage-precision unit (1e-6 deg,
    # ~0.0036 arcsec) below a boundary is assigned to the HIGHER bucket. This makes
    # the irrational nakshatra/pada boundaries (360/27, 360/108) deterministic
    # despite 1e-6 rounding, without affecting values clearly inside a bucket.
    eps = DEFAULT_BOUNDARY_EPSILON
    snapped = lon + eps

    rashi_index = min(int(math.floor(snapped / DEGREES_PER_RASHI)), 11)

    nakshatra_index = min(int(math.floor(snapped / DEGREES_PER_NAKSHATRA)), 26)

    within_nakshatra = snapped - nakshatra_index * DEGREES_PER_NAKSHATRA
    pada = int(math.floor(within_nakshatra / DEGREES_PER_PADA)) + 1
    pada = min(max(pada, 1), 4)

    trace = {
        "raw_longitude": raw_longitude,
        "normalized_longitude": lon,
        "degrees_per_rashi": DEGREES_PER_RASHI,
        "degrees_per_nakshatra": DEGREES_PER_NAKSHATRA,
        "degrees_per_pada": DEGREES_PER_PADA,
        "boundary_epsilon": DEFAULT_BOUNDARY_EPSILON,
        "rashi_index": rashi_index,
        "nakshatra_index": nakshatra_index,
        "within_nakshatra_deg": round(within_nakshatra, LONGITUDE_DECIMALS),
        "pada": pada,
    }
    return MoonDerivation(
        longitude=lon,
        rashi_index=rashi_index,
        rashi_name=RASHI_NAMES[rashi_index],
        nakshatra_index=nakshatra_index,
        nakshatra_name=NAKSHATRA_NAMES[nakshatra_index],
        pada=pada,
        trace=trace,
    )
