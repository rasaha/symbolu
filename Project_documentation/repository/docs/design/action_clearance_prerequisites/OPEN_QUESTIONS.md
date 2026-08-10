# Open Questions (Post-Closure)

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Which of the merged design's open questions
this phase **closes**, and what remains — each remaining item with owner, required future PR, blocking
stage, and acceptance criterion. No item is left as vague "TBD."

## Closed by this phase

| Merged Q | Closed how | This-phase doc |
|---|---|---|
| **Q2** ClearanceReceipt persistence owner | Workflow Service owns the interface + lifecycle; package defines schema only | `RECEIPT_PERSISTENCE_INTERFACE.md`, `RECEIPT_LIFECYCLE.md`, `CLEARANCE_RECEIPT_SCHEMA.md` |
| **Q3** Signal provenance/integrity mechanism | Level-1 trusted-ingestion digest for MVP; L1/L2/L3 model; source-trust projection | `TRUSTED_SIGNAL_PROVENANCE.md`, `SIGNAL_SOURCE_REGISTRY.md`, `SIGNAL_NORMALIZATION_AND_DIGESTS.md` |
| **Q4** One-time-use ledger + atomic reservation | `reserve_once` contract + execution key; extend existing port; durable backend is the enforcement blocker | `EXECUTION_RESERVATION_CONTRACT.md`, `EXECUTION_KEY.md`, `EXISTING_EXECUTION_REPOSITORY_ASSESSMENT.md` |

## Remaining open items (each fully specified)

| ID | Question | Owner | Required future PR | Blocking stage | Acceptance criterion |
|---|---|---|---|---|---|
| PQ-1 | Which durable backend for the atomic reservation? (SQL uniqueness vs CAS document store vs event store) | execution | PR-9 | enforcement | one `ACQUIRED` under concurrency on the chosen store; scenarios 26–38 green |
| PQ-2 | Which durable backend for `ClearanceReceiptRepository`? | Workflow Service | PR-8 | enforcement | durable, tenant-isolated, read-after-write, optimistic concurrency |
| PQ-3 | When to raise signal integrity to L2/L3, and via which key service? | security/platform | PR (adapter) | enforced / high-risk | keyed/signed envelope verified at ingestion for gated signal types |
| PQ-4 | Source-registry projection cadence and versioning | integration/platform | PR-7 | shadow+ | immutable versioned snapshot consumed read-only by the evaluator |
| PQ-5 (merged Q6) | Merge-queue derived authorization minting | Code Governance | PR-12 | Phase I | new authorization per `merge_group_sha`; new lineage |
| PQ-6 (merged Q7) | Rebase exact-tree binding | Code Governance | PR-12 | Phase I | deterministic pre-merge tree or documented permanent deferral |
| PQ-7 (merged Q1) | Confirm `ugence-governance-contracts` dep vs stdlib-only leaf | packaging | PR-1 | package core | package builds with chosen dependency floor |
| PQ-8 (merged Q5) | Which controls are in the first product vs received elsewhere | product | PR-7 | profile scope | profile signal set finalized for direct+squash |

Every remaining item has an owner, a future PR, a blocking stage, and an acceptance criterion. None
blocks the **package core**; PQ-1/PQ-2/PQ-3 block **enforcement**; PQ-5/PQ-6 are **future** (Phase I).
