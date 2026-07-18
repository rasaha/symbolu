"""Runtime state for one run."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from ..contracts.goal import Goal
from ..contracts.observation import Observation
from ..contracts.plan import Plan

RUNNING = "running"
COMPLETED = "completed"
STOPPED = "stopped"
CANCELLED = "cancelled"
AWAITING_HUMAN = "awaiting_human"
BUDGET_STOP = "budget_stop"


@dataclass
class RuntimeState:
    run_id: str
    goal: Goal
    plan: Optional[Plan] = None
    status: str = RUNNING
    turns: int = 0
    observations: List[Observation] = field(default_factory=list)
