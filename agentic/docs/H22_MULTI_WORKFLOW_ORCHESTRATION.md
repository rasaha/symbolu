# H22 — Multi-Workflow Orchestration

**Status:** implemented. Package `agentic.agentic_framework` `v1.22.0`.
**Module:** `agentic/agentic_framework/multi_workflow_orchestration.py`
**Tests:** `agentic/agentic_framework/tests/test_multi_workflow_orchestration.py` (43 tests)
**Examples:** `python -m agentic.agentic_framework.examples_h22` (Scenarios A–F)

H22 introduces **deterministic, bounded multi-workflow orchestration** over the
existing governed workflow runtime.

> **H21 governs parallelism *within* a workflow. H22 governs scheduling,
> dependencies, budgets, and resource contention *across* workflows.**
> H20 governed external actions remain deferred and are outside H22.

```
Portfolio Scheduler
        ↓
┌──────────────────────────────┐
│ Workflow A  (H21 waves)      │
│ Workflow B  (H21 waves)      │
│ Workflow C  (H21 waves)      │
└──────────────────────────────┘
```

## Architecture summary

A `WorkflowPortfolio` aggregates registered workflows plus shared state
(dependency graph, resource ledger, one shared budget, output registry,
trace). A `PortfolioScheduler` advances the portfolio in deterministic
*rounds*: evaluate dependencies → classify readiness → order eligible
workflows by effective priority (with aging) and fairness → reserve portfolio
budget → acquire resources atomically → grant each selected workflow one
*quantum* (one committed H21 wave, via the unchanged
`ParallelHierarchyExecutor`) → reconcile usage → checkpoint. The scheduler
never executes goals directly — it advances workflows through their public
H17/H21 interfaces. H21 stays authoritative for intra-workflow parallelism;
H19 stays authoritative for human governance.

## Architectural boundary — composed, not modified

H22 composes only on the public APIs of H11 `RunBudget`, H14 `WorkingMemory`,
H15 planning, H16 authority/ownership, H17 workflows, H18 durability, H19 human
governance, and H21 parallel execution. It modifies none of them. It implements
no H20 external actions, no distributed queues, no cluster scheduling, no
production database locking, no cross-machine execution, and does no
repository-wide restructuring.

The per-workflow quantum reuses H21 directly: `H21WorkflowController` wraps a
`ParallelHierarchyExecutor(max_waves=1)` and calls `run()` once per quantum —
one committed wave per call — reading precise progress from the result and the
goal tree. Committed work is never repeated.

### Files added / modified

* `multi_workflow_orchestration.py` (new — the phase)
* `tests/test_multi_workflow_orchestration.py` (new — 43 tests)
* `examples_h22.py` (new — Scenarios A–F)
* `docs/H22_MULTI_WORKFLOW_ORCHESTRATION.md` (new)
* `__init__.py` (additive re-exports; version `1.21.0 → 1.22.0`)

H10–H19 and H21 code is unchanged: the only edits outside the new files are the
additive export block and the version bump.

## Public API introduced

Aggregate & registration: `WorkflowPortfolio`, `PortfolioWorkflowEntry`,
`PortfolioStatus`, `PortfolioWorkflowStatus`, `WorkflowPriority`,
`priority_rank`.

Scheduling: `PortfolioScheduler`, `PortfolioResult`,
`PortfolioConcurrencyPolicy`, `SchedulingPolicy`.

Dependencies: `WorkflowDependency`, `DependencyGraph`, `DependencyType`,
`DependencyFailurePolicy`.

Resources: `WorkflowResourceClaim`, `ResourceLedger`, `ResourceAccessMode`,
`DeadlockPolicy`.

Budget: `PortfolioBudgetCoordinator`, `BudgetAllocationPolicy`.

Outputs: `WorkflowOutputRef`.

Workflow controller seam: `WorkflowController`, `H21WorkflowController`,
`QuantumResult`.

