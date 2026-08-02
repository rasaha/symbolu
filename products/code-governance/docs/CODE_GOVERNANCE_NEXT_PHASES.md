# Code Governance — Next Phases (out of scope for MVP 1A)

MVP 1A stops after ActionGate shadow evaluation and chain reconstruction. The
items below are **not** implemented in this phase and must not be started under
it. They are recorded so the boundary is explicit.

## Enforcement rungs (design §7)

- **MVP 1B — Recommendation.** Publish governance status (check-run + summary);
  humans keep the existing merge path. No Ugence-driven merge.
- **MVP 1C — Enforced authorization.** Requires the complete chain, live
  clearance, exact-artifact binding, and controlled dispatch.

## Deferred components (each a separate, later change)

| Component | Why deferred |
|---|---|
| **Action Clearance** (immediate executability) | evaluated *after* ActionGate; introduced with its own runtime. `ACTION_CLEARANCE_V0_1_DESIGN_SPEC.md` is the future boundary only. |
| **Execution reservation** | one-time consumption at dispatch; belongs with 1C. |
| **GitHub Execution Provider** | a GPF-registrable `EXTERNAL_EXECUTION` provider modeled on `actiongate_provider/`; not created here. |
| **Merge-queue / rebase / deployment** | derived authorization for merge-group artifacts; deployment is a separate optional workflow. |
| **Change Intelligence analyzers** | mutation/fuzz/taint/complexity/performance engines; product currently consumes external evidence only. |
| **Production durable store** | append-only hash-chained persistence for the full chain; in-memory reference stores are used in 1A. |
| **Competitive Code Adjudication** | separate capability package (MVP2); advisory. |

## Invariants the next phases must preserve

- No new `ProviderKind` (reuse `ASSERTION_GOVERNANCE` / `ACTION_GOVERNANCE` /
  `EXTERNAL_EXECUTION`).
- No neutral-contract modification; no `cer.v2` unless owned by Decision
  Authority for a proven need.
- Dependency direction strictly downward: product → capabilities → neutral
  contracts; product → connector; product → GPF → GitHub execution provider.
- The Workflow Service never owns governance authority.
- "All automated checks passed" must never silently mean "binding approval
  granted."
