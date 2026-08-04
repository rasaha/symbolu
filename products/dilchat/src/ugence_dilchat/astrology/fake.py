"""Deterministic fake astrology provider.

Production-safe default: it performs a fixed, documented analytical mapping from a
UTC instant to a Moon longitude. It is **not** an ephemeris and must never be
presented as real astronomy — it exists so the interface, services, and
authorization can be exercised without any external ephemeris. It is deterministic
for identical inputs and versions.
"""

from __future__ import annotations

import datetime as dt

from .derivation import derive_moon
from .provider import MoonResult, Provenance

# A fixed synthetic mean-lunar-rate model. Documented, deterministic, NOT real.
_J2000 = dt.datetime(2000, 1, 1, 12, 0, 0, tzinfo=dt.UTC)
_MEAN_MOON_LON_AT_J2000 = 218.316  # deg (synthetic anchor)
_MEAN_MOON_DEG_PER_DAY = 13.176396  # deg/day (synthetic sidereal-ish rate)


class FakeAstrologyProvider:
    provider_id = "fake"
    provider_version = "fake-1"
    ayanamsa = "lahiri"
    ephemeris_mode = "synthetic"

    def julian_day(self, utc_instant: dt.datetime) -> float:
        utc = _as_utc(utc_instant)
        # Standard Julian Day for a UT instant.
        return 2451545.0 + (utc - _J2000).total_seconds() / 86400.0

    def compute_moon(
        self,
        utc_instant: dt.datetime,
        *,
        input_confidence: float,
        time_assumption: str | None = None,
    ) -> MoonResult:
        utc = _as_utc(utc_instant)
        days = (utc - _J2000).total_seconds() / 86400.0
        raw_lon = _MEAN_MOON_LON_AT_J2000 + _MEAN_MOON_DEG_PER_DAY * days
        derivation = derive_moon(raw_lon)
        provenance = Provenance(
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            ephemeris_mode=self.ephemeris_mode,
            ayanamsa=self.ayanamsa,
            calculation_timestamp=dt.datetime.now(dt.UTC),
            numerical_precision_class="synthetic_non_astronomical",
            fallback_used=False,
            fallback_reason=None,
            input_confidence=input_confidence,
            time_assumption=time_assumption,
        )
        trace = {"julian_day": self.julian_day(utc), **derivation.trace}
        return MoonResult(
            julian_day=self.julian_day(utc),
            derivation=derivation,
            provenance=provenance,
            trace=trace,
        )


def _as_utc(instant: dt.datetime) -> dt.datetime:
    if instant.tzinfo is None:
        raise ValueError("utc_instant must be timezone-aware")
    return instant.astimezone(dt.UTC)
