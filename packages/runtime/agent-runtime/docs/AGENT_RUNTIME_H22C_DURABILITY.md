# Agent Runtime — H22-C Durable Multi-Workflow Orchestration

**Version:** 0.5.0 · **Module:** `ugence_agent_runtime.orchestration` (re-exported from
`ugence_agent_runtime.api`) · **Tests:** `tests/test_portfolio_durability.py`

H22-C makes the H22-B portfolio/team coordinator **durable, reconstructable, auditable, and
safely controllable** across process crash / restart, workflow failure, and operator
cancellation — **without changing single-workflow execution truth**. It answers:

> If the process crashes, restarts, workflows fail, or an operator cancels part of the
> portfolio, can we reconstruct exactly where the multi-workflow team was and safely continue
> **without inventing or repeating work**?

## The four layers, in one line each

| Phase | Plain-language role | Status |
| --- | --- | --- |
| **H22-A** | *"One worker takes one safe step."* — bounded workflow advancement | delivered (0.3.0) |
| **H22-B** | *"Which worker goes next?"* — deterministic portfolio scheduling | delivered (0.4.0) |
| **H22-C** | *"Remember the whole team, recover it safely, record what happened, control failures/cancellation."* | **delivered (0.5.0) — this document** |
| **H22-D** | true bounded concurrency / resource coordination / shared budgets / compensation | future |

## Ownership boundary — four distinct state layers, never merged

H22-C owns **portfolio orchestration durability**. It does **not** own single-workflow
execution truth. The layers stay distinct:

| Layer | Owner | H22-C relationship |
| --- | --- | --- |
| 1. Agent reasoning context | agent/model/framework | not H22-C |
| 2. Canonical Execution State (trajectory + digests) | Agent Runtime | **referenced by digest only** |
| 3. Per-workflow runtime checkpoint | Agent Runtime persistence/recovery | **referenced, never duplicated** |
| 4. Portfolio orchestration checkpoint | **H22-C** | owned here |

> **H22-C does not duplicate Canonical Execution State.** The portfolio checkpoint references
> underlying runtime checkpoints and execution-state snapshots **by digest**; it never embeds a
> copy of either. The runtime checkpoint remains the sole authority for each workflow.

```
                     H22 PORTFOLIO (registry · deps · priority/fairness/aging ·
                          │          scheduler round · failure · cancellation · trace)
                          ▼
                  Portfolio Checkpoint  ── references (by digest) ──▶ runtime checkpoints
                          ▼
                    Durable Store
                          │  crash / restart
                          ▼
                  Portfolio Recovery      (NO execution here)
                          ▼
                explicit continuation      (operator/application decides)
                          ▼
              H22-B scheduler ▶ H22-A advance_workflow ▶ fresh governance ▶ exact action
```

## The portfolio checkpoint (`PortfolioCheckpoint`)

A versioned (`checkpoint_version = "1"`), self-verifying snapshot. It contains **only** what is
needed to deterministically reconstruct the H22-B portfolio and scheduler.

**Persisted** (not safely recomputable, or drives *future* scheduling):

- `portfolio_id`, `portfolio_status`, `round` (logical scheduler round);
- per registration: `instance_id`, `registration_sequence`, `priority`, `weight`, `age`, and
  the smooth-weighted-round-robin `fair_credit` — **`age` and `fair_credit` must be persisted**
  because they change the *next* scheduler decision;
