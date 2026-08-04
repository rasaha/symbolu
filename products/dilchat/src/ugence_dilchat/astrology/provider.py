"""AstrologyProvider interface and value objects.

The provider is a replaceable boundary (DEC-007): it may later be a licensed
Swiss Ephemeris build, an alternative validated ephemeris, or an external approved
calculation service. Providers MUST be deterministic for identical inputs and
versions, use the Lahiri ayanamsa, normalize longitude to [0,360), expose their
actual ephemeris mode, and never silently fall back.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .derivation import MoonDerivation


class EphemerisUnavailableError(Exception):
    """Raised when a provider's required ephemeris resources are unavailable.

    Providers raise this explicitly instead of silently switching modes.
    """


@dataclass(frozen=True)
class Provenance:
    provider_id: str
    provider_version: str
    ephemeris_mode: str
    ayanamsa: str
    calculation_timestamp: dt.datetime
    numerical_precision_class: str
    fallback_used: bool
    fallback_reason: str | None
    input_confidence: float
    time_assumption: str | None = None

    def to_dict(self) -> dict:
        d = {
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "ephemeris_mode": self.ephemeris_mode,
            "ayanamsa": self.ayanamsa,
            "calculation_timestamp": self.calculation_timestamp.isoformat(),
            "numerical_precision_class": self.numerical_precision_class,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "input_confidence": self.input_confidence,
        }
        if self.time_assumption is not None:
            d["time_assumption"] = self.time_assumption
        return d


@dataclass(frozen=True)
class MoonResult:
    julian_day: float
    derivation: MoonDerivation
    provenance: Provenance
    trace: dict = field(default_factory=dict)


@runtime_checkable
class AstrologyProvider(Protocol):
    provider_id: str
    provider_version: str
    ayanamsa: str
    ephemeris_mode: str

    def julian_day(self, utc_instant: dt.datetime) -> float:
        """Convert a UTC instant to Julian Day (UT)."""
        ...

    def compute_moon(
        self,
        utc_instant: dt.datetime,
        *,
        input_confidence: float,
        time_assumption: str | None = None,
    ) -> MoonResult:
        """Compute the sidereal Moon position + derivation + provenance."""
        ...
