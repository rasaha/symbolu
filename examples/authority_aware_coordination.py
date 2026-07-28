#!/usr/bin/env python3
"""
Authority-Aware Multi-Agent Coordination (H16)
==============================================

A deterministic coordinator assigns mission goals to worker agents through
explicit capability, authority, and immutable delegation contracts — while
every agent shares ONE governed WorkingMemory (H14) and ONE RunBudget (H11).

Demonstrates:

  1. Capability-based selection: the qualified agent is chosen deterministically.
  2. Authority enforcement: a delegation is rejected when the agent lacks the
     required permission.
  3. Worker-failure recovery: the coordinator falls back to another qualified
     agent without corrupting shared memory.
  4. Shared state + budget: workers hand results through one WorkingMemory and
     consume one RunBudget.
  5. Full reconstruction: every delegation, ownership transfer, and decision is
     traceable.

No API key, no GPU — deterministic scripted workers (plus one real governed
AgentWorker).

Run:
    python examples/authority_aware_coordination.py
"""

from agentic.agentic_framework import (
    build_agent,
    MockLLMAdapter,
    RunBudget,
    RunBudgetLimits,
    WorkingMemory,
    AgentProfile,
    CapabilityRegistry,
    CoordinationGoal,
    Mission,
    Coordinator,
    ScriptedWorker,
    AgentWorker,
    WorkerResult,
    MissionStatus,
    format_coordination_trace,
    format_working_memory,
)
from agentic.agentic_framework.safety_contract import (
    SafetyGate,
    SafetyContractEvaluator,
)


def _profile(aid, caps, *, perms=frozenset(), trust=0, role=""):
    return AgentProfile(agent_id=aid, role=role or aid,
                        capabilities=frozenset(caps), permissions=frozenset(perms),
                        trust_level=trust)


def _agent():
    a = build_agent(adapter=MockLLMAdapter(default_response="report drafted"),
                    use_llm_for_decomposition=False, max_revisions=0)
    a.safety_gate = SafetyGate(SafetyContractEvaluator(0.0, 0.0, 1.0, 0.0))
    return a


def demo_capability_and_authority():
    print("=" * 66)
    print("Capability selection + authority enforcement + recovery")
    print("=" * 66)

    registry = CapabilityRegistry()
    # A research team: a senior researcher (higher trust) and a junior one.
    registry.register(_profile("senior_researcher", {"search", "summarize"}, trust=9),
                      ScriptedWorker(WorkerResult(success=True, outputs={"findings": "market is growing"})))
    registry.register(_profile("junior_researcher", {"search"}, trust=2),
                      ScriptedWorker(WorkerResult(success=True, outputs={"findings": "market is growing"})))
    # A writer with PII authority; and a real governed agent that invokes tools.
    registry.register(_profile("compliance_writer", {"write"}, perms={"pii_access"}, trust=5),
                      ScriptedWorker(WorkerResult(success=True, outputs={"report": "compliant report.pdf"})))
    registry.register(_profile("executor", {"invoke"}, trust=3), AgentWorker(_agent()))

    mission = Mission.of("quarterly_report", [
        CoordinationGoal("research", "research the market",
                         required_capabilities=frozenset({"search", "summarize"}),
                         expected_outputs=("findings",)),
        CoordinationGoal("write", "write a PII-compliant report",
                         required_capabilities=frozenset({"write"}),
                         authority_scope=frozenset({"pii_access"}),
                         required_memory=("findings",), expected_outputs=("report",)),
        CoordinationGoal("publish", "publish the report",
                         required_capabilities=frozenset({"invoke"}),
                         required_memory=("report",), expected_outputs=("receipt",)),
    ])

    memory = WorkingMemory()
    budget = RunBudget(RunBudgetLimits())
    result = Coordinator(registry, memory, run_budget=budget).run(mission)

    print(f"\n  mission status: {result.status}")
    print(f"  assignments:")
    for g in ("research", "write", "publish"):
        a = result.assignment_for(g)
        print(f"    {g:<8} → {a.agent_id if a else '(none)'}  [{a.state if a else '-'}]")
    print(f"\n  budget: handoffs={budget.usage.handoffs}, model_calls={budget.usage.model_calls} "
          "(one shared RunBudget across all agents)")
    print("\n" + format_coordination_trace(result))
    print("\n" + format_working_memory(memory))


def demo_authority_rejection():
    print("\n" + "=" * 66)
    print("Delegation rejected — required authority not held")
    print("=" * 66)
    registry = CapabilityRegistry()
    # The only 'write'-capable agent lacks pii_access.
    registry.register(_profile("plain_writer", {"write"}, perms=frozenset()),
                      ScriptedWorker(WorkerResult(success=True, outputs={"report": "x"})))
    mission = Mission.of("m", [CoordinationGoal(
        "write", "write PII report", required_capabilities=frozenset({"write"}),
        authority_scope=frozenset({"pii_access"}), expected_outputs=("report",))])
    result = Coordinator(registry, WorkingMemory()).run(mission)
    print(f"\n  status: {result.status}")
    for rej in result.trace.entries[0].rejections:
        print(f"  rejected {rej['agent_id']}: {rej['reason']} — {rej['detail']}")


def demo_worker_failure_recovery():
    print("\n" + "=" * 66)
    print("Worker failure recovery (shared memory not corrupted)")
    print("=" * 66)
    registry = CapabilityRegistry()
    registry.register(_profile("primary", {"analyze"}, trust=9),
                      ScriptedWorker(WorkerResult(success=False, outputs={"score": 999}, detail="model crashed")))
    registry.register(_profile("backup", {"analyze"}, trust=1),
                      ScriptedWorker(WorkerResult(success=True, outputs={"score": 0.42})))
    memory = WorkingMemory()
    mission = Mission.of("m", [CoordinationGoal(
        "assess", "assess risk", required_capabilities=frozenset({"analyze"}), expected_outputs=("score",))])
    result = Coordinator(registry, memory).run(mission)
    print(f"\n  status: {result.status}")
    print(f"  final agent: {result.assignment_for('assess').agent_id}")
    print(f"  score in memory: {memory.peek('score').value}")
    print(f"  memory versions of 'score': {[r.value for r in memory.records('score')]} "
          "(the failed worker's 999 was never committed)")


def main():
    demo_capability_and_authority()
    demo_authority_rejection()
    demo_worker_failure_recovery()
    print(
        "\nKey properties demonstrated:\n"
        "  • The coordinator selects agents by capability + authority, "
        "deterministically.\n"
        "  • Unauthorized delegations are rejected with explicit reasons.\n"
        "  • The coordinator never executes worker tasks — it delegates and "
        "recovers.\n"
        "  • Every goal has one owner; ownership transfers are reconstructable.\n"
        "  • All agents share one WorkingMemory and one RunBudget."
    )


if __name__ == "__main__":
    main()
