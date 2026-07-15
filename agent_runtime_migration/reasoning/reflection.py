"""Reflection — decide continue / stop / replan / request_human after an observation.

This is runtime reasoning over the GOVERNED result. It never re-decides eligibility;
it interprets what the control plane already decided plus the execution outcome.
"""
from __future__ import annotations
from dataclasses import dataclass
from ..contracts.observation import Observation

CONTINUE = "continue"
STOP = "stop"
REPLAN = "replan"
REQUEST_HUMAN = "request_human"


@dataclass(frozen=True)
class Reflection:
    decision: str
    rationale: str


class Reflector:
    def reflect(self, observation: Observation) -> Reflection:
        o = observation.outcome
        if o in ("executed", "local"):
            return Reflection(CONTINUE, "action succeeded; continue the plan")
        if o == "held":
            return Reflection(REQUEST_HUMAN, "ACP held the action; a human should decide to wait/retry")
        if o == "pending":
            return Reflection(REQUEST_HUMAN, "authorization pending (evidence/approval needed)")
        if o == "blocked":
            return Reflection(REPLAN, "authorization denied; replan a different approach")
        return Reflection(STOP, f"unrecoverable outcome {o!r}; stop")
