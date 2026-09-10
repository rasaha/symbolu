# ADR — Model Egress Unit, reference vertical slice

**Status:** implemented under delegated authority; **ratifies nothing**.
**Package:** `packages/integration/model-egress-unit` (`ugence-model-egress-unit` 0.1.0)
**Maturity:** `REFERENCE_GRADE_SHADOW_ONLY` · `ENFORCEMENT_ENABLED = False` · `LIVE_VENDOR_EGRESS = False`

Evidence labels: `[V]` verified against this repository, `[I]` inferred,
`[R]` requires ratification, `[G]` gap.

## The load-bearing question

**Can the egress boundary be built without first answering D-1 to D-5?**

Yes, for everything in this slice, and the reason is narrow enough to state
exactly: this unit has no egress. It carries no HTTP client, no vendor SDK, no
credential reader and no destination configuration `[V]`, so nothing it does
crosses a boundary the owner has reserved. What it builds is the *place* a live
provider would land — the schema, the roles, the isolation, the digests, the
reconciliation — none of which depends on whether a live provider is ever
ratified.

The open decisions stay open, and are named below rather than assumed away.

## What was ratified, and what was not

`CR-1` to `CR-5` were ruled by the owner on 2026-09-05
(`ADR_UGENCE_REVIEW_SERVICE_COMPOSITION_ROOT_SCOPING.md` §5) `[V]`.

**CR-5 is not contradicted by this package.** It scopes *the worker's* egress:
"the worker's only egress is the configured JWKS host". This is a different
deployment unit — which is precisely what `SEPARATE_EGRESS_UNIT` means in D-2, and
why that option preserves CR-5 rather than amending it `[V]`. In this slice the
question does not even arise, because the unit's egress set is empty.

**CR-4 is preserved.** `ENFORCEMENT_ENABLED` is `False` and the maturity label is
`REFERENCE_GRADE_SHADOW_ONLY`, matching every package the worker composes `[V]`.

**D-1 to D-5 remain unanswered `[R]`.** The ballot records `SEPARATE_EGRESS_UNIT`
as the owner's *stated preference*, explicitly "recorded as a preference; the
decision is open" `[V]`. This slice is built along that preference and does not
convert it into a ratification. In particular:

- **D-1 (is inference an action?)** is untouched. This package is deliberately
  **not** wired into the governed execution hook, and nothing here decides whether
  a model call requires clearance. That seam is left unbuilt `[G]` — building it
  either way would have answered D-1 by implementation.
- **D-3 (credential custody)** cannot arise: there is no credential to custody,
  and `tests/test_boundaries.py` fails if any module reads the environment `[V]`.
- **D-4 (what is recorded)** is implemented as the *shape* `RECORD_DIGEST_AND_METADATA`
  can occupy, plus a purge that reduces a full exchange to exactly that. Which
  posture a deployment runs under is still D-4's to decide.
- **D-5 (concentration limits at execution)** is out of scope by instruction —
  the vendor-mix quantity is undefined and no counter is implemented `[G]`.

**A live provider still requires the CR-family ruling §4b names.** Nothing here
shortens that path.

## Decisions taken (reversible mechanics)

Each of these was mine to make under the delegation, and each is recorded because
it is the kind of thing a reader will otherwise have to reverse-engineer.

**A bespoke migration runner rather than Alembic.** Alembic orders by a
`down_revision` chain and identifies a revision by a hand-typed hash. The runner
here identifies a migration by *the digest of its own text* and refuses to
proceed if an already-applied migration no longer hashes to what the ledger
recorded. Editing an applied migration is the classic way two deployments diverge
silently — the file says one thing, the database contains another, and nothing
notices until a constraint that "exists" turns out not to. This turns that into a
refusal at startup naming the migration. It also adds no dependency, and the
repository's other `packages/` Postgres consumer has no migration tool at all `[V]`.

