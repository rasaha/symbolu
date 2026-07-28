# H21 — Deterministic Parallel Goal Execution

**Status:** implemented. Package `agentic.agentic_framework` `v1.21.0`.
**Module:** `agentic/agentic_framework/parallel_execution.py`
**Tests:** `agentic/agentic_framework/tests/test_parallel_execution.py` (26 tests)
**Example:** `python -m agentic.agentic_framework.examples_h21`

H21 introduces **bounded, deterministic, in-process parallel execution** for
independent governed goals inside one workflow. Where H15 runs a wave of READY
goals sequentially through the unchanged H16 `Coordinator`, H21 lets
*proven-independent* goals in a wave execute concurrently — without weakening any
governance, authority, budget, durability, or audit guarantee from H10–H19.

```
          ┌─ Goal A ─┐
READY ────┤          ├── Deterministic Join ── Commit
          └─ Goal B ─┘
```

## Architectural boundary

H21 is **purely additive**. It composes only on the public interfaces of
H10–H19 in this package and modifies none of them. New files only:

* `parallel_execution.py` (the phase)
* `tests/test_parallel_execution.py`
* `examples_h21.py`
* additive re-exports + version bump in `__init__.py`

It does **not** touch alternate control-plane / ActionGate / TAP
implementations, message buses, distributed schedulers, cloud orchestration, or
databases. The broader monorepo consolidation remains deferred.

### What it reuses (unchanged)

| Phase | Reused public surface |
|------|-----------------------|
| H11 `run_budget` | `RunBudget`, `RunBudgetLimits`, `Reservation`, `BudgetExhausted` — accessed only through `reserve()` / `record_usage()` / `remaining()`. |
| H13 `plan_validity` | `AssumptionContext`, `AssumptionState`, `PlanAssumption.transition()` (read + append-only transition). |
| H14 `working_memory` | `WorkingMemory` versioned reads (`peek().version`) and append-only `write()`. |
| H15 `hierarchical_planning` | `Goal`, `GoalTree`, `GoalStatus`, `GoalNode`, `MissionPlan`, `GoalTree.replace_leaf()` (localized replan). |
| H16 `coordination` | `CapabilityRegistry.candidates_for()`, `AuthorityModel.authorize()`, `DelegationContract`, `GoalOwnershipLedger`, `WorkerExecutor`, `WorkerResult`. |
| H18 `workflow_durability` | `canonical_json()`, `digest_of()`, `CheckpointConflict`, `RecoveryError` (fail-closed posture + store contract). |
| H19 review | `ReviewGate` seam, wireable to `HumanPolicyEngine` / `ApprovalStore` (H21 ships a deterministic `StaticReviewGate`). |
| R2 `cancellation` | `CancellationToken` (thread-safe cooperative cancellation). |

## Public API introduced

Scheduling & model: `ExecutionWave`, `ParallelGoalScheduler`,
`ConcurrencyPolicy`, `GoalExecutionFootprint`, `footprint_from_goal`,
`FootprintConflictDetector`, `GoalConcurrency`, `FailurePolicy`, `WaveStatus`.

Execution: `ParallelGoalContext`, `MemoryView`, `AssumptionView`,
`GoalExecutionResult`, `GoalOutcome`, `ProposedMemoryWrite`,
`ProposedAssumptionTransition`, `ParallelWorker`, `CoordinatedParallelWorker`,
`DispatchUnit`.

Budget: `SharedBudgetCoordinator`, `BudgetEstimate`, `BudgetLedgerEntry`,
`BudgetReservation`.

Join: `DeterministicJoiner`, `JoinReport`, `MemoryConflictPolicy`.

Backends: `ParallelExecutionBackend`, `SynchronousBackend`, `ThreadPoolBackend`.

Review: `ReviewGate`, `StaticReviewGate`.

Durability / recovery: `WaveCheckpoint`, `InMemoryWaveStore`,
`WaveRecoveryPlanner`, `InFlightStatus`, `SideEffectClass`.

Trace: `ParallelExecutionTrace`, `ParallelTraceEntry`, `ParallelEvent`.

