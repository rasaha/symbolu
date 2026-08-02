"""A neutral no-op governance hook.

This is the default hook when no external governance is configured. It returns
CLEAR for every evaluation. It creates no authority — it simply expresses "no
governance is integrated, so coordination is unconstrained." Production deployments
inject a real governance adapter; the runtime core never ships one.
"""
from __future__ import annotations

from .interfaces import (
    ExecutionContext,
    GovernanceDisposition,
    GovernanceEvaluation,
    GovernanceHook,
)


class NoopGovernanceHook(GovernanceHook):
    def evaluate(
        self,
        context: ExecutionContext,
        proposed_transition: str,
        evaluation_time: float,
    ) -> GovernanceEvaluation:
        return GovernanceEvaluation(
            disposition=GovernanceDisposition.CLEAR,
            reason_codes=("NO_GOVERNANCE_CONFIGURED",),
            evaluation_reference=None,
            correlation_reference=context.correlation.correlation_id,
        )