Cancellation / failure: `CancellationScope`, `PauseState`,
`PortfolioFailurePolicy`.

Durability / recovery: `PortfolioCheckpoint`, `InMemoryPortfolioStore`,
`InFlightWorkflowStatus`.

Trace: `PortfolioTrace`, `PortfolioTraceEntry`, `PortfolioEvent`.

## Portfolio aggregate (§4)

`WorkflowPortfolio` holds: portfolio id + scope, status
(`CREATED→ACTIVE→PAUSED→COMPLETED|FAILED|CANCELLED`), workflow registrations
(deterministic, append-only, idempotent), priorities, the shared
`PortfolioBudgetCoordinator`, the `ResourceLedger`, the `DependencyGraph`,
scheduling + concurrency policy, cancellation state, the `PortfolioTrace`, the
current round, and lifecycle history. A portfolio is complete only when every
non-cancelled workflow reaches an allowed terminal state.

## Workflow-registration model (§5)

`PortfolioWorkflowEntry` records id, controller reference, priority, weight,
registration sequence, orchestration status, budget estimate + max allocation,
resource claims, authority scope, assigned agent, resource class, cancellation
policy, durable `output_keys` / `milestone_keys` / `review_decisions`, and
runtime bookkeeping (age, deficit, pause state, cancel reason). Registration is
append-only; re-registering the same id returns the existing entry.

## Scheduling algorithm (§7) & deterministic ordering (§8)

Each round: classify every workflow → collect the eligible (`READY`) set →
order by the stable key

```
(effective_priority, dependency_depth, -fairness_deficit, registration_sequence, workflow_id)
```

→ select up to the concurrency limit (respecting per-agent / per-scope /
per-resource-class caps) → grant each a quantum. No thread order, wall clock,
dict iteration, object identity, or randomness is used. Identical portfolio
state + configuration + workflow results + human decisions ⇒ identical
selection order (proven by `test_3`).

## Priority & aging model (§9, §10)

Five classes (`CRITICAL…BACKGROUND`) map to numeric ranks spaced by 100 (lower
= preferred). `effective_rank = base_rank − min(age, aging_cap)`, floored at 1
for non-critical classes; **CRITICAL never ages** (stays absolute). Aging is
driven by logical rounds: a *runnable-but-not-selected* workflow ages by a
bounded increment; selected workflows reset; **waiting / blocked / review
workflows do not accrue runnable age** (`test_8`). Aging prevents starvation
(`test_7`) without overriding hard constraints or letting a lower class reach
CRITICAL.

## Fairness (§21)

Deficit round-robin: each eligible workflow accrues its `weight` per round; ties
within an effective-priority class are broken by highest deficit; selection
costs one deficit unit. Priority selects the class; fairness selects within it.
Fairness state (`deficit`, `age`) is checkpointed.

## Shared-budget hierarchy (§11, §12)

```
Portfolio budget → Workflow allocation → H21 wave reservation → Goal execution
```

`PortfolioBudgetCoordinator` mirrors the H21 `SharedBudgetCoordinator`: a
lock-protected, H22-owned reservation pool measured against the shared
budget's live headroom (fully reversible), with H11's monotonic counters
mutated only at reconcile with actual usage — H11 semantics unchanged. It also
enforces a per-workflow maximum allocation and records the allocation policy
(`FIXED_ALLOCATION` / `WEIGHTED_SHARE` / `PRIORITY_WEIGHTED` /
`ON_DEMAND_BOUNDED`). Guarantees: no double reservation, no portfolio
oversubscription (`test_11`), no workflow exceeding its max allocation
(`test_12`), reservations reconciled after every committed quantum (`test_13`),
insufficient budget → `WAITING_FOR_BUDGET` (`test_14`).

## Dependency model (§13, §14, §15)

