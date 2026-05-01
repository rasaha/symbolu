"""
Duration / Wall-Clock Policy

Lightweight per-run wall-clock governance layered on top of the existing
event + tracing backbone.  Peer to ``token_budget.BudgetPolicy``: where
``BudgetPolicy`` answers "has this run consumed too much?",
``DurationPolicy`` answers "has this run persisted too long?".

The runtime invariant becomes::

    cancel -> budget -> deadline -> approve -> execute

Two terminal/non-terminal events are gated by this policy:

- ``DEADLINE_EXCEEDED`` — run-level wall-clock deadline elapsed (terminal).
- ``ACTION_TIMEOUT``    — single action exceeded its per-action budget
  (non-terminal; the run continues to the next action).

Usage::

    from agentic.agentic_framework.duration_policy import DurationPolicy

    policy = DurationPolicy(max_run_duration_s=30.0, max_action_duration_s=10.0)
    for event in agent.run_stream("Hello", duration_policy=policy):
        ...

Gating uses ``time.monotonic()`` so it is immune to NTP / wall-clock jumps.
Wall-clock ISO strings on traces (``started_at`` / ``ended_at``) are kept
as today and remain wall-clock for observability.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Run clock
# ---------------------------------------------------------------------------


class RunClock:
    """Per-run monotonic clock.

    Captures ``time.monotonic()`` at construction.  ``elapsed_s()`` returns
    seconds since construction and is used at every gating check site.
    Monotonic — never goes backwards even under NTP correction.
    """

    __slots__ = ("started_monotonic",)

    def __init__(self) -> None:
        self.started_monotonic: float = time.monotonic()

    def elapsed_s(self) -> float:
        """Return seconds elapsed since this clock was started."""
        return time.monotonic() - self.started_monotonic


# ---------------------------------------------------------------------------
# Duration policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DurationPolicy:
    """Optional per-run wall-clock limits.

    Set any field to ``None`` (the default) to leave it unconstrained.

    Args:
        max_run_duration_s: Hard cap on wall-clock seconds from
            ``RUN_STARTED`` to terminal event.  Checked at the same sites
            as ``BudgetPolicy``.
        max_action_duration_s: Hard cap on wall-clock seconds for a single
            ``ACTION_STARTED`` -> ``ACTION_COMPLETED`` span.
    """

    max_run_duration_s: Optional[float] = None
    max_action_duration_s: Optional[float] = None

    def run_exceeded(self, elapsed_s: float) -> Optional[str]:
        """Return a human-readable reason if the run-level deadline is
        exceeded, or ``None`` if within the deadline.
        """
        if (
            self.max_run_duration_s is not None
            and elapsed_s > self.max_run_duration_s
        ):
            return (
                f"Run elapsed {elapsed_s:.3f}s exceeds deadline "
                f"{self.max_run_duration_s:.3f}s"
            )
        return None

    def action_exceeded(self, elapsed_s: float) -> Optional[str]:
        """Return a human-readable reason if the per-action deadline is
        exceeded, or ``None`` if within the deadline.
        """
        if (
            self.max_action_duration_s is not None
            and elapsed_s > self.max_action_duration_s
        ):
            return (
                f"Action elapsed {elapsed_s:.3f}s exceeds deadline "
                f"{self.max_action_duration_s:.3f}s"
            )
        return None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
