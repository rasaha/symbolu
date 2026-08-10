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

### Portfolio self-recoverability invariant (runtime-bound)

Both the pre-persist path (`PortfolioController.checkpoint()`) and `recover_portfolio()` run the
**same side-effect-free, runtime-bound validator** — `validate_portfolio_checkpoint_bound(cp,
runtime)` — so nothing that recovery would reject can ever be persisted. Beyond the structural
`validate_portfolio_checkpoint` (version → digest → structural invariants → references →
label/contiguity), it checks everything evaluable *without actually performing recovery*:

- every referenced runtime checkpoint **exists** in the runtime's own store and matches the
  reference across **both** integrity domains (base `checkpoint_digest`, `checkpoint_version`,
  `extension_digest`) — a mismatch is `PORTFOLIO_RUNTIME_CHECKPOINT_DIVERGENCE`;
- each referenced runtime checkpoint passes its **own** integrity (`verify` / `verify_extension`
  / `validate_execution_states`);
- the H22-C **semantic** state (`failure_state` / `cancellation_state` / terminal lifecycle) is
  consistent with the referenced workflows' persisted runtime statuses.

**Invariant:** every checkpoint emitted by `PortfolioController.checkpoint()` satisfies, at the
instant it is persisted, all H22-C recovery validation that can be evaluated without performing
recovery. Validation makes **no** provider / governance / advance / resume / continuation call. A
checkpoint that would not recover is **refused** (fail closed) and the store is left unchanged.

### Cross-binding to workflow checkpoints (both integrity domains)

Recovery proves each referenced runtime checkpoint belongs to the registration it claims to
represent, binding the **complete** runtime checkpoint across **both** of its integrity domains.
The runtime `Checkpoint` deliberately splits integrity in two: the base `digest` covers only the
coordination payload and **excludes** the canonical-execution-state extension (for backward
compatibility), while a separate `extension_digest` covers `checkpoint_version` + the execution
states + the journal + workflow/task lineage. Binding the base digest alone would therefore
*not* uniquely bind a v1 checkpoint's full snapshot. So `WorkflowCheckpointRef` binds:

```
instance_id · workflow_id · correlation_id
checkpoint_digest      (base coordination integrity)
checkpoint_version     ("1", or "0" for a legacy pre-CES checkpoint)
extension_digest       (canonical-execution-state extension integrity; "" for v0)
```

Recovery matches all of these against the runtime checkpoint the store actually holds, **and**
verifies that checkpoint's own integrity (`verify()`, and for v1 `verify_extension()` +
`validate_execution_states()`; a v0 checkpoint must carry no extension data). A CES/lineage
extension that was altered and validly resealed — base digest unchanged — is caught because the
portfolio reference still binds the *original* `extension_digest`. `runtime_id` /
`runtime_version` are **not** bound — origin provenance (the Canonical Execution State
precedent), so a portfolio written under one runtime version recovers cleanly under a later,
compatible one (the mismatch is reported, never fatal).

### Semantic cross-binding (after workflow recovery)

Beyond structural checks, recovery proves the orchestration state H22-C *claims* matches the
underlying runtime truth actually reconstructed:

- `failure_state[iid]` ⇒ the recovered workflow is `FAILED`; `cancellation_state[iid]` ⇒ it is
  `CANCELLED`; failure/cancellation labels must be drawn from the permitted vocabulary;
- a terminal `portfolio_status` (`COMPLETED` / `FAILED` / `CANCELLED`) ⇒ **every** registered
  workflow is terminal (and `FAILED` ⇒ at least one recorded workflow failure); intermediate
  `CREATED` / `ACTIVE` portfolios are not over-constrained;
- registration sequences must be the canonical **contiguous** range `0 .. len-1` (the exact
  H22-B registration invariant).

So a resealed checkpoint claiming `portfolio_status = COMPLETED` while a workflow is non-terminal,
or `cancellation_state[B] = WORKFLOW_ONLY` while B recovers `RUNNING`/`PAUSED`, **fails closed**
even though its outer portfolio digest was recomputed.

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

## Portfolio audit trace (durable)

A separate, append-only orchestration trace ordered by a **logical sequence number**
(1, 2, 3, …), never wall-clock. It answers *"why did the coordinator make this decision?"* —
distinct from the runtime trace's *"what happened inside execution?"*. Events carry ids/digests
only (`instance_id`, `execution_state_digest`, `workflow_checkpoint_digest`); they **never**
embed workflow execution payload or Canonical Execution State, so the portfolio trace never
duplicates the runtime trace. History is never mutated.

`PortfolioTrace` is a thin stateful writer/view. Bound to a **`PortfolioEventStore`** (neutral,
append-only, portfolio-scoped; reference implementation `InMemoryPortfolioEventStore`), every
event is also appended to that durable store — so **pre-crash audit history survives recovery**,
not just the last sequence number (`trace.history()` returns the full durable log). The store
enforces a contiguous monotonic sequence and **rejects duplicate/out-of-order events**
(`PortfolioTraceSequenceError`). Records are stored as **canonical JSON snapshots**, so they are
genuinely immutable — mutating the original `entry.detail` after append, or a nested value in an
event returned by `events()`, can never change stored history (no shared mutable aliasing in
either direction). Event detail must be composed only of JSON-supported structured values; an
opaque object or a NaN/±Inf **fails closed** (`PortfolioTraceEncodingError`). Without a store the
trace degrades to an in-process log (only the checkpoint anchor is then durable). No
SQL/Redis/filesystem/cloud backend is included.

