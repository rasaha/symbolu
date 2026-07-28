# Durable Workflow State, Checkpointing & Recovery (H18)

Adds **deterministic, local** durability to the H17 event-driven workflow
runtime. A waiting workflow can serialize its complete recoverable state,
survive destruction of the runtime process, restore into a new runtime, reject
duplicate events, and resume from the exact prior point with an equivalent
outcome and a single reconstructable history.

```
Mission → Execute → WAIT → Checkpoint → (process destroyed) → Restore
       → Event → Resume → Complete
```

> **Scope statement.** H18 adds **deterministic local workflow durability,
> checkpointing, and recovery**. It is **not** a distributed workflow service.
> It does not provide distributed durability, exactly-once external execution,
> or production-grade fault tolerance. It is not Kafka, queues, cloud
> databases, webhooks, leader election, or consensus. The reference store is
> in-memory or filesystem-backed.

H18 owns **persistence, restoration, idempotency, and recovery only**. It does
not modify H10–H17 or any governance layer — it composes on their public APIs
and serializes their state through the accessors they already expose.

---

## Checkpoint architecture

A **`WorkflowCheckpoint`** is an immutable, self-describing durable snapshot.
Its `body` holds the full recoverable state — enough to restore the workflow
with **no hidden runtime state**:

| Area | Contents |
|------|----------|
| framing | `checkpoint_id`, `workflow_id`, `checkpoint_sequence`, `schema_version`, `logical_sequence`, `created_at`, `parent_checkpoint_id`, `integrity_digest`, `recovery_metadata` |
| workflow | `workflow_status`, `current_goal`, active + satisfied wait conditions, `wait_by_goal`, workflow history, workflow trace, `wave` |
| planning (H15) | `mission_id`, full `goal_tree` (nodes + statuses + append-only histories + assigned agents + roots) |
| memory (H14) | all records, versions, statuses, producing/consuming steps, expiration, status history, operation log |
| assumptions (H13) | declarations, states, append-only transition histories, dependency graph, trace |
| budget (H11) | limits, all counters, status, termination reason, violations |
| coordination (H16) | per-goal assigned agent + in-flight recovery status |
| idempotency | processed event IDs |

---

## Canonical serialization

`canonical_json(...)` produces deterministic content: stable key ordering,
sets → sorted lists, tuples → lists, explicit enum/timestamp encoding, no object
addresses, **no pickle**, no executable code, no provider/adapter objects. The
same workflow state produces byte-identical canonical JSON. `digest_of(...)` is
the SHA-256 over that canonical content (excluding the digest field).

---

## Storage abstraction

`CheckpointStore` is strategy-agnostic and contains **no workflow logic**:
`save`, `load`, `load_latest`, `list_checkpoints`, `latest_id`,
`compare_and_save`, `mark_superseded`, `verify_integrity`. Two references ship:

- **`InMemoryCheckpointStore`** — deterministic, process-local.
- **`FileCheckpointStore`** — canonical JSON files under
  `<root>/<workflow_id>/<seq>-<id>.json` plus a `LATEST` pointer. No pickle.

---

## Checkpoint boundaries

Checkpoints are created at deterministic recovery boundaries: **after workflow
creation and reaching WAIT/terminal** (`create_workflow`), **after accepted
event effects are applied and before caller acknowledgment** (`deliver`, the
post-event checkpoint), **after completion / failure**, and on demand via
`checkpoint()`. The durable state is never advanced past an uncommitted event —
partially-mutated in-memory state is never persisted.

---

## Restoration sequence (`WorkflowRestorer` / `DurableWorkflowEngine.restore`)

1. Load the selected checkpoint (latest by default).
2. Validate schema version and integrity digest.
3. Validate cross-component invariants (identity, sequences, goal-tree acyclicity, nonnegative budget).
4. Reconstruct the `MissionPlan` + `GoalTree` (statuses + histories).
5. Restore `WorkingMemory` (records, versions, operation log).
6. Restore assumptions (states + transition histories + graph).
7. Restore the cumulative `RunBudget`.
8. Restore wait conditions, satisfied set, and processed event IDs.
9. Restore the workflow trace and logical sequence.
10. **Rebind live runtime dependencies** — capability registry, coordinator
    (a fresh H16 `Coordinator` per advance), replanner, authority. Checkpoints
    store durable state, never live service objects. A missing dependency fails
    with `RECOVERY_DEPENDENCY_UNAVAILABLE`.
11. Apply the in-flight recovery policy, then return a runnable
    `WorkflowInstance`.

Completed goals are **not replayed** to reconstruct state — their status and
outputs are restored directly.

---

## Event idempotency

Every accepted event is idempotent by `event_id`. The first delivery is
`EVENT_APPLIED`; a repeat is `DUPLICATE_EVENT_IGNORED`. A duplicate does not
create another memory version, repeat an assumption transition, re-satisfy the
wait, increment counters, resume again, or invoke workers. Processed event IDs
are **persisted in the checkpoint**, so deduplication survives restart.

---

## Atomic event processing

Event processing is one logical transaction, recorded in an append-only
`RecoveryJournal` (`PREPARED → APPLIED → COMMITTED | ABORTED`). The H17
`deliver` (validate → memory → assumptions → wait → resume) is the atomic
effect-application unit; the transaction commits only when the post-event
checkpoint is durably saved. If a fault occurs before commit, the transaction
is `ABORTED`, the durable latest checkpoint is unchanged, and the event is not
in the persisted processed-set. Restoration therefore yields one of two valid
outcomes: the event **was not applied and may be safely retried**, or it **was
fully applied and future delivery is a duplicate**. The runtime never restores
into a partially-applied event state.

