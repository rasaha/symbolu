"""Goal contract — the runtime's input intent."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from .errors import ContractError

PURPOSE_TYPES = ("informational", "task", "analysis", "creative")


@dataclass(frozen=True)
class Goal:
    goal_id: str
    objective: str
    purpose_type: str = "task"
    constraints: Tuple[str, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.goal_id or not isinstance(self.goal_id, str):
            raise ContractError("Goal.goal_id required (non-empty str)")
        if not self.objective or not isinstance(self.objective, str):
            raise ContractError("Goal.objective required (non-empty str)")
        if self.purpose_type not in PURPOSE_TYPES:
            raise ContractError(f"Goal.purpose_type must be one of {PURPOSE_TYPES}")
