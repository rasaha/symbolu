# Ugence Durable Execution

**The engine owns scheduling and recovery. It owns nothing else.**

This package lets an external durable-execution engine *drive* Agent Runtime transitions
without holding any governance state. Workflow IR and governance state are always
Ugence's; Agent Runtime owns proposal binding, the governance hook, budgets, checkpoints
and receipts. The engine never decides whether a step may run, and never re-drives a
step past the hook — every retry re-enters the same Agent Runtime transition and
therefore re-crosses the same governance boundary.

Scoped by [`docs/architecture/ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md`](../../../docs/architecture/ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md).
Sequenced as GAS-2 in the Ugence productization roadmap §11.

---

## Maturity — read this before citing the package

**DBOS is RATIFIED as the initial durable-execution engine** by owner ruling OD-3
(ADR §9, 2026-09-05), on the evidence of every ADR §8 matrix row passing in CI against
a real PostgreSQL (durable-execution-ci job 101257085510 on `fe6f1591`). `engine_status()`
reports the state and the test suite asserts it together with the ADR record, so the
claim cannot drift away from the evidence:

```python
>>> from ugence_durable_execution import engine_status
>>> engine_status()
{'engine': 'dbos', 'status': 'RATIFIED', 'ratified': True, ...}
```

This package is **not** pilot-validated and **not** production-certified. Nothing in it
reaches a live system, and it carries no credentials — the Credential Broker
(cloud-scaling Phase 5X) does not exist, and nothing here substitutes for it. Agent
Runtime's own statements about not being distributed-safe or exactly-once are revised
only for the properties the matrix actually proves, and only here — the runtime's own
README is untouched.

Ratified means exactly this: the ADR §8 matrix passes in CI. It does not mean piloted,
certified, or approved for any live system. See **Matrix status** below.

## What this package is not

It does not schedule retries of its own, author policy, mint authority, hold a
credential, or interpret Workflow IR. It re-implements no package logic: the governance
chain is Agent Runtime's, unchanged, and the adapter imports no governance package at
all — asserted by `tests/test_boundaries.py`.

---

## The shape

```
        ugence-agent-runtime  (leaf — UNTOUCHED by this package)
            ▲
        ugence-durable-execution  ──>  dbos, sqlalchemy, psycopg
```

The dependency is one-way and enforced: Agent Runtime gains no import from here, and
`tests/test_boundaries.py::test_agent_runtime_gains_no_import_from_this_package` fails
if that ever changes.

Three Protocols, transcribed verbatim from ADR §4 and pinned by
`tests/test_adr_conformance.py`:

| Protocol | Role |
|---|---|
| `DurableExecutionAdapter` | `start` / `advance` / `signal` / `status` / `recover` |
| `DurableStepOutcome` | what one advance reports back — deliberately coarse |
| `DurableStoreBundle` | the three runtime stores, supplied together |

`DurableStepOutcome` collapses WAITING and PAUSED into one `awaiting_external` flag on
purpose: the engine must not be able to schedule differently depending on whether
governance said HOLD or ESCALATE, so it never learns which.

## Where the step boundary is drawn

One `advance` is one `AgentRuntime.advance_workflow` — one bounded advancement quantum.
The runtime already runs proposal construction, `GovernanceHook.evaluate`,
`validate_clearance`, the last-mile authority recheck, the provider invocation and the
transition inside that quantum, precisely so nothing can interleave between a CLEAR and
the invocation it cleared. The durable step wraps exactly that. Anything smaller would
let an engine retry replay an invocation against a stale clearance.

Two consequences worth stating plainly:

* **Idempotency keys and fingerprints survive retries unchanged.** The runtime derives
  its key as `{instance_id}:{task_id}` — no attempt number, no timestamp — so attempt 1
  and attempt 7 of a task produce the same key and the same proposal fingerprint. The
  adapter's `attempt_token` is deliberately excluded from both; mixing it in would make
  every retry look like a brand-new action.
* **Recovery never auto-runs, and resume is bounded.** Agent Runtime restores a
  recovered instance as PAUSED requiring explicit continuation. So a retry after a
  crash is two steps — an explicit resume, then an advance that re-crosses the boundary
  from the beginning. `resume` delegates to the runtime's bounded `continue_workflow`:
  it re-arms and runs nothing, so one durable step never crosses the governance
  boundary more than once. Asserted by matrix rows 1–3 and row 9.

## Two configuration requirements that are not optional

**Inject a wall clock.** `AgentRuntimeConfig.clock` defaults to `time.monotonic`, and
that reading is compared against a clearance's `valid_until`. Monotonic time is
process-local: after a crash and recovery in a new process, a `valid_until` minted
before the crash is compared against an unrelated number, and can read as *not yet
expired* for an arbitrarily long outage. `DbosRuntimeHost` refuses the monotonic default
at construction. Pass `ugence_durable_execution.clock.wall_clock`, and make sure the
evaluator mints `valid_until` on the same time base.