Top-level: `ParallelHierarchyExecutor`, `ParallelHierarchyResult`,
`ParallelHierarchyStatus`, `derive_execution_state`.

## Execution-wave model

An `ExecutionWave` holds only goals that are READY at the same deterministic
scheduling boundary and are proven co-schedulable. Fields: `wave_id`,
`workflow_id`, `ordered_goal_ids`, `concurrency_limit`,
`created_logical_sequence`, `failure_policy`, `status`, `started/completed/
failed/cancelled/blocked/review_goal_ids`, `result_order`, and an append-only
`history`. Lifecycle:

```
CREATED → RESERVED → RUNNING → JOINING → COMPLETED | FAILED | CANCELLED | BLOCKED
```

## Scheduling algorithm (`ParallelGoalScheduler`)

1. Inspect the H15 goal tree; find READY leaves (deps COMPLETED, no dep FAILED,
   inherited assumptions valid) — mirrors H15 readiness, mutates no H15 policy.
2. Exclude blocked / waiting / terminal / executing goals.
3. Hold review-gated, uncleared goals (they don't block unrelated goals); a
   rejected review fails only that goal's subtree.
4. Order deterministically, then greedily select a compatible batch under the
   concurrency caps.

### Deterministic ordering (§7)

`(priority, hierarchy_depth, parent_goal_id, goal_id)`. No thread timing, no
object identity, no dict-iteration order, no wall clock, no randomness. Same
initial state → same wave membership and order.

### Concurrency classification (§10)

`PARALLEL_SAFE` may enter a parallel wave (if footprints are compatible);
`SERIAL_ONLY` runs alone; `EXCLUSIVE_GROUP` never overlaps another goal in the
same group; `UNKNOWN` defaults to **serial**. Parallel safety is **never**
inferred from the absence of a dependency edge — a goal must declare it.

### Footprint conflict model (§9)

Two goals co-schedule only if their `GoalExecutionFootprint`s are compatible.
`FootprintConflictDetector` rejects: same write key (write/write),
read-after-write hazards, assumption write vs read/write, shared owned
resource / exclusive goal ownership, shared exclusive execution group, and
policy-exclusive authority scopes. Conservative serialization always wins over
unsafe parallelism.

## Shared-budget reservation protocol (§11)

One shared H11 `RunBudget`, mediated by `SharedBudgetCoordinator` (a lock +
an H21-owned reservation pool):

```
Estimate → Reserve (before dispatch, all-or-nothing) →
Execute (against an isolated per-goal budget capped at the reservation) →
Reconcile actual usage into the shared budget → Release the reservation
```

* Reservations are measured against the shared budget's live headroom and held
  in an H21 pool, so they are fully reversible — H11's monotonic counters are
  mutated **only** at reconcile with *actual* usage. H11 semantics unchanged.
* A single lock serialises reserve + reconcile, so two workers can never observe
  the same remaining budget and overspend it.
* Because each worker runs against an isolated budget capped at its reservation,
  actual usage is always `≤` the estimate — the invariant that keeps the shared
  budget safe. A wave whose aggregate estimate exceeds the remaining budget is
  **not dispatched** (no unsafe partial dispatch).

## Worker isolation model (§13)

Each worker receives an immutable `ParallelGoalContext`: a `Goal` snapshot,
workflow/wave ids, the selected agent, its budget reservation + isolated budget,
a `MemoryView` (immutable read snapshot with the versions the joiner will check),
an `AssumptionView`, and a `CancellationToken`. Workers **never** mutate shared
joined state; they return a structured `GoalExecutionResult` (outcome, proposed
memory writes with `expected_version`, proposed assumption transitions, budget
usage, evidence, error, retry/replan recommendations, and a canonical
`result_digest`).

`CoordinatedParallelWorker` is the reference worker: it independently authorizes
the assignment through **H16** (`candidates_for` → `AuthorityModel.authorize`),
issues an immutable `DelegationContract`, runs the selected agent's H16
`WorkerExecutor` against the *isolated* snapshot + per-goal budget, and turns
declared outputs into **proposed** writes.

## Deterministic join (§15–§18)

`DeterministicJoiner` applies results in the wave's **original stable order**,
independent of completion timing:

1. Barrier check for contradictory assumption transitions across the wave.
2. Per goal (stable order): reconcile budget; validate the result digest
   (fail-closed); for memory writes, verify `expected_version ==` current
   version — on mismatch apply `MemoryConflictPolicy` (default **REJECT**, never
   silent last-writer-wins); apply verified assumption transitions via H13.
3. Commit memory + assumptions for clean successes; roll parents up.
4. **Dependency barrier:** a dependent goal becomes READY only after every
   predecessor is durably joined here — worker completion alone never releases
   it (`DEPENDENCY_BARRIER_RELEASED` is emitted at join, not at completion).

### Memory & assumption conflict handling (§16, §17)

Memory version conflicts fail closed (REJECT) unless an explicit MERGE/replan
policy is configured. Contradictory assumption transitions
(`A: SATISFIED` vs `B: INVALIDATED`) are detected before applying any of them;
no timing winner is chosen — an `ASSUMPTION_TRANSITION_CONFLICT` is raised and
the smallest affected subtree is blocked/replanned.

## Cancellation model (§20)

Cooperative, via the thread-safe `CancellationToken`. Sources are enumerated in
`CancellationSource` (mission, workflow, wave failure policy, human, budget,
assumption invalidation, dependency failure). Cancellation is explicit,
traceable (`GOAL_CANCEL_REQUESTED`), idempotent, scoped to the wave, and
checkpointed. Workers observe it at defined safe points (before dispatch and at
the worker seam). Failure policies (`FAIL_FAST`, `COMPLETE_IN_FLIGHT`,
`ISOLATE_FAILURE` (default), `REPLAN_AFFECTED`) are enforced by an internal
guard and recorded on the wave.

## Human-governance integration (§21, §22)

A review-gated goal is held (`WAITING_FOR_REVIEW`) without blocking unrelated
parallel-safe goals; its dependents stay blocked by the barrier. `ReviewGate`
is the seam (deterministic `StaticReviewGate` shipped; wireable to H19).
`derive_execution_state()` is an **H21-owned derived view** over the goal tree —
it reports mixed branch states (running / ready / blocked / waiting-review /
completed / failed) without forcing an H17 `WorkflowInstance` globally into
WAITING, and without modifying H17.

## Checkpoint & recovery (§23, §24)

`WaveCheckpoint` captures the active wave, ordered goal list, concurrency policy,
reservations, dispatched goals, results-not-joined, joined goals, memory + 
assumption versions, cancellation state, logical sequence, and trace. It is
serialised with H18's public `canonical_json` / `digest_of` and validated
fail-closed (digest + invariants). `InMemoryWaveStore` mirrors H18's
`compare_and_save` / `CheckpointConflict` optimistic-concurrency contract, making
duplicate recovery idempotent. `WaveRecoveryPlanner` classifies dispatched goals:

| Class | Recovery rule |
|------|---------------|
| `NOT_STARTED` | safe to dispatch |
| `STARTED_NO_RESULT` | never auto-replayed unless `allow_deterministic_replay` **and** the goal is PURE/DETERMINISTIC (fail-closed) |
| `RESULT_AVAILABLE_NOT_JOINED` | join without re-executing |
| `JOINED` | never re-executed |

## Trace model (§25)

`ParallelExecutionTrace` is append-only with **logical sequence numbers**
(never wall-clock). Events: `WAVE_CREATED`, `GOAL_SELECTED_FOR_WAVE`,
`GOAL_HELD_FOR_REVIEW`, `BUDGET_RESERVED`/`BUDGET_DENIED`, `GOAL_DISPATCHED`,
`GOAL_RESULT_PRODUCED`, `GOAL_CANCEL_REQUESTED`, `GOAL_RESULT_JOINED`,
`MEMORY_CONFLICT_DETECTED`, `ASSUMPTION_CONFLICT_DETECTED`,
`DEPENDENCY_BARRIER_RELEASED`, `BUDGET_RECONCILED`, `WAVE_COMPLETED`,
`WAVE_FAILED`, `WAVE_RECOVERED`.

## Deterministic equivalence (§27)

For deterministic workers, running the same mission through the
`SynchronousBackend` (baseline) and the `ThreadPoolBackend` (concurrent) yields
identical committed state: final goal statuses, memory records + versions,
assumption states, cumulative deterministic budget counters, hierarchy outcome,
and the logical trace after canonical ordering. Wall-clock elapsed time is not
required to match. This is proven by `test_22_sequential_parallel_equivalence`.

## Test evidence (24 required scenarios)

All in `tests/test_parallel_execution.py`:

| # | Scenario | Test |
|---|----------|------|
| 1 | Independent parallel execution | `test_1_independent_parallel_execution` |
| 2 | Dependency barrier | `test_2_dependency_barrier` |
| 3 | Stable scheduling | `test_3_stable_scheduling` |
| 4 | Completion-order independence | `test_4_completion_order_independence` |
| 5 | Concurrency limit | `test_5_concurrency_limit` |
| 6 | Shared budget reservation (no oversubscription) | `test_6_shared_budget_no_oversubscription` |
| 7 | Budget exhaustion → no partial dispatch | `test_7_budget_exhaustion_no_partial_dispatch` |
| 8 | Memory conflict detected | `test_8_memory_conflict_detected` |
| 9 | Assumption conflict — no race winner | `test_9_assumption_conflict_no_winner` |
| 10 | Serial-only goal runs alone | `test_10_serial_only_executes_alone` |
| 11 | Exclusive group never overlaps | `test_11_exclusive_group` |
| 12 | Per-agent concurrency limit | `test_12_per_agent_concurrency_limit` |
| 13 | Authority enforced per worker | `test_13_authority_enforced_per_worker` |
| 14 | Isolated failure | `test_14_isolated_failure` |
| 15 | Fail-fast cancellation | `test_15_fail_fast_cancellation` |
| 16 | Localized replanning | `test_16_localized_replanning` |
| 17 | Human-review coexistence (+ rejection subtree) | `test_17_human_review_coexistence`, `test_17b_...` |
| 18 | Checkpoint classifies in-flight | `test_18_checkpoint_classifies_inflight` |
| 19 | Result-available-not-joined joins without re-exec | `test_19_result_available_not_joined_joins_without_reexec` |
| 20 | Joined goal never re-executed | `test_20_joined_goal_never_reexecuted` |
| 21 | Duplicate recovery idempotent (+ corrupt fail-closed) | `test_21_duplicate_recovery_idempotent`, `test_21b_...` |
| 22 | Sequential–parallel equivalence | `test_22_sequential_parallel_equivalence` |
| 23 | Trace reconstruction | `test_23_trace_reconstruction` |
| 24 | Regression (H10–H19 unchanged) | full-suite run (below) |

**Regression:** the full `agentic/agentic_framework/tests/` suite has an
identical failure set with and without H21 — baseline **16 failed / 2103
passed**, with H21 **16 failed / 2129 passed** (the 26 new passes are H21).
Incremental H21-caused failures: **0**. The 16 pre-existing failures are an
environment gap (`pytest-asyncio` not installed; unrelated async scheduler /
entropy-hookup tests) and are independent of H21.

## Known limitations

* Concurrency is bounded and **in-process** (threads). No distributed or
  multi-process execution, no cluster scheduling, no cross-machine fault
  tolerance — out of scope by design.
* Determinism guarantees hold for **deterministic** workers; workers with
  external, non-reproducible side effects are outside the equivalence claim and
  should be classified `SideEffectClass.EXTERNAL` (never auto-replayed).
* No exactly-once guarantee for external side effects; H20 external-action
  execution is out of scope.
* A wave whose aggregate budget estimate does not fit the remaining budget is
  blocked wholesale (conservative) rather than shrunk to a fitting prefix.

## H22 preparation

H21 exposes stable public interfaces (`ParallelHierarchyExecutor` and the types
above) that H22 can package and freeze. H22 (runtime wrap-up: unified façade,
end-to-end reference scenarios, config, docs, API-stability freeze) is **not**
implemented here.
