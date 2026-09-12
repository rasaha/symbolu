# Ugence Model Egress Unit

**Version:** 0.5.0
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
| Four roles | `meu_exchange_owner` (**NOLOGIN**, owns every table), `meu_worker`, `meu_unit`, and since 0.3.0 `meu_migrator` (**NOLOGIN NOINHERIT**, holds nothing until it assumes the owner during a reviewed migration) |
| Forced RLS | `FORCE ROW LEVEL SECURITY` on every tenant table, so the owner is bound too |
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
| Limits (0.2.0) | LP-5 as constants: 8,192 input tokens, 1,024 output tokens, 10 genuine calls, USD 25, concurrency 1, one retry only before dispatch, no streaming; `check_request` refuses a request outside them, an unpinned model, `store`, tools or background; `CallBudget` reserves before dispatch and refunds nothing |
| Destination (0.2.0) | `OPENAI_RESPONSES`: exactly `https://api.openai.com/v1/responses`; `check_destination` refuses every other URL |
| Pinned-version custody (0.2.0) | `PinnedSecretVersionCustodyAdapter` over an injected reader (fake path only): refuses `latest`, a service-account-key identity and a rotation over 90 days; production-authoritative only under workload identity federation |
| Transport protection (0.2.0) | `require_transport_protection` refuses a production DSN without `sslmode=verify-full`; `protected_connect` applies it before the driver is imported; the error never echoes the DSN |
| Migrator identity (0.3.0) | `meu_migrator`: a separately controlled migration identity, member of the owner with `SELECT, INSERT` on the ledger only; migration 2 is applied through it in a reviewed run, never at import or startup |
| Tenant-bound identities (0.3.0) | `role_tenant_binding` plus a `RESTRICTIVE` policy `identity_binding` on every tenant table keyed on `current_user`: a bound login is refused every other tenant whatever its session setting claims; `postgres/provision.py` emits the statements for a per-tenant `LOGIN` member of each runtime group with **no password**, and reports every login member and whether it is bound |
| Runtime roles cannot escalate (0.3.0) | from a genuine `LOGIN` probe in each runtime group, DDL, `DISABLE`/`NO FORCE ROW LEVEL SECURITY`, `DROP POLICY`, `DROP CONSTRAINT`, `DROP TRIGGER`, a binding write, a ledger write, `SET ROLE` to the owner or the migrator, `CREATE ROLE` and `ALTER ROLE … BYPASSRLS` are each `InsufficientPrivilege` |
| Custody columns and the `genuine_call` constraint (0.3.0) | `custody_lease_id`, `custody_authority_id` outside every digest; `CHECK egress_result_genuine_call_requires_custody` replaces the reference-slice `CHECK egress_result_no_genuine_call` under the owner's confirmation (ADR §0.3.1). `EgressResult` refuses `genuine_call: true` without a verified `GenuineCallAdmission` for that request (ADR §0.6); `MET` is the outcome of the validation, never its prerequisite |
| Durable reservation (0.3.0) | `commissioning_budget` and `commissioning_reservation`: `Exchange.reserve_commissioning_call` is one `UPDATE … RETURNING` under the LP-5 ceilings, taken before dispatch; a `BEFORE UPDATE` trigger raises on any decrement and no role may delete. The in-memory `CallBudget` remains for unit tests and fake-transport development only |
| Migration compatibility (0.3.0) | fresh install applies `[1, 2]`; rows and digests written under migration 1 read back unchanged after migration 2; a failing upgrade leaves migration 1 intact |
| Step-8 designation shape (0.4.0) | `infrastructure.Step8Designation` and `check_step8_designation`: the seventeen mandatory designation obligations of LP-7 ruling 12, represented by 23 checked fields (obligation 14, spend-control evidence and classification, is two typed fields; two derived scope subfields; three attestation fields; `step8_field_counts()` states the counts from the definitions), each refused when missing, a placeholder, `latest` or any non-numeric version, secret-shaped, a human or default-compute identity, an unconstrained principal, a project-level binding, a key scope other than `api.responses.write`, an unclassified spend control, a model name offered as availability evidence, a production environment, or unverified; `check_rotation_plan` accepts only the owner's eight-step order and refuses destruction during initial commissioning; `rollback_permitted` needs both versions valid and owner-authorized. Supplies no value; changes no status |
| Typed, consumable live-validation authorization (0.5.0) | `authorization.LiveSyntheticValidationAuthorization`: the owner's typed, immutable record (ID, non-reusable nonce, owner, acceptance reference, validity window, `NON_PRODUCTION`, OpenAI organization/project/service account, provider, pinned model, exact endpoint, designation-record digest, validation-plan digest, bounded request digests, synthetic-only, calls ≤ 10, token limits, USD 25, concurrency 1, retries ≤ 1), pinned by digest in `MEU_LIVE_VALIDATION.json`; `admit_genuine_call` holds six conditions (G1 from the canonical record; present and canonical; every scope field; unexpired and unrevoked; nonce not replayed; durable capacity) and consumes the attempt durably before dispatch (migration 3's `commissioning_authorization` and `_consumption`, `ExchangeAuthorizationLedger`); a genuine result and a genuine row both need the consumption. A string, flag, name or altered constant never satisfies it |

