"""Plan contract — an ordered set of actions with dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .action import Action
from .errors import ContractError


@dataclass
class Plan:
    plan_id: str
    goal_id: str
    steps: List[Action] = field(default_factory=list)
    dependencies: Dict[str, Tuple[str, ...]] = field(default_factory=dict)  # action_id -> prereqs
    completed: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.plan_id or not self.goal_id:
            raise ContractError("Plan.plan_id and goal_id required")
        ids = [s.action_id for s in self.steps]
        if len(ids) != len(set(ids)):
            raise ContractError("Plan step action_ids must be unique")

    def next_action(self) -> Optional[Action]:
        done = set(self.completed)
        for step in self.steps:
            if step.action_id in done:
                continue
            if all(dep in done for dep in self.dependencies.get(step.action_id, ())):
                return step
        return None

    def mark_done(self, action_id: str) -> None:
        if action_id not in self.completed:
            self.completed.append(action_id)

    @property
    def is_complete(self) -> bool:
        return len(self.completed) == len(self.steps)
