# Agent Runtime — H22-B Deterministic Multi-Workflow Coordination

**Version:** 0.4.0 · **Module:** `ugence_agent_runtime.orchestration` (re-exported from
`ugence_agent_runtime.api`) · **Tests:** `tests/test_portfolio_scheduler.py`

H22-B is the deterministic coordination layer **above** the single-workflow runtime. It
consumes the H22-A bounded-advancement seam and answers exactly one question:

> Given N prepared independent workflows, **which** workflow is eligible to receive the
> next execution quantum, and **why**?

It is the coordination equivalent of a team lead over a shared task graph — with Ugence
deterministic execution semantics and independent governance underneath. **H22-B provides
deterministic interleaving, NOT simultaneous multi-workflow execution.**

## Phase map

| Phase | Scope | Status |
| --- | --- | --- |
| **H22-A** | bounded workflow advancement (`prepare_workflow` / `advance_workflow`) | delivered (0.3.0) |
| **H22-B** | deterministic coordination: portfolio, dependency graph, eligibility, priority, fairness, aging, scheduler | **delivered (0.4.0) — this document** |
| **H22-C** | portfolio durability / trace / failure propagation / cancellation scopes | future |
| **H22-D** | true bounded concurrency / resource coordination / budget coordination / compensation | future |

## Where it sits

```
                    H22-B PORTFOLIO
             ┌───────────────────────────┐
             │ Workflow Registry         │
             │ Dependency Graph          │
             │ Eligibility Engine        │
             │ Priority / Fairness / Aging│
             │ Deterministic Picker      │
             └─────────────┬─────────────┘
                           │  grant ONE quantum
                           ▼
                  runtime.advance_workflow(instance_id)      ← unchanged H22-A seam
                           ▼
   build proposal → FRESH governance → CLEAR/HOLD/BLOCK/ESCALATE →
   exact-action validation → provider (iff allowed) → runtime transition →
   canonical execution state → self-recoverable checkpoint
```

The scheduler decides *"Workflow B receives the next quantum."* It **never** decides
*"Workflow B's consequential action is authorized."* Governance remains entirely below
H22-B.

## Portfolio

A `WorkflowPortfolio` is a deterministic aggregate of already-prepared Agent Runtime
workflow instances plus the orchestration metadata a scheduler needs. **It is orchestration
state only** — it references each workflow by its `instance_id` and never duplicates the
runtime-owned workflow/task state, canonical execution state, or checkpoints. The Agent
Runtime stays the sole authority for execution truth.

`PortfolioStatus` is minimal: `CREATED` (before any round) → `ACTIVE` (stepping, some
workflow can still progress) → `COMPLETED` (every registered workflow terminal). A
*quiescent* portfolio — all workflows WAITING / PAUSED / dependency-blocked — is `ACTIVE`,
**not** `COMPLETED`; governance `WAITING` is never silently treated as completion.

### Registration

`portfolio.register(instance_id, *, runtime=None, priority=NORMAL, weight=1.0)` is:

- **deterministic & order-stable** — each entry gets a monotonic `registration_sequence`;
- **explicit** — only prepared instances are registered;
- **idempotent** — re-registering an `instance_id` returns the existing entry **unchanged**
  (priority/weight/sequence are immutable registered identity);
- **validated** — with a `runtime` given, an unknown `instance_id` is rejected;
- **inert** — registration runs no workflow and mutates no runtime state.

`PortfolioWorkflowEntry` stores only orchestration metadata: `instance_id`,
`registration_sequence`, `priority`, `weight`, and the mutable per-round `age` / `deficit`
scheduler bookkeeping. There is **no** agent/model selection here.

## Dependency graph

A deterministic DAG over registrations. Two dependency types are implemented — exactly the
two the packaged runtime can represent durably from committed terminal status:

| Type | Satisfied when | Failure semantics |
| --- | --- | --- |
| `REQUIRES_COMPLETION` | predecessor reaches **any** terminal state (COMPLETED / FAILED / CANCELLED) | never blocks — "wait until done, however it ends" |
| `REQUIRES_SUCCESS` | predecessor reaches **COMPLETED** | fail-closed — a terminal-but-not-COMPLETED predecessor makes the dependent `BLOCKED_DEPENDENCY` |

Richer types (`REQUIRES_OUTPUT` / `REQUIRES_MILESTONE` / `REQUIRES_REVIEW_DECISION`) are
**not** invented here — they need a durable public representation of workflow outputs /
milestones / review decisions that the packaged runtime does not yet expose. They are
documented as later (H22-C+) extensions.

Graph validation is fail-closed: **self-dependency**, **unknown references**, and **direct
or indirect cycles** are all rejected (and `add_dependency` rejects a cycle without leaving
partial state). Duplicate edges are idempotent; a duplicate pair with a conflicting type is
rejected. `depth(id)` is the deterministic longest path from a root (a root has depth 0).

Example release chain:

```
A --success--> B --completion--> C
before A succeeds:  A=ELIGIBLE   B=WAITING_DEPENDENCY   C=WAITING_DEPENDENCY
after  A COMPLETED: A=TERMINAL   B=ELIGIBLE             C=WAITING_DEPENDENCY
after  B terminal:  A=TERMINAL   B=TERMINAL             C=ELIGIBLE
```

## Eligibility

Every registered workflow is classified deterministically each round, mapped one-to-one
from its runtime `WorkflowStatus` and dependency verdict (terminal dominates; then a failed
hard dependency; then a pending dependency; then the runtime status):

