# Agent Runtime — H22-D Bounded Concurrent Multi-Workflow Execution

**Version:** 0.6.0 · **Module:** `ugence_agent_runtime.orchestration` (re-exported from
`ugence_agent_runtime.api`) · **Tests:** `tests/test_portfolio_concurrency.py`

H22-D lets several **mutually-safe** workflows make progress **at the same time**, while
preventing resource conflicts, budget overruns, governance bypass, duplicate consequential
actions, and unsafe compensation. It answers:

> Given multiple eligible workflows, which ones may receive **simultaneous** bounded execution
> grants without conflicting with each other or exceeding shared limits — and without ever
> becoming the authority that permits the consequential actions inside those grants?

## The four layers, in one line each

| Phase | Plain-language role | Status |
| --- | --- | --- |
| **H22-A** | *"One worker takes one safe step."* — bounded workflow advancement | delivered (0.3.0) |
| **H22-B** | *"Which worker goes next?"* — deterministic portfolio scheduling | delivered (0.4.0) |
| **H22-C** | *"Remember the whole team, recover it safely, record what happened."* | delivered (0.5.0) |
| **H22-D** | *"Let several safe workers operate at once — without colliding or overspending."* | **delivered (0.6.0) — this document** |

## The one non-negotiable boundary

H22-D decides **which safe workflow quanta may execute concurrently**. It **never** becomes the
authority that permits the consequential actions inside those quanta. Three different questions,
three different owners:

```
SCHEDULING ELIGIBILITY   → H22-B   ("which eligible workflow is preferred?")
CONCURRENT ADMISSION     → H22-D   ("which eligible workflows may run at once?")
ACTION AUTHORIZATION     → external governance, BELOW H22-A ("may this exact action proceed?")
```

Workflow A eligible, B eligible, H22-D admits both concurrently — then inside A governance may
`BLOCK` while inside B it `CLEAR`s. H22-D turning concurrency admission into authorization is
exactly what it must never do, and does not.

## What "concurrency" means here

H22-D implements the **smallest justified form**: **bounded, in-process concurrency over
independent H22-A workflow quanta** — real OS threads, capped at `max_concurrent_quanta`, each
running exactly one indivisible H22-A quantum for a *distinct* workflow.

* It is **not** mere logical interleaving (that is H22-B).
* It is **not** distributed concurrency. There is **no** cross-process/cross-machine execution,
  no distributed locking, no cluster scheduler, and no exactly-once external effect.

The unit of concurrency is `advance_workflow(instance_id)`. No internal state-machine phase is
ever interleaved: the governance → exact-action → provider → transition → checkpoint chain runs
entirely **within** one quantum and cannot be observed or preempted between a governance CLEAR
and the provider call it cleared.

## The barrier discipline — plan → execute → join → reconcile → checkpoint

Every concurrent round runs this exact sequence, and portfolio checkpoints are committed **only
at the stable batch boundary** at the end:

```
                 H22-B eligible set (fairness-ranked)
                              │
   ┌──────────────────────────────────────────────────────────┐
   │ 1. PLAN  (single coordinator thread)                       │
   │    deterministic batch selection + atomic resource/budget  │
   │    admission → ConcurrentAdmissionPlan [A, C, D]           │
   └──────────────────────────────────────────────────────────┘
                              │
   ┌──────────────────────────────────────────────────────────┐
   │ 2. EXECUTE   A ─┐  C ─┐  D ─┐   each = one indivisible     │
   │                 ▼     ▼     ▼   H22-A quantum, on threads   │
   │            governance→exact-action→provider→checkpoint     │
   └──────────────────────────────────────────────────────────┘
                              │
   ┌──────────────────────────────────────────────────────────┐
   │ 3. JOIN   wait for every admitted quantum's stable boundary│
   │ 4. RECONCILE (coordinator, in admission order)             │
   │    release resources · settle/release budget · observe     │
   │    failures (H22-C) · coordinate compensation              │
   │ 5. CHECKPOINT (optional) — reservations are empty here     │
   └──────────────────────────────────────────────────────────┘
```

Workers are **narrow**: a worker only calls `advance_workflow` for one distinct instance and
returns an immutable outcome. Only the coordinator thread mutates portfolio / scheduler /
resource / budget / trace / checkpoint state, so no lock guards those aggregates — the isolation
is structural, not a giant global lock that would make concurrency fake.

