"""The advisory signal ladder — the *only* outputs the analyzer may recommend.

This module is the enforced guarantee that the Composite Capability &
Sequence-Risk Analyzer is **advisory**. Per ``ACTION_GATE_SPECIFICATION.md`` §3
(behavioral evidence is ADVISORY, OPTIONAL) and §12 (extensions "MAY add
evidence" but "MAY NEVER bypass deterministic policy" — they cannot admit,
satisfy a hard requirement, or approve), a sequence-risk signal may only move a
decision toward *more* assurance, never less.

The analyzer's output alphabet is exactly ``{OBSERVE, ESCALATE, UNAVAILABLE}``.
There is deliberately no ``ALLOW``, ``AUTHORIZE``, ``DENY``, ``BLOCK``, or
``EXECUTE`` here — those are *authoritative* consequences that only an ActionGate
or workflow policy may bind (see ``policy.py``). ``UNAVAILABLE`` is emitted when
the analyzer cannot faithfully evaluate a case (e.g. bounded-state exhaustion);
it is fail-loud, never silent evidence loss.
"""

from __future__ import annotations

# Ordered from least to most concern. NONE is internal (no finding emitted).
NONE = "NONE"
OBSERVE = "OBSERVE"
ESCALATE = "ESCALATE"
# Fail-loud signal: the analyzer could not evaluate faithfully. Never silent.
UNAVAILABLE = "UNAVAILABLE"

# The signals a caller may actually receive on a finding.
ADVISORY_SIGNALS = frozenset({OBSERVE, ESCALATE, UNAVAILABLE})
# Outputs the analyzer must NEVER emit — these belong to the authoritative layer.
FORBIDDEN_SIGNALS = frozenset(
    {"ALLOW", "AUTHORIZE", "DENY", "BLOCK", "EXECUTE", "ALLOW_WITH_CONSTRAINTS"}
)

_ORDER = {NONE: 0, OBSERVE: 1, ESCALATE: 2, UNAVAILABLE: 3}


def signal_for(completeness: float, *, observe_at: float, escalate_at: float) -> str:
    """Map a completeness score to an advisory signal.

    ``completeness`` is in [0, 1]. Thresholds are inclusive lower bounds. This is
    a *necessary* condition for the signal, not a sufficient one: the analyzer
    only escalates when the recipe's structural constraints and required
    corroboration are also satisfied (see ``matcher.py``). Count alone never
    escalates.
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
    """Guardrail: the analyzer must only ever emit an advisory signal."""
    return signal in ADVISORY_SIGNALS
