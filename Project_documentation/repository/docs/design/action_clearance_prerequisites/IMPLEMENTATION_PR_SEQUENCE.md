# Implementation PR Sequence

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. The concrete PR sequence that turns the
closed prerequisites into a package, aligned to the merged Phases A–I
(`Project_documentation/repository/docs/design/action_clearance/IMPLEMENTATION_SEQUENCE.md`). Each PR lists its blocking stage and
acceptance criterion. **None is executed in this phase.**

| PR | Scope | Prereqs required | Blocking stage | Acceptance criterion |
|---|---|---|---|---|
| PR-1 | Package skeleton `packages/capabilities/action-clearance/` (src-layout, version, errors) | none (gate open) | package core | package imports; `ugence-governance-contracts` optional dep resolves |
| PR-2 | Neutral contracts: `ClearanceRequest`/`ClearanceResult`/`TrustedSignal`/`SignalProvenance`/`ClearanceStatus`/`ClearanceReasonCode` | A (fingerprints), B (receipt schema refs) | package core | schemas match `clearance_receipt.schema.json` + `trusted_signal_provenance.schema.json`; fingerprints deterministic |
| PR-3 | Deterministic evaluator + reason-code catalog + fail-closed rules | A, freshness/conflict rules | package core | acceptance scenarios 1–10 pass in-memory; byte-stable fingerprints |
| PR-4 | In-memory reference adapters + `ClearanceReceiptRepository` protocol + in-memory impl | B interface | shadow integration | scenarios 11–18 pass in-memory |
| PR-5 | ActionGate authorization projection consumption (shadow only) | merged D12 | shadow integration | denials never clearable; projection read-only |
| PR-6 | Receipt lifecycle events + supersession/revocation (Workflow Service) | C | shadow integration | scenarios 19–25 pass |
| PR-7 | GitHub signal adapters (Level-1 provenance), `github_exact_merge` profile, shadow | A, CG mapping | shadow integration | real GitHub signals normalized; direct+squash shadow clearances |
| PR-8 | Durable `ClearanceReceiptRepository` backend (Workflow Service) | B guarantees (enforcement set) | **enforcement** | durable, tenant-isolated, read-after-write, optimistic concurrency |
| PR-9 | Atomic `reserve_once` behind `ExecutionRepository` port + durable backend | D (backend) | **enforcement (P0)** | scenarios 26–38 pass on the durable store; exactly one `ACQUIRED` under concurrency |
| PR-10 | GitHub execution provider dispatch/observe + reconciliation wiring | D, dispatch linkage | **enforcement** | one-time direct+squash merge; uncertain→reconcile |
| PR-11 | Code Governance enforced direct+squash merge | all four | **enforcement** | end-to-end enforced merge with full chain reconstruction |
| PR-12 | Merge queue + rebase (Phase I) | Q6, Q7 | future | out of first enforcement profile |

## Ordering rule

PRs 1–7 depend on **no** enforcement blocker and may proceed as soon as this closure PR merges. PRs 8–11
depend on the durable atomic backend and durable receipt store (the two enforcement blockers). PR-12 is
explicitly future.

## Owners

- Package core (PR-1–3): Action Clearance capability.
- Receipt persistence/lifecycle (PR-4, 6, 8): Workflow Service.
- Signal adapters/profile (PR-5, 7): integration + Code Governance.
- Execution reservation/provider (PR-9, 10): execution layer.
- Enforced merge (PR-11): Code Governance.
