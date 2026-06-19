"""
outcome_reputation.py — Phase 2 deterministic observable (PROVISIONAL, advisory-only).

Converts accumulated governance history (the existing audit chain) into a present trust
signal per action type (tool). Pure aggregation of prior audit entries + fixed-threshold
classification — no ML, no hidden state, no wall-clock. Reads only fields already recorded in
Phase 1.5: `tool_name`, `decision`, `human_confirmed`.

Asymmetry: reputation only ever LOWERS trust (escalate to CONFIRM on a poor history); a good
history never raises trust. The Observation is VALIDATOR/PROVISIONAL → confirm-only (the kernel
guarantees a PROVISIONAL validator never blocks); promotion to PROVEN is what would let an
egregious reputation BLOCK.

Inert unless there is enough history: `build_reputation_observation` returns None below
`MIN_VOLUME`, and the gateway only computes it when `enable_outcome_reputation=True` (off by
default) — so production decisions never change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from agentic.agentic_framework.trust.observables import (
    EvidenceStatus,
    Observation,
    ObservableType,
    Verdict,
)

# Fixed policy thresholds — CALIBRATION PLACEHOLDERS (see OUTCOME_REPUTATION.md §Promotion).
MIN_VOLUME = 5            # minimum prior calls for this action type to emit any signal
MIN_ADJUDICATED = 3       # minimum human-adjudicated confirmations to judge approval_rate
APPROVAL_FLOOR = 0.5      # approval_rate below this → poor
DENIAL_CEIL = 0.3         # denial_rate (denied escalations / n) at/above this → poor
VIOLATION_CEIL = 0.5      # violation_rate at/above this → poor
EGREGIOUS_VIOLATION = 0.8 # violation_rate at/above this → egregious
MAX_LOOKBACK = 500        # bounded window over the most recent entries (determinism + cost)


def _classify(entry) -> str:
    """Deterministically classify one prior audit entry from decision + human_confirmed."""
    decision = getattr(entry, "decision", None)
    dval = str(getattr(decision, "value", decision) or "").lower()
    human = bool(getattr(entry, "human_confirmed", False))
    if dval == "allowed":
        return "approved" if human else "auto_allow"
    if dval == "escalate":
        return "denied"          # confirmation requested and denied/timed-out
    if dval == "blocked":
        return "blocked"         # hard policy violation (jepa/domain/shadow/forbidden/floor)
    if dval in ("error", "timeout"):
        return "error"
    return "other"


@dataclass(frozen=True)
class ReputationStats:
    action_key: str
    n: int = 0
    approvals: int = 0
    denials: int = 0
    blocked: int = 0
    errors: int = 0

    @property
    def adjudicated(self) -> int:
        return self.approvals + self.denials

    @property
    def approval_rate(self) -> Optional[float]:
        return (self.approvals / self.adjudicated) if self.adjudicated else None

    @property
    def confirmation_rate(self) -> float:
        return (self.adjudicated / self.n) if self.n else 0.0

    @property
    def denial_rate(self) -> float:
        return (self.denials / self.n) if self.n else 0.0

    @property
    def violation_rate(self) -> float:
        return (self.blocked / self.n) if self.n else 0.0

    @property
    def error_rate(self) -> float:
        return (self.errors / self.n) if self.n else 0.0


def compute_reputation(entries: Iterable, *, tool_name: str,
                       max_lookback: int = MAX_LOOKBACK) -> ReputationStats:
    """Aggregate prior audit entries for `tool_name` into deterministic reputation stats.

    `entries` is any iterable of audit-entry-like objects (duck-typed: `.tool_name`,
    `.decision`, `.human_confirmed`) — e.g. the gateway's in-memory audit log, which mirrors
    the durable hash-chained store. Only the most recent `max_lookback` matching entries count.
    """
    matching = [e for e in entries if getattr(e, "tool_name", None) == tool_name]
    if max_lookback and len(matching) > max_lookback:
        matching = matching[-max_lookback:]

    approvals = denials = blocked = errors = 0
    for e in matching:
        c = _classify(e)
        if c == "approved":
            approvals += 1
        elif c == "denied":
            denials += 1
        elif c == "blocked":
            blocked += 1
        elif c == "error":
            errors += 1
    return ReputationStats(action_key=tool_name, n=len(matching), approvals=approvals,
                           denials=denials, blocked=blocked, errors=errors)


def _verdict_for(stats: ReputationStats) -> Verdict:
    egregious = (
        (stats.adjudicated >= MIN_ADJUDICATED and stats.approval_rate == 0.0)
        or stats.violation_rate >= EGREGIOUS_VIOLATION
    )
    if egregious:
        return Verdict.UNSAFE
    poor = (
        (stats.adjudicated >= MIN_ADJUDICATED
         and stats.approval_rate is not None and stats.approval_rate < APPROVAL_FLOOR)
        or stats.violation_rate >= VIOLATION_CEIL
        or stats.denial_rate >= DENIAL_CEIL          # recurring denied escalations
    )
    return Verdict.UNSURE if poor else Verdict.SAFE


def build_reputation_observation(
    stats: Optional[ReputationStats],
    *,
    evidence: EvidenceStatus = EvidenceStatus.PROVISIONAL,
    min_volume: int = MIN_VOLUME,
) -> Optional[Observation]:
    """Build the outcome-reputation Observation, or None when there is no signal.

    Returns None when stats is absent or below `min_volume` (insufficient history) — so the
    observable never fires without an established track record. Default evidence PROVISIONAL
    (confirm-only); a promotion would pass PROVEN.
    """
    if stats is None or stats.n < min_volume:
        return None

    verdict = _verdict_for(stats)
    ar = stats.approval_rate
    severity = round(min(1.0, max(stats.violation_rate,
                                  (1.0 - ar) if ar is not None else 0.0)), 4)
    reason = (
        f"reputation[{stats.action_key}] n={stats.n} "
        f"approval_rate={'n/a' if ar is None else f'{ar:.2f}'} "
        f"confirm_rate={stats.confirmation_rate:.2f} "
        f"violation_rate={stats.violation_rate:.2f}"
    )
    return Observation(
        name="outcome_reputation",
        otype=ObservableType.VALIDATOR,
        evidence=evidence,
        verdict=verdict,
        severity=severity if verdict != Verdict.SAFE else 0.0,
        reason=reason,
        detail={
            "n": stats.n, "approvals": stats.approvals, "denials": stats.denials,
            "blocked": stats.blocked, "errors": stats.errors,
            "approval_rate": ar, "confirmation_rate": round(stats.confirmation_rate, 4),
            "violation_rate": round(stats.violation_rate, 4),
        },
    )
