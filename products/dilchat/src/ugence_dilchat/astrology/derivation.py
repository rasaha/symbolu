"""Deterministic derivation of rashi / nakshatra / pada from a sidereal longitude.

**Exact half-open rational arithmetic** (Area C hardening; supersedes the former
1e-6 snap-up policy). A longitude belongs to the half-open category interval
``[start, end)``; a value slightly below a boundary is NOT moved into the higher
category by any tolerance band. Category assignment is kept separate from provider
numerical uncertainty (which is handled by the interval-evaluation service).

Conversion rule (documented, deterministic): the provider float longitude is
normalized to ``[0, 360)`` and converted ONCE to ``Decimal`` via
``Decimal(str(round(longitude, LONGITUDE_DECIMALS)))`` (i.e. rounded to
``LONGITUDE_DECIMALS`` fractional digits, then taken as an exact decimal). All
classification is then rational multiplication + floor:

    rashi_index       = floor(lon * 12  / 360)          in 0..11
    nakshatra_index   = floor(lon * 27  / 360)          in 0..26
    pada_global_index = floor(lon * 108 / 360)
    pada              = (pada_global_index mod 4) + 1    in 1..4

``360`` normalizes to ``0``. Negative / >360 inputs are normalized (the provider
contract permits raw longitudes outside [0,360); see ``normalize_longitude``).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

from .tables import NAKSHATRA_NAMES, RASHI_NAMES

# Fractional digits kept when converting the provider longitude to Decimal. This is
# the declared classification input resolution (~3.6 milli-arcsec), NOT a boundary
# tolerance: the value is classified exactly at this resolution with no snap-up.
LONGITUDE_DECIMALS = 9

_360 = Decimal(360)
_D12 = Decimal(12)
_D27 = Decimal(27)
_D108 = Decimal(108)


def normalize_longitude(longitude: float) -> float:
    """Return ``longitude`` wrapped into ``[0, 360)`` (float, provider contract)."""
    wrapped = longitude % 360.0
    # Python's float % already yields a non-negative result for a positive modulus,
    # but guard against a rounding artifact producing exactly 360.0.
    if wrapped >= 360.0:
        wrapped -= 360.0
    if wrapped < 0.0:
        wrapped += 360.0
    return wrapped


def to_decimal_longitude(longitude: float) -> Decimal:
    """Normalize and convert once to an exact Decimal in ``[0, 360)``."""
    norm = normalize_longitude(longitude)
    dec = Decimal(str(round(norm, LONGITUDE_DECIMALS)))
    # Rounding at the declared resolution can land exactly on 360; wrap to 0.
    if dec >= _360:
        dec = dec - _360
    if dec < 0:
        dec = dec + _360
    return dec


def _floor_div(lon: Decimal, parts: Decimal) -> int:
    """floor(lon * parts / 360) using exact Decimal arithmetic."""
    return int((lon * parts / _360).to_integral_value(rounding=ROUND_FLOOR))


def classify_rashi(lon: Decimal) -> int:
    return min(_floor_div(lon, _D12), 11)


def classify_nakshatra(lon: Decimal) -> int:
    return min(_floor_div(lon, _D27), 26)


def classify_pada(lon: Decimal) -> int:
    pada_global = min(_floor_div(lon, _D108), 107)
    return (pada_global % 4) + 1


@dataclass(frozen=True)
class MoonDerivation:
    longitude: float          # normalized sidereal longitude in [0,360) (float view)
    longitude_decimal: str    # exact decimal used for classification
    rashi_index: int          # 0..11
    rashi_name: str
    nakshatra_index: int      # 0..26
    nakshatra_name: str
    pada: int                 # 1..4
    trace: dict


def derive_moon(raw_longitude: float) -> MoonDerivation:
    lon = to_decimal_longitude(raw_longitude)
    rashi_index = classify_rashi(lon)
    nakshatra_index = classify_nakshatra(lon)
    pada = classify_pada(lon)

    trace = {
        "method": "exact_half_open_rational_decimal",
        "raw_longitude": raw_longitude,
        "normalized_decimal": str(lon),
        "longitude_decimals": LONGITUDE_DECIMALS,
        "rashi_index": rashi_index,
        "nakshatra_index": nakshatra_index,
        "pada_global_index": min(_floor_div(lon, _D108), 107),
        "pada": pada,
    }
    return MoonDerivation(
        longitude=float(lon),
        longitude_decimal=str(lon),
        rashi_index=rashi_index,
        rashi_name=RASHI_NAMES[rashi_index],
        nakshatra_index=nakshatra_index,
        nakshatra_name=NAKSHATRA_NAMES[nakshatra_index],
        pada=pada,
        trace=trace,
    )
