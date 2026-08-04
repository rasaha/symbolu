"""Swiss Ephemeris astrology provider — DEVELOPMENT / TEST ONLY.

LICENSING (DEC-007): pyswisseph wraps the AGPL edition of the Swiss Ephemeris.
Per this phase it may be used only for internal development, test fixtures, and
reference validation. It must never run in a production-like environment (enforced
by :mod:`ugence_dilchat.config` and by :mod:`ugence_dilchat.astrology.registry`).
It is NOT presented as a licensed commercial build.

Ephemeris mode is **explicit** and there is NO silent fallback:
- ``swieph``  : uses ``.se1`` data files; if they are unavailable (Swiss would
  internally revert to Moshier) the provider raises ``EphemerisUnavailableError``.
- ``moshier`` : the built-in analytical ephemeris, honestly stamped as such.
"""

from __future__ import annotations

import datetime as dt

from .derivation import derive_moon
from .provider import EphemerisUnavailableError, MoonResult, Provenance

_PRECISION_BY_MODE = {
    "swieph": "arcsecond_swiss_ephemeris",
    "moshier": "arcminute_moshier_analytical",
}


class SwissEphemerisProvider:
    provider_id = "swiss"
    ayanamsa = "lahiri"

    def __init__(self, mode: str = "moshier", ephemeris_path: str | None = None) -> None:
        try:
            import swisseph as swe
        except ImportError as exc:  # pragma: no cover - import guard
            raise EphemerisUnavailableError(
                "pyswisseph is not installed (dev/test extra 'swiss')."
            ) from exc
        if mode not in ("swieph", "moshier"):
            raise ValueError(f"Unsupported Swiss ephemeris mode: {mode!r}")
        self._swe = swe
        self.ephemeris_mode = mode
        self.provider_version = f"pyswisseph-{swe.version}"
        if ephemeris_path:
            swe.set_ephe_path(ephemeris_path)
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        self._base_flags = swe.FLG_SIDEREAL | (
            swe.FLG_SWIEPH if mode == "swieph" else swe.FLG_MOSEPH
        )

    def julian_day(self, utc_instant: dt.datetime) -> float:
        utc = _as_utc(utc_instant)
        hour = utc.hour + utc.minute / 60 + (utc.second + utc.microsecond / 1e6) / 3600
        return self._swe.julday(utc.year, utc.month, utc.day, hour, self._swe.GREG_CAL)

    def compute_moon(
        self,
        utc_instant: dt.datetime,
        *,
        input_confidence: float,
        time_assumption: str | None = None,
    ) -> MoonResult:
        swe = self._swe
        jd = self.julian_day(utc_instant)
        xx, retflag = swe.calc_ut(jd, swe.MOON, self._base_flags)
        if retflag < 0:
            raise EphemerisUnavailableError(f"swe.calc_ut failed (retflag={retflag}).")
        # No silent fallback: if we asked for swieph but Swiss internally used
        # Moshier (files missing), fail explicitly.
        if self.ephemeris_mode == "swieph" and (retflag & swe.FLG_MOSEPH):
            raise EphemerisUnavailableError(
                "Swiss Ephemeris .se1 files unavailable; refused silent Moshier fallback."
            )
        raw_lon = xx[0]
        derivation = derive_moon(raw_lon)
        provenance = Provenance(
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            ephemeris_mode=self.ephemeris_mode,
            ayanamsa=self.ayanamsa,
            calculation_timestamp=dt.datetime.now(dt.UTC),
            numerical_precision_class=_PRECISION_BY_MODE[self.ephemeris_mode],
            fallback_used=False,  # explicit mode; never a silent fallback
            fallback_reason=None,
            input_confidence=input_confidence,
            time_assumption=time_assumption,
        )
        trace = {
            "julian_day": jd,
            "raw_ecliptic": list(xx),
            "retflag": retflag,
            **derivation.trace,
        }
        return MoonResult(jd, derivation, provenance, trace)


def _as_utc(instant: dt.datetime) -> dt.datetime:
    if instant.tzinfo is None:
        raise ValueError("utc_instant must be timezone-aware")
    return instant.astimezone(dt.UTC)
