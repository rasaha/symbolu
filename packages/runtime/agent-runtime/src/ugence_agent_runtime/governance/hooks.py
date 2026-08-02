"""Built-in neutral governance hooks.

Two hooks ship with the core, plus a deprecated alias:

* ``UnconfiguredGovernanceHook`` — the DEFAULT. Returns BLOCK for every consequential
  transition with reason ``GOVERNANCE_NOT_CONFIGURED``. The runtime fails closed when
  no real governance adapter is configured; it never treats its own default as
  permission to execute a consequential action.

* ``AllowAllGovernanceHook`` — an EXPLICIT, OPT-IN testing/simulation helper. It CLEARs
  every proposal and binds the result to the proposal fingerprint so the CLEAR path can
  be exercised. It is UNSAFE for consequential execution in production and is never a
  configuration default. You must construct and pass it deliberately.

Neither hook creates authority. Production deployments inject a real governance adapter.
"""
from __future__ import annotations

import warnings

from ..models.proposal import TransitionProposal
from .interfaces import (
    GovernanceDisposition,
    GovernanceEvaluation,
    GovernanceHook,
)

GOVERNANCE_NOT_CONFIGURED = "GOVERNANCE_NOT_CONFIGURED"


class UnconfiguredGovernanceHook(GovernanceHook):
    """Default hook: fail closed. No governance is configured, so no consequential
    transition may proceed."""

    def evaluate(self, proposal: TransitionProposal, evaluation_time: float) -> GovernanceEvaluation:
        return GovernanceEvaluation(
            disposition=GovernanceDisposition.BLOCK,
            proposal_fingerprint=proposal.fingerprint,
            reason_codes=(GOVERNANCE_NOT_CONFIGURED,),
            correlation_reference=proposal.correlation_id,
            detail={"message": "No governance adapter configured; failing closed."},
        )


class AllowAllGovernanceHook(GovernanceHook):
    """UNSAFE explicit testing/simulation hook. CLEARs every proposal.

    NOT a configuration default and NOT safe for consequential production execution.
    It binds CLEAR to the exact proposal fingerprint and supplies a synthetic binding
    reference so tests can exercise the cleared path deterministically.
    """

    def __init__(self, *, reference_prefix: str = "allow-all") -> None:
        self._prefix = reference_prefix

    def evaluate(self, proposal: TransitionProposal, evaluation_time: float) -> GovernanceEvaluation:
        return GovernanceEvaluation(
            disposition=GovernanceDisposition.CLEAR,
            proposal_fingerprint=proposal.fingerprint,
            reason_codes=("ALLOW_ALL_TEST_HOOK",),
            evaluation_reference=f"{self._prefix}:{proposal.fingerprint[:12]}",
            correlation_reference=proposal.correlation_id,
        )


class NoopGovernanceHook(AllowAllGovernanceHook):
    """Deprecated. Renamed to :class:`AllowAllGovernanceHook` to make its permissive,
    unsafe nature explicit. Retained only for API stability; never a default."""

    def __init__(self, *, reference_prefix: str = "allow-all") -> None:
        warnings.warn(
            "NoopGovernanceHook is deprecated and unsafe as a default; it CLEARs every "
            "proposal. Use AllowAllGovernanceHook explicitly for tests, or inject a real "
            "governance adapter. The runtime default is UnconfiguredGovernanceHook (BLOCK).",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(reference_prefix=reference_prefix)