**Configure `authority_recheck`.** Without it, a revocation or epoch advance landing
between CLEAR and the effect goes unnoticed. In a single-process run that gap is
unusual; under a durable engine, retries and recovery make it routine. Matrix row 6
asserts both the fail-closed behaviour *and* the negative case, so the requirement is
proven load-bearing rather than decorative.

---

## Storage, and the consistency boundary

Per owner ruling **OD-2** (`COEXIST_WITH_BOUNDARY`), this package's tables and the DBOS
step record share one PostgreSQL database. Risk Authority and execution-reservation keep
their separately ratified SQLite Posture B; nothing here migrates or redesigns a
governance store.

| Table | Shape |
|---|---|
| `ugence_art.runtime_state` | one row per instance — the resume point and the claim row |
| `ugence_art.checkpoints` | append-only history, unique `(instance_id, seq)` |
| `ugence_art.runtime_events` | append-only log; `attempt_token` recorded, never branched on |
| `ugence_art.budgets` / `budget_consumption` | ceiling as a CHECK constraint; consumption keyed by the runtime's own idempotency key |

**The boundary you must know about.** DBOS keeps *workflow status* in a separate system
database, which is **not** part of the application transaction. After a crash the system
database can say `PENDING` while the application database holds nothing from the killed
transaction — that is what makes recovery re-drive the instance, and it is why the
adapter never treats engine status as evidence that an effect happened or that a
clearance was consumed. `tests/test_od1_single_transaction.py` asserts this separation
directly rather than leaving it as prose.

### OD-1 — the single-transaction property

Owner ruling **OD-1** (`REQUIRE_SINGLE_TRANSACTION`) makes atomic commit a ratification
gate rather than a documented residual. It holds, and it is proven rather than inferred:

* a SIGKILL with the transaction open leaves **neither** the application write nor the
  DBOS step record — two separate commits could not produce that;
* a success commits both;
* an exception before commit rolls back the application write and records only an error
  outcome.

One non-obvious implementation detail makes this real: `run_tx_step` writes its step
record **only inside a DBOS workflow context**. Calling it directly gives the
transaction without the durable step, which would not satisfy OD-1. So every mutating
operation here is a `@DBOS.workflow()` whose body is a `@datasource.transaction`.
Read-only operations stay on a plain transaction, since a step record would record an
attempt that changed nothing.

Attempts deliberately do **not** share a workflow id, so DBOS never replays a previously
recorded advance. Every attempt re-enters the runtime and re-crosses the hook; the step
record's role here is atomicity and durable evidence, not replay.

---

## Matrix status

Run against a real PostgreSQL server — a mocked crash proves nothing about what was
rolled back, so the crash rows kill real processes and the outage row stops the real
database.

```bash
export UGENCE_DE_TEST_PG='postgresql+psycopg://postgres@127.0.0.1:5432/postgres'
export UGENCE_DE_PGDATA=/var/lib/postgresql/data      # row 7 stops the server
export UGENCE_DE_PGBIN=/usr/lib/postgresql/16/bin
pytest packages/integration/durable-execution/tests -q
```

A skipped row is **not** a passing row. Row 7's server-stop case skips loudly when
`UGENCE_DE_PGDATA` is unset, and a connection-refusal simulation is not accepted as
evidence for it.

| Row | Failure | Status |
|---:|---|---|
| 1 | Crash before the provider call | PASSING |
| 2 | Crash during the provider call | PASSING |
| 3 | Crash after the effect, before the commit | PASSING |
| 4 | Duplicate delivery / retry of a consequential step | PASSING |
| 5 | Clearance expiry during a retry (incl. inclusive boundary) | PASSING |
| 6 | Revocation / epoch advance, incl. the negative case | PASSING |
| 7 | PostgreSQL unavailable, incl. checkpoint corruption | PASSING |
| 8 | Concurrent instances contending for one budget | PASSING |
| 9 | Pause and resume across a human decision | PASSING |
| 10 | Recovery after a workflow-definition version change | PASSING |
| 11 | Clock skew, incl. the monotonic-clock refusal | PASSING |

Passing the matrix is the evidence the ADR asks for. Promotion from *candidate* to
*ratified* was a deliberate owner act (OD-3, ADR §9) on that evidence, not a side
effect of a green suite.

## Known gaps

Multi-region consistency, HSM/KMS custody and key rotation are untouched. ESCALATE has
a sink since GAS-7 HR-A (`packages/integration/governed-review` binds and consumes an
approval before the engine advances), but no queue or decision surface is built yet, so
a parked instance (row 9) is still not visible to a human. Risk Authority `production_mode` still raises
`ProductionContainmentError`. Clock discipline is enforced against the known monotonic
default; a deployment that hides a monotonic reading behind an unrecognisable wrapper
defeats the guard, and that residual is stated rather than papered over.
