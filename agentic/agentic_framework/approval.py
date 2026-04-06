"""
Human-in-the-Loop Interrupts / Approvals (R4)

Provides a minimal but real interrupt/approval capability at the
orchestration layer.  Runs can pause cleanly at pre-action boundaries
and resume after human approval.

Key concepts:

- **ApprovalPolicy** — decides which actions require approval (by
  action type or tool name).
- **PendingApproval** — immutable snapshot of an action waiting for
  a human decision.
- **ApprovalResponse** — the human's approve/deny verdict.
- **ApprovalController** — the callback surface plugged into
  ``run_stream()`` / ``run_stream_async()``.

Usage::

    from agentic.agentic_framework.approval import (
        ApprovalPolicy, ApprovalController, ApprovalResponse,
    )

    policy = ApprovalPolicy(require_approval_for={"compute", "search"})

    def decider(pending):
        # Inspect pending.action_type / pending.description
        return ApprovalResponse(approved=True)

    ctrl = ApprovalController(policy=policy, callback=decider)

    for event in agent.run_stream("do work", approval_controller=ctrl):
        ...
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, FrozenSet, Optional, Set


# ---------------------------------------------------------------------------
# Approval policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApprovalPolicy:
    """Determines which actions require human approval before execution.

    Args:
        require_approval_for: Set of action types (or tool names) that
            must be approved.  An empty set means *no* actions require
            approval (the default — backward-compatible).
        require_all: If ``True``, *every* action requires approval
            regardless of ``require_approval_for``.
    """

    require_approval_for: FrozenSet[str] = frozenset()
    require_all: bool = False

    def requires_approval(self, action_type: str) -> bool:
        """Return ``True`` if *action_type* must be approved."""
        if self.require_all:
            return True
        return action_type in self.require_approval_for


# ---------------------------------------------------------------------------
# Pending-approval snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PendingApproval:
    """Immutable snapshot of an action awaiting human approval.

    Carries enough context for a caller or UI to make an informed
    decision.

    Fields:
        action_id: Unique action identifier from GoalState.
        action_type: The kind of action (e.g. "compute", "search").
        description: Human-readable description of the action.
        parameters: Action parameters (may be empty).
        turn_id: Turn index in the current session.
        session_id: Session identifier.
        reason: Why approval is required (human-readable).
    """

    action_id: str = ""
    action_type: str = ""
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    turn_id: int = 0
    session_id: str = ""
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-safe dict."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Approval response
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApprovalResponse:
    """Human verdict on a ``PendingApproval``.

    Fields:
        approved: ``True`` to execute the action, ``False`` to skip it.
        reason: Optional human-readable justification.
    """

    approved: bool = False
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"approved": self.approved, "reason": self.reason}


# ---------------------------------------------------------------------------
# Approval controller
# ---------------------------------------------------------------------------

# Callback type: receives a PendingApproval, returns an ApprovalResponse.
ApprovalCallback = Callable[[PendingApproval], ApprovalResponse]


class ApprovalController:
    """Pluggable controller that gates action execution in ``run_stream()``.

    The controller pairs a *policy* (which actions need approval) with
    a *callback* (how to obtain the decision).  The callback is invoked
    synchronously — it may block (e.g. prompt in a terminal) or return
    immediately (e.g. auto-approve in tests).

    Args:
        policy: ``ApprovalPolicy`` that decides which actions need approval.
        callback: Callable that receives ``PendingApproval`` and returns
            ``ApprovalResponse``.
    """

    def __init__(
        self,
        policy: ApprovalPolicy,
        callback: ApprovalCallback,
    ) -> None:
        self.policy = policy
        self.callback = callback

    def needs_approval(self, action_type: str) -> bool:
        """Check whether *action_type* requires human approval."""
        return self.policy.requires_approval(action_type)

    def request_approval(self, pending: PendingApproval) -> ApprovalResponse:
        """Invoke the callback and return the human's decision."""
        return self.callback(pending)
