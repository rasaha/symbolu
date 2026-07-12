"""Gateway RUNTIME state machine.

These are operational lifecycle states of a request inside the gateway. They are
NOT the specification's decision state machine (RECEIVED -> VALIDATED -> ... ->
COMMITTED/DENIED), which lives in the frozen harness (``gate.evaluate`` emits the
``state_trace``). The gateway never modifies that machine; it records the
harness decision and drives its own lifecycle around it.
"""

from __future__ import annotations

PENDING = "PENDING"
APPROVED = "APPROVED"
EXECUTING = "EXECUTING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
DENIED = "DENIED"
ESCALATED = "ESCALATED"
EXPIRED = "EXPIRED"

ALL = (PENDING, APPROVED, EXECUTING, COMPLETED, FAILED, DENIED, ESCALATED, EXPIRED)
# ESCALATED is NOT terminal: a human approval can re-admit the request to
# evaluation (escalate -> approve -> execute). DENY is terminal.
TERMINAL = frozenset({COMPLETED, FAILED, DENIED, EXPIRED})

# Legal runtime transitions. Re-evaluation may keep a request PENDING (awaiting
# evidence/simulation) or move it forward/backward among non-terminal verdicts.
_LEGAL = {
    PENDING: {PENDING, APPROVED, DENIED, ESCALATED, EXPIRED},
    APPROVED: {EXECUTING, EXPIRED, DENIED, PENDING, ESCALATED},  # re-eval can revoke approval
    EXECUTING: {COMPLETED, FAILED},
    ESCALATED: {ESCALATED, APPROVED, DENIED, PENDING, EXPIRED},  # human input re-admits
    COMPLETED: set(),
    FAILED: set(),
    DENIED: set(),
    EXPIRED: set(),
}

# Map a frozen decision outcome to the runtime state it induces.
from ._ref import gate as _gate  # noqa: E402

OUTCOME_TO_STATE = {
    _gate.ALLOW: APPROVED,
    _gate.ALLOW_WITH_CONSTRAINTS: APPROVED,
    _gate.DENY: DENIED,
    _gate.ESCALATE_TO_HUMAN: ESCALATED,
    _gate.SIMULATE_AND_RETRY: PENDING,
    _gate.REQUEST_MORE_EVIDENCE: PENDING,
}


def can_transition(src: str, dst: str) -> bool:
    return dst in _LEGAL.get(src, set())


def is_terminal(state: str) -> bool:
    return state in TERMINAL
