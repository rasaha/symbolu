"""Neutral governance-integration boundary owned by the Agent Runtime.

The runtime COORDINATES execution; it does not decide permission. Before a
consequential transition, the runtime asks an external governance implementation
whether the transition may proceed, and then obeys the returned disposition. It
never authors policy, never binds a business decision, and never converts a
restrictive disposition into permission.

This interface depends on NOTHING concrete. It does not import TAP, Decision
Authority, ActionGate, Action Clearance, Code Governance, or StoryGraph. Concrete
Ugence governance adapters live outside this core package.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Protocol, Tuple, runtime_checkable

from ..models.proposal import TransitionProposal


class GovernanceDisposition(str, Enum):
    """The established governance outcome vocabulary, preserved by value.

    The runtime maps each disposition to a coordination behavior (see
    ``governance.decisions``). It never reinterprets or broadens a disposition:
    HOLD and ESCALATE can never become CLEAR inside the runtime.
    """

    CLEAR = "CLEAR"
    HOLD = "HOLD"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


@dataclass(frozen=True)
class CorrelationContext:
    """Neutral correlation/tracing identifiers carried across the boundary."""

    correlation_id: str
    instance_id: Optional[str] = None
    causation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionContext:
    """What the runtime tells governance about the transition it is proposing.

    This is a *description* of a proposed transition, not a request to execute. It
    carries no credentials and no policy.
    """

    workflow_id: str
    instance_id: str
    task_id: str
    operation: str
    correlation: CorrelationContext
    arguments: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GovernanceEvaluation:
    """The result governance returns to the runtime.

    Contains only what the runtime needs to coordinate: the disposition, why, the
    proposal fingerprint the result is bound to, references produced by governance
    (never minted by the runtime), an optional validity horizon, and any external
    resolution the runtime must wait for. It never contains authority the runtime can
    act on beyond continue/wait/stop.

    For a CLEAR result to permit execution, the runtime requires ``proposal_fingerprint``
    to match the exact proposal AND at least one non-empty binding reference
    (``evaluation_reference``, ``authorization_reference``, or ``clearance_reference``).
    ``valid_until`` (when set) is checked against the runtime clock immediately before
    provider invocation.
    """

    disposition: GovernanceDisposition
    proposal_fingerprint: Optional[str] = None
    reason_codes: Tuple[str, ...] = ()
    evaluation_reference: Optional[str] = None
    authorization_reference: Optional[str] = None
    clearance_reference: Optional[str] = None
    valid_until: Optional[float] = None
    required_resolution: Optional[str] = None
    correlation_reference: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)

    def binding_reference(self) -> Optional[str]:
        """The first non-empty governance-produced reference, if any."""
        return (
            self.evaluation_reference
            or self.authorization_reference
            or self.clearance_reference
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "proposal_fingerprint": self.proposal_fingerprint,
            "reason_codes": list(self.reason_codes),
            "evaluation_reference": self.evaluation_reference,
            "authorization_reference": self.authorization_reference,
            "clearance_reference": self.clearance_reference,
            "valid_until": self.valid_until,
            "required_resolution": self.required_resolution,
            "correlation_reference": self.correlation_reference,
            "detail": dict(self.detail),
        }


@runtime_checkable
class GovernanceHook(Protocol):
    """The neutral contract an external governance implementation satisfies.

    The hook evaluates an immutable ``TransitionProposal`` — the exact intended
    provider invocation, identified by a deterministic fingerprint — not a loose
    operation string with mutable arguments. ``evaluation_time`` is caller-controlled
    so the runtime (not the hook) owns the logical clock, preserving determinism.

    The hook returns a ``GovernanceEvaluation`` and MUST NOT execute the proposed
    action or mint any authority. To permit execution it must bind CLEAR to the exact
    ``proposal.fingerprint`` and supply a non-empty binding reference.
    """

    def evaluate(
        self,
        proposal: TransitionProposal,
        evaluation_time: float,
    ) -> GovernanceEvaluation:
        ...
