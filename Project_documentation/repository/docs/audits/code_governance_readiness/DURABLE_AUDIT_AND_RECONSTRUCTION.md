# Durable Audit & Reconstruction — Code Governance

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§6 persistence note, §17.4).
> Verified against live code at commit `3ec11e4e`. **Maturity is not invented; the design's persistence
> overstatement is corrected.**

## 1. What durable audit actually exists

| Store | Real & durable? | Properties | Path |
|---|---|---|---|
| StoryGraph `DurableAuditLog` | **Yes (reference-grade)** | SQLite, WAL, **DB-enforced append-only triggers**, hash-linked `record_digest`+`prev_digest`, `verify_chain()`, restart recovery, tenant-partitioned, `SCHEMA_VERSION="ctd.audit/1.0.0"` | `storygraph/src/ugence_storygraph/durable_audit.py:29` |
| `agentic/ledger` `GovernanceAuditStore` | **Yes (reference-grade)** | SQLite, WAL, SHA-256 hash chain, `verify_chain()`/`replay_verify()`, fail-closed on write error, JSONL export | `agentic/ledger/governance_audit_store.py:246` |
| `control_plane` `AuditLog` | Partial | append-only SHA-256 hash-chained; optional file-backed JSONL; fail-loud | `control_plane/decisions.py:66` |
| Decision Authority audit | **No (in-memory)** | `AuditEvent` has `payload_hash` (per-event fingerprint) but `previous_event_hash` is **RESERVED / never populated**; `InMemoryAuditRepository` (plain list) | `decision-authority/audit/event.py:41`, `audit/repository.py:23` |
| DA domain repositories | **No (in-memory)** | `DecisionCaseRepository`/`ActionRequestRepository`/`ExecutionRepository` are Protocol ports + `InMemory*` reference impls; one docstring says "Applications may inject a durable sink" | `decision-authority/repositories/*` |

**Caveats stated in-code:** StoryGraph's store is a "durable-interface reference, not production-grade
storage validation … tamper-evident, not tamper-proof" and defaults to `:memory:` unless a file path
is passed.

## 2. Can the chain be reconstructed today?

The required reconstruction:
```
GitHub event → evidence artifacts/refs → TAP request/result → recommendation/assessment →
authorized actor decision → DecisionRecord → CER + content_hash → ActionGovernanceRequest →
ActionGovernanceResult + fingerprint → ACP clearance → execution dispatch → execution observation →
resulting merge commit/tree
```

| Link | Record | Persisted durably? | Immutable? | Content-addressed? |
|---|---|---|---|---|
| evidence refs | product records | **No store** (evidence subsystem has none) | refs immutable | yes (digests) |
| TAP req/result | `AssertionGovernanceResult` (+ `fingerprint`) | no (in-flight) | frozen | yes (fingerprint) |
| recommendation | `RecommendationRecord` | DA in-memory | frozen | no hash |
| decision | `DecisionRecord` | DA in-memory | frozen | **no content_hash** |
| CER | `ContextEnvelopeRecord` | DA in-memory | frozen | **yes (`content_hash`)** |
| action authz | `ActionGovernanceResult` / `ActionAuthorizationResponse` | in-flight / DA in-memory | frozen | yes (`fingerprint`) |
| ACP clearance | `ClearanceVerdict` | **no durable ref** | ephemeral | no |
| dispatch | `ExecutionAttempt` | DA in-memory | frozen | `request_payload_hash` |
| observation | `ExecutionRecord` | DA in-memory | frozen | **yes (`content_hash`)** |
| merge commit/tree | product data in `observed_parameters`/`evidence_refs` | no store | — | product digest |

**Reference linking is present** (every record carries id references — `decision_id`, `cer_id`,
`authorization_id`, `action_request_id`, `external_result_id`, `evidence_refs`), so a chain can be
*assembled* in memory. **Durable persistence of the chain is not present in the decision kernel.**
Supersession is representable (`supersedes_*` + status enums). Tenant boundaries are preserved on
records. Hashes are content-addressed on CER/ExecutionRecord but **not on DecisionRecord** and **not
chained** in DA audit.

## 3. `CHAIN_INCOMPLETE`

Per design §4.7/§7, a broken governance chain must **fail closed**. `CHAIN_INCOMPLETE` should be a
**product workflow state** (terminal, non-executed) owned by the Workflow Service — not a neutral
contract error and not a DA state (DA has no executed/chain state). The Workflow Service reconstructs
the chain at dispatch time; any missing/mismatched link → `CHAIN_INCOMPLETE`, no dispatch.

## 4. Classification

**Durable audit persistence: PARTIAL.**
- Real, tested, hash-chained durable stores exist (StoryGraph `durable_audit`, `agentic/ledger`),
  but the **decision kernel — the primary subject of the audit — persists nothing durably** and its
  audit chaining field is reserved/unused.
- A unified, tamper-evident, hash-chained store spanning the full Code Governance chain is a
  **roadmap item**, consistent with the design's corrected persistence statement.

## 5. Required work

1. Provide (or adopt) a **durable, append-only, hash-chained store** for the decision-kernel records
   and the product workflow/audit records. The StoryGraph/`agentic` stores are viable reference
   patterns to productionize.
2. Persist evidence artifacts + immutable refs (evidence store — currently absent).
3. Add a **durable, one-time ACP clearance reference**.
4. Implement product-side chain reconstruction + `CHAIN_INCOMPLETE` fail-closed.
5. Optionally, add a `content_hash` to `DecisionRecord` (additive, DA-owned) or rely on the durable
   store's chaining to bind the decision — the latter avoids a contract change.

**These are pilot/production prerequisites (P0/P1), not architecture blockers.** The contracts carry
the references and hashes needed; the store to hold them durably must be built or adopted.
