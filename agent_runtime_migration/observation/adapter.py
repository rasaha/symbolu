"""Build an Observation from an ExecutionResult (governed or local)."""
from __future__ import annotations
from ..contracts.observation import Observation
from ..contracts.result import ExecutionResult

_OUTCOME = {
    "PROCEED": "executed",
    "BLOCKED_BY_AUTHORIZATION": "blocked",
    "PENDING_AUTHORIZATION": "pending",
    "HELD_BY_ACP": "held",
}


def to_observation(result: ExecutionResult) -> Observation:
    if result.combined_outcome is None:      # local fast path (no CER)
        outcome = "local" if result.executed else "failed"
    else:
        outcome = _OUTCOME.get(result.combined_outcome, "failed")
        if outcome == "executed" and not result.executed:
            outcome = "failed"
    return Observation(
        action_id=result.action_id, outcome=outcome, output=result.output,
        error=result.error, cer_digest=result.cer_digest,
        governance={"actiongate": result.actiongate_outcome, "acp": result.acp_decision,
                    "composed": result.combined_outcome,
                    "execution_reference": result.execution_reference,
                    "reason_codes": list(result.reason_codes)})
