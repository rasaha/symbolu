# Ugence Model Egress Unit

**Version:** 0.1.0
**Maturity:** `REFERENCE_GRADE_SHADOW_ONLY` · `ENFORCEMENT_ENABLED = False` · `LIVE_VENDOR_EGRESS = False`

The reference exchange between the governance worker and a model call, as a
separate deployment unit.

## This package cannot call a model vendor

No HTTP client, no vendor SDK, no credential reader, no destination
configuration. The two providers it ships answer from a hash or refuse outright.
That is not a configuration setting — `tests/test_boundaries.py` parses every
module and fails if any of them imports something that could open a socket, reads
the environment, or reaches a wall clock.

What *is* real is the boundary. The exchange, the roles, the row-level security
and the reconciliation are built and tested against PostgreSQL 16, so that a live
provider — **if one is ever ratified** — has somewhere to land.

Whether a live provider may run here at all is an open owner decision:
`docs/architecture/OWNER_RATIFICATION_LIVE_MODEL_PROVIDER.md`, D-1 through D-5.
This package neither answers it nor presumes an answer, and deliberately does not
wire itself into the governed execution hook — that seam is D-1's to decide.

## What it provides

| Concern | How |
| --- | --- |
| Dedicated schema | `meu_exchange`, nothing in `public` but the migration ledger |
| Three roles | `meu_exchange_owner` (**NOLOGIN**, owns every table), `meu_worker`, `meu_unit` |
| Forced RLS | `FORCE ROW LEVEL SECURITY` on both tables, so the owner is bound too |
| Required tenant identity | `current_setting('ugence.tenant_id')` **without** `missing_ok` — an unscoped session raises rather than reading an empty exchange |
| Application checks | every row read back is re-checked against the caller's tenant, independently of the policy |
| Complete digests | canonical request and response digests over every field, content by digest |
| Reconciliation | expired leases become terminal `OUTCOME_UNKNOWN`, never a retry |
| Consumption | a result is acknowledged before its content may be purged |
| Purge | content destroyed on both sides; digests survive as a tombstone |
| Migrations | ordered, digest-pinned, all-or-nothing; a drifted schema is refused |

## The three decisions worth knowing

**A refusal is terminal.** A retriable condition is not a refusal; it is a request
that is still pending. Every `RefusalReason` names a condition re-running cannot
change, and there is no `OTHER` member.

**`OUTCOME_UNKNOWN` is terminal too.** When a lease expires the exchange cannot
tell whether the vendor was called. Returning the request to the queue would turn
"we don't know" into "we did it twice" — and an unknown outcome can be reconciled
by a human, whereas a duplicated side effect cannot be undone. Some requests that
never reached a vendor will therefore be recorded as unknown and need
re-submitting. That is the trade, taken deliberately.

**Content is digested separately from the record.** The request digest covers a
*content digest*, not the content. That is what keeps a purged row verifiable: the
tombstone still answers "was it this?" for a reader holding a candidate, and still
cannot answer "what was it?" for anyone.

## Running the tests

The suite needs a real PostgreSQL server and **fails rather than skips** without
one — row-level security cannot be exercised against a stand-in, and a skipped row
that looks like a pass is worse than a red one.

```bash
export UGENCE_MEU_TEST_PG="postgresql://postgres@127.0.0.1:5433/postgres"
cd packages/integration/model-egress-unit && python -m pytest -q
```

## Dependency direction

```
psycopg (third party)
    ▲
ugence-model-egress-unit
```

No first-party dependency, so it cannot drag the governance kernel into an egress
deployment unit. Only the `postgres` subpackage imports the driver; the records,
digests and providers stay importable without it.
