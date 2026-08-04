"""Unit tests for deterministic rashi/nakshatra/pada derivation and normalization."""

from __future__ import annotations

import pytest

from ugence_dilchat.astrology.derivation import (
    DEGREES_PER_NAKSHATRA,
    DEGREES_PER_PADA,
    derive_moon,
    normalize_longitude,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (0.0, 0.0),
        (360.0, 0.0),
        (720.0, 0.0),
        (-1.0, 359.0),
        (-360.0, 0.0),
        (400.0, 40.0),
        (359.9999996, pytest.approx(359.9999996, abs=1e-6)),
    ],
)
def test_normalize_longitude_range(raw, expected):
    val = normalize_longitude(raw)
    assert 0.0 <= val < 360.0
    assert val == expected


@pytest.mark.parametrize(
    "lon,rashi",
    [
        (0.0, 0),        # Aries start
        (29.999, 0),     # clearly before Taurus
        (30.0, 1),       # Taurus boundary -> higher bucket
        (59.999, 1),
        (60.0, 2),
        (330.0, 11),     # Pisces
        (359.999, 11),
    ],
)
def test_rashi_boundaries(lon, rashi):
    d = derive_moon(lon)
    assert d.rashi_index == rashi


@pytest.mark.parametrize(
    "n",
    list(range(27)),
)
def test_nakshatra_boundaries(n):
    # Exactly on the start of nakshatra n -> bucket n, pada 1.
    lon = n * DEGREES_PER_NAKSHATRA
    d = derive_moon(lon)
    assert d.nakshatra_index == n
    assert d.pada == 1
    # Clearly before the boundary -> previous nakshatra, pada 4.
    if n > 0:
        d_prev = derive_moon(lon - 1e-3)
        assert d_prev.nakshatra_index == n - 1
        assert d_prev.pada == 4


def test_within_epsilon_of_boundary_snaps_up():
    # A longitude within 1e-6 below a boundary is assigned to the higher bucket.
    d = derive_moon(30.0 - 1e-7)
    assert d.rashi_index == 1


@pytest.mark.parametrize("p", [0, 1, 2, 3])
def test_pada_boundaries(p):
    # Within nakshatra 0, pada p+1 begins at p * DEGREES_PER_PADA.
    lon = p * DEGREES_PER_PADA
    d = derive_moon(lon)
    assert d.nakshatra_index == 0
    assert d.pada == p + 1


def test_all_derivations_in_range():
    lon = 0.0
    while lon < 360.0:
        d = derive_moon(lon)
        assert 0 <= d.rashi_index <= 11
        assert 0 <= d.nakshatra_index <= 26
        assert 1 <= d.pada <= 4
        assert 0.0 <= d.longitude < 360.0
        lon += 0.37


def test_determinism_same_input_same_output():
    a = derive_moon(123.456789)
    b = derive_moon(123.456789)
    assert a == b
    assert a.trace == b.trace


def test_names_match_indices():
    d = derive_moon(0.0)
    assert d.rashi_name == "Aries"
    assert d.nakshatra_name == "Ashwini"
    d2 = derive_moon(330.0)
    assert d2.rashi_name == "Pisces"