## What 0.4.0 adds, and what it still cannot do

LP-7 (`ADR_UGENCE_LIVE_MODEL_PROVIDER_COMMISSIONING.md` §0.4) designed the non-production
step-8 infrastructure without supplying a value. This release carries the shape checks
(`infrastructure.py`) so that a placeholder, an alias, a forbidden identity or an
unverified string can never be accepted as a designation, and the eight-step rotation order of
ruling 6 as a checked sequence. Every one of the seventeen obligations stays `UNDESIGNATED`;
`COMMISSIONING_STATUS` is unchanged; accepting a designation admits neither a live call
nor a genuine result.

## What 0.3.0 adds, and what it still cannot do

Under the owner's confirmation of 2026-09-11 (`ADR_UGENCE_LIVE_MODEL_PROVIDER_COMMISSIONING.md`
§0.3), this release carries LP-6 step 4 as migration 2 — the migrator identity, tenant-bound
runtime identities, the constraint-only lifting of the reference-slice `genuine_call`
restriction, and the durable LP-5 reservation — and LP-6 step 6 as a **separate
distribution**, `ugence-model-egress-provider-openai` 0.1.0, which depends on this unit
and which this unit never imports. The adapter's only transport is an injected fake;
it has no credential access and no live network path.

Still no HTTP client, no vendor SDK, no credential reader and no destination
configuration here. `EgressResult` still refuses `genuine_call: true` without a verified admission, and the
canonical `live_synthetic_validation_authorization` is `NOT_GIVEN`, and
`MEU_LIVE_VALIDATION.json` stays at that status with every row unexecuted: fake-transport
evidence marks no row. The live transport, the unit's use of the durable reservation,
the owner-run verifier and the acceptance-report generator are step 7, behind the
step 8 designations; the credential is step 9 and the custody owner's act.

## What 0.2.0 adds, and what it still cannot do

The owner ratified the commissioning rulings LP-1 to LP-6 on 2026-09-11
(`ADR_UGENCE_LIVE_MODEL_PROVIDER_COMMISSIONING.md` §0): OpenAI `gpt-5.4-mini-2026-03-17`
at `/v1/responses`, Google Cloud Secret Manager as custody, the LP-5 limits and an
eleven-step order. This release carries the steps that order authorizes before any
credential exists: the ledger-kind schema, transport protection, the custody port with
an inert reference and a fake-path pinned-version adapter, the destination policy and
the limits (`MEU_LIVE_PROVIDER_DESIGNATION.json`, beside this file). There is still no HTTP client, no vendor SDK, no credential reader and no
destination configuration; `tests/test_boundaries.py` still fails the package if one
appears. `EgressResult` still refuses any provenance with `genuine_call` other than
`False`, and `MEU_LIVE_VALIDATION.json` is `BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS` with every
row unexecuted. The Google Secret Manager adapter is a separate distribution that does
not exist yet; the OpenAI adapter exists since 0.3.0 as `ugence-model-egress-provider-openai`.

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
deployment unit. `ugence-model-egress-provider-openai` depends on this unit; the reverse
import is refused by `tests/test_boundaries.py`. Only the `postgres` subpackage needs the driver; the records,
digests, providers and failure vocabulary stay importable without it — tested by
uninstalling `psycopg` and importing, not by reasoning about the import graph.
