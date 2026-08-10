# Receipt Persistence Guarantees

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Companion to
`RECEIPT_PERSISTENCE_INTERFACE.md`. Classifies each guarantee by the operating mode that first requires
it, so the package core can begin before enforcement-grade durability exists.

## Guarantee classification

| Guarantee | Classification | Notes |
|---|---|---|
| append-only | **REQUIRED_FOR_SHADOW** | matches the existing `ExecutionRepository` append-only model; cheap even in-memory |
| immutable body | **REQUIRED_FOR_SHADOW** | evaluator fields never change once written |
| content-addressed identity | **REQUIRED_FOR_SHADOW** | `receipt_id = acr_<result_fingerprint>` makes puts idempotent |
| idempotent put | **REQUIRED_FOR_SHADOW** | re-put of identical result → same receipt (scenario 12) |
| tenant isolation | **REQUIRED_FOR_RECOMMENDATION** | reads/writes scoped by `tenant_id`; the existing repo keys idempotency by `(tenant_id, key)` |
| read-after-write consistency | **REQUIRED_FOR_RECOMMENDATION** | a persisted receipt must be immediately retrievable for the chain check |
| optimistic concurrency | **REQUIRED_FOR_ENFORCEMENT** | version-guarded lifecycle-event append (mirrors `VersionConflictError`) |
| atomic supersession link | **REQUIRED_FOR_ENFORCEMENT** | `supersede_receipt` links old→new atomically so lineage never forks silently |
| durable audit reference | **REQUIRED_FOR_ENFORCEMENT** | the chain must reconstruct after process restart — needs a real store |
| access control | **REQUIRED_FOR_ENFORCEMENT** | permission-gated reads/writes, as DA gates repository access by permission |
| retention | **PRODUCTION_HARDENING** | policy-driven retention windows |
| encryption at rest | **PRODUCTION_HARDENING** | backend responsibility |
| tamper-evident hash chaining | **PRODUCTION_HARDENING** | per CG §6, a roadmap item; CER `content_hash` already supports reconstruction meanwhile |

## Does an existing implementation satisfy these?

The `InMemoryExecutionRepository` (decision-authority) demonstrates the **shadow/recommendation** set:
append-only version chains, immutable snapshots, `content_hash`, `(tenant_id, key)` idempotency indexes,
read-after-write within the process. It does **not** provide the **enforcement** set: it is in-memory
(no durability across restart), has no optimistic-concurrency-guarded lifecycle append for receipts, and
no access control on reads. Therefore:

- **Shadow / recommendation guarantees:** `CLOSED_BY_EXISTING_REPOSITORY_CAPABILITY` — the append-only
  in-memory pattern is directly reusable behind the new `ClearanceReceiptRepository` port.
- **Enforcement guarantees:** `OPEN_IMPLEMENTATION_DECISION` — a durable backend for the Workflow
  Service (SQL or document store) is a Phase-E deliverable; it is an **enforcement blocker**, not a
  package-core blocker.

## No runtime code here

This phase records the required guarantees and their staging. It creates no repository, no backend, and
no migration. Selecting the durable backend is deferred to `EXECUTION_RESERVATION_CONTRACT.md`'s
neutrality analysis and the Workflow Service's own implementation phase.
