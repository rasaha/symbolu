"""Neutral test doubles for the Agent Runtime package tests.

Kept in a distinctly-named module (not ``conftest``) so it never collides with a
host repository's root conftest when these tests run inside the monorepo, and so it
imports cleanly when the tests run from an installed wheel. No monorepo application
fixture is imported here.
"""
from __future__ import annotations

from ugence_agent_runtime.governance.interfaces import (
    ExecutionContext,
    GovernanceDisposition,
    GovernanceEvaluation,
    GovernanceHook,
)
from ugence_agent_runtime.providers.interfaces import (
    Provider,
    ToolInvocation,
    ToolResult,
)
from ugence_agent_runtime.runtime.errors import ProviderExecutionError


class RecordingProvider(Provider):
    """A neutral fake provider that records the operations it executed."""

    def __init__(self, provider_id: str = "fake", *, output=None):
        self.provider_id = provider_id
        self.version = "1.0.0"
        self.calls = []
        self._output = output

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        self.calls.append(invocation)
        return ToolResult(
            provider_id=self.provider_id,
            operation=invocation.operation,
            ok=True,
            output=self._output if self._output is not None else {"op": invocation.operation},
        )


class FailingProvider(Provider):
    def __init__(self, provider_id: str = "failing", *, retriable=True, fail_times=None):
        self.provider_id = provider_id
        self.version = "1.0.0"
        self.calls = 0
        self._retriable = retriable
        self._fail_times = fail_times  # None = always fail

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        self.calls += 1
        if self._fail_times is not None and self.calls > self._fail_times:
            return ToolResult(provider_id=self.provider_id, operation=invocation.operation, ok=True, output="ok")
        raise ProviderExecutionError("boom", retriable=self._retriable)


class DispositionHook(GovernanceHook):
    """A neutral fake governance hook returning a fixed disposition."""

    def __init__(self, disposition: GovernanceDisposition, *, reference="gov-ref-1"):
        self.disposition = disposition
        self.reference = reference
        self.evaluations = []
        self.evaluation_times = []

    def evaluate(self, context: ExecutionContext, proposed_transition: str, evaluation_time: float) -> GovernanceEvaluation:
        self.evaluations.append((context.task_id, proposed_transition))
        self.evaluation_times.append(evaluation_time)
        return GovernanceEvaluation(
            disposition=self.disposition,
            reason_codes=("TEST",),
            evaluation_reference=self.reference,
            correlation_reference=context.correlation.correlation_id,
        )
