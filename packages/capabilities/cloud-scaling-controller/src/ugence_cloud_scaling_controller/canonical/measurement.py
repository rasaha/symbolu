"""Typed measurements and explicit units for the canonical capacity layer.

Provider and monitoring systems emit the *same* logical quantity in different units
and scales (CPU as a percent vs a ratio; latency in milliseconds vs seconds; a queue as
a raw count). Carrying a bare ``float`` loses that distinction and invites silent,
wrong normalization. :class:`Measurement` pairs a value with an explicit :class:`Unit`
so the normalization layer can convert deterministically and fail closed on ambiguity.

A ``Measurement`` records only *what was observed*; it is never a normalized controller
signal. The separation ``raw measurement != normalized signal`` is enforced downstream
by the normalization module, which consumes ``Measurement`` and emits ``NormalizedSignal``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class MeasurementError(ValueError):
    """Raised when a measurement value/unit is invalid (fail closed)."""


class Unit(str, Enum):
    """Explicit units for observed quantities. Provider-neutral."""

    RATIO = "ratio"                 # already in [0, 1]
    PERCENT = "percent"             # 0..100 (utilization / error percentage)
    MILLISECONDS = "milliseconds"   # latency in ms
    SECONDS = "seconds"             # latency / age / duration in s
    COUNT = "count"                 # non-negative integer-valued count
    PER_SECOND = "per_second"       # rate of events per second (throughput, RPS)
    RATE = "rate"                   # fraction in [0, 1] (error_rate, oom_rate)
    BYTES = "bytes"                 # non-negative byte quantity
    CORES = "cores"                 # CPU cores (non-negative)
    CURRENCY_MINOR = "currency_minor"  # exact money as integer minor units


# Units whose admissible domain is non-negative.
_NON_NEGATIVE_UNITS = frozenset({
    Unit.PERCENT, Unit.MILLISECONDS, Unit.SECONDS, Unit.COUNT,
    Unit.PER_SECOND, Unit.RATE, Unit.BYTES, Unit.CORES,
})


@dataclass(frozen=True)
class Measurement:
    """An observed value with an explicit unit. Immutable.

    Validation (fail-closed) runs in ``__post_init__``:
      * ``value`` must be a real number (``bool`` rejected); ``NaN``/``±inf`` rejected.
      * ``RATIO``/``RATE`` values must lie in ``[0, 1]``.
      * ``PERCENT`` values must lie in ``[0, 100]``.
      * counts/durations/rates/bytes/cores must be ``>= 0``.
      * ``COUNT``/``CURRENCY_MINOR`` must be integer-valued.
    """

    value: float
    unit: Unit

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise MeasurementError(
                f"measurement value must be a real number, got {self.value!r}"
            )
        fvalue = float(self.value)
        if math.isnan(fvalue) or math.isinf(fvalue):
            raise MeasurementError(f"measurement value must be finite, got {self.value!r}")
        if not isinstance(self.unit, Unit):
            raise MeasurementError(f"unit must be a Unit, got {self.unit!r}")

        if self.unit in (Unit.RATIO, Unit.RATE) and not (0.0 <= fvalue <= 1.0):
            raise MeasurementError(
                f"{self.unit.value} value must be in [0, 1], got {fvalue!r}"
            )
        if self.unit is Unit.PERCENT and not (0.0 <= fvalue <= 100.0):
            raise MeasurementError(f"percent value must be in [0, 100], got {fvalue!r}")
        if self.unit in _NON_NEGATIVE_UNITS and fvalue < 0.0:
            raise MeasurementError(f"{self.unit.value} value must be >= 0, got {fvalue!r}")
        if self.unit in (Unit.COUNT, Unit.CURRENCY_MINOR) and float(fvalue).is_integer() is False:
            raise MeasurementError(
                f"{self.unit.value} value must be integer-valued, got {fvalue!r}"
            )

    def to_canonical_dict(self) -> Dict[str, Any]:
        # COUNT / CURRENCY_MINOR digest as integers for exactness; others as-is.
        value: Any = self.value
        if self.unit in (Unit.COUNT, Unit.CURRENCY_MINOR):
            value = int(round(float(self.value)))
        return {"value": value, "unit": self.unit.value}

    @classmethod
    def from_dict(cls, data: Any) -> "Measurement":
        if not isinstance(data, dict):
            raise MeasurementError("measurement must be a mapping")
        unknown = set(data) - {"value", "unit"}
        if unknown:
            raise MeasurementError(f"unknown measurement field(s): {sorted(unknown)}")
        if "value" not in data or "unit" not in data:
            raise MeasurementError("measurement requires 'value' and 'unit'")
        try:
            unit = Unit(data["unit"])
        except ValueError as exc:
            raise MeasurementError(f"unsupported unit: {data['unit']!r}") from exc
        return cls(value=data["value"], unit=unit)


def measure(value: float, unit: Unit) -> Measurement:
    """Convenience constructor: ``measure(82.0, Unit.PERCENT)``."""
    return Measurement(value=value, unit=unit)


__all__ = [
    "MeasurementError",
    "Unit",
    "Measurement",
    "measure",
]
