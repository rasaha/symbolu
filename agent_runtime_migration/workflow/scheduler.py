"""Scheduler — drives a workflow's steps in deterministic dependency order through
an injected ActionExecutor, checkpointing after each step. Runtime-owned; the
executor owns governance."""
from __future__ import annotations
from typing import List
from ..contracts.result import ExecutionResult
from .step import DONE, FAILED
from .workflow import Workflow


class WorkflowScheduler:
    def __init__(self, executor):
        self._executor = executor

    def run(self, workflow: Workflow) -> List[ExecutionResult]:
        results: List[ExecutionResult] = []
        while True:
            step = workflow.next_step()
            if step is None:
                break
            result = self._executor.execute(step.action)
            results.append(result)
            step.status = DONE if result.executed else FAILED
            if not result.executed:
                break   # deterministic stop on first non-executed step
        return results
