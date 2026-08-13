from decimal import Decimal

import pytest

from governed_value.domain.errors import (
    CurrencyMismatchError,
    InvalidMultiplierError,
    InvalidRatioError,
)
from governed_value.domain.money import Money
from governed_value.domain.rates import nonneg_multiplier, to_decimal, unit_ratio
from governed_value.domain.value import RealizedValue


def test_realized_value_gross_sums_three_sources():
    rv = RealizedValue(
        labor_displaced=Money(100, "USD"),
        throughput_gained=Money(50, "USD"),
        loss_avoided=Money(25, "USD"),
    )
    assert rv.gross().minor_units == 175
    assert rv.currency == "USD"


def test_realized_value_mixed_currency_fails_closed():
    with pytest.raises(CurrencyMismatchError):
        RealizedValue(
            labor_displaced=Money(100, "USD"),
            throughput_gained=Money(50, "EUR"),
            loss_avoided=Money(25, "USD"),
        )


def test_unit_ratio_bounds():
    assert unit_ratio(Decimal("0.3"), "x") == Decimal("0.3")
    with pytest.raises(InvalidRatioError):
        unit_ratio(Decimal("1.5"), "x")
    with pytest.raises(InvalidRatioError):
        unit_ratio(Decimal("-0.1"), "x")


def test_nonneg_multiplier_allows_above_one_rejects_negative():
    assert nonneg_multiplier(Decimal("2.5"), "m") == Decimal("2.5")
    with pytest.raises(InvalidMultiplierError):
        nonneg_multiplier(Decimal("-0.1"), "m")


def test_float_ratio_rejected_to_prevent_binary_drift():
    with pytest.raises(InvalidRatioError):
        to_decimal(0.1)  # type: ignore[arg-type]
