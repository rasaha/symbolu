# Ugence Model Egress Unit

**Version:** 0.2.0
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

**D-1 through D-5 were ratified on 2026-09-10**, together with the exchange grants
and tenancy and the retention horizons, and this package is written against them
(`SPEC_MODEL_EGRESS_UNIT.md`, `OWNER_RATIFICATION_MEU_EXCHANGE_TENANCY.md`). What
is still unauthorized is a *live* provider: D-3 keeps provider custody out of this
deployment, and CR-1 admits only one companion deployment unit, so the MEU's
boundary is specified while its commissioning as a running unit is not.

## What it provides

| Concern | How |
| --- | --- |
| Dedicated schema | `meu_exchange`, nothing in `public` but the migration ledger |
| Three roles | `meu_exchange_owner` (**NOLOGIN**, owns every table), `meu_worker`, `meu_unit` |
| Forced RLS | `FORCE ROW LEVEL SECURITY` on both tables, so the owner is bound too |
| Required tenant identity | `current_setting('ugence.tenant_id')` **without** `missing_ok` — an unscoped session raises rather than reading an empty exchange |
| Application checks | every row read back is re-checked against the caller's tenant, independently of the policy |
| Authorization binding | clearance reference and digest, tenant, authorized vendor and model, policy and reservation identity — **verified** by the unit, never decided by it |
| Ordered context | `{unit_id, text, token_count}` in run order; the digest binds identifiers, exact text and order |
| Complete digests | request digest binds tenant, schema version, content digest, vendor/model binding, parameters and clearance identity |
| Reconciliation | before dispatch an expired lease is claimable again; after possible dispatch it is terminal `OUTCOME_UNKNOWN` |
| Consumption | acknowledgement starts a one-hour grace — it does not gate the 24-hour deadline |
| Retention | per artifact, the earlier of ack + 1h and creation + 24h, failing closed at the hard deadline |
| Purge | content destroyed on both sides; the approved tombstone survives |
| Migrations | ordered, digest-pinned, all-or-nothing; a drifted schema is refused |
| Custody port (0.2.0) | `ModelCredentialCustodyPort` mirroring the credential broker's port; a `CredentialLease` whose secret is reachable only through `use(consumer, now=…)`, absent from `repr`, records, equality and pickling; every materialization audited as identifiers and digests; the only adapter shipped is the inert `ReferenceCustodyAdapter`, never production-authoritative, refused in production |
| Ledger kinds (0.2.0) | five `meu.*` kinds with allowlists; `ledger_payload` refuses unknown keys, content- or credential-bearing keys at any depth, and strings long enough to be content (D-4) |
| Transport protection (0.2.0) | `require_transport_protection` refuses a production DSN without `sslmode=verify-full`; `protected_connect` applies it before the driver is imported; the error never echoes the DSN |

## What 0.2.0 adds, and what it still cannot do

The owner designated OpenAI as the vendor and Google Secret Manager as the custody
store on 2026-09-11 (`MEU_LIVE_PROVIDER_DESIGNATION.json`, beside this file). The
ballot that commissions them (`ADR_UGENCE_LIVE_MODEL_PROVIDER_COMMISSIONING.md`,
LP-1 to LP-6) is not yet ruled, so this release carries only what D-3 already permits:
the custody **port** with an inert reference, the ledger-kind schema and transport
protection. There is still no HTTP client, no vendor SDK, no credential reader and no
destination configuration; `tests/test_boundaries.py` still fails the package if one
appears. `EgressResult` still refuses any provenance with `genuine_call` other than
`False`, and `MEU_LIVE_VALIDATION.json` is `BLOCKED_PENDING_OWNER_RULINGS` with every
row unexecuted. The Google Secret Manager adapter and the OpenAI adapter are separate
distributions that do not exist yet.

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
*content digest* whose preimage is the ordered `[unit_id, exact_text]` pairs — a
composed commitment to the exact text, not an identifiers-only one. **The owner
ratified this on 2026-09-11 as satisfying D-4**; inlining plaintext into the outer
digest is not required and no `v2` is authorized.

After a purge the tombstone can verify the integrity and linkage of the retained
digest chain, and can answer "was it this?" for a reader who already holds a
candidate. It cannot reconstruct the deleted plaintext or re-prove what it was to
anyone holding no candidate — the chain survives, the content does not.

**The reservation is never released.** Neither lease expiry nor content purging
releases the vendor allocation an `OUTCOME_UNKNOWN` conservatively consumed —
purging the content does not purge the obligation, and a database CHECK makes
"released" unrepresentable rather than merely unwritten.

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
deployment unit. Only the `postgres` subpackage needs the driver; the records,
digests, providers and failure vocabulary stay importable without it — tested by
uninstalling `psycopg` and importing, not by reasoning about the import graph.
