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


def _group(results: Iterable[ControlResult]) -> dict[str, list[ControlResult]]:
    """Group *all* results per control id (never collapse duplicates).

    Collapsing to one result per id (e.g. last-wins) would let a later ``PASS``
    silently mask an earlier ``FAIL`` for the same required control. Every
    submitted result for a control must be accounted for, fail-closed.
    """

    grouped: dict[str, list[ControlResult]] = {}
    for r in results:
        grouped.setdefault(r.control_id, []).append(r)
    return grouped


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
    """Return ``(control_id, effective_status)`` for each unsatisfied control.

    Fail-closed on duplicates: a required control is satisfied only when it is
    present and *every* submitted result for it has a satisfying effective
    status. A single non-satisfying duplicate (e.g. a ``FAIL`` alongside a
    ``PASS``) governs, and its status is reported — a later ``PASS`` can never
    mask an earlier failure for the same control.
    """

    grouped = _group(results)
    failures: list[tuple[str, ControlStatus]] = []
    for control_id in required:
        matches = grouped.get(control_id)
        if not matches:
            failures.append((control_id, ControlStatus.MISSING))
            continue
        offending = [
            m for m in matches if m.effective_status(now) not in SATISFYING_STATUSES
        ]
        if offending:
            # Deterministic: report the first non-satisfying duplicate's status.
            failures.append((control_id, offending[0].effective_status(now)))
    return tuple(failures)
