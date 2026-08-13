"""Validated scalar helpers.

All ratios and multipliers are :class:`~decimal.Decimal` so the whole spine is
exact and deterministic — no binary-float drift in a number a CFO will audit.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Union

from .errors import InvalidRatioError

__all__ = ["to_decimal", "unit_ratio", "ZERO", "ONE"]

Number = Union[int, str, Decimal]

ZERO = Decimal(0)
ONE = Decimal(1)


def to_decimal(value: Number) -> Decimal:
    """Coerce an int / str / Decimal to Decimal. Floats are rejected upstream.

    Floats are intentionally *not* accepted: ``Decimal(0.1)`` is
    ``0.1000000000000000055...`` and would silently reintroduce the drift this
    module exists to prevent. Callers pass ``"0.1"`` or ``Decimal("0.1")``.
    """

    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):  # bool is an int subclass — never a ratio
        raise InvalidRatioError(f"boolean is not a numeric ratio: {value!r}")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value)
    raise InvalidRatioError(
        f"expected int / str / Decimal (not float), got {type(value).__name__}"
    )


def unit_ratio(value: Number, name: str) -> Decimal:
    """A fraction in the closed interval [0, 1]."""

    d = to_decimal(value)
    if d < ZERO or d > ONE:
        raise InvalidRatioError(f"{name} must be in [0, 1], got {d}")
    return d
