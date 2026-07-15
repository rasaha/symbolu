"""A workflow step wraps a single Action with status."""
from __future__ import annotations
from dataclasses import dataclass
from ..contracts.action import Action

PENDING = "pending"
DONE = "done"
FAILED = "failed"


@dataclass
class Step:
    action: Action
    status: str = PENDING

    @property
    def action_id(self) -> str:
        return self.action.action_id