`WorkflowDependency` types: `REQUIRES_COMPLETION`, `REQUIRES_SUCCESS`,
`REQUIRES_MILESTONE`, `REQUIRES_REVIEW_DECISION`, `REQUIRES_OUTPUT`. The
`DependencyGraph` is validated acyclic (cycles rejected — `test_19`).
Evaluation is deterministic and reads **durable** committed state: milestones
and outputs release a dependent only after the producing workflow commits them
(`WorkflowOutputRef` with digest + version). Completion alone is insufficient
when success / output / milestone / review is specifically required.
Dependency-failure policies: `BLOCK_DEPENDENT` (default), `CANCEL_DEPENDENT`,
`ALLOW_DEGRADED`, `REQUIRE_HUMAN_DECISION` — a failed hard dependency never
silently lets a dependent proceed (`test_16`, `test_20`).

## Resource-claim model & contention (§16, §17, §18)

`WorkflowResourceClaim` (READ / WRITE / EXCLUSIVE / UNKNOWN) are portfolio-level
*logical* claims — not H20 external mutations. `ResourceLedger.try_acquire` is
**atomic (all-or-none)** against a stable global resource ordering, so partial
acquisition and last-arrival-wins never occur (`test_26`). Contention rules:
READ∥READ coexist; WRITE conflicts READ and WRITE; EXCLUSIVE conflicts
everything; **UNKNOWN fails closed** (`test_22`–`test_25`). A blocked workflow is
marked `WAITING_FOR_RESOURCE`; claims release at the safe post-quantum boundary
and on pause/cancel. A wait-for-graph cycle detector plus a deadlock policy
(`PAUSE_YOUNGEST` default, "youngest" = highest registration sequence) provides a
safety net (`test_27`, `test_28`) — though atomic acquisition already prevents
hold-and-wait in the common case.

## Workflow-concurrency rules & quantum (§19, §20)

`PortfolioConcurrencyPolicy`: max concurrent workflows (default 3, conservative),
max active waves, per-agent / per-authority-scope / per-resource-class caps,
scheduling quantum, preemption policy. The quantum is **one committed H21 wave**
(or an equivalent sequential step) — a durable boundary that prevents any one
workflow from monopolizing the scheduler.

## Pause / preemption (§22)

Preemption happens only at safe boundaries (after a committed quantum, before
dispatching new work, while waiting). Worker threads are never forcibly
terminated. `pause()` releases the workflow's resources and freezes it as
`PAUSED`; `resume()` returns it to scheduling. A paused workflow preserves its
memory, budget, ownership, review state, wave state, and trace sequence
(`test_29`).

## Human-governance integration (§23)

H19 stays authoritative. A workflow whose H21 review gate holds a goal surfaces
as `WAITING_FOR_REVIEW` at the portfolio level and **does not block unrelated
workflows**; its dependents stay blocked (`test_30`). Durable human decisions
gate `REQUIRES_REVIEW_DECISION` dependencies (`test_31`).
`notify_review_ready()` is the seam an external approval event uses to
reconsider a held workflow.

## Cross-workflow outputs & memory isolation (§24, §25)

Each workflow keeps its own H14 `WorkingMemory`; one workflow's mutable memory
is never exposed to another (`test_35`). Sharing happens only through immutable
`WorkflowOutputRef`s (durable, digest-stamped) harvested after a producing
workflow commits. The recommended namespace is `portfolio_id / workflow_id /
memory_key`.

## Cancellation scopes & failure isolation (§26, §27)

Cancellation scopes: `WORKFLOW_ONLY` (`test_32`), `DEPENDENT_SUBGRAPH`
(`test_33`), `PORTFOLIO_ALL` (`test_34`, idempotent). Cancellation is explicit,
reason-coded, idempotent, traceable, checkpointed, and cooperative. Portfolio
failure policies: `ISOLATE_WORKFLOW` (default — one failure never fails the
portfolio, `test_21`), `FAIL_DEPENDENTS`, `DEGRADED_CONTINUATION`,
`FAIL_PORTFOLIO`, `REQUIRE_HUMAN_REVIEW`.

