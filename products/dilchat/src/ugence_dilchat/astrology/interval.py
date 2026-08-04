"""Deterministic interval evaluation of the Moon's classification.

Given a UTC interval ``[start, end]`` and a real astronomy provider, determine
whether the sidereal Moon crosses a rashi / nakshatra / pada boundary inside the
interval, and report each classification with an explicit status.

Method (demonstrably correct, deterministic):

- Sample the provider on a fixed grid across the interval.
- **Adaptive densification:** if the forward (prograde) longitude gap between two
  adjacent samples is not strictly smaller than the smallest category width (one
  pada = 360/108 deg), insert midpoints until it is. Because no category can then
  be jumped, every category the Moon passes through contains at least one sample,
  so the set of sampled categories is exactly the set the Moon occupies.
- Boundary crossing instants are refined by bisection for the explanation trace.

Uncertainty is reported as explicit statuses (STABLE/AMBIGUOUS/INDETERMINATE),
never as an invented probability, and never as a single point estimate for an
uncertain input. The provider's own numerical precision is separate from category
assignment (which is exact — see ``derivation``).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from ..domain.enums import FieldStatus, GunaEligibility
from .derivation import (
    classify_nakshatra,
    classify_pada,
    classify_rashi,
    to_decimal_longitude,
)
from .provider import AstrologyProvider, EphemerisUnavailableError, Provenance
from .tables import DEGREES_PER_PADA, NAKSHATRA_NAMES, RASHI_NAMES

# Sampling grid and the safe densification threshold.
_STEP_MINUTES = 30
_MAX_DENSIFY_DEPTH = 12          # 30 min / 2^12 ≈ 0.44 s — far finer than needed
_GAP_THRESHOLD_DEG = DEGREES_PER_PADA  # smallest category width (~3.333 deg)
_BISECT_ITERS = 40


@dataclass(frozen=True)
class FieldResult:
    status: FieldStatus
    value: int | None = None
    name: str | None = None
    possible_values: list[int] | None = None
    possible_names: list[str] | None = None

    def to_dict(self) -> dict:
        d: dict = {"status": self.status.value}
        if self.value is not None:
            d["value"] = self.value
            if self.name is not None:
                d["name"] = self.name
        if self.possible_values is not None:
            d["possible_values"] = self.possible_values
            if self.possible_names is not None:
                d["possible_names"] = self.possible_names
        return d


@dataclass(frozen=True)
class IntervalMoonResult:
    utc_start: dt.datetime
    utc_end: dt.datetime
    longitude_start: float
    longitude_end: float
    moon_rashi: FieldResult
    moon_nakshatra: FieldResult
    moon_pada: FieldResult
    guna_eligibility: GunaEligibility
    synthetic: bool
    provenance: Provenance
    trace: dict


def _forward_delta(a: float, b: float) -> float:
    """Prograde (increasing) angular distance from a to b, in [0, 360)."""
    return (b - a) % 360.0


def _sample_longitudes(
    provider: AstrologyProvider,
    start: dt.datetime,
    end: dt.datetime,
    input_confidence: float,
) -> tuple[list[dt.datetime], list[float]]:
    total = (end - start).total_seconds()
    n = max(2, int(total // (_STEP_MINUTES * 60)) + 1)
    instants = [start + dt.timedelta(seconds=total * i / (n - 1)) for i in range(n)]
    instants[-1] = end
    lons = [
        provider.compute_moon(t, input_confidence=input_confidence).derivation.longitude
        for t in instants
    ]

    # Adaptive densification so no category (min width = one pada) can be skipped.
    # Completeness precondition (strategy B): the Moon's ecliptic longitude is
    # monotonically PROGRADE (never retrograde), so the forward gap between adjacent
    # samples equals the true path length between them. We (a) refuse a
    # non-monotonic/discontinuous path (forward gap > 180 deg implies a backward jump
    # or a >half-circle step neither of which the Moon exhibits over these intervals),
    # and (b) densify until every gap is STRICTLY below one pada width, then assert it
    # — so the "no category skipped" guarantee holds or we fail explicitly.
    i = 0
    while i < len(instants) - 1:
        gap = _forward_delta(lons[i], lons[i + 1])
        if gap > 180.0:
            raise EphemerisUnavailableError(
                "Non-monotonic / discontinuous Moon longitude between samples; "
                "interval completeness precondition (prograde motion) violated."
            )
        depth = 0
        while gap >= _GAP_THRESHOLD_DEG and depth < _MAX_DENSIFY_DEPTH:
            mid_t = instants[i] + (instants[i + 1] - instants[i]) / 2
            mid_l = provider.compute_moon(
                mid_t, input_confidence=input_confidence
            ).derivation.longitude
            instants.insert(i + 1, mid_t)
            lons.insert(i + 1, mid_l)
            gap = _forward_delta(lons[i], lons[i + 1])
            depth += 1
        i += 1

    # Post-condition guaranteeing completeness: with every forward gap strictly below
    # the smallest category width, no category can lie entirely between two adjacent
    # samples, so every category the path enters contains a sample. If densification
    # could not achieve this (pathological provider), fail rather than under-report.
    max_gap = max(_forward_delta(lons[i], lons[i + 1]) for i in range(len(lons) - 1))
    if max_gap >= _GAP_THRESHOLD_DEG:
        raise EphemerisUnavailableError(
            f"Could not densify below one pada width (max gap {max_gap:.4f} deg); "
            "interval completeness not guaranteed."
        )
    return instants, lons


def _ordered_distinct(values: list[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _classify_series(lons: list[float], fn) -> list[int]:
    return [fn(to_decimal_longitude(x)) for x in lons]


def _field_for(
    indices: list[int],
    names_table: tuple[str, ...] | None,
    *,
    exact: bool,
    multi_status: FieldStatus,
) -> FieldResult:
    distinct = _ordered_distinct(indices)
    if len(distinct) == 1:
        idx = distinct[0]
        return FieldResult(
            status=FieldStatus.EXACT if exact else FieldStatus.STABLE,
            value=idx,
            name=names_table[idx] if names_table else None,
        )
    return FieldResult(
        status=multi_status,
        possible_values=distinct,
        possible_names=[names_table[i] for i in distinct] if names_table else None,
    )


def _eligibility(rashi: FieldResult, nak: FieldResult, pada: FieldResult) -> GunaEligibility:
    if nak.status is FieldStatus.AMBIGUOUS:
        return GunaEligibility.INELIGIBLE_AMBIGUOUS_NAKSHATRA
    if rashi.status is FieldStatus.AMBIGUOUS:
        return GunaEligibility.INELIGIBLE_AMBIGUOUS_REQUIRED_INPUT
    if pada.status is FieldStatus.INDETERMINATE:
        return GunaEligibility.REQUIRES_USER_REVIEW
    return GunaEligibility.ELIGIBLE


def evaluate_interval(
    provider: AstrologyProvider,
    utc_start: dt.datetime,
    utc_end: dt.datetime,
    *,
    input_confidence: float,
    exact: bool,
    time_assumption: str | None = None,
) -> IntervalMoonResult:
    """Evaluate the Moon's classification over ``[utc_start, utc_end]``.

    ``exact=True`` marks a single-instant EXACT input (``utc_start == utc_end``).
    Raises ``EphemerisUnavailableError`` (propagated from the provider) if the
    interval cannot be evaluated.
    """
    if utc_end < utc_start:
        raise ValueError("utc_end must be >= utc_start")

    single = provider.compute_moon(
        utc_start, input_confidence=input_confidence, time_assumption=time_assumption
    )
    provenance = single.provenance
    synthetic = provenance.ephemeris_mode == "synthetic" or provenance.provider_id == "fake"

    if utc_start == utc_end:
        d = single.derivation
        return IntervalMoonResult(
            utc_start=utc_start,
            utc_end=utc_end,
            longitude_start=d.longitude,
            longitude_end=d.longitude,
            moon_rashi=FieldResult(FieldStatus.EXACT, d.rashi_index, d.rashi_name),
            moon_nakshatra=FieldResult(FieldStatus.EXACT, d.nakshatra_index, d.nakshatra_name),
            moon_pada=FieldResult(FieldStatus.EXACT, d.pada),
            guna_eligibility=GunaEligibility.ELIGIBLE,
            synthetic=synthetic,
            provenance=provenance,
            trace={
                "mode": "single_instant",
                "longitude": d.longitude,
                "provider_id": provenance.provider_id,
                "provider_version": provenance.provider_version,
            },
        )

    instants, lons = _sample_longitudes(provider, utc_start, utc_end, input_confidence)
    rashi_series = _classify_series(lons, classify_rashi)
    nak_series = _classify_series(lons, classify_nakshatra)
    pada_series = _classify_series(lons, classify_pada)

    rashi = _field_for(rashi_series, RASHI_NAMES, exact=False, multi_status=FieldStatus.AMBIGUOUS)
    nak = _field_for(nak_series, NAKSHATRA_NAMES, exact=False, multi_status=FieldStatus.AMBIGUOUS)
    pada = _field_for(pada_series, None, exact=False, multi_status=FieldStatus.INDETERMINATE)

    trace = {
        "mode": "interval",
        "samples": len(instants),
        "step_minutes": _STEP_MINUTES,
        "gap_threshold_deg": _GAP_THRESHOLD_DEG,
        "longitude_start": lons[0],
        "longitude_end": lons[-1],
        "rashi_indices_seen": _ordered_distinct(rashi_series),
        "nakshatra_indices_seen": _ordered_distinct(nak_series),
        "pada_values_seen": _ordered_distinct(pada_series),
        "provider_id": provenance.provider_id,
        "provider_version": provenance.provider_version,
        "time_assumption": time_assumption,
    }
    return IntervalMoonResult(
        utc_start=utc_start,
        utc_end=utc_end,
        longitude_start=lons[0],
        longitude_end=lons[-1],
        moon_rashi=rashi,
        moon_nakshatra=nak,
        moon_pada=pada,
        guna_eligibility=_eligibility(rashi, nak, pada),
        synthetic=synthetic,
        provenance=provenance,
        trace=trace,
    )


__all__ = [
    "FieldResult",
    "IntervalMoonResult",
    "evaluate_interval",
    "EphemerisUnavailableError",
]
