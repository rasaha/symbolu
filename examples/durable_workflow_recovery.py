#!/usr/bin/env python3
"""
Durable Workflow State, Checkpointing & Recovery (H18)
======================================================

Deterministic LOCAL durability for the H17 event-driven runtime: a waiting
workflow is checkpointed, the original runtime is destroyed, and the workflow
restores into a brand-new runtime and completes as though nothing happened.

    Mission → Execute → WAIT → Checkpoint → (process lost) → Restore
           → Event → Resume → Complete

Demonstrates:

  1. Process-loss recovery: suspend, checkpoint, destroy runtime, restore,
     deliver the event, complete — without re-running completed work.
  2. Cross-restart idempotency: the same event delivered again is ignored.
  3. Corruption + conflict protection fail closed.

This is local deterministic durability — NOT a distributed workflow service,
and not exactly-once external execution.

No API key, no GPU — deterministic scripted workers, filesystem-backed store.

Run:
    python examples/durable_workflow_recovery.py
"""

import dataclasses
import tempfile

from agentic.agentic_framework import (
    WorkingMemory,
    MemoryWrite,
    RunBudget,
    RunBudgetLimits,
    AgentProfile,
    CapabilityRegistry,
    ScriptedWorker,
    WorkerResult,
    Goal,
    GoalStatus,
    StaticDecomposer,
    WaitCondition,
    WaitKind,
    WorkflowEvent,
    WorkflowStatus,
    EventType,
    DurableWorkflowEngine,
    FileCheckpointStore,
    CheckpointIntegrityValidator,
    RecoveryError,
    EventOutcome,
    format_recovery_trace,
)


def _registry():
    r = CapabilityRegistry()
    r.register(AgentProfile("ops", capabilities=frozenset({"do"}), trust_level=5),
               ScriptedWorker(lambda c, m: WorkerResult(success=True, outputs={k: f"{c.goal_id}:done" for k in c.expected_outputs})))
    return r


def _goals():
    return [
        Goal("collect", "collect the paperwork", required_capabilities=frozenset({"do"}),
             produced_memory=("paperwork",), expected_outputs=("paperwork",), priority=1),
        Goal("finalize", "finalize the contract", required_capabilities=frozenset({"do"}),
             dependencies=("collect",), required_memory=("paperwork", "signature"),
             produced_memory=("contract",), expected_outputs=("contract",), priority=2),
    ]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        store = FileCheckpointStore(tmp)

        print("=" * 66)
        print("Runtime #1: run to the wait, then checkpoint")
        print("=" * 66)
        budget = RunBudget(RunBudgetLimits())
        engine1 = DurableWorkflowEngine(_registry(), store)
        wf = engine1.create_workflow(
            "contract_7", StaticDecomposer().decompose("close_contract", _goals()), WorkingMemory(),
            run_budget=budget,
            wait_conditions=[WaitCondition("await_signature", "finalize", kind=WaitKind.WAIT_FOR_EVENT,
                                           event_type="signature_received", match=(("contract", "7"),))],
        )
        print(f"\n  status: {wf.status}")
        print(f"  collect: {wf.tree.lookup('collect').status}  (done before the wait)")
        print(f"  budget handoffs at wait: {budget.usage.handoffs}")
        latest = store.latest_id("contract_7")
        print(f"  durable checkpoint on disk: {latest}")

        # Corruption is rejected before it is ever trusted.
        cp = store.load_latest("contract_7")
        tampered = dataclasses.replace(cp, workflow_id="HACKED")
        try:
            CheckpointIntegrityValidator().validate(tampered)
        except RecoveryError as exc:
            print(f"  tampered checkpoint rejected: {exc.code}")

        print("\n" + "=" * 66)
        print("Runtime #1 destroyed — only the checkpoint files remain")
        print("=" * 66)
        del engine1, wf, budget

        print("\n" + "=" * 66)
        print("Runtime #2: restore from disk and resume")
        print("=" * 66)
        engine2, wf2 = DurableWorkflowEngine.restore(store, "contract_7", registry=_registry())
        print(f"\n  restored status: {wf2.status}")
        print(f"  collect (preserved): {wf2.tree.lookup('collect').status}")
        print(f"  budget handoffs (preserved): {wf2.run_budget.usage.handoffs}")

        # The signature arrives — writes memory, then execution resumes.
        signature = WorkflowEvent("sig_7", "signature_received", {"contract": "7"}, timestamp=5,
                                  source="notary", memory_writes=[MemoryWrite("signature", "notarized")])
        result = engine2.deliver(wf2, signature)
        print(f"\n  event outcome: {result.outcome}")
        print(f"  status: {wf2.status}")
        print(f"  finalize: {wf2.tree.lookup('finalize').status}  (collect was NOT re-run)")
        print(f"  budget handoffs total: {wf2.run_budget.usage.handoffs}")

        # The same event again is ignored (cross-restart idempotency).
        dup = engine2.deliver(wf2, WorkflowEvent("sig_7", "signature_received", {"contract": "7"}, timestamp=6))
        print(f"\n  duplicate delivery outcome: {dup.outcome}")

        print("\n" + format_recovery_trace(wf2))

    print(
        "\nKey properties demonstrated:\n"
        "  • A waiting workflow was checkpointed, the runtime destroyed, and the\n"
        "    workflow restored into a NEW runtime with no hidden state.\n"
        "  • Completed work was preserved and not re-executed.\n"
        "  • The cumulative RunBudget, memory, and status were preserved exactly.\n"
        "  • The re-delivered event was ignored (idempotent across restart).\n"
        "  • A tampered checkpoint was rejected deterministically.\n"
        "  • One trace reconstructs the whole lifecycle across the restart."
    )


if __name__ == "__main__":
    main()