## Deterministic admission, non-deterministic completion

**Admission is fully deterministic** — the admitted batch is reproducible from explicit state
alone; thread completion timing can never change *who* was admitted. Each admitted quantum gets a
deterministic identity (`batch_id` + `admission_sequence`) **before** launch. Reconciliation and
the audit trace proceed in **admission order**, so even though quanta finish in a racy order, the
recorded orchestration history is reproducible.

## Fairness — the batch selection seam (the critical design point)

H22-D does **not** implement a second scheduler. It consumes H22-B's fairness ranking through one
additive seam, `PortfolioScheduler.plan_batch(...)`, which is the **same** smooth-weighted
round-robin (SWRR) core `step()` uses, generalized to admit a *batch*:

* it scans eligible workflows in SWRR-preferred order and asks an **admission predicate** (the
  H22-D resource/budget gate) whether each fairness winner may take a slot;
* an admitted workflow performs one real SWRR pick (accrue the live tier's weight, charge the
  winner the tier total, reset its age) — so **all admitted workflows are counted as served**;
* a **deferred** workflow (resource/budget) is removed from the round's contention but is
  **never charged SWRR credit and never age-reset**, so a resource-conflicted workflow keeps its
  full starvation protection and is retried first next round;
* after the batch, every eligible workflow held **strictly below the lowest served tier** ages
  (bounded by `aging_cap`); tier-peers of a served tier never age (SWRR owes them).

**At `max_concurrent_quanta == 1` with no resource/budget constraints, `plan_batch` commits
fairness/aging state identical to a single `step()`** — concurrency=1 is semantically bounded
H22-B execution (proven in `test_B_concurrency_one_matches_single_quantum_scheduler`), and SWRR
weight proportionality survives concurrent batching under resource-forced serialization (an exact
2:1 in `test_Z_...`).

## Resource claims

A **resource claim** (`ResourceClaim(resource_key, mode)`) is a portfolio-coordination
requirement declared *before* a quantum runs — **not** application authority. A `WRITE` claim on
`crm/customer/123` means "do not run another conflicting quantum concurrently with mine"; it does
**not** mean "I am authorized to update customer 123" (that still crosses governance below H22-A).

Claims are supplied explicitly (a static per-workflow map or an injected `claims_resolver`) so
they are known before admission. The fixed, exhaustively-tested conflict matrix — the only
compatible pair is `READ + READ`:

| | READ | WRITE | EXCLUSIVE | UNKNOWN |
| --- | --- | --- | --- | --- |
| **READ** | compatible | conflict | conflict | conflict |
| **WRITE** | conflict | conflict | conflict | conflict |
| **EXCLUSIVE** | conflict | conflict | conflict | conflict |
| **UNKNOWN** | conflict | conflict | conflict | conflict |

`UNKNOWN` is **fail-closed** (an undeclared/unresolvable resource conflicts with everything).
Multiple claims on one key within a workflow collapse to the strongest mode (`R READ` + `R WRITE`
→ `R WRITE`). Reservation is **atomic all-or-none**: a multi-resource claim reserves every claim
together or nothing, and reservations are released on **every** exit — success, HOLD, ESCALATE,
BLOCK, provider failure, cancellation, or a worker infrastructure fault — so nothing can leak and
permanently block the portfolio. Because the full claim set is planned and reserved before
execution, there are no runtime lock-acquisition chains and **no deadlock by design**.

> **Scope:** resource coordination is **portfolio-local**. It prevents two workflows *in this one
> in-process coordinator* from running conflicting quanta at once. It is **not** a distributed
> lock and does not protect an external resource from an independent process. A deployment needing
> cross-process exclusion must supply that separately; H22-D never implies it.

## Shared budget

A generic, typed ledger over **named numeric dimensions** (the caller's names — `token_units`,
`model_cost`, `external_api_calls`, … — never hardcoded cloud billing). The key invariant: a
concurrent quantum must **reserve** its declared maximum *before* it is admitted, so two quanta
each individually affordable cannot together exceed the remaining budget. Per dimension:

```
available = limit − consumed − reserved
```

