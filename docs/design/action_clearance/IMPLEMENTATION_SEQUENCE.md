# Implementation Sequence (PROPOSED — not executed)

No code is written in this phase. This is the future plan. Evidence tiers mirror the platform's other
migrations (shadow → equivalence → enforced).

| Phase | Goal | Prerequisites | Package ownership | Contracts | Tests | Acceptance | Rollback | Evidence tier |
|---|---|---|---|---|---|---|---|---|
| **A** Skeleton | package metadata, version, curated `api.py`, no integrations | naming (§5) locked | `packages/capabilities/action-clearance/` | none new | packaging + import tests | wheel builds; imports clean | delete package dir | build-only |
| **B** Neutral contracts + evaluator | request/result/signal/policy models, fingerprints, deterministic `evaluate` | A | package | `Clearance*`, `TrustedSignal`, `ClearancePolicy` | full [`acceptance_scenarios.json`](acceptance_scenarios.json); fingerprint stability | 25/25 scenarios pass; determinism proven | revert to A | unit + scenario |
| **C** In-memory reference adapters | deterministic signal fixtures; no networks | B | package (`ADAPTER_ONLY`) | `SignalAdapter` protocol | fixture-driven; no I/O | shadow evaluation reproducible | drop adapters | fixture |
| **D** ActionGate integration | exact-action binding; shadow only | B, C | Workflow Service | authorization projection | binding-mismatch tests | mismatches → BLOCK; no dispatch | disable integration | shadow |
| **E** Durable receipts | workflow persistence; content-addressed linkage; no dispatch | D; **receipt-owner decision** | Workflow Service | `ClearanceReceipt` | receipt lifecycle tests | receipts persisted & linked | stop persisting | shadow |
| **F** GitHub clearance profile | repo/PR/artifact/check signals; shadow | C, D | GitHub signal adapter | `github_exact_merge` profile | merge-tree/head/group tests | shadow clearance matches manual | disable profile | shadow |
| **G** Execution-ledger integration | one-time reservation, idempotency, replay protection | E, F; **ledger-owner decision** | execution ledger | replay key | race/duplicate tests | one reservation wins | fall back to no-dispatch | pilot |
| **H** Code Governance enforced merge | direct + squash merge only; no queue | G proven | Code Governance Workflow Service | — | end-to-end enforced tests | enforced merges gated by CLEAR | revert to shadow | enforced |
| **I** Merge queue + rebase | merge-group clearance; rebase support | H; exact-artifact proven | GitHub profile | merge-group / rebase | queue/rebase tests | group-identity clearance correct | disable queue/rebase | enforced |

## Discipline

- **Phases A–C** depend on none of the four open prerequisites and can begin as soon as the design is
  accepted.
- **Phase D onward** is **shadow-only** until Phase H; no real dispatch happens before the
  execution-ledger integration (Phase G) is proven.
- Each enforced phase (H, I) is preceded by a semantic-equivalence capture
  ([`DETERMINISM_AND_FINGERPRINTS.md`](DETERMINISM_AND_FINGERPRINTS.md)) and a shadow-calibration window.
- **Do not execute this plan in the design phase.** The next action is the P0 decisions in
  [`RISK_REGISTER.md`](RISK_REGISTER.md) / [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md).