Event vocabulary (`PortfolioEventType`): `PORTFOLIO_CREATED`, `WORKFLOW_REGISTERED`,
`DEPENDENCY_ADDED`, `QUANTUM_GRANTED`, `NO_ELIGIBLE_WORKFLOW`, `WORKFLOW_FAILURE_OBSERVED`,
`CANCELLATION_REQUESTED`, `WORKFLOW_CANCELLED_BY_PORTFOLIO`, `PORTFOLIO_CHECKPOINT_COMMITTED`,
`PORTFOLIO_RECOVERED`, `PORTFOLIO_CANCELLED`, `PORTFOLIO_FAILED`, `PORTFOLIO_COMPLETED`.

### Checkpoint / commit-event sequencing (crash-safe, honestly in-process)

The checkpoint captures the trace anchor that existed **before** the commit event; the store is
saved; then a `PORTFOLIO_CHECKPOINT_COMMITTED` event is appended:

```
anchor N = trace.last_sequence
save checkpoint(trace_sequence = N)
append PORTFOLIO_CHECKPOINT_COMMITTED   (sequence N+1, durable)
```

Recovery continues at `max(checkpoint.trace_sequence, event_store.last_sequence) + 1`, which is
crash-safe across both windows:

- **Window A** — checkpoint saved, crash *before* the commit event: anchor and store agree at
  `N`, so `PORTFOLIO_RECOVERED` takes `N+1`; no gap, no collision.
- **Window B** — commit event durably appended (`N+1`), then crash: the store's last sequence is
  `N+1`, so recovery continues at `N+2` and never reuses the commit sequence.

The portfolio checkpoint store and the event store are **two independent stores** — H22-C does
**not** pretend they form one atomic distributed transaction. The reconciliation above is the
honest in-process/reference guarantee; a production deployment supplies durable backends and the
same `max(anchor, last-event) + 1` invariant holds.

### Torn cross-store state (workflow runtime ahead of the portfolio snapshot)

There are three independent persistence layers — the runtime workflow checkpoint/state store,
the H22-C portfolio checkpoint store, and the portfolio event store. H22-C makes **no** claim of
an atomic distributed transaction across them. A *torn* state is therefore possible:

```
portfolio checkpoint P10 references workflow checkpoint W10
one workflow receives another H22-A quantum → runtime durably reaches W11
crash BEFORE a new portfolio checkpoint is committed
```

**v0.5.0 cross-store recovery contract.** *Automatic H22-C recovery is guaranteed from
synchronized committed portfolio-checkpoint boundaries. A torn cross-store state — where a
workflow's runtime state has advanced beyond the checkpoint referenced by the latest portfolio
checkpoint — is detected and **fails closed**; the reference implementation does not claim
exactly-once cross-store transactions or automatic reconciliation.*

Recovering from the stale `P10` is **refused** with the diagnostic token
`PORTFOLIO_RUNTIME_CHECKPOINT_DIVERGENCE` (the runtime checkpoint on record, `W11`, no longer
matches the reference to `W10`). Recovery deliberately does **not**: roll the runtime back to
`W10`; rerun the already-committed `W11` provider action; silently accept `W11` as though `P10`
referenced it; or fabricate scheduler state. Reconciliation (commit a fresh portfolio checkpoint
at the new synchronized boundary) is required; once resynchronized, recovery succeeds normally.
Loading an older workflow checkpoint and continuing from it is explicitly **not** done — it could
repeat an already-committed provider action.

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

**Failure-policy continuity across recovery.** The configured policy is persisted in the
checkpoint and surfaced as a **typed, first-class** `failure_policy: PortfolioFailurePolicy` on
`PortfolioRecoveryResult` (not buried in generic metadata). `PortfolioController.from_recovery(...)`
adopts the recovered policy by default, so a portfolio checkpointed under `FAIL_DEPENDENTS`
resumes under `FAIL_DEPENDENTS` — never silently reset to the constructor default.

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

`IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED` after the final correctness corrections (real
runtime-bound pre-persist self-recoverability shared with recovery; genuinely immutable
canonical-JSON event records; explicit torn cross-store state detection and contract) on top of
the earlier audit corrections (durable trace event store; crash-window sequencing; full
base+extension checkpoint binding; semantic lifecycle/failure/cancellation cross-binding;
contiguous-registration validation; typed failure-policy continuity). Package suite **246 passed,
2 skipped** (`tests/test_portfolio_durability.py` = 68); isolated wheel-install **PASS** at
`0.5.0`; platform-freeze **PASS**. Promotes to `IMPLEMENTED_AND_CI_VERIFIED` only once all scoped
`agent-runtime-ci` checks are observed green on the exact new final head. No claim of production /
pilot / live-environment / distributed / exactly-once / runtime-assurance / cluster-safe
validation.