Reservation is atomic all-or-none across dimensions; an unconstrained dimension always fits.
H22-D never invents an estimate — a workflow declares a `BudgetRequirement` (or an injected
`budget_resolver` supplies one). Settlement is driven by **authoritative provider-execution
evidence** (`WorkflowAdvanceOutcome.provider_invoked`), never inferred from a terminal task
status: on a quantum whose governance→exact-action→provider chain actually reached the provider
(a CLEAR that ran, whether it succeeded or the provider failed), the full reservation is charged
as `consumed` (the conservative rule — never under-charge; `actual_known = False` records that no
usage telemetry exists); on a quantum that ran **no** provider — a governance HOLD/ESCALATE/BLOCK,
an exact-action clearance/integrity rejection (both fail closed *before* the provider), a no-op,
a cancellation, or an infrastructure fault — the reservation is **released** without charging.
This keeps `0 ≤ consumed ≤ limit` always. If a caller ever settles with a *measured* actual usage
greater than the reservation, settlement fails **closed** (`BudgetEstimateExceeded`) rather than
silently clamping, so the ledger can never claim `consumed ≤ limit` by discarding real usage.
NaN/±Inf/negative values fail closed. Budget exhaustion makes a workflow *not concurrently
admissible* (`DEFERRED_BUDGET`) — it never creates a governance decision and never marks the
workflow FAILED.

## Governance under concurrency

Each consequential quantum obtains **fresh** governance every time (never cached across quanta),
and H22-D itself never calls a provider outside `advance_workflow`. Concurrent dispositions are
independent: `A → HOLD` (WAITING), `B → CLEAR` (progresses), `C → ESCALATE` (PAUSED) run in the
same batch without A or C blocking B — reservations are released the moment their quantum reaches
its stable HOLD/ESCALATE boundary.

## Compensation

Compensation is **not** "undo the provider action" — H22-D cannot reverse an arbitrary external
side effect and never claims to. Compensation means: **record the intent to schedule a
separately-defined, explicitly-governed workflow** that mitigates an earlier effect, **exactly
once**, with provenance back to the origin workflow.

* The application declares a `CompensationSpec` (which compensation workflow definition
  compensates which origin workflow, on which bounded trigger — `ON_WORKFLOW_FAILURE`,
  `ON_PORTFOLIO_FAILURE`, `EXPLICIT_OPERATOR_REQUEST`). H22-D synthesizes no prompt, model, tool,
  refund amount, or rollback payload.
* Registration is **idempotent** (keyed by a deterministic identity), so a repeated failure
  observation — or a recovery replay — never duplicates it, and the origin lineage is recorded.
* The compensation workflow, when the application schedules it, is an **ordinary** workflow: it
  flows through the same H22-A → TransitionProposal → **fresh governance** → exact-action →
  provider chain and obeys resources/budget/concurrency. H22-D **never** calls a compensation
  provider directly, and never fabricates that the original effect occurred.

## Durability, crash, and recovery

The portfolio checkpoint gains a **v2** schema carrying only the durable H22-D slice — the shared
**budget** (`limits` + `consumed`; transient reservations are **never** persisted) and the
**compensation registrations**. A **v1** (H22-C) checkpoint recovers unchanged (its payload and
digest exclude the H22-D block). Concurrency policy and resource-conflict policy are
operator-supplied configuration on recovery (like `SchedulingPolicy`), not persisted.

Checkpoints are committed **only at a stable batch boundary**, where the coordinator validates
that there are **no active resource reservations and no active budget reservations** before
building anything (`reserved == 0`, `0 ≤ consumed ≤ limit`). H22-D never persists a thread/future
handle. Recovery is strictly reconstruction: **provider calls = 0, governance calls = 0, workflow
advancement = 0, concurrent task launch = 0**, and the recovered portfolio `requires_continuation`
— an active batch is **never** resurrected from guesses.

The H22-C torn-state contract is preserved untouched: if the runtime workflow checkpoint has
advanced beyond the portfolio snapshot (a crash mid-batch), recovery fails **closed** with
`PORTFOLIO_RUNTIME_CHECKPOINT_DIVERGENCE`. There is no rollback, no replay, and no fabricated
completed-batch state.

## Cancellation during an active batch

Cancellation never interrupts an in-flight indivisible H22-A quantum. A quantum already admitted
this round runs to its stable boundary; the cancellation applies to **future** quanta (the runtime
checks the cancellation token at the start of the next quantum). Cancellation is cooperative and
delegated to the H22-C controller, with the same `WORKFLOW_ONLY` / `DEPENDENT_SUBGRAPH` /
`PORTFOLIO_ALL` scopes.

