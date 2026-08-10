# Action Clearance Prerequisite Closure — Executive Summary

**Status:** PROPOSED · documentation-only · `action_clearance.prerequisites.v0.1`. No package created, no
runtime module, no source moved, no runtime behavior changed, no `ProviderKind` added, no neutral
contract modified, no freeze artifact touched.

## What this phase is

The merged Action Clearance v0.1 design (PR #1276) resolved authority and trust semantics but left **four
implementation-prerequisites** open. This phase **closes** them at the interface/contract level so a
decision can be made on whether canonical package implementation may begin. It is architecture,
interface-definition, persistence-boundary, trust-model, and execution-safety work — **not**
implementation.

## The four prerequisites and their closure

| # | Prerequisite | Closure | Blocking level |
|---|---|---|---|
| A | Trusted-signal provenance & integrity | **CLOSED_BY_NEW_PRODUCT_INTERFACE** — `SignalProvenance` projection; Level-1 trusted-ingestion digest for MVP; L1/L2/L3 model; source-trust projection | none for core; L2/L3 for enforcement |
| B | ClearanceReceipt persistence interface | **CLOSED_BY_NEW_PRODUCT_INTERFACE** — `ClearanceReceiptRepository` protocol; **Workflow Service owns** the interface + lifecycle; package defines schema only | durable backend = enforcement |
| C | Durable receipt-lifecycle ownership | **CLOSED_BY_NEW_PRODUCT_INTERFACE** — 5-state lifecycle (ISSUED/EXPIRED/SUPERSEDED/REVOKED/INVALIDATED), derived expiry, append-only events, immutable body | none for core |
| D | Atomic one-time execution reservation | **CLOSED_BY_NEW_PRODUCT_INTERFACE (contract)** + **EXTEND_BEHIND_EXISTING_INTERFACE** — `reserve_once` contract; durable atomic backend is the **P0 enforcement blocker** | **enforcement (P0)** |

## Key decisions

- **Signal trust:** MVP shadow = **Level 1** (approved adapter + `content_digest` + controlled ingestion
  boundary). Recommendation raises consumption/authorization signals to L2; enforcement floor is L2, L3
  for high-risk. Public-key signatures are **not** required for MVP (no key infra today; shadow never
  executes).
- **Signal source registry:** owned by the platform integration layer; the evaluator consumes an
  **immutable versioned projection** — the package is not an integration-management system.
- **Fingerprints:** three domains — `signal_content_fingerprint`, `signal_provenance_fingerprint`,
  `signal_bundle_fingerprint` — over the merged `action_clearance` SHA-256 pattern.
- **Receipt:** content-addressed `receipt_id = acr_<result_fingerprint>`; immutable body; four field
  partitions (evaluator / persistence / lifecycle / reconstruction); Workflow Service owns persistence.
- **Lifecycle:** five states; expiry **derived** from `valid_until`; transitions are append-only events;
  the evaluator never mutates a stored receipt. `CONSUMED/EXECUTING/EXECUTED/FAILED` stay on execution
  records, not the receipt.
- **Execution key:** `(tenant_id, authorization_ref, authorized_action_fingerprint, target_ref,
  operation)` — the merged replay key, mapping onto the existing `execution_idempotency_key`.
- **Reservation:** `reserve_once(...) → {ACQUIRED, ALREADY_RESERVED, ALREADY_DISPATCHED,
  ALREADY_COMPLETED, CONFLICT, INVALID_RECEIPT, EXPIRED_CLEARANCE, STALE_AUTHORIZATION}`; **exactly one
  `ACQUIRED`** per key; uncertain outcomes require reconciliation before reuse.
- **Existing repo:** the decision-authority `ExecutionRepository` provides **check-then-insert**
  idempotency, **not** atomic reserve-once — extend the port with `reserve_once` + a durable backend.
- **Neutral contracts unchanged:** correlation the neutral contracts omit (receipt/authorization/action
  refs) is carried by a **product execution envelope** reusing the `ExecutionIntent` pattern.

## Baseline (reproduced at default HEAD `154b24b9`, Merge PR #1277)

| Check | Result |
|---|---|
| `python -m platform_freeze.verify --manifest platform/PLATFORM_FREEZE_V1.json` | **PASS** — substantive digest `d4ad77e16516e0db6bf2faf3275c8ac8351644e7561d33f157bb55b5a174a1a6` (**unchanged**) |
| `python scripts/validate_terminology.py` | **PASS** (8 governed docs) |
| `python scripts/check_doc_links.py` | **PASS** (21 links) |
| `platform_freeze.dependencies.dependency_report()` | **passed=True, 0 violations** |
| Robotics local freeze (`acp/ACP_V1_FREEZE.md`) | **13/13 module hashes byte-accurate**; combined `8f8660e293308cf94c983a26a2ae69c9` (**unchanged**) |
| Governance Contracts / GPF / Decision Authority / Robotics Autonomous Control Plane | **45 / 84 / 79 / 112 passed** |
| Action Clearance runtime package | **does not exist** (module unimportable) |

Pre-existing, non-attributable failures remain as recorded in prior baselines
(`test_classify_change_reports_evidence`, `test_hiring_baseline_discovery`,
`test_ground_truth_two_class_and_deterministic`).

## Gate outcome

All nine package-start gate conditions are **TRUE** (`PACKAGE_START_GATE.md`); there are **zero
`PACKAGE_CORE_BLOCKER`s**. The durable atomic reservation backend and the durable receipt store remain
**enforcement blockers**.

## Verdict

> **ACTION CLEARANCE PREREQUISITES PARTIALLY CLOSED — package core may begin, but named enforcement
> prerequisites remain** (durable atomic `reserve_once` backend + durable `ClearanceReceiptRepository`,
> plus L2/L3 signal integrity for enforcement).

The request/result and receipt/reservation **contracts** no longer depend on any unresolved semantic, so
Phases A–C (skeleton, neutral contracts + deterministic evaluator, in-memory reference adapters) may
begin immediately. Enforced execution must not begin until PQ-1/PQ-2 (durable atomic backends) are
resolved.