---

## Optimistic concurrency (compare-and-save)

`compare_and_save(checkpoint, expected_latest_id=...)` saves only if the store's
current latest matches the expected parent. Two stale restored instances writing
a successor from the same parent cannot both win — the loser fails with
`CHECKPOINT_CONFLICT`. Newer state is never silently overwritten.

---

## Corruption detection

Loading validates the integrity digest, required fields, schema version, parent
linkage, monotonic sequences, workflow identity, goal-tree acyclicity, and
nonnegative budget counters. Corrupt or inconsistent checkpoints **fail closed**
with deterministic errors — `CHECKPOINT_CORRUPT`, `CHECKPOINT_SCHEMA_UNSUPPORTED`,
`CHECKPOINT_INVARIANT_VIOLATION`. There is **no silent repair**.

---

## In-flight work recovery

Per-leaf in-flight status is captured: `NOT_STARTED`, `STARTED_NO_RESULT`,
`RESULT_RECORDED`, `OUTPUT_COMMITTED`. Because checkpoints are taken at
recovery boundaries (WAIT / after committed event), the normal states are
`OUTPUT_COMMITTED` (completed) or `NOT_STARTED`. If a checkpoint captured an
`EXECUTING` goal with no durable result (`STARTED_NO_RESULT`), the restorer
does **not** auto-replay it — it transitions the goal to `BLOCKED` with reason
`REQUIRES_RECONCILIATION`, requiring an external completion event. The runtime
never assumes an interrupted external action succeeded or failed without durable
evidence.

---

## Interaction with H11–H17

- **H11 RunBudget** — the exact cumulative counters (model/tool calls, handoffs,
  iterations, tokens, cost), limits, status, and violations are restored;
  recovery never resets or increases available budget. Suspended wall-clock
  `elapsed_time` is not counted (consistent with H11's "waiting is free"); on
  restore `_start_time` is cleared and `elapsed_time` is preserved as a
  monotonic floor. H18 does not redefine H11 behavior.
- **H14 WorkingMemory** — records, versions, and the operation log are restored
  verbatim; the next `write` continues version numbering with no duplicates.
- **H13 assumptions** — states and append-only histories are identical across
  restore, so post-recovery evaluation matches.
- **H15 hierarchy** — completed / blocked / waiting / aborted-and-replaced goals
  and their histories are restored; only the waiting subtree resumes; completed
  goals do not run again.
- **H16 coordination** — used unchanged after recovery; it assigns post-recovery
  work normally.
- **H17 workflow semantics** — suspend/resume, event routing, and subtree
  resume behave exactly as before; H18 wraps them with durability.

---

## Trace and logical time

Two concepts: operational timestamps (observability) and monotonic logical
sequence numbers (deterministic reconstruction). A restored workflow **continues
the prior trace** rather than starting a new one:

```
STARTED → WAVE → WAIT → CHECKPOINTED → RESTORED → EVENT → RESUMED → WAVE → COMPLETED
```

`format_recovery_trace(wf)` renders it; `WorkflowCheckpoint.to_dict()` and the
`RecoveryJournal` serialize the durable record.

---

## Known limitations

- Local and deterministic only — no distributed durability, exactly-once
  external effects, or production fault tolerance.
- Memory record values must be JSON-serializable (canonical JSON).
- The atomic unit is the whole H17 `deliver`; fine-grained mid-`deliver`
  rollback is achieved by only committing (checkpointing) after it succeeds, not
  by partial undo.
- Fault injection (`FaultInjector`) is a test facility, not a production
  supervisor.

---

## Quickstart

```python
from agentic.agentic_framework import (
    WorkingMemory, RunBudget, RunBudgetLimits,
    AgentProfile, CapabilityRegistry, ScriptedWorker, WorkerResult,
    Goal, StaticDecomposer, WaitCondition, WorkflowEvent, EventType,
    DurableWorkflowEngine, FileCheckpointStore,
)

registry = CapabilityRegistry()
registry.register(AgentProfile("ops", capabilities=frozenset({"do"}), trust_level=5),
                  ScriptedWorker(lambda c, m: WorkerResult(success=True, outputs={k: "ok" for k in c.expected_outputs})))

store = FileCheckpointStore("/tmp/wf_checkpoints")
plan = StaticDecomposer().decompose("m", [
    Goal("collect", "collect", required_capabilities=frozenset({"do"}), expected_outputs=("data",), priority=1),
    Goal("finalize", "finalize", required_capabilities=frozenset({"do"}), dependencies=("collect",), expected_outputs=("result",), priority=2),
])

# Runtime #1
engine = DurableWorkflowEngine(registry, store)
engine.create_workflow("wf", plan, WorkingMemory(), run_budget=RunBudget(RunBudgetLimits()),
                       wait_conditions=[WaitCondition("w", "finalize", event_type=EventType.APPROVAL_RECEIVED, match=(("doc", "D1"),))])
# ... process dies ...

# Runtime #2
engine2, wf = DurableWorkflowEngine.restore(store, "wf", registry=registry)
engine2.deliver(wf, WorkflowEvent("e1", EventType.APPROVAL_RECEIVED, {"doc": "D1"}, timestamp=2))
print(wf.status)  # COMPLETED
```

See [`examples/durable_workflow_recovery.py`](../../examples/durable_workflow_recovery.py)
— checkpoint, destroy runtime, restore from disk, resume, cross-restart
idempotency, and corruption rejection, with scripted workers and no API key.
