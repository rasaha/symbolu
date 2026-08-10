"""Controls as non-compensatory predicates (spec §10, user brief §4).

A control is a *status*, never a score. ``required_controls_satisfied`` is the
implementation of the non-compensatory architecture: a required control is
satisfied only when it is ``PASS`` (or ``NOT_APPLICABLE``); no positive control
can compensate for a ``FAIL`` / ``MISSING`` / ``STALE`` / ``UNKNOWN``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from .enums import ControlStatus

__all__ = [
    "ControlResult",
    "SATISFYING_STATUSES",
    "required_controls_satisfied",
    "unsatisfied_controls",
]

# The only statuses that let a required control contribute to an approval.
SATISFYING_STATUSES = frozenset({ControlStatus.PASS, ControlStatus.NOT_APPLICABLE})


@dataclass(frozen=True)
class ControlResult:
    """A deterministic, evidence-backed result for one required control."""

    control_id: str
    status: ControlStatus
    evidence_ids: tuple[str, ...] = ()
    evaluated_at: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    reason: str = ""

    def is_current(self, now: datetime) -> bool:
        return self.valid_until is None or now <= self.valid_until

    def effective_status(self, now: datetime) -> ControlStatus:
        """Return the status accounting for freshness.

        A ``PASS`` whose validity window has elapsed is reported as ``STALE``
        — freshness is never silently ignored (spec §10 fail-closed rule).
        """

        if self.status is ControlStatus.PASS and not self.is_current(now):
            return ControlStatus.STALE
        return self.status


def _index(results: Iterable[ControlResult]) -> dict[str, ControlResult]:
    return {r.control_id: r for r in results}


def required_controls_satisfied(
    required: Iterable[str],
    results: Iterable[ControlResult],
    now: datetime,
) -> bool:
    """Return ``True`` iff *every* required control is satisfied.

    Non-compensatory and fail-closed: a required control that is absent from
    ``results`` is treated as ``MISSING`` and fails the whole set.
    """

    return not unsatisfied_controls(required, results, now)


def unsatisfied_controls(
    required: Iterable[str],
    results: Iterable[ControlResult],
    now: datetime,
) -> tuple[tuple[str, ControlStatus], ...]:
    """Return ``(control_id, effective_status)`` for each unsatisfied control."""

    by_id = _index(results)
    failures: list[tuple[str, ControlStatus]] = []
    for control_id in required:
        result = by_id.get(control_id)
        if result is None:
            failures.append((control_id, ControlStatus.MISSING))
            continue
        status = result.effective_status(now)
        if status not in SATISFYING_STATUSES:
            failures.append((control_id, status))
    return tuple(failures)
