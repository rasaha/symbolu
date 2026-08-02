"""Neutral test doubles for the Agent Runtime package tests.

Kept in a distinctly-named module (not ``conftest``) so it never collides with a
host repository's root conftest when these tests run inside the monorepo, and so it
imports cleanly when the tests run from an installed wheel. No monorepo application
fixture is imported here.
"""
from __future__ import annotations

from ugence_agent_runtime.governance.interfaces import (
    GovernanceDisposition,
    GovernanceEvaluation,
    GovernanceHook,
)
from ugence_agent_runtime.models.proposal import TransitionProposal
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
    """A neutral fake governance hook returning a fixed disposition.

    It evaluates the immutable ``TransitionProposal`` and, for a CLEAR result, binds
    the evaluation to the exact proposal fingerprint and supplies a binding reference,
    so the runtime's exact-action clearance check passes. Set ``bind=False`` to model a
    misbehaving hook that returns CLEAR without binding (which must fail closed).
    """

    def __init__(self, disposition: GovernanceDisposition, *, reference="gov-ref-1",
                 bind=True, valid_until=None):
        self.disposition = disposition
        self.reference = reference
        self.bind = bind
        self.valid_until = valid_until
        self.evaluations = []
        self.evaluation_times = []
        self.proposals = []

    def evaluate(self, proposal: TransitionProposal, evaluation_time: float) -> GovernanceEvaluation:
        self.evaluations.append((proposal.task_id, proposal.operation))
        self.evaluation_times.append(evaluation_time)
        self.proposals.append(proposal)
        return GovernanceEvaluation(
            disposition=self.disposition,
            proposal_fingerprint=proposal.fingerprint if self.bind else None,
            reason_codes=("TEST",),
            evaluation_reference=self.reference if self.bind else None,
            valid_until=self.valid_until,
            correlation_reference=proposal.correlation_id,
        )
