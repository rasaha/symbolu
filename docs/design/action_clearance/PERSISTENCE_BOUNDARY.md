# Persistence Boundary

The Action Clearance core is deterministic and **side-effect free**. It persists nothing.

## Who persists what

```text
Action Clearance core
    persists NOTHING (pure function: request → ClearanceResult)

Workflow Service
    persists ClearanceReceipt  (result + storage metadata + lifecycle state)
    links receipt → decision → CER → authorization via references/fingerprints

Execution / idempotency ledger  (today: ugence_decision_authority execution repositories)
    persists reservation, consumption, dispatch linkage, observation, reconciliation
    owns the authoritative one-time-use state
```

| Artifact | Persisted by | Not persisted by core |
|---|---|---|
| request | Workflow Service (as part of the receipt / audit) | ✅ core holds it transiently |
| signal references | Workflow Service | ✅ |
| result (`ClearanceResult`) | Workflow Service (inside `ClearanceReceipt`) | ✅ core returns it |
| receipt (`ClearanceReceipt`) | Workflow Service | ✅ |
| supersession | Workflow Service (`superseded_by`) | ✅ |
| expiry | derived from `valid_until` (no separate store needed) | ✅ |
| dispatch linkage | execution ledger | ✅ |
| observation linkage | execution ledger | ✅ |
| reservation / consumption | execution ledger | ✅ |

## Content-addressed linkage

The layers link **without shared mutable state** via content addresses:

```text
DecisionRecord.decision_id
  → cer_id + CER.content_hash
    → ActionGovernanceResult.fingerprint
      → ClearanceResult.result_fingerprint  (acr_…)
        → execution reservation keyed by the replay key (ONE_TIME_USE_AND_REPLAY.md)
```

Each link is a reference or a fingerprint; reconstructability (Code Governance §4.7 "prove the chain")
is achieved by walking these references, not by the core owning a store.

## Persistence maturity caveat

Per `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` §6, a production-ready tamper-evident hash-chained store is a
**roadmap item**, not available today; the CER already carries a `content_hash` usable for chain
reconstruction. The `ClearanceReceipt` persistence owner (shared durable audit service vs Workflow
Service) is an open implementation-prerequisite ([`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) Q2).

## Do not

Do **not** move durable workflow or execution-ledger responsibilities into the core to simplify
packaging. That would make Action Clearance a stateful workflow/idempotency system — a role the
authority boundary forbids ([`AUTHORITY_BOUNDARY.md`](AUTHORITY_BOUNDARY.md)).