## Public API (added in 0.6.0)

```python
from ugence_agent_runtime import (
    create_concurrent_executor, ConcurrentPortfolioExecutor, ConcurrencyPolicy,
    ConcurrentPortfolioStepResult, ConcurrentStepReason, QuantumOutcome,
    ExecutionBackend, SynchronousExecutionBackend, ThreadPoolExecutionBackend,
    ExecutorInfrastructureError,
    ResourceMode, ResourceClaim, ResourceConflict, ResourceCoordinator,
    PortfolioBudget, BudgetRequirement, BudgetShortfall, BudgetCoordinator,
    CompensationTrigger, CompensationSpec, CompensationRegistration, CompensationRegistry,
    AdmissionDecision, BatchPlan,
)

executor = create_concurrent_executor(
    runtime, portfolio,
    policy=ConcurrencyPolicy(max_concurrent_quanta=4),
    budget=PortfolioBudget({"model_cost": 500}),
    backend=ThreadPoolExecutionBackend(),
)
executor.set_resource_claims(a, [ResourceClaim("crm/customer/123", ResourceMode.WRITE)])
executor.set_budget_requirement(a, BudgetRequirement({"model_cost": 70}))
result = executor.step_concurrent()   # plan → execute → join → reconcile
executor.checkpoint()                 # stable batch boundary only
```

## Independent-audit hardening (0.6.0)

Five corrections tighten the safety envelope without changing the architecture:

- **Runtime concurrency ceiling respected.** H22-D never exceeds the runtime's own configured
  in-flight-task bound: the effective concurrency is
  `min(ConcurrencyPolicy.max_concurrent_quanta, AgentRuntimeConfig.max_concurrent_tasks)`
  (`ConcurrentPortfolioExecutor.effective_max_concurrent_quanta`). A runtime configured for one
  in-flight task makes H22-D serial regardless of policy.
- **Undeclared ≠ empty (fail-closed default).** An *explicitly empty* resource claim set (or
  budget requirement) is the application asserting "no shared footprint" and permits concurrency.
  A workflow that has **not** declared is treated as *unknown* and handled fail-closed: an
  undeclared resource footprint conservatively **serializes** (it runs alone;
  `RESOURCE_REQUIREMENT_UNAVAILABLE`), and an undeclared budget requirement is refused whenever the
  portfolio budget has configured limits (`BUDGET_REQUIREMENT_UNAVAILABLE`). Undeclared is never
  silently assumed conflict-free / zero-cost.
- **Exception-safe admission planning.** Requirements are resolved up front, *before* any
  reservation or fairness/service state is committed. A resolver/coordinator fault fails **closed**
  with all reservations released and **no** H22-B fairness state mutated — planning is all-or-none,
  and no batch executes on a partially-reserved plan.
- **Authoritative settlement evidence.** Budget settlement uses `WorkflowAdvanceOutcome.provider_invoked`
  (additive, immutable) instead of inferring provider execution from a terminal task status — so a
  governance BLOCK or an exact-action rejection (no provider) correctly *releases* rather than
  charges, and a measured overrun fails closed instead of silently clamping.
- **Recovery reconstruction seam.** `ConcurrentPortfolioExecutor.from_recovery(...)` /
  `create_concurrent_executor_from_recovery(...)` rebuild the executor from a
  `PortfolioRecoveryResult`, adopting the recovered portfolio, append-only trace, H22-C failure
  policy, durable **consumed budget**, and **compensation registrations** — so a recovered
  portfolio continues instead of silently resetting shared budget, compensation state, failure
  policy, or trace continuity. Reconstruction launches zero workers, makes zero
  provider/governance/advance calls, and preserves `requires_continuation`; a v1 checkpoint yields
  empty-but-valid H22-D state.

## Explicit non-claims (limitations)

H22-D provides **bounded in-process multi-workflow concurrency**, and nothing more. It does
**not** provide, and this release does **not** claim: distributed cluster scheduling, distributed
locking, Kubernetes/Redis/DB coordination, global transactions, exactly-once external effects,
Runtime Assurance, model/agent selection, peer-to-peer agent messaging, autonomous workflow
generation, or production / pilot / live-environment / cluster-safe validation. Resource
coordination is portfolio-local; the correct claim is **bounded deterministic admission +
fail-closed divergence detection + no intentional replay from stale portfolio state** — not
exactly-once execution.
