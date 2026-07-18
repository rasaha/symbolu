"""Bounded resolution policy for non-terminal governed outcomes (Phase 2 §8).

Maps an observation to the runtime's next control action under EXPLICIT budgets — no
unbounded autonomous retry loop. The runtime never authorizes; it only decides whether
to continue, retry (bounded), replan (bounded), request human input, or stop.

    executed / local          -> CONTINUE
    blocked (ActionGate DENY) -> REPLAN if replans remain else STOP  (denials are not
                                 auto-retried; a different plan is required)
    pending (more evidence)   -> REQUEST_HUMAN (evidence/approval needed)
    held   (ACP unsafe-now)   -> REQUEST_HUMAN (wait / choose a safer candidate)
    failed (execution error)  -> RETRY if retries remain else STOP  (reflect + retry)

A ``RETRY`` re-executes the SAME action; an optional refresh hook may rebuild its state
first (stale state -> a new CER identity). All three budgets are hard caps.
"""
from __future__ import annotations
from dataclasses import dataclass

CONTINUE = "continue"
RETRY = "retry"
REPLAN = "replan"
REQUEST_HUMAN = "request_human"
STOP = "stop"


@dataclass(frozen=True)
class ResolutionBudget:
    max_replans: int = 2
    max_retries_per_action: int = 0     # 0 = no retry (default; Phase 1 behavior)
    max_iterations: int = 64            # hard cap on loop iterations (anti-runaway)


def decide(outcome: str, *, retries_used: int, replans_used: int,
           budget: ResolutionBudget) -> str:
    if outcome in ("executed", "local"):
        return CONTINUE
    if outcome == "failed":
        return RETRY if retries_used < budget.max_retries_per_action else STOP
    if outcome == "blocked":
        return REPLAN if replans_used < budget.max_replans else STOP
    if outcome in ("pending", "held"):
        return REQUEST_HUMAN
    return STOP
