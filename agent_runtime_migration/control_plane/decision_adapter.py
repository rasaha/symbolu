"""Map a composed control-plane outcome to the runtime's next step.

This is pure interpretation of the FROZEN outcome set — it does not decide
anything. The runtime uses ``required_next_step`` to continue, replan, provide
evidence, request human input, wait, or stop. It never converts a hold into
authorization or an authorization into operational safety.
"""
from __future__ import annotations

from typing import Optional

# composed outcome -> runtime next step
_NEXT = {
    "PROCEED": "execute",
    "BLOCKED_BY_AUTHORIZATION": "replan_or_stop",
    "PENDING_AUTHORIZATION": "provide_evidence_or_request_human",
    "HELD_BY_ACP": "wait_or_reobserve",
}


def required_next_step(composed: Optional[str], actiongate: Optional[str]) -> str:
    if composed in _NEXT:
        return _NEXT[composed]
    # Unknown / missing composed outcome -> conservative stop (fail closed).
    return "stop"
