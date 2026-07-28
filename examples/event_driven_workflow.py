#!/usr/bin/env python3
"""
Event-Driven Execution & Long-Lived Workflows (H17)
===================================================

Turns the bounded execution engine into a persistent orchestration engine: a
workflow runs, SUSPENDS to wait for an external event, then RESUMES
deterministically from preserved state — reusing H15 hierarchy, H16
coordination, H14 memory, H13 assumptions, and one shared H11 RunBudget.

    Mission → Execute → WAIT → Event → Resume → Continue → Complete

Demonstrates:

  1. A workflow suspends at an approval gate (no budget consumed while waiting).
  2. A wrong event is ignored — the workflow stays waiting.
  3. The correct event applies its effects (memory + assumption) and resumes
     from preserved state — earlier work is NOT re-run.
  4. Two independent waiting subtrees resume only when their own event arrives.

No API key, no GPU — deterministic scripted workers.

Run:
    python examples/event_driven_workflow.py
"""

from agentic.agentic_framework import (
    WorkingMemory,
    MemoryWrite,
    RunBudget,
    RunBudgetLimits,
    AgentProfile,
    CapabilityRegistry,
    ScriptedWorker,
    WorkerResult,
    PlanAssumption,
    AssumptionRegistry,
    AssumptionDependencyGraph,
    AssumptionContext,
    AssumptionState,
    Goal,
    GoalStatus,
    StaticDecomposer,
    WorkflowEngine,
    WorkflowStatus,
    WaitCondition,
    WaitKind,
    WorkflowEvent,
    EventType,
    format_workflow_trace,
    format_working_memory,
)


def _registry():
    r = CapabilityRegistry()
    r.register(AgentProfile("ops", capabilities=frozenset({"do"}), trust_level=5),
               ScriptedWorker(lambda c, m: WorkerResult(success=True, outputs={k: f"{c.goal_id}:done" for k in c.expected_outputs})))
    return r


def demo_approval_workflow():
    print("=" * 66)
    print("Long-lived workflow: collect → WAIT for approval → finalize")
    print("=" * 66)

    goals = [
        Goal("collect", "collect the documents", required_capabilities=frozenset({"do"}),
             produced_memory=("documents",), expected_outputs=("documents",), priority=1),
        Goal("finalize", "finalize the deal", required_capabilities=frozenset({"do"}),
             dependencies=("collect",), assumptions=("approved",),
             required_memory=("documents", "approval"), produced_memory=("contract",),
             expected_outputs=("contract",), priority=2),
    ]
    # 'finalize' is gated by both an approval event AND the 'approved' assumption.
    ctx = AssumptionContext(
        AssumptionRegistry([PlanAssumption("approved", "deal approved", "authorization", mandatory=True)]),
        AssumptionDependencyGraph())
    ctx.registry.get("approved").transition(AssumptionState.INVALID, timestamp=0)

    memory = WorkingMemory()
    budget = RunBudget(RunBudgetLimits())
    engine = WorkflowEngine(_registry())
    wf = engine.create_workflow(
        "deal_42", StaticDecomposer().decompose("close_deal", goals), memory,
        assumption_context=ctx, run_budget=budget,
        wait_conditions=[WaitCondition("await_approval", "finalize", kind=WaitKind.WAIT_FOR_APPROVAL,
                                       event_type=EventType.APPROVAL_RECEIVED, match=(("deal", "42"),))],
    )

    engine.start(wf)
    print(f"\n  after start: status={wf.status}, current_goal={wf.current_goal}")
    print(f"  collect: {wf.tree.lookup('collect').status}   finalize: {wf.tree.lookup('finalize').status}")
    print(f"  budget handoffs while waiting: {budget.usage.handoffs} (collect only)")

    # A wrong event is ignored.
    engine.deliver(WorkflowEvent("noise", EventType.FILE_UPLOADED, {"file": "x.pdf"}, timestamp=1))
    print(f"\n  after a non-matching event: status={wf.status} "
          f"(budget handoffs still {budget.usage.handoffs})")

    # The approval arrives — it writes memory AND satisfies the assumption,
    # then execution resumes from preserved state.
    approval = WorkflowEvent(
        "appr_42", EventType.APPROVAL_RECEIVED, {"deal": "42"}, timestamp=2, source="cfo",
        memory_writes=[MemoryWrite("approval", "approved by CFO")],
        assumption_signals={"approved": AssumptionState.SATISFIED},
    )
    engine.deliver(approval)
    print(f"\n  after approval: status={wf.status}")
    print(f"  assumption 'approved': {ctx.registry.get('approved').state}")
    print(f"  finalize: {wf.tree.lookup('finalize').status}  (resumed — collect was NOT re-run)")
    print(f"  budget handoffs total: {budget.usage.handoffs} (one shared RunBudget)")
    print("\n" + format_working_memory(memory))
    print("\n" + format_workflow_trace(wf))


def demo_two_waiting_subtrees():
    print("\n" + "=" * 66)
    print("Only the affected subtree resumes")
    print("=" * 66)
    goals = [
        Goal("emea", "process EMEA region", required_capabilities=frozenset({"do"}), expected_outputs=("emea",), priority=1),
        Goal("apac", "process APAC region", required_capabilities=frozenset({"do"}), expected_outputs=("apac",), priority=2),
    ]
    engine = WorkflowEngine(_registry())
    wf = engine.create_workflow("rollout", StaticDecomposer().decompose("global_rollout", goals), WorkingMemory(),
                                wait_conditions=[WaitCondition("w_emea", "emea", event_type="emea_ready"),
                                                 WaitCondition("w_apac", "apac", event_type="apac_ready")])
    engine.start(wf)
    print(f"\n  waiting on: {[wc.condition_id for wc in wf.waiting_conditions]}")
    engine.deliver(WorkflowEvent("e1", "emea_ready", {}, timestamp=1))
    print(f"  after emea_ready: emea={wf.tree.lookup('emea').status}, "
          f"apac={wf.tree.lookup('apac').status}, workflow={wf.status}")
    engine.deliver(WorkflowEvent("e2", "apac_ready", {}, timestamp=2))
    print(f"  after apac_ready: apac={wf.tree.lookup('apac').status}, workflow={wf.status}")


def main():
    demo_approval_workflow()
    demo_two_waiting_subtrees()
    print(
        "\nKey properties demonstrated:\n"
        "  • Workflows suspend at wait conditions and consume no budget while waiting.\n"
        "  • Non-matching events are ignored; the workflow stays suspended.\n"
        "  • The matching event updates memory + assumptions, then resumes.\n"
        "  • Resume continues from preserved state — earlier work is not re-run.\n"
        "  • Only the subtree whose event arrived resumes; the rest keeps waiting.\n"
        "  • The same event sequence always produces the same workflow history."
    )


if __name__ == "__main__":
    main()
