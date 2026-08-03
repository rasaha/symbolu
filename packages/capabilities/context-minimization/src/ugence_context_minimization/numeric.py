"""Strict, stdlib-only numeric value contracts.

These predicates are the single source of truth for what Context Minimization
accepts as a timestamp, a token count, and a fingerprint-serializable number. They
never coerce strings, dates, datetimes, or arbitrary numeric-like objects, and they
reject ``bool`` (a ``bool`` is an ``int`` in Python but is never a valid count or
timestamp here).
"""

from __future__ import annotations

import math
import numbers
from typing import Any


def is_timestamp(value: Any) -> bool:
    """A timestamp is a finite real number that is not a Boolean.

    Accepted: ``int`` / ``float`` that is finite (e.g. ``0``, ``1``, ``1.5``,
    ``1700000000.0``). Rejected: ``bool``, NaN, ±inf, ``str``, ``None``,
    ``Decimal`` (not a ``numbers.Real``… actually it is — see note), ``complex``,
    arbitrary objects.

    Note: ``decimal.Decimal`` IS a ``numbers.Number`` but is NOT a ``numbers.Real``
    in CPython, so it is rejected here — timestamps must be plain ``int``/``float``.
    """
    if isinstance(value, bool):
        return False
    if not isinstance(value, numbers.Real):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError, TypeError):
        return False


def is_token_count(value: Any) -> bool:
    """A token count is a non-negative ``int`` that is not a Boolean.

    Non-integral floats, NaN, ±inf, ``bool``, ``str`` and arbitrary objects are
    rejected. Zero and arbitrarily large positive integers are accepted.
    """
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def is_finite_number(value: Any) -> bool:
    """A fingerprint-serializable number: a finite ``int``/``float`` (``bool`` ok as
    a scalar elsewhere, but here treated as a number only when explicitly allowed).

    Used to gate scalar metadata values; ``bool`` is handled by the caller before
    this check so it is excluded here.
    """
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError, TypeError):
        return False
