# Owner ratification — the model-egress exchange's grants and tenancy

**Status:** open. Nothing here is ratified, nothing is implemented, and no table, column,
index or DDL is designed. Blocking: D-4 (`SPEC_MODEL_EGRESS_UNIT.md` §4.4) forbids designing
a content-bearing exchange table until this is ruled. No gate identifier of P3E-CTR or
GRW-CTR is marked satisfied and no ratified pin, gate record or evidence manifest is modified
by this document.

**The question:** in the model-egress exchange, what is the tenant authority — the database,
the row, or the code that reads the row?

**The audit's answer, and the reason this ballot exists:** today, in every store this
repository has, it is the code. **No `CREATE ROLE`, no `GRANT`, and no row-level security
statement exists anywhere in the repository** `[V]` — the only `CREATE SCHEMA` is the
worker's own (`durable-execution/postgres/schema.py:25`). So `SPEC_MODEL_EGRESS_UNIT.md`
§5.2's claim that the worker/MEU separation is "enforced by the database rather than by the
code's good behaviour" describes an intention, not an implementation `[G]`. The exchange
would be the first schema in this repository to need a database-enforced boundary, and the
first PostgreSQL table to carry a tenant at all.

## 1 — What the repository enforces today

| Finding | |
|---|---|
| **The worker's application schema does not model tenancy.** `ugence_art` has six tables keyed on `instance_id` and `budget_id`; the string "tenant" does not occur anywhere in `durable-execution`'s source `[V]` (`postgres/schema.py:22-86`) | There is no PostgreSQL precedent to copy. The exchange cannot inherit a pattern that does not exist. |
| **The audit ledger is tenant-partitioned, and by more than a column.** `tenant_id TEXT NOT NULL`, `UNIQUE (tenant_id, tenant_seq)` (`control-plane-root/…/ledger.py:111-124`), a **per-tenant hash chain** through `_head(tenant_id)` and `prev_digest` (`ledger.py:170-184, 201-207`), reads scoped `WHERE tenant_id=? AND correlation_id=?` (`ledger.py:235-237`) `[V]` | The strongest tenancy artefact in the repository. An entry cannot be moved between tenants without breaking a chain — but it is SQLite, one file, one process, one connection, so the enforcement is still the code's. |
| **Tenant is always a required argument, never inferred.** Every directory read takes `tenant_id` keyword-only (`authority-directory/…/directory.py:64-70`); `grant_id_for(tenant_id, …)` derives the grant's identity from it (`grants.py:56-57`) `[V]` | A grant cannot be reattributed to another tenant without becoming a different grant. This is the house pattern, and the exchange should not depart from it. |
| **A foreign tenant's row is refused as indistinguishable from an unknown one** — 404, not 403, "on purpose" (`governed-runtime-worker/…/authority_reads.py:190-192`) `[V]` | A settled ruling on what a mismatch may reveal. E-4 below asks whether the exchange follows it. |
| **A tenant mismatch is refused at construction** in data-use admission (`data-use-admission/…/declaration.py:164-168`) `[V]`, and `DataUseDeclaration.data_ref` removes the field that could carry content rather than trusting discipline (`declaration.py:127-130`) `[V]` | The repository's preferred shape: make the violation unrepresentable, not merely checked. |
| **The idempotency contract already carries the vocabulary.** `IdempotencyKey` has an opaque `partition` token, present so "the same key in two tenants stays two identities" (`governance-contracts/…/idempotency.py:28-31, 162, 191`) `[V]` | Unused by any store today `[G]`. If the exchange keys work by identity, this is the existing contract to bind to rather than a new one. |

## 2 — What the reference deployment actually is

**Single-tenant by configuration `[V]`.** `UGENCE_REVIEW_TENANT_ID` is required
(`config.py:64, 111, 151-155`), the service composes as `TenantMode.SINGLE_TENANT`
(`composition.py:299`), and the worker takes no tenant from any caller — "a foreign tenant's
grants are not expressible" (`authority_reads.py:9-11`). `MULTI_TENANT` exists in the code
(`identity.py:94-100`) and this deployment does not use it.

**One database credential `[V]`.** Both DSNs come from Railway's single
`DATABASE_PRIVATE_URL` and differ only in database name
(`RAILWAY_REFERENCE_DEPLOYMENT.md` §7.4). Railway provisions one database user; no runbook
step creates a second, and no code or gate would notice if none existed `[G]`.

**No transport protection on the database connection `[V]`.** `sslmode` is set nowhere in
the repository or the runbook, on either DSN. This does not change which option is right —
it means E-1's stronger options are not, on their own, sufficient: row-level security over an
unencrypted connection controls who may read a row, not who may observe it in flight.

**The consequence, stated plainly `[I]`:** an exchange added today would be reached by the
same credential that reaches `ugence_art` — exactly what §3.4 forbids — over a connection
with no declared transport protection, and nothing in the repository or the deployment would
detect either condition. The boundary is currently a sentence.

## 3 — The ballot

### E-1 — What enforces tenant isolation in the exchange?

