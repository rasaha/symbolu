"""Domain-level errors. All are fail-closed construction signals."""

from __future__ import annotations

__all__ = [
    "GovernedValueError",
    "CurrencyMismatchError",
    "InvalidRatioError",
    "InvalidMultiplierError",
]


class GovernedValueError(Exception):
    """Base class for all governed-value domain errors."""


class CurrencyMismatchError(GovernedValueError):
    """Money in different currencies was combined without an explicit FX step."""


class InvalidRatioError(GovernedValueError):
    """A value expected to be a unit ratio (0..1 inclusive) was out of range."""


class InvalidMultiplierError(GovernedValueError):
    """A value expected to be a non-negative multiplier was negative."""
