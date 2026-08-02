# Open Questions

Decisions this design **resolves**, and the ones that **remain** as implementation-prerequisites.

## Resolved by this design

| # | Question | Resolution |
|---|---|---|
| R1 | Authorize or only clear? | **Clear-only.** Never mints authorization; robotics grant-minting not reused. |
| R2 | Which world does the package serve? | **Domain-neutral core + profiles**; GitHub exact-merge first. |
| R3 | New `Clearance*` family or reuse `ActionGovernance*`? | **New `Clearance*` family** that *consumes* the neutral `ActionGovernance*` seam (projection), not a fork of it. |
| R4 | Package dependency floor? | Recommended single downward dep on `ugence-governance-contracts>=0.1.0`; stdlib-only leaf is a legal fallback. |
| R6 | Result states? | Four: `CLEAR`/`HOLD`/`BLOCK`/`ESCALATE`; finer conditions are reason codes; `DENY` not used. |
| R9 | Naming? | **Action Clearance** / `ugence_action_clearance` / `ugence-action-clearance`; bare "ACP" prohibited. |
| R10 | GPF relationship? | Directly-invoked capability; **no new `ProviderKind`**. |

## Remaining (implementation-prerequisites — owned by the platform, not this spec)

| # | Question | Owner | Blocks |
|---|---|---|---|
| Q1 | Confirm the recommended `ugence-governance-contracts` dependency vs stdlib-only leaf | packaging | Phase A/B contract shape |
| Q2 | **ClearanceReceipt persistence owner** — shared durable audit service vs Workflow Service | platform persistence | Phase E |
| Q3 | **Signal provenance/integrity mechanism** — how `integrity_digest`/`provenance_ref` are produced & verified per `source_kind` | security/platform | Phase C/D signal trust |
| Q4 | **One-time-use ledger owner + atomic reservation contract** — confirm the execution ledger and replay-key reservation API | execution | Phase G, enforced merge |
| Q5 | Which controls (actor identity, credentials, incidents, duplicate-dispatch) are in the first product, and which are received vs owned elsewhere | product | profile scope |
| Q6 | Merge-queue derived-authorization flow — who mints the merge-group `ActionGovernanceRequest`? | Code Governance | Phase I |
| Q7 | Rebase support — accept the MVP deferral, or invest in server-side exact-tree computation? | Code Governance | Phase I |
| Q8 | Console reconciliation — migrate the console onto the core, or keep it as a separate domain expression? | console | future |

None of the remaining questions is an authority- or trust-semantics gap; they are persistence, provenance,
ledger, and scope decisions. Phases A–C proceed without them.
