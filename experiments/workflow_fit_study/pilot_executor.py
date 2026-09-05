"""Phase 4A executor adapter: runs the research harness's reasoning workflows behind the
pilot's gateway stub. Lives in experiments/ because it imports the runtime workflows; the
pilot package never does."""

from __future__ import annotations

from agentic.agentic_framework.reasoning_workflows import WorkflowType, create_workflow_registry
from ugence_reasoning_method_governance.api import ReasoningMethodRef
from ugence_workflow_fit_pilot.api import ExecutionOutcome


class HarnessWorkflowExecutor:
    """WorkflowExecutorPort over the research harness's workflow registry."""

    def __init__(self, max_llm_calls: int) -> None:
        if max_llm_calls <= 0:
            raise ValueError("max_llm_calls must be positive (caller-declared research configuration)")
        self._registry = create_workflow_registry()
        self._max = max_llm_calls

    def execute(self, method: ReasoningMethodRef, query: str, context: str, client) -> ExecutionOutcome:
        wf = self._registry.get(WorkflowType(method.method_id))
        result = wf.execute(query, client, context=context, max_llm_calls=self._max)
        return ExecutionOutcome(final_response=result.final_response, total_llm_calls_reported=int(result.total_llm_calls))


__all__ = ["HarnessWorkflowExecutor"]