| `WorkflowEligibility` | From | Eligible? | Ages? |
| --- | --- | --- | --- |
| `ELIGIBLE` | RUNNING + all deps satisfied | yes | if unselected |
| `WAITING_DEPENDENCY` | a prerequisite not yet met | no | no |
| `BLOCKED_DEPENDENCY` | a hard success-prerequisite failed | no | no |
| `WAITING_RUNTIME` | runtime WAITING (governance HOLD) | no | no |
| `PAUSED` | runtime PAUSED (ESCALATE / explicit pause) | no | no |
| `TERMINAL` | COMPLETED / FAILED / CANCELLED | no | no |

Classification reads status only — it invokes **zero** provider calls and **zero**
governance evaluations. H22-B never calls `resume_workflow`: a governance HOLD or ESCALATE
simply makes a workflow non-eligible and stays that way until an explicit resume outside
H22-B.

## Deterministic scheduler

One `scheduler.step(portfolio)` runs one logical round: classify → (if none eligible, return
a deterministic stop reason) → accrue fairness → order eligible workflows by the stable key
→ age the unselected, reset the selected → grant **exactly one** quantum via
`advance_workflow` → return a frozen `PortfolioStepResult`.

**Stable ordering key** (the selected workflow is the minimum):

```
( effective_rank, dependency_depth, -fairness_deficit, registration_sequence, instance_id )
```

Reproducible from explicit portfolio state alone — no wall-clock, object identity,
dictionary iteration order, thread scheduling, randomness, or global mutable state. Two
identical portfolios with identical runtime/governance/provider outcomes produce identical
selection sequences.

### Priority

`WorkflowPriority` — `CRITICAL(0) · HIGH(100) · NORMAL(200) · LOW(300) · BACKGROUND(400)`,
lower rank preferred. Priority is **orchestration priority only**: it never creates
governance authority and never bypasses a dependency, a WAITING/PAUSED runtime state, or
exact-action validation. A CRITICAL workflow that is dependency-blocked does not run.

### Aging (bounded starvation prevention)

Driven by **logical scheduler rounds**, not wall-clock. Only a workflow that is
`ELIGIBLE`-but-not-selected ages; the selected workflow resets to 0; dependency-blocked /
WAITING / PAUSED / terminal workflows never age.

```
effective_rank = max(1, base_rank − min(age, aging_cap))     # non-critical
effective_rank = base_rank                                    # CRITICAL (never ages)
```

The floor at 1 guarantees no non-critical workflow can ever reach the CRITICAL rank (0) —
aging prevents starvation without letting a lower class become an emergency class.
`aging_cap` (default 500) bounds the effect.

### Fairness

Deterministic deficit round-robin: every eligible workflow accrues its `weight` each round,
selection costs one deficit unit, and ties within a comparable effective priority are broken
by highest deficit (the `-fairness_deficit` term). **Priority chooses the class; fairness
arbitrates within comparable effective priority.** Fairness/aging state lives on the
portfolio entries as plain serializable numbers, ready for later H22-C persistence.

### Step result & explainability

`PortfolioStepResult` (frozen) carries `reason` (`QUANTUM_GRANTED` /
`NO_ELIGIBLE_WORKFLOW` / `ALL_TERMINAL` / `EMPTY_PORTFOLIO`), `selected_instance_id`, the
ordered `eligible` candidates, every workflow's `classifications`, and the granted quantum's
`advance_outcome` (itself an H22-A `WorkflowAdvanceOutcome` referencing runtime state **by
digest**). A structured `SelectionReason` answers *"why B instead of A?"* without free-form
prose:

```
selected = B
reason: effective_rank=100 (HIGH), dependency_depth=0, fairness_deficit=3.0,
        age=0, registration_sequence=2
```

## Determinism & boundaries (guarantees)

- Selection is reproducible from explicit portfolio state; identical inputs → identical
  choices.
- Eligibility/selection perform no execution — provider calls = 0, governance calls = 0.
  Execution occurs only when a quantum is granted.
- The scheduler reaches providers **only** through `advance_workflow`; it never calls a
  provider directly, caches/manufactures a CLEAR, reinterprets a HOLD, downgrades a BLOCK,
  auto-resumes an ESCALATE, or mutates a proposal.
- Every selected quantum still produces the same canonical execution-state digest/history
  and self-recoverable checkpoints as plain H22-A; individual workflow recovery is
  unchanged.
- Dependency direction is orchestration → runtime: this layer imports the runtime's public
  contracts; the runtime engine never imports orchestration, so the single-workflow runtime
  stays usable without H22-B.

## Known limitations (out of scope here)

- **No true concurrency.** Deterministic interleaving only — no threads, asyncio, pools,
  workers, or distributed queues (H22-D).
- **No shared budget or resource ledger, no deadlock detection** (H22-D).
- **No portfolio checkpoint/recovery or portfolio trace** — the portfolio's orchestration
  state is designed to be serializable (plain numbers, `to_dict()`), but H22-B persists
  nothing (H22-C).
- **No failure-propagation policy matrix, cancellation scopes, or compensation** — a failed
  hard prerequisite yields `BLOCKED_DEPENDENCY` and stops there (H22-C).
- **No peer-to-peer agent messaging and no agent/model selection.** Cross-workflow
  coordination relies on committed runtime facts, not shared reasoning memory.