| Option | Consequence |
|---|---|
| `APPLICATION_CHECK_ONLY` | Matches every existing store, including the tenant-chained ledger. Cheapest, and it makes the database a bystander: a bug or a misused connection reads another tenant's prompt text. Under D-4 the exchange holds real content, which is what makes this weaker here than where it is already accepted. |
| `ROW_LEVEL_SECURITY` | PostgreSQL refuses the read regardless of the query. First use of RLS in the repository; needs a session-level tenant setting, which is a new operator-visible mechanism and a new failure mode when it is unset. |
| `SCHEMA_PER_TENANT` | Strong and simple to reason about; turns tenant onboarding into DDL and does not fit a deployment whose tenant is configuration. |

### E-2 — How many database roles, and who creates them?

| Option | Consequence |
|---|---|
| `ONE_SHARED_CREDENTIAL` | The status quo. It contradicts §3.4 and §5.2 as written; ratifying it would mean amending both rather than leaving them describing something absent. |
| `TWO_ROLES_OPERATOR_CREATED` | A documented runbook step creating a worker role and an MEU role with distinct grants. Honest and inspectable; an unperformed step is silently insecure, exactly like the volume attachment already recorded as load-bearing and unenforced `[V]`. |
| `TWO_ROLES_BY_MIGRATION` | The roles and grants are code, so they exist wherever the schema exists. Requires a migration mechanism the repository does not have `[G]`. |

### E-3 — Who owns the exchange schema and may grant on it?

| Option | Consequence |
|---|---|
| `WORKER_OWNS` | The worker creates the exchange and grants the MEU its access. Fewest moving parts; the worker can then revoke or widen the MEU's access unilaterally, which makes the boundary the worker's to move. |
| `THIRD_ROLE_OWNS` | An owner role that is neither party holds the schema; both receive grants and neither can widen its own. The separation §3.4 asserts becomes structural. Adds a third credential to custody. |
| `MEU_OWNS` | Rejected on its face: the unit the boundary constrains would define it. |

### E-4 — How is a tenant mismatch on a leased request refused?

| Option | Consequence |
|---|---|
| `INDISTINGUISHABLE_FROM_UNKNOWN` | Follows the ratified authority-plane pattern `[V]`: the row is simply not there. Reveals nothing about other tenants' traffic; an operator debugging a misconfigured role sees an empty queue rather than an error. |
| `TYPED_REFUSAL_TO_THE_EXCHANGE` | The mismatch is written back as a refusal, so the worker's reconciliation driver observes it and the instance advances (§3.5's requirement that nothing stays parked). Names the condition, and thereby confirms to the wrong role that a request exists. |
| `BOTH_BY_DIRECTION` | Unclaimable rows are invisible; a mismatch detected *after* a claim is a typed refusal. More rules, and it is the only pair that satisfies both the disclosure ruling and the never-parked ruling. |

### E-5 — Does the exchange model tenancy at all, given `SINGLE_TENANT`?

| Option | Consequence |
|---|---|
| `MODEL_TENANCY_NOW` | Tenant is a first-class column and a claim predicate from the first table, unused in this deployment. Costs almost nothing now. |
| `DEFER_TO_MULTI_TENANT` | Simpler tables today; retrofitting a tenant column into a **content-bearing** table later means migrating rows that hold prompt and response text, under a retention policy that says they should already have been purged. |

## 4 — Recommendation

**E-1 `ROW_LEVEL_SECURITY`, E-2 `TWO_ROLES_OPERATOR_CREATED`, E-3 `THIRD_ROLE_OWNS`,
E-4 `BOTH_BY_DIRECTION`, E-5 `MODEL_TENANCY_NOW`.**

The reasoning is one observation. Everywhere else in this repository the store holds
identifiers, digests and decisions, and an application check over them is proportionate.
Under D-4 the exchange is the one place that holds **customer content**, briefly, reachable
by a unit that also holds vendor credentials in any deployment that has them. That is the
only store where the difference between "the code checks" and "the database refuses" is the
difference between a bug and a disclosure — so it is the one place worth paying for the
stronger mechanism, and paying once, before any table exists.

`TWO_ROLES_OPERATOR_CREATED` is recommended without enthusiasm. A runbook step that nothing
enforces is the same shape as the volume attachment already recorded as load-bearing and
unenforced `[V]`, and it will fail the same way. It is recommended only because
`TWO_ROLES_BY_MIGRATION` needs a migration mechanism that does not exist `[G]` — and if the
owner would rather commission that first, the ordering is defensible and this ballot should
wait for it.

## 5 — What this document does not do

It designs no table, column, index, constraint or DDL, and specifies no session variable,
policy expression or grant statement. It implements nothing. It does not authorize genuine
customer content or a genuine provider call — under §4.4 those additionally require
retention and deletion policy, transport protection and production credential custody, none
of which are in scope here.

**On ratification, the next artifact is the exchange schema specification**, which §4.4 gates
on this document and which must state its enforcement mechanism before its first column.
