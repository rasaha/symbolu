"""Planner — turns a Goal into a Plan. Runtime-owned; pluggable; deterministic default."""
from __future__ import annotations
from typing import Callable, List, Optional
from ..contracts.action import Action
from ..contracts.goal import Goal
from ..contracts.plan import Plan
from ..contracts.errors import ContractError
from .decomposition import decompose
from .policies import PlanningPolicy


class Planner:
    def __init__(self, policy: Optional[PlanningPolicy] = None,
                 decomposer: Optional[Callable[[Goal], List[Action]]] = None):
        self.policy = policy or PlanningPolicy()
        self._decompose = decomposer or decompose

    def plan(self, goal: Goal) -> Plan:
        steps = self._decompose(goal)
        if len(steps) > self.policy.max_steps:
            raise ContractError(f"plan exceeds max_steps ({len(steps)} > {self.policy.max_steps})")
        deps = goal.metadata.get("dependencies", {})
        return Plan(plan_id=f"plan:{goal.goal_id}", goal_id=goal.goal_id,
                    steps=steps, dependencies={k: tuple(v) for k, v in deps.items()})