**Raw psycopg3 rather than SQLAlchemy Core.** `durable-execution` uses SQLAlchemy
because DBOS requires it `[V]`; this package does not use DBOS. The exchange is
eight statements, and it needs precise control over `SET LOCAL` and role-scoped
connections — plumbing an ORM layer would obscure rather than help.

**Three roles, with the owner unable to log in.** `meu_exchange_owner` owns every
object and has `NOLOGIN`; neither application role owns anything, so neither can
`DROP`, `ALTER` or disable a policy. A role nobody can authenticate as cannot be
phished, leaked or reused.

**Column-scoped grants for the worker.** The worker must purge content and stamp
an acknowledgement. A table-level `UPDATE` granting that would also let it set
`state` — so it could mark its own request `COMPLETED` with no exchange having
happened, or rewrite an outcome the unit recorded. `GRANT UPDATE (content,
content_purged_at)` gives exactly the needed capability and the database refuses
the rest `[V]`.

**`current_setting` without `missing_ok`.** The two-argument form returns `NULL`
when unset, `tenant_id = NULL` is false for every row, and a session that forgot
its tenant identity would read an empty exchange and conclude there was no work —
an answer indistinguishable from a correct one. The one-argument form raises `[V]`.

**Per-operation connections, and a refusal for anything else.** See the finding
below.

**Content digested separately from the record.** The request digest covers a
*content digest*, not the content. Inlining would make the request digest
unrecomputable the moment content was purged, leaving a tombstone whose central
claim could no longer be checked. Asserted directly: a purged row still rebuilds
its own request digest `[V]`.

## Two findings the tests produced

**`CREATE SCHEMA ... AUTHORIZATION` does not own the tables.** It sets the
schema's owner and nothing else; tables created inside it belong to whoever ran
the statement. The first implementation therefore left the migrating superuser
owning them — `FORCE ROW LEVEL SECURITY` was binding a role nobody used, and "the
owner cannot log in" was a true statement about a role that owned nothing. Caught
by asserting ownership directly rather than trusting the `AUTHORIZATION` clause;
fixed with an explicit `SET ROLE` in the migration `[V]`.

**`SET LOCAL` is scoped to a transaction, not to a savepoint.** Hand the exchange
a connection that already has a transaction open and `conn.transaction()` gives a
savepoint — the tenant identity then survives its release and stays live for
whatever the next caller does. Nothing fails; a later read just quietly belongs to
the wrong tenant, and no policy can catch it because the session genuinely *is*
that tenant by then. Measured, both directions: on an `IDLE` connection the
identity reverts and the next read fails closed; on an `INTRANS` one it leaks
`[V]`. The exchange now refuses a connection it cannot scope
(`UnscopableConnection`), and both the leak and the refusal are tests.

## Verification

114 tests, all passing against PostgreSQL 16.13 `[V]`. The suite **fails rather
than skips** without a server, and CI fails the job if any test skipped or if none
was collected — row-level security cannot be exercised against a stand-in, and for
a security boundary a skipped row that reads as a pass is worse than a red one.

Properties asserted with their mechanism removed, so each measures what it claims:

| Property | The mutation that proves it |
| --- | --- |
| `FORCE` binds the table owner | dropping `FORCE` makes the owner read across the tenant boundary |
| the wall-clock scan works | a planted `datetime.now()` trips it; a docstring mentioning it does not |
| the `SET LOCAL` refusal is needed | the raw leak is reproduced outside `Exchange` |
| refusals are terminal | a positive control answers, so "refuses everything" fails |
| the sweep is not a retry | a unit polling after reconciliation finds nothing |
| drift is refused | an edited applied migration; a pending step is proven not to land |

Repo gates: package CI coverage, package license and import boundaries all pass
with the new package present `[V]`.

## What this does not do

It composes nothing into the worker, changes no signed field, no canonical
serialization of any other package, no digest and no signature format. It adds no
external destination, no credential, no vendor dependency and no Railway
migration. It marks no gate identifier satisfied and changes no ratified pin.

It is not production-capable and is not a step that makes live egress closer to
authorized — only better prepared for, if it ever is.
