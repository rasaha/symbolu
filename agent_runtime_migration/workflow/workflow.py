"""A workflow is an ordered set of steps with dependencies + checkpointing.

Deterministic ordering is preserved: steps run in registration order subject to
dependencies. Resumable from a checkpoint.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from ..contracts.errors import ContractError
from .step import Step, DONE, PENDING
from .checkpoint import Checkpoint


@dataclass
class Workflow:
    workflow_id: str
    steps: List[Step] = field(default_factory=list)
    dependencies: Dict[str, Tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ids = [s.action_id for s in self.steps]
        if len(ids) != len(set(ids)):
            raise ContractError("workflow step ids must be unique")

    def next_step(self) -> Optional[Step]:
        done = {s.action_id for s in self.steps if s.status == DONE}
        for s in self.steps:
            if s.status != PENDING:
                continue
            if all(dep in done for dep in self.dependencies.get(s.action_id, ())):
                return s
        return None

    def checkpoint(self) -> Checkpoint:
        return Checkpoint(workflow_id=self.workflow_id,
                          completed=[s.action_id for s in self.steps if s.status == DONE],
                          statuses={s.action_id: s.status for s in self.steps})

    def restore(self, cp: Checkpoint) -> None:
        for s in self.steps:
            if s.action_id in cp.statuses:
                s.status = cp.statuses[s.action_id]
