# Package-Start Gate

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Defines the exact gate for beginning
canonical Action Clearance package implementation, and classifies every remaining blocker by the stage it
blocks. Machine-readable: `implementation_gate.json`.

## Gate conditions (all must be TRUE to begin the package core)

| Condition | State | Evidence |
|---|---|---|
| signal provenance model is stable | **TRUE** | `TRUSTED_SIGNAL_PROVENANCE.md` (Level 1 MVP; additive projection) |
| signal fingerprint rules are stable | **TRUE** | `SIGNAL_NORMALIZATION_AND_DIGESTS.md` (three domains over merged pattern) |
| receipt schema is stable | **TRUE** | `CLEARANCE_RECEIPT_SCHEMA.md` + `clearance_receipt.schema.json` |
| receipt repository owner is selected | **TRUE** | Workflow Service (`RECEIPT_PERSISTENCE_INTERFACE.md`) |
| receipt lifecycle semantics are stable | **TRUE** | `RECEIPT_LIFECYCLE.md` (5-state, derived expiry, append-only) |
| execution key is stable | **TRUE** | `EXECUTION_KEY.md` + `execution_key.schema.json` |
| atomic reservation semantics are stable | **TRUE** | `EXECUTION_RESERVATION_CONTRACT.md` (`reserve_once` contract) |
| existing repository reuse decision is recorded | **TRUE** | `EXISTING_EXECUTION_REPOSITORY_ASSESSMENT.md` (extend port) |
| no authority boundary remains ambiguous | **TRUE** | merged design D1–D19; nothing reopened here |

**All nine gate conditions are TRUE.** The request/result contracts no longer depend on any unresolved
semantic. Therefore the **package core (Phases A–C: skeleton, neutral contracts + deterministic
evaluator, in-memory reference adapters) may begin.**

## Blocker classification

| Blocker | Class | Blocks |
|---|---|---|
| durable `ClearanceReceiptRepository` backend | `ENFORCEMENT_BLOCKER` | enforced merge (Phase E/H) |
| receipt lifecycle/invalidation wiring in Workflow Service | `SHADOW_INTEGRATION_BLOCKER` | shadow with real receipts (Phase E) |
| signal adapters emitting Level-1 provenance | `SHADOW_INTEGRATION_BLOCKER` | shadow with real signals (Phase C/D/F) |
| atomic `reserve_once` durable backend | `ENFORCEMENT_BLOCKER` (P0) | enforced execution (Phase G/H) |
| Level-2/3 signal integrity (keyed/signed) | `ENFORCEMENT_BLOCKER` / `PRODUCTION_BLOCKER` | enforced / high-risk |
| tamper-evident hash-chained store | `PRODUCTION_BLOCKER` | production audit hardening |
| merge-queue derived authorization (Q6) | `ENFORCEMENT_BLOCKER` | Phase I (not first profile) |
| rebase exact-tree binding (Q7) | `ENFORCEMENT_BLOCKER` | Phase I (not first profile) |

## The explicit allowance

> It is acceptable for the package core to begin while durable execution infrastructure remains an
> enforcement blocker, provided the request/result contracts no longer depend on unresolved semantics.

That precondition is satisfied: none of the four `PACKAGE_CORE_BLOCKER`s remains. There are **zero**
`PACKAGE_CORE_BLOCKER`s. The remaining blockers are all `SHADOW_INTEGRATION_BLOCKER`,
`ENFORCEMENT_BLOCKER`, or `PRODUCTION_BLOCKER`.

## Verdict input

Four prerequisites closed at the interface/contract level; no package-core blocker remains; the atomic
durable reservation backend remains an enforcement blocker. → **PREREQUISITES PARTIALLY CLOSED — package
core may begin, enforcement prerequisites (durable atomic reservation + durable receipt store) remain.**