- the cross-workflow dependency edges;
- the orchestration failure / cancellation state;
- one `WorkflowCheckpointRef` per workflow (identity + the runtime checkpoint's base digest);
- the portfolio trace sequence anchor.

**Deliberately NOT persisted** — recomputed on recovery so no stale derived state can drift:

- dependency depth (recomputed from the edge set);
- eligibility (recomputed from recovered runtime status + dependency verdict);
- the scheduler ordering / eligible list / effective ranks (recomputed each round);
- the full historical trace (audit history, not durable orchestration state);
- any workflow task status or canonical execution state (owned by the runtime checkpoint).

### Integrity

A single SHA-256 `portfolio_digest` covers a deterministic canonical serialization (stable key
ordering, enums by value, no object identity, no wall-clock in integrity-critical scheduling
semantics). Serialization uses `allow_nan=False`, so a NaN/±Inf that reached a weight or
`fair_credit` **fails closed** rather than being accepted. Recovery rejects a malformed,
tampered, or unsupported-version checkpoint.

### Portfolio self-recoverability invariant

Before persisting, a checkpoint is validated by **the same validator recovery uses**
(`validate_portfolio_checkpoint`): version → digest → structural invariants → workflow
references → orchestration consistency. A checkpoint that would not recover is **refused**
(fail closed) and the store is left unchanged — H22-C never writes a checkpoint its own recovery
would reject. This is the portfolio-level analogue of the single-workflow checkpoint
self-recoverability invariant.

### Cross-binding to workflow checkpoints

Recovery proves each referenced runtime checkpoint belongs to the registration it claims to
represent: it binds `instance_id`, `workflow_id`, `correlation_id`, and the `checkpoint_digest`
against the runtime checkpoint the runtime store actually holds. It **does not** require
`runtime_id` / `runtime_version` equality — those are *origin provenance* (the Canonical
Execution State precedent), so a portfolio written under one runtime version recovers cleanly
under a later, compatible one (the mismatch is reported, never fatal).

## Recovery is side-effect free (`recover_portfolio`)

```
recover_portfolio(store=…, portfolio_id=…, runtime=…, definitions=…)
    → load + verify the portfolio checkpoint
    → for each workflow ref: cross-bind, then runtime.recover_runtime(...)  ← existing contract
    → rebuild the portfolio (round, age, fair_credit, deps, failure/cancellation state)
    → re-seat the trace position, emit exactly one PORTFOLIO_RECOVERED
```

During recovery: **provider calls = 0, governance calls = 0, workflow advancement = 0,
automatic resume = 0.**

> **H22-C recovery performs no workflow execution.** It reconstructs; it does not continue.

## Explicit continuation

A recovered portfolio `requires_continuation`. Recovery never calls `scheduler.run`,
`advance_workflow`, or `resume_workflow`. A recovered mid-flight workflow returns from the
runtime recovery contract PAUSED (never auto-run); the operator/application then explicitly
continues it. The runtime provides the bounded continuation seam
`continue_workflow(instance_id)` — the bounded analogue of `resume_workflow` that re-arms a
workflow to RUNNING for one-quantum-at-a-time advancement **without draining it**, so a recovered
portfolio resumes deterministic interleaving. Committed work never repeats: recovery restores
COMPLETED tasks as COMPLETED, so an already-consumed quantum is never re-run, and the next
consequential quantum still crosses **fresh** governance (a historical CLEAR is never reused).

## Portfolio audit trace

A separate, append-only orchestration trace ordered by a **logical sequence number**
(1, 2, 3, …), never wall-clock. It answers *"why did the coordinator make this decision?"* —
distinct from the runtime trace's *"what happened inside execution?"*. Events carry ids/digests
only (`instance_id`, `execution_state_digest`, `workflow_checkpoint_digest`); they **never**
embed workflow execution payload or Canonical Execution State, so the portfolio trace never
duplicates the runtime trace. History is never mutated. The checkpoint stores only the latest
sequence anchor; recovery re-seats the position so post-recovery events stay strictly
increasing.

Event vocabulary (`PortfolioEventType`): `PORTFOLIO_CREATED`, `WORKFLOW_REGISTERED`,
`DEPENDENCY_ADDED`, `QUANTUM_GRANTED`, `NO_ELIGIBLE_WORKFLOW`, `WORKFLOW_FAILURE_OBSERVED`,
`CANCELLATION_REQUESTED`, `WORKFLOW_CANCELLED_BY_PORTFOLIO`, `PORTFOLIO_CHECKPOINT_COMMITTED`,
`PORTFOLIO_RECOVERED`, `PORTFOLIO_CANCELLED`, `PORTFOLIO_FAILED`, `PORTFOLIO_COMPLETED`.

## Bounded failure propagation

`PortfolioFailurePolicy` is small and conservative:

| Policy | Effect |
| --- | --- |
| `ISOLATE_WORKFLOW` (**default**) | record the failure; take no further action — hard-dependents are already blocked by the dependency classification, independent workflows continue |
| `FAIL_DEPENDENTS` | additionally cancel the transitive dependent subgraph of the failed workflow; independent workflows continue |
| `FAIL_PORTFOLIO` | cancel every non-terminal workflow and drive the portfolio to terminal `FAILED`; no further quantum is granted |

**Why `ISOLATE_WORKFLOW` is the default:** it is the behavior most consistent with live H22-B
semantics — H22-B already isolates a failure through the dependency graph (a failed
`REQUIRES_SUCCESS` predecessor turns its dependents into `BLOCKED_DEPENDENCY` while independent
workflows keep running). Degraded continuation and compensation are **not** implemented (H22-D).

**Failure authority boundary.** H22-C decides orchestration *consequences* ("do not schedule
workflows dependent on failed A"). It never reinterprets *why* A failed. If governance `BLOCK`ed
a task, governance owns the `BLOCK`, the runtime owns `A = FAILED`, and H22-C only observes the
failure and applies the policy. H22-C never turns `BLOCK → retry/CLEAR` or `FAILED → COMPLETED`.

## Cooperative cancellation scopes

`CancellationScope`:

| Scope | Cancels |
| --- | --- |
| `WORKFLOW_ONLY` | just the named workflow (its dependents are then classified by the graph) |
| `DEPENDENT_SUBGRAPH` | the named workflow + every workflow transitively dependent on it; independent workflows untouched |
| `PORTFOLIO_ALL` | every non-terminal workflow; the portfolio becomes terminal `CANCELLED` |

Cancellation is **cooperative** — it calls the runtime's own `cancel_workflow`, and the runtime
owns the task/workflow `CANCELLED` transition. H22-C never spawns threads, terminates processes,
or mutates runtime task status directly. It is **idempotent** — a repeated request is a no-op
that neither duplicates side effects nor corrupts the trace, and it reports the current
cancellation state. Multi-target cancellation applies in **registration order** (deterministic;
because each cancellation is independent and idempotent, order does not affect the outcome).

**Cancellation vs governance.** A workflow WAITING from a governance `HOLD` (or PAUSED from an
`ESCALATE`) may be cancelled by explicit portfolio control. That is the operator choosing not to
continue the workflow — **not** H22-C overruling governance. Cancellation consults no governance
hook and reinterprets no disposition.

## Portfolio lifecycle

`PortfolioStatus`: `CREATED` (topology mutable) → `ACTIVE` (a round ran) → terminal
`COMPLETED` / `FAILED` / `CANCELLED`. A **quiescent** portfolio (all workflows
WAITING/PAUSED/dependency-blocked) is deliberately **not** a status — it stays `ACTIVE` and is
surfaced only as the scheduler stop reason `NO_ELIGIBLE_WORKFLOW`. Governance WAITING is never
silently turned into completion or failure.

## Store

`PortfolioCheckpointStore` is a neutral interface; the core ships only
`InMemoryPortfolioCheckpointStore` (deterministic, dependency-free, round-trips through the
serialized form). It tracks a monotonic per-portfolio `generation` and supports optional
compare-and-save (`expected_generation`) for in-process optimistic concurrency — **not**
distributed consensus. No SQL/Redis/DynamoDB/filesystem/cloud backend is included; a production
backend is supplied externally, exactly as for the single-workflow `CheckpointStore`.

## Determinism & continuity guarantees (tested)

- **SWRR `fair_credit`, aging, registration order, `round`** all survive recovery, so an
  uninterrupted scheduling sequence equals a checkpoint→recover→continue sequence for the same
  deterministic inputs (verified at weights 2:1 and 3:1, and across an aging threshold).
- **Committed tasks never rerun** after recovery; the next consequential quantum obtains fresh
  governance; canonical-state digests remain resolvable.
- **Dependency, failure, and cancellation truth** reconstruct exactly; a cancelled workflow can
  never become eligible after recovery.
- A **resealed-but-inconsistent** checkpoint (outer digest recomputed) is still rejected by
  structural cross-binding (bad workflow ref, introduced cycle, unknown target).

## Explicitly out of scope (H22-D and beyond)

No true concurrency (no threads/asyncio/pools/workers/distributed queues), no shared budget or
resource ledger, no deadlock detection, no compensation/reversal coordination, no
runtime-assurance (observation of provider effects / actual-vs-intended verification), no
peer-to-peer agent messaging, and no agent/model selection. H22-C persists and coordinates the
runtime/orchestration state it is given; it never becomes the authority that decides whether a
consequential action is permitted.

## Maturity

`IMPLEMENTED_AND_CI_VERIFIED` (scoped `agent-runtime-ci`: package suite, isolated wheel-install
verification, import boundaries, platform-freeze, and API-stability registry observed on the PR
head). No claim of production / pilot / live-environment / distributed / exactly-once /
runtime-assurance / cluster-safe validation.
