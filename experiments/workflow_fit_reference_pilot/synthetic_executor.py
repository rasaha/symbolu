"""SYNTHETIC workflow executor for the mechanism-validation fixture. It is NOT a reasoning
workflow: it makes a declared number of gateway calls per method and case (including zero)
and returns the last provider text, so the capture, attestation, evaluation and lifecycle
machinery can be exercised end to end. The real workflows are reached through
experiments.workflow_fit_study.pilot_executor.HarnessWorkflowExecutor instead."""

from __future__ import annotations

from typing import Dict, Mapping

from ugence_reasoning_method_governance.api import ReasoningMethodRef
from ugence_workflow_fit_pilot.api import ExecutionOutcome


class SyntheticWorkflowExecutor:
    def __init__(self, calls: Mapping[str, Mapping[str, int]], *, bypass_method: str = "", fail_method: str = "") -> None:
        """calls[method_id][case_id] = number of gateway calls to make (0 permitted).
        bypass_method: one extra in-process call that skips the gateway (incomplete capture).
        fail_method: raise before any call (a workflow failure)."""
        self.calls = calls
        self.bypass_method, self.fail_method = bypass_method, fail_method
        self.counts: Dict[str, int] = {}

    def execute(self, method: ReasoningMethodRef, query: str, context: str, client) -> ExecutionOutcome:
        if method.method_id == self.fail_method:
            raise RuntimeError("synthetic workflow failure")
        case_id = self._case_id(query)
        n = self.calls[method.method_id][case_id]
        text = "ANSWER: (no call made)"
        for _ in range(n):
            self.counts[method.method_id] = self.counts.get(method.method_id, 0) + 1
            text = client.call(f"{query} [{method.method_id} call {self.counts[method.method_id]}]")
        if method.method_id == self.bypass_method:
            client.calls += 1  # counted by the harness wrapper but never captured by the boundary
        return ExecutionOutcome(final_response=text, total_llm_calls_reported=n)

    def _case_id(self, query: str) -> str:
        return self._by_query[query]

    _by_query: Dict[str, str] = {}

    def bind_cases(self, cases) -> "SyntheticWorkflowExecutor":
        """The runner hands the executor a query, not a case id; the fixture's call table is
        keyed by case id, so the mapping is bound from the same case documents."""
        self._by_query = {c.query: c.case_id for c in cases}
        return self


__all__ = ["SyntheticWorkflowExecutor"]
