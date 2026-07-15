"""Observation return path (milestone §7).

Governance ends at execution eligibility. The composed control-plane result is
handed BACK to the runtime, which resumes ownership of observation, reflection,
and subsequent planning. This module models the hypothetical governed execution
result and the runtime's post-execution reflection — proving the loop is not a
one-way waterfall.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .control_plane import ControlPlaneResult


@dataclass(frozen=True)
class GovernedExecutionResult:
    """Hypothetical execution result returned to the runtime after the CP verdict.

    Nothing actuated (ACP shadow-only). ``executed`` is the hypothetical: an
    eligible action WOULD execute with the minted token; an ineligible one does
    not. Either way, the result returns to the runtime.
    """
    cer_digest: str
    eligible: bool
    combined_outcome: Optional[str]
    execution_identity: Optional[str]
    executed: bool  # hypothetical: eligible => would-execute

    @classmethod
    def from_cp(cls, cp: ControlPlaneResult) -> "GovernedExecutionResult":
        return cls(
            cer_digest=cp.cer_digest, eligible=cp.eligible,
            combined_outcome=cp.combined_outcome,
            execution_identity=cp.execution_identity, executed=cp.eligible)


def observe_and_reflect(runtime_name: str, result: GovernedExecutionResult) -> dict:
    """The runtime ingests the result and reflects/plans the next step.

    Returns the runtime's post-governance decision — proving the runtime, not the
    control plane, owns what happens after eligibility.
    """
    if result.eligible:
        reflection = "action authorized+safe; would execute and observe outcome"
        next_step = "await_execution_result_then_verify"
    elif result.combined_outcome == "HELD_BY_ACP" or (
            result.combined_outcome and result.combined_outcome.startswith("HELD")):
        reflection = "operationally held; re-observe live state and re-propose later"
        next_step = "backoff_and_reobserve"
    elif result.combined_outcome == "PENDING_AUTHORIZATION":
        reflection = "authorization not final; gather evidence/approval and re-propose"
        next_step = "gather_evidence_and_repropose"
    else:  # BLOCKED_BY_AUTHORIZATION / other
        reflection = "blocked by authorization; do not retry the same action; re-plan"
        next_step = "replan"
    return {
        "runtime": runtime_name,
        "observed_cer_digest": result.cer_digest,
        "eligible": result.eligible,
        "combined_outcome": result.combined_outcome,
        "reflection": reflection,
        "next_step": next_step,
        # the memory update the runtime records (runtime-owned, not CP-owned)
        "memory_update": {
            "last_action_digest": result.cer_digest,
            "last_outcome": result.combined_outcome,
        },
    }
