"""Domain and geography as **descriptive context only** (GV-1 scope).

In the prior kernel these carried monetary knobs (severity floor, regulatory
load, residency and locale multipliers) that a caller could set per call to move
the result — caller-controlled policy. GV-1 removes every such computational
lever: here `DomainProfile` and `GeographyProfile` are *descriptive* — they label
the assessment and travel with the result, but they touch **no** money.

Turning these into first-class, versioned, authority-resolved policy
(applicable benchmarks, mandatory gates, evidence standards, permitted valuation
methods) is GV-2c and is deliberately **not** in this phase. Until then, no
opaque geography/domain multiplier is allowed to influence a monetary figure.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import DomainKind, ValueSource

__all__ = ["DomainProfile", "GeographyProfile"]


@dataclass(frozen=True)
class DomainProfile:
    """Descriptive domain label: the kind, the natural unit, the dominant source."""

    kind: DomainKind
    natural_unit: str
    dominant_source: ValueSource


@dataclass(frozen=True)
class GeographyProfile:
    """Descriptive geography label. ``currency`` participates only in the

    case-wide single-currency consistency check — it applies no FX and no
    multiplier (FX and valuation basis are GV-5, deferred).
    """

    label: str
    currency: str
