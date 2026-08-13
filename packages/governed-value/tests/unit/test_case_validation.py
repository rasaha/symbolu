"""RF-3: required Money fields fail closed with a typed domain error.

A missing or wrong-typed ``actual_losses`` must raise a clear
``GovernedValueError`` at construction, never an incidental ``AttributeError``
that surfaces deep in the scorer.
"""

import pytest

from governed_value.domain.errors import GovernedValueError

from ..scenario import money, scorable_support_case


def test_actual_losses_none_rejected_with_typed_error():
    with pytest.raises(GovernedValueError, match="actual_losses is required"):
        scorable_support_case(actual_losses=None)


def test_actual_losses_wrong_type_rejected_with_typed_error():
    with pytest.raises(GovernedValueError, match="actual_losses is required"):
        scorable_support_case(actual_losses=500)  # int, not Money


def test_actual_losses_explicit_zero_is_valid():
    # An explicit zero is a legitimate claim of no incurred loss.
    case = scorable_support_case(actual_losses=money(0))
    assert case.actual_losses.minor_units == 0


def test_reported_net_per_period_wrong_type_rejected():
    with pytest.raises(GovernedValueError, match="reported_net_per_period"):
        scorable_support_case(reported_net_per_period=1000)  # int, not Money