## Checkpoint & restore (§28, §29, §30)

`PortfolioCheckpoint` persists portfolio metadata, registrations, orchestration
statuses, priorities + effective priorities, fairness state, shared budget,
allocations, dependency graph + satisfaction, resource claims, cancellation
state, trace, per-workflow checkpoint digest references, round, and recovery
metadata — serialised with H18's public `canonical_json` / `digest_of` and
validated fail-closed. It stores **references** to durable workflow checkpoints
rather than duplicating them. `InMemoryPortfolioStore` mirrors H18's
`compare_and_save` / `CheckpointConflict` contract, so repeated recovery is
idempotent (`test_39`); corrupt or portfolio/workflow-disagreeing checkpoints
fail closed (`test_40`). `classify_in_flight()` maps each workflow to
`NOT_GRANTED / GRANTED_NOT_STARTED / RUNNING_NO_COMMIT / COMMITTED / WAITING /
TERMINAL`; interrupted work delegates to H18/H21 fail-closed recovery and is
never assumed complete (`test_38`); committed quanta are never repeated
(`test_37`).

## Trace model (§31)

`PortfolioTrace` is append-only with **portfolio logical sequence numbers**
(wall-clock is diagnostic only). Events cover creation, registration, readiness,
selection, quantum grant/commit, each waiting reason, resource acquire/release,
dependency satisfied/failed, priority aging, deadlock, pause/resume/cancel,
checkpoint/restore, and portfolio completion/failure. The full lifecycle
reconstructs from the trace (`test_41`).

## Test evidence (43 scenarios)

Tests 1–41 are in `tests/test_multi_workflow_orchestration.py` (43 test
functions total including two extra unit-coverage tests). Mapping to the
required list: registration (1, 2), scheduling order/priority/fairness/aging
(3–8), concurrency + bounded waves (9, 10), budget (11–14), dependencies
(15–20), failure isolation (21), resources (22–26), deadlock (27, 28),
pause/resume (29), human review (30, 31), cancellation (32–34), memory
isolation (35), durability/recovery (36–40), trace (41).

**Regression (scenarios 42–43).** The full `agentic/agentic_framework/tests/`
suite: **16 failed / 2172 passed** with H22, versus **16 failed / 2129 passed**
before it (H21 baseline). The +43 are H22; incremental H22-caused failures:
**0**. The 16 pre-existing failures are an environment gap (`pytest-asyncio`
not installed; unrelated async scheduler / entropy-hookup tests) independent of
H22 and of H21.

## Reference scenarios (§33)

`examples_h22.py` runs, without external services: A priority & fairness, B
dependency chain with durable output/milestone release, C shared bounded budget
(2 of 4 run, 2 wait — no oversubscription), D exclusive resource contention +
safe release, E human-review dependency (unrelated workflow continues), F
checkpoint/restore with no repeated committed quanta.

## Known limitations

* Orchestration is deterministic, bounded, and **in-process**. No distributed
  orchestration, cluster scheduling, production resource locking, external-system
  transactions, distributed consensus, or cross-machine fault tolerance.
* No **exactly-once** workflow execution guarantee for external side effects;
  H20 governed external actions are not implemented or claimed.
* Resource claims are quantum-scoped and released at each safe boundary; true
  cross-quantum hold-and-wait requires longer-lived claims, so the deadlock
  detector is a safety net rather than a common path.
* The portfolio budget's per-workflow *max allocation* is enforced via the H11
  budget's monotonic headroom; a workflow that cannot afford its next quantum
  within its cap fails rather than degrading automatically.
* This is not full enterprise-platform readiness and performs no
  repository-wide architectural consolidation.

## Package version, branch, commit

`__version__ = "1.22.0"`. Branch `claude/architecture-design-review-67cc9s`;
see the commit that adds this document for the exact SHA.
