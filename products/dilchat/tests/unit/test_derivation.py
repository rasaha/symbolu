"""Exact half-open rational boundary arithmetic (Area C). No epsilon snap-up."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ugence_dilchat.astrology.derivation import (
    classify_nakshatra,
    classify_pada,
    classify_rashi,
    derive_moon,
    normalize_longitude,
    to_decimal_longitude,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (0.0, 0.0),
        (360.0, 0.0),
        (720.0, 0.0),
        (-1.0, 359.0),
        (-360.0, 0.0),
        (390.0, 30.0),
    ],
)
def test_normalize_range(raw, expected):
    v = normalize_longitude(raw)
    assert 0.0 <= v < 360.0
    assert v == pytest.approx(expected)


def test_zero_is_aries_ashwini_pada1():
    d = derive_moon(0.0)
    assert (d.rashi_index, d.nakshatra_index, d.pada) == (0, 0, 1)
    assert d.rashi_name == "Aries" and d.nakshatra_name == "Ashwini"


# --- rashi: exact boundary belongs to the HIGHER category (half-open) ------- #
@pytest.mark.parametrize("n", list(range(1, 12)))
def test_rashi_exact_boundary_and_just_below(n):
    boundary = Decimal(n) * Decimal(30)  # representable integer degrees
    assert classify_rashi(boundary) == n            # [start, end): start is inside n
    assert classify_rashi(boundary - Decimal("0.000000001")) == n - 1  # just below -> n-1


# --- nakshatra: integer (representable) boundaries at n*40/3 for n%3==0 ------ #
@pytest.mark.parametrize("n", [3, 6, 9, 12, 15, 18, 21, 24])
def test_nakshatra_exact_integer_boundary(n):
    boundary = Decimal(n) * Decimal(40) / Decimal(3)  # exact integer (40,80,...)
    assert boundary == boundary.to_integral_value()   # confirm representable
    assert classify_nakshatra(boundary) == n
    assert classify_nakshatra(boundary - Decimal("0.000000001")) == n - 1


@pytest.mark.parametrize(
    "lon,expected_nak",
    [
        (Decimal("13.3"), 0),   # just below the irrational 40/3 boundary
        (Decimal("13.4"), 1),   # just above it
        (Decimal("26.6"), 1),   # just below 2*40/3 = 26.666...
        (Decimal("26.7"), 2),   # just above
    ],
)
def test_nakshatra_around_irrational_boundary(lon, expected_nak):
    assert classify_nakshatra(lon) == expected_nak


# --- pada: representable boundary at 10.0 (pada 3->4 within nakshatra 0) ----- #
def test_pada_exact_boundary_representable():
    assert classify_pada(Decimal("10.0")) == 4
    assert classify_pada(Decimal("10.0") - Decimal("0.000000001")) == 3
    assert classify_nakshatra(Decimal("10.0")) == 0


@pytest.mark.parametrize(
    "lon,pada",
    [
        (Decimal("3.3"), 1),
        (Decimal("3.4"), 2),
        (Decimal("6.6"), 2),
        (Decimal("6.7"), 3),
    ],
)
def test_pada_around_irrational_boundary(lon, pada):
    assert classify_pada(lon) == pada


# --- edges near 360 and normalization of out-of-range inputs ---------------- #
def test_near_360_stays_pisces_and_360_wraps():
    assert derive_moon(359.999999999).rashi_index == 11  # Pisces
    assert derive_moon(360.0).rashi_index == 0           # wraps to Aries


def test_negative_and_over_360_normalized():
    assert derive_moon(-30.0).rashi_index == 11  # 330 -> Pisces
    assert derive_moon(390.0).rashi_index == 1   # 30 -> Taurus


def test_no_snapup_value_just_below_boundary_stays_lower():
    # The former 1e-6 snap-up is gone: a value 1e-9 below 30 is still Aries.
    assert derive_moon(30.0 - 1e-9).rashi_index == 0


def test_decimal_conversion_is_exact_and_recorded():
    d = derive_moon(271.8935440)
    assert d.longitude_decimal == str(to_decimal_longitude(271.8935440))
    assert d.trace["method"] == "exact_half_open_rational_decimal"


def test_full_sweep_indices_in_range():
    lon = Decimal("0")
    step = Decimal("0.37")
    while lon < Decimal("360"):
        assert 0 <= classify_rashi(lon) <= 11
        assert 0 <= classify_nakshatra(lon) <= 26
        assert 1 <= classify_pada(lon) <= 4
        lon += step


def test_determinism():
    assert derive_moon(123.456789012) == derive_moon(123.456789012)
