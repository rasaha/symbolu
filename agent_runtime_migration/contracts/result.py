"""Result contract — the outcome of one governed (or local) execution attempt.

The governed executor produces this; it carries the control-plane decision summary
and, only when the control plane deemed the action eligible, the execution output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ExecutionResult:
    action_id: str
    executed: bool
    eligible: bool
    combined_outcome: Optional[str]           # PROCEED / BLOCKED_BY_AUTHORIZATION / ...
    actiongate_outcome: Optional[str] = None
    acp_decision: Optional[str] = None
    cer_digest: Optional[str] = None
    execution_reference: Optional[str] = None  # from the control plane only
    output: Optional[Any] = None
    error: Optional[str] = None
    reason_codes: tuple = ()
    metadata: Dict[str, Any] = field(default_factory=dict)
