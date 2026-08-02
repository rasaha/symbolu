# Transaction Boundaries

> One workflow stage = one atomic durable commit. A stage never becomes visible as
> committed unless **every** record it produced persisted, its workflow event was
> appended, and the workflow index was advanced — all in a single transaction.

## The stage transaction

`DurableShadowStore.commit_stage(...)` runs, inside one SQLite transaction:

1. `BEGIN`
2. `put_if_absent` each record envelope (idempotent identical / collision on differing content)
3. append one hash-linked workflow event (verifying previous-event linkage)
4. upsert the `workflow_index` pointer (current state, chain id, last event fingerprint)
5. `COMMIT`

Any exception triggers `ROLLBACK`. There is no partial visibility: if the event
or the index update fails, the stage's records do not appear either.

## Deterministic failure injection

For tests, the store exposes a single injection point, `_inject_at`, that raises
`InjectedFailure` at a named boundary — `after_records`, `after_event`, or
`before_commit`. Each is asserted to roll back the entire stage:

```
record_count == 0 and event_count == 0 and get_index(...) is None
```

This proves the atomicity guarantee at each internal boundary, not just on the
happy path.

## Idempotent re-commit

Because records use `put_if_absent` and events key on `event_id`, re-running a
stage with identical content is a no-op: no duplicates, no error. Re-ingesting the
same change event produces the same change fingerprint and adds no new records.
This makes a crash-then-retry safe.

## Stage → event mapping

Each public stage commits under a distinct, deterministic `event_id`
(`<revision_id>:<stage>`), so stages that share a workflow state (or don't
transition state) never collide in the journal. Evidence commits are keyed per
evidence id. Fail-closed transitions commit a `STAGE_FAILED_CLOSED` event (with or
without an accompanying record) so recovery can see exactly where a workflow
stopped.

## What is *not* transactional here

This is shadow persistence. A stage commit records that the shadow workflow
reached a state; it authorizes nothing and consumes nothing. There is no
two-phase commit against an external system, no reservation, and no
execution-consumption ledger — those are explicitly out of scope for 1C.
