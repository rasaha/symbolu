"""Standalone, deterministic demonstration of the Agent Runtime.

Run it from the installed wheel:

    pip install ugence_agent_runtime-0.1.0-py3-none-any.whl
    python agent_runtime_demo.py

It imports ONLY ``ugence_agent_runtime`` — no Code Governance, no product package,
no monorepo module. It exercises the four governance dispositions and a
persist/restart/recover cycle, and prints the final event sequence for each case.
"""
from __future__ import annotations

from ugence_agent_runtime.api import (
    AgentRuntimeConfig,
    TaskDefinition,
    WorkflowDefinition,
    cancel_workflow,  # noqa: F401 (kept to show the surface)
    create_runtime,
    recover_runtime,
    register_provider,
    resume_workflow,
)
from ugence_agent_runtime.governance.interfaces import (
    GovernanceDisposition,
    GovernanceEvaluation,
    GovernanceHook,
)
from ugence_agent_runtime.models.proposal import TransitionProposal
from ugence_agent_runtime.models.workflow import WorkflowStatus
from ugence_agent_runtime.persistence.in_memory import InMemoryRuntimeStateStore
from ugence_agent_runtime.providers.interfaces import Provider, ToolInvocation, ToolResult


class FakeProvider(Provider):
    """A neutral fake provider that records whether it was invoked."""

    def __init__(self) -> None:
        self.provider_id = "fake-provider"
        self.version = "1.0.0"
        self.invocations = []

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        self.invocations.append(invocation.operation)
        return ToolResult(
            provider_id=self.provider_id,
            operation=invocation.operation,
            ok=True,
            output={"echo": invocation.arguments},
        )


class FakeGovernanceHook(GovernanceHook):
    """A neutral fake governance hook returning a configured disposition."""

    def __init__(self, disposition: GovernanceDisposition) -> None:
        self.disposition = disposition
        self.calls = 0

    def evaluate(self, proposal: TransitionProposal, evaluation_time: float) -> GovernanceEvaluation:
        self.calls += 1
        # A real adapter would consult TAP/ActionGate/Action Clearance here. This fake
        # binds its result to the exact proposal fingerprint and supplies a reference,
        # so a CLEAR is provably about THIS invocation.
        return GovernanceEvaluation(
            disposition=self.disposition,
            proposal_fingerprint=proposal.fingerprint,
            reason_codes=(f"DEMO_{self.disposition.value}",),
            evaluation_reference=f"demo-eval-{self.calls}",
            correlation_reference=proposal.correlation_id,
        )


def _workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="demo-workflow",
        tasks=(TaskDefinition(task_id="t1", operation="do-thing",
                              provider_id="fake-provider", arguments={"x": 1}),),
    )


def _banner(title: str) -> None:
    print("\n" + "=" * 68)
    print(title)
    print("=" * 68)


def demo_clear_with_recovery() -> None:
    _banner("CASE 1 — CLEAR, checkpoint, restart, recover, continue, complete")
    provider = FakeProvider()
    hook = FakeGovernanceHook(GovernanceDisposition.ESCALATE)  # pause first, then CLEAR
    store = InMemoryRuntimeStateStore()
    cfg = AgentRuntimeConfig(governance_hook=hook, state_store=store)
    rt = create_runtime(cfg)                                    # (2) create a runtime
    register_provider(rt, provider)                            # (3) register fake provider
    #                                                            (4) fake governance hook via cfg
    inst = rt.start_workflow(_workflow())                      # (5) one workflow, (6) run one task
    print(f"after start: workflow={inst.status.value}, provider_invoked={provider.invocations}")
    assert inst.status is WorkflowStatus.PAUSED
    assert provider.invocations == []  # ESCALATE -> not executed yet

    # Flip governance to CLEAR and simulate a process restart before continuing.
    hook.disposition = GovernanceDisposition.CLEAR
    instance_id = inst.instance_id

    # (10) simulate restart: a brand-new runtime with only the persisted store
    rt2 = create_runtime(AgentRuntimeConfig(governance_hook=hook, state_store=store))
    register_provider(rt2, provider)
    before = list(provider.invocations)
    result = recover_runtime(rt2, instance_id, _workflow())     # (11) recover, no external calls
    assert provider.invocations == before, "recovery must not invoke the provider"
    print(f"recovered: status={result.instance.status.value}, "
          f"requires_continuation={result.requires_continuation}")

    inst2 = resume_workflow(rt2, instance_id)                   # (12) explicitly continue
    print(f"after resume: workflow={inst2.status.value}, "     # (7) CLEAR (8) execute
          f"provider_invoked={provider.invocations}")          # (9) checkpoint happened each step
    assert inst2.status is WorkflowStatus.COMPLETED            # (13) complete
    assert provider.invocations == ["do-thing"]
    _print_events(rt2, instance_id)


def demo_hold() -> None:
    _banner("CASE 2 — HOLD, provider is NOT invoked")
    provider = FakeProvider()
    rt = create_runtime(AgentRuntimeConfig(governance_hook=FakeGovernanceHook(GovernanceDisposition.HOLD)))
    register_provider(rt, provider)
    inst = rt.start_workflow(_workflow())
    print(f"workflow={inst.status.value}, provider_invoked={provider.invocations}")
    assert inst.status is WorkflowStatus.WAITING           # (14) HOLD
    assert provider.invocations == []                      # (15) provider not invoked
    _print_events(rt, inst.instance_id)


def demo_escalate() -> None:
    _banner("CASE 3 — ESCALATE, workflow PAUSES")
    provider = FakeProvider()
    rt = create_runtime(AgentRuntimeConfig(governance_hook=FakeGovernanceHook(GovernanceDisposition.ESCALATE)))
    register_provider(rt, provider)
    inst = rt.start_workflow(_workflow())
    print(f"workflow={inst.status.value}, provider_invoked={provider.invocations}")
    assert inst.status is WorkflowStatus.PAUSED            # (16,17) ESCALATE -> paused
    assert provider.invocations == []
    _print_events(rt, inst.instance_id)


def demo_block() -> None:
    _banner("CASE 4 — BLOCK, no execution occurs")
    provider = FakeProvider()
    rt = create_runtime(AgentRuntimeConfig(governance_hook=FakeGovernanceHook(GovernanceDisposition.BLOCK)))
    register_provider(rt, provider)
    inst = rt.start_workflow(_workflow())
    print(f"workflow={inst.status.value}, provider_invoked={provider.invocations}")
    assert inst.status is WorkflowStatus.FAILED           # (18) BLOCK
    assert provider.invocations == []                     # (19) no execution
    _print_events(rt, inst.instance_id)


def _print_events(rt, instance_id: str) -> None:  # (20) final event sequence
    print("  event sequence:")
    for e in rt.trace(instance_id).events:
        print(f"    [{e.seq:02d}] {e.type}")


def main() -> None:
    import ugence_agent_runtime  # (1) import the package
    print(f"ugence_agent_runtime {ugence_agent_runtime.__version__}")
    demo_clear_with_recovery()
    demo_hold()
    demo_escalate()
    demo_block()
    _banner("DEMO COMPLETE — runtime coordinated; governance decided; provider executed only on CLEAR")


if __name__ == "__main__":
    main()
