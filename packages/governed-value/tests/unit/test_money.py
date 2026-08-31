from decimal import Decimal

import pytest

from governed_value.domain.errors import CurrencyMismatchError, GovernedValueError
from governed_value.domain.money import Money


def test_scaled_rounds_half_to_even():
    # 50.5 -> 50 (nearest even), 51.5 -> 52 (nearest even): banker's rounding.
    assert Money(101, "USD").scaled(Decimal("0.5")).minor_units == 50
    assert Money(103, "USD").scaled(Decimal("0.5")).minor_units == 52


def test_add_and_sub_same_currency():
    assert (Money(100, "USD") + Money(25, "USD")).minor_units == 125
    assert (Money(100, "USD") - Money(25, "USD")).minor_units == 75


def test_cross_currency_fails_closed():
    with pytest.raises(CurrencyMismatchError):
        Money(100, "USD") + Money(100, "EUR")
    with pytest.raises(CurrencyMismatchError):
        _ = Money(100, "USD") < Money(100, "EUR")


def test_float_minor_units_rejected():
    with pytest.raises(GovernedValueError):
        Money(10.5, "USD")  # type: ignore[arg-type]


def test_zero_and_negation():
    assert Money.zero("USD").minor_units == 0
    assert (-Money(5, "USD")).minor_units == -5
