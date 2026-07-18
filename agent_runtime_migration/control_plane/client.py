"""Narrow client to the FROZEN AI Control Plane.

Submits a CER and returns a structured, SEPARATED decision (ActionGate
authorization, ACP operational safety, composed eligibility, required next step,
execution reference, reason codes). It is a thin wrapper over
``cer_v0_3.control_plane.run_control_plane`` — it makes no policy, re-decides
nothing, and never authorizes. The runtime consumes the decision; it may not
override it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .. import _paths  # noqa: F401
from ..contracts.errors import GovernanceBoundaryError

from cer_v0_3 import control_plane as _frozen_cp  # frozen  # noqa: E402
from cer_v0_3 import envelope as _cer_env  # frozen  # noqa: E402

from .decision_adapter import required_next_step


@dataclass(frozen=True)
class GovernanceDecision:
    """Structured, separated result of governing one CER. Read-only for the runtime."""
    cer_digest: str
    actiongate_authorization: str        # ActionGate outcome
    acp_operational_safety: str          # ACP recommendation/decision
    composed_eligibility: Optional[str]  # PROCEED / BLOCKED_BY_AUTHORIZATION / PENDING / HELD_BY_ACP
    eligible: bool
    execution_reference: Optional[str]   # ONLY present when the control plane deemed it eligible
    required_next_step: str              # execute / replan / provide_evidence / request_human / wait / stop
    reason_codes: Tuple[str, ...] = ()
    trace_ref: Dict[str, Any] = field(default_factory=dict)

    @property
    def authorized(self) -> bool:
        return self.actiongate_authorization in ("ALLOW", "ALLOW_WITH_CONSTRAINTS")


class ControlPlaneClient:
    """The only integration point with ActionGate + ACP. Deterministic (caller supplies ``now``)."""

    def __init__(self, *, signed_policy: Optional[dict] = None, auto_evidence: bool = True):
        self._signed_policy = signed_policy
        self._auto_evidence = auto_evidence

    def submit(self, cer: Dict[str, Any], *, now: str,
               evidence: Optional[List[dict]] = None,
               approvals: Optional[List[dict]] = None) -> GovernanceDecision:
        # The runtime must not have mutated the CER into an invalid state.
        _cer_env.validate_cer(cer)
        res = _frozen_cp.run_control_plane(
            cer, now=now, signed_policy=self._signed_policy, evidence=evidence,
            approvals=approvals, auto_evidence=self._auto_evidence and evidence is None)
        return GovernanceDecision(
            cer_digest=res.cer_digest,
            actiongate_authorization=res.actiongate_outcome,
            acp_operational_safety=res.acp_decision,
            composed_eligibility=res.combined_outcome,
            eligible=res.eligible,
            execution_reference=res.execution_identity,   # None unless eligible
            required_next_step=required_next_step(res.combined_outcome, res.actiongate_outcome),
            reason_codes=tuple(res.reason_codes),
            trace_ref={"actiongate_action_hash": res.actiongate_action_hash,
                       "profile": res.profile, "risk_tier": res.risk_tier})

    @staticmethod
    def ensure_not_self_authorized(decision: GovernanceDecision) -> None:
        """Guard: the runtime may never treat anything but a control-plane eligibility
        (with an execution reference) as permission to run a governed tool."""
        if decision.eligible and not decision.execution_reference:
            raise GovernanceBoundaryError(
                "eligible decision without a control-plane execution reference; refuse")
