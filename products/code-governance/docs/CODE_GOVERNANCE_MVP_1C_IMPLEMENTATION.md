# Code Governance MVP 1C — Implementation

> **Read-only, non-enforcing, execution disabled.** MVP 1C adds an **opt-in
> durable shadow audit store**, **restart-safe workflow recovery**, and
> **integrity-verified governance-chain reconstruction** to
> `ugence_code_governance` (PRs #1279 / #1280 / #1281). It is a *persistence*
> phase — it changes how the shadow record is stored, not what the product is
> allowed to do. There is still no GitHub write path, no merge credential, no
> execution provider, no reservation (`reserve_once`), and no authoritative
> execution-consumption ledger. `execution_status()` returns `DISABLED` in every
> mode.

## What 1C adds

| Capability | Module | Notes |
|---|---|---|
| Durable append-only, hash-linked store | `persistence/sqlite.py` | stdlib `sqlite3`, WAL, append-only triggers — `DURABLE_SHADOW_REFERENCE` |
| Immutable record envelope + event journal | `persistence/envelope.py` | content-addressed; previous-fingerprint chains |
| Canonical serialization + data minimization | `persistence/serialization.py` | rejects credential/PII field names and naive datetimes |
| Domain-separated integrity | `persistence/integrity.py` | reuses product-wide `fingerprints.domain_hash` |
| Atomic stage recorder + journal | `persistence/recorder.py`, `persistence/journal.py` | one transaction per workflow stage |
| Restart-safe recovery | `persistence/recovery.py` | advisory; no external call; no auto-transition |
| Integrity-verified reconstruction | `persistence/durable_reconstruction.py` | recomputes every fingerprint from the store |
| Offline-verifiable audit bundle | `persistence/audit_bundle.py` | canonical JSON; verifies with no store connection |

## Storage architecture

The in-memory repositories from MVP 1A/1B remain the **default** and the source
of truth for a live run. Durable mode is **additive**: when enabled, a
`DurableWorkflowJournal` records an append-only, integrity-verified **audit
projection** of each stage alongside the in-memory run. Enabling it never changes
the workflow state machine, the authority boundary, or the execution posture.

```
CodeGovernanceService(persistence_mode=DURABLE_SHADOW)   # or store_path="…​.db"
    -> in-memory run  (authoritative for the live workflow)
    -> DurableWorkflowJournal -> DurableShadowStore   (append-only audit projection)
```

Each public workflow stage maps to exactly one atomic durable commit: the
records that stage produced **plus** one hash-linked workflow event **plus** the
workflow index update. A stage is never visible as committed unless every record
for it persisted (see `TRANSACTION_BOUNDARIES.md`).

## The persisted chain

```
GOVERNED_CHANGE_IDENTITY -> EVIDENCE_RECORD* -> CLAIM_MANIFEST -> CLAIM_EVALUATION
  -> TAP_RESULT_PROJECTION -> GOVERNANCE_RECOMMENDATION -> DECISION_RECORD_PROJECTION
  -> CONTEXT_ENVELOPE_PROJECTION + PREPARED_MERGE_ACTION -> ACTIONGATE_RESULT_PROJECTION
  -> OPERATIONAL_SNAPSHOT -> CLEARANCE_REQUEST_PROJECTION + ACTION_CLEARANCE_EVALUATION
  -> HUMAN_INTERVENTION_ASSESSMENT -> GOVERNANCE_CHAIN + WORKFLOW_REVISION
  -> EXECUTION_DISABLED
```

Externally-owned authoritative records (DecisionRecord, CER, ActionGate result,
TAP result) are stored **only as projections** — reference + content hash +
minimal linkage. The durable store never re-issues authority. See
`PERSISTENCE_RECORDS.md`.

## Public API additions

```python
svc = CodeGovernanceService(persistence_mode=PersistenceMode.DURABLE_SHADOW)
# or a file-backed store that survives a restart:
svc = CodeGovernanceService(store_path="governance.db")

svc.resume_workflow(tenant_id, revision_id, current_identity=None)      # RecoveryResult
svc.reconstruct_chain_from_store(tenant_id, revision_id, …)             # DurableReconstructionResult
bundle = svc.export_governance_audit_bundle(tenant_id, revision_id)     # dict (canonical JSON)
CodeGovernanceService.verify_governance_audit_bundle(bundle)           # BundleVerification (offline)
svc.durable_store        # the DurableShadowStore, or None in-memory mode
svc.persistence_mode     # IN_MEMORY_SHADOW | DURABLE_SHADOW
svc.execution_status()   # always "DISABLED"
```

The default constructor (`CodeGovernanceService()`) is unchanged: in-memory,
`durable_store is None`, all existing tests and callers behave exactly as before.

## Restart-safe recovery

Recovery re-opens a store, verifies schema + record/event integrity, loads the
immutable workflow state, and reports the last committed stage and whether the
artifact is stale — with **no external call and no automatic transition**. The
caller decides what to do next. Recovery is not execution reconciliation and
never resumes an external side effect. See `RESTART_RECOVERY.md`.

## Integrity + tamper evidence

Every record carries a payload fingerprint and an envelope fingerprint; every
event links to its predecessor. Reconstruction and the audit bundle **recompute**
all of these. The `records`/`events` tables are append-only via SQLite triggers,
so ordinary tampering is refused outright; a raw mutation that bypasses the
triggers is caught by fingerprint recomputation (`INTEGRITY_FAILURE`). See
`DURABLE_SHADOW_STORE.md`.

## What 1C deliberately does **not** do

- No enforcement-grade durability claim; this is a shadow audit store.
- No `reserve_once`, no execution-consumption ledger, no dispatch/execute/merge.
- No GitHub write path, merge credential, webhook secret, or execution provider.
- No PostgreSQL/MySQL/Redis/Kafka/cloud DB/external infrastructure — stdlib
  `sqlite3` only, confined to `persistence/`.
- No auto-resume of external side effects after restart.
- No modification to the canonical Action Clearance package, ActionGate, TAP,
  Decision Authority, governance contracts, GPF, StoryGraph, or robotics ACP. The
  only changed product boundary is `products/code-governance/`.

See `DURABILITY_LIMITATIONS.md` for the full boundary statement and
`CODE_GOVERNANCE_NEXT_PHASES.md` for what a future enforcement phase would need.

## Validation

- `pytest products/code-governance` — full suite green (1A + 1B + 1C).
- Offline demo: `examples/durable_shadow_demo.py` (persist → restart → recover →
  reconstruct → bundle → staleness → tamper), asserted by `tests/test_durable_demo.py`.
- Machine-readable companions in `docs/`: `store_schema.json`, `record_types.json`,
  `workflow_event_types.json`, `recovery_statuses.json`,
  `audit_bundle_manifest_schema.json`, `data_minimization.json`,
  `persistence_acceptance_scenarios.json`, `public_api.json`.
