"""The advisory signal ladder — the *only* outputs the detector may recommend.

This module is the enforced guarantee that the composite-threat detector is
**escalate-only**. Per ``ACTION_GATE_SPECIFICATION.md`` §3 (behavioral evidence
is ADVISORY, OPTIONAL) and §12 (extensions "MAY add evidence" but "MAY NEVER
bypass deterministic policy" — they cannot admit, satisfy a hard requirement, or
approve), a composite-narrative signal may only move a decision toward *more*
assurance, never less.

There is deliberately no ``ALLOW`` or ``DENY`` here. The richest thing the
detector can say is "a human should look at this correlation now".
"""

from __future__ import annotations

# Ordered from least to most concern. NONE is used internally (no finding
# emitted); OBSERVE and ESCALATE are the two advisory outputs.
NONE = "NONE"
OBSERVE = "OBSERVE"
ESCALATE = "ESCALATE"

ADVISORY_SIGNALS = frozenset({OBSERVE, ESCALATE})
_ORDER = {NONE: 0, OBSERVE: 1, ESCALATE: 2}


def signal_for(completeness: float, *, observe_at: float, escalate_at: float) -> str:
    """Map a completeness score to an advisory signal.

    ``completeness`` is in [0, 1]. The two thresholds are inclusive lower bounds.
    Fully assembled (``completeness >= escalate_at``, default 1.0) escalates;
    partial assembly at or above ``observe_at`` is a watch signal; below that,
    nothing is emitted.
    """
    if not 0.0 <= completeness <= 1.0:
        raise ValueError(f"completeness out of range: {completeness!r}")
    if completeness >= escalate_at:
        return ESCALATE
    if completeness >= observe_at:
        return OBSERVE
    return NONE


def rank(signal: str) -> int:
    return _ORDER[signal]


def is_advisory(signal: str) -> bool:
    """Guardrail: the detector must only ever emit an advisory signal."""
    return signal in ADVISORY_SIGNALS
