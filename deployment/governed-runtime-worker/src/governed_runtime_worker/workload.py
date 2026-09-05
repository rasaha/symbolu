"""The shadow workload: one fixture workflow, one fixture provider, one upstream
governance source that parks every proposal on ESCALATE.

    FIXTURE. Every provider the worker invokes is this one, and it changes nothing
    outside the process. That is the ceiling the ADR records for this release.

A composition root that runs a real workload supplies its own ``Workload``: the
definitions the runtime executes, the providers it may invoke, and the deployment's
real governance input source. The worker composes whatever it is given through the
same governed hook, the same approval-bound source and the same ledger.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable, Iterable, Optional, Protocol, runtime_checkable

from ugence_agent_runtime.models.proposal import TransitionProposal
from ugence_agent_runtime.models.task import TaskDefinition
from ugence_agent_runtime.models.workflow import WorkflowDefinition
from ugence_agent_runtime.providers.interfaces import ToolInvocation, ToolResult
from ugence_agent_runtime_governance import CompositionInputs
from ugence_risk_authority_runtime.contracts import (
    GovernanceRestrictions,
    GovernanceVetoResult,
    RiskAuthorityDisposition,
    RiskAuthorityMachineResult,
    VetoDisposition,
)

__all__ = ["Workload", "ShadowWorkload", "ShadowProvider", "ShadowUpstreamSource"]


@runtime_checkable
class Workload(Protocol):
    """What a composition root must supply for the runtime to have anything to run."""

    def definition_for(self, workflow_id: str) -> WorkflowDefinition: ...

    def providers(self) -> Iterable[Any]: ...

    def upstream_source(self, clock: Callable[[], Any]) -> Any: ...


class ShadowProvider:
    """Records each invocation in memory and returns success. No external effect."""

    provider_id = "shadow-recorder"
    version = "0.1.0"
    maturity = "FIXTURE_ONLY"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        self.calls.append((invocation.idempotency_key or "", invocation.operation))
        return ToolResult(provider_id=self.provider_id, operation=invocation.operation, ok=True,
                          output={"recorded": True, "fixture": True})


class _ShadowScope:
    purposes = ("review",)
    tools_allow = frozenset({ShadowProvider.provider_id})
    tools_deny = frozenset()
    data_allow = frozenset({"synthetic"})
    data_deny = frozenset()
    destinations = frozenset({"none"})
    jurisdictions = frozenset({"eu"})
    max_autonomy_level = 2
    max_amount_minor_units = 10_000
    required_approvals = frozenset()


class ShadowUpstreamSource:
    """The deployment's governance inputs, reduced to fixtures that make every
    proposal ESCALATE-bound: Decision Authority HOLDs and requires the configured
    role's approval; Risk Authority allows; ActionGate does not veto."""

    maturity = "FIXTURE_ONLY"

    def __init__(self, *, clock: Callable[[], Any], required_role: str) -> None:
        self._clock = clock
        self._label = required_role
        self.calls = 0

    def inputs_for(self, proposal: TransitionProposal) -> Optional[CompositionInputs]:
        self.calls += 1
        ra = RiskAuthorityMachineResult(
            disposition=RiskAuthorityDisposition.ALLOW, reason_codes=("RA_ALLOW",),
            envelope_id="rae_shadow_0001", action_digest=proposal.fingerprint[:16],
            scope=_ShadowScope(), expires_at=self._clock() + timedelta(hours=1),
            source_version="shadow",
        )
        return CompositionInputs(
            risk_authority=ra,
            decision_authority=GovernanceVetoResult(
                source="decision_authority", disposition=VetoDisposition.HOLD,
                reason_codes=("DA_HOLD",),
                restrictions=GovernanceRestrictions(required_approvals=frozenset({self._label}),
                                                    max_amount_minor_units=500),
                source_version="shadow",
            ),
            actiongate=GovernanceVetoResult(source="actiongate", disposition=VetoDisposition.NO_VETO,
                                            reason_codes=("AG_NO_VETO",), source_version="shadow"),
            action=None, envelope=None, tier=None,
        )


class ShadowWorkload:
    """One consequential task on the fixture provider; parks on ESCALATE every time."""

    WORKFLOW_ID = "wf-shadow"
    maturity = "FIXTURE_ONLY"

    def __init__(self, *, required_role: str) -> None:
        self._role = required_role
        self.provider = ShadowProvider()
        self.source: Optional[ShadowUpstreamSource] = None

    def definition_for(self, workflow_id: str) -> WorkflowDefinition:
        if workflow_id != self.WORKFLOW_ID:
            raise KeyError(f"the shadow workload defines only {self.WORKFLOW_ID!r}")
        return WorkflowDefinition(
            workflow_id=workflow_id,
            tasks=(TaskDefinition(task_id="t1", operation="do",
                                  provider_id=ShadowProvider.provider_id,
                                  consequential=True, arguments={"n": 1}),),
        )

    def providers(self) -> Iterable[Any]:
        return (self.provider,)

    def upstream_source(self, clock: Callable[[], Any]) -> ShadowUpstreamSource:
        self.source = ShadowUpstreamSource(clock=clock, required_role=self._role)
        return self.source
