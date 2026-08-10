# Risk Register (Prerequisite Closure)

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Risks introduced or clarified by closing the
four prerequisites, ranked, each with owner, blocking stage, and mitigation. Complements the merged
`docs/design/action_clearance/RISK_REGISTER.md` (not duplicated).

| ID | Risk | Sev | Class | Owner | Blocking stage | Mitigation |
|---|---|---|---|---|---|---|
| PR-R1 | No atomic reserve-once exists today; the current ledger is check-then-insert (race-prone) | **P0** | enforcement blocker | execution | enforced execution | `reserve_once` contract defined; durable atomic backend required before any enforced dispatch; shadow phases dispatch nothing |
| PR-R2 | Execution repository is in-memory only (no durability across restart) | **P0** | enforcement blocker | enforcement | execution | durable backend (SQL uniqueness / CAS) selected at PR-9; in-memory kept for tests only |
| PR-R3 | `ClearanceReceiptRepository` durable backend unbuilt | P1 | enforcement blocker | Workflow Service | enforcement | interface + guarantees fixed; durable impl at PR-8 |
| PR-R4 | Level-1 provenance (trusted-ingestion digest) is weaker than signed signals | P1 | enforcement/production | security | enforced / high-risk | evaluator built to check L1/L2/L3; required level is policy; raise to L2/L3 for enforcement/high-risk with no contract change |
| PR-R5 | No producer-key infrastructure in the repo today | P1 | production hardening | platform | high-risk domains | L3 deferred; L1 sufficient for shadow; key service is a platform prerequisite for L3 |
| PR-R6 | Uncertain-outcome reconciliation not yet implemented; risk of false release | P1 | enforcement blocker | execution | enforcement | state machine forbids auto-release of `OUTCOME_UNCERTAIN`; reconciliation gate required before reuse |
| PR-R7 | Tamper-evident hash-chained store is a roadmap item (CG §6) | P2 | production hardening | platform persistence | production | CER `content_hash` supports reconstruction meanwhile; receipt body immutable + content-addressed |
| PR-R8 | Source registry projection freshness (stale approval snapshot) | P2 | shadow/enforcement | integration/platform | shadow+ | immutable versioned snapshot; policy_refs pin the admitting policy version |
| PR-R9 | Merge-queue derived authorization (Q6) unresolved | P2 | future | Code Governance | Phase I | out of first profile; regenerated group = new lineage |
| PR-R10 | Product execution envelope adds a record type the neutral contracts don't carry | P2 | design | execution | enforcement | reuse `ExecutionIntent` pattern; do not widen neutral contracts |

## Highest risks

PR-R1 and PR-R2 are the two hard **P0 enforcement** risks: without an atomic, durable reservation, one-time
execution cannot be guaranteed. Both are contained by the phasing rule — shadow and recommendation modes
dispatch nothing, so the risk is realized only at enforced execution, which is explicitly gated on these
being resolved.
