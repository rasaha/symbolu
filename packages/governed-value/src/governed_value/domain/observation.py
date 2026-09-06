"""Observation bindings — typed evidence carried, never scored.

GV-2's evidence contracts live in ``ugence-governance-contracts``. This module
holds the kernel's own record of an observation it has admitted: what was bound,
not what it is worth. Nothing here participates in any monetary term, guard,
reason, advisory or scorability verdict, and nothing here lifts the emitted
classification — see ``ADR_UGENCE_GOVERNED_VALUE_OBSERVATION_INGRESS.md`` §4 for
why a bound observation is still ``REPORTED``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import GovernedValueError

__all__ = ["ObservationBindingError", "ObservedMetric"]


class ObservationBindingError(GovernedValueError):
    """An observation did not bind to the case it was offered against."""


@dataclass(frozen=True)
class ObservedMetric:
    """What the kernel recorded about one admitted observation.

    A flattened copy, deliberately: the kernel keeps the identifiers and the
    window it verified against, never the observation object, so no later stage
    can read a field this seam did not check.
    """

    observation_id: str
    metric_id: str
    governed_unit: str
    window_start: str
    window_end: str
    evidence_reference_count: int
    content_digest: str
