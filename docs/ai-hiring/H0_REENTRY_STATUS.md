# AI Hiring — Re-entry Status (post-H0)

Supersedes the "Existing DGM integration → Surface note" caveat in
`AI_HIRING_REENTRY_BASELINE.md`. After H0, AI Hiring is a clean consumer of the frozen
Platform v1.0 public API and is ready to begin H1.

## Current architecture

- **Composition root** `applications/ai_hiring/platform.py` wires the hiring domain
  (`domains.hiring`) to the governance engine using **only** `decision_governance.api`.
- **Domain layer** `domains/hiring/*` and **application** `ai_hiring/*` (services, API
  facades, adapters, policies, domain models, repositories) consume governance concepts
  **only** through `decision_governance.api` (`contracts`, `services`, `ports`,
  `repositories`, `identity`, `policy`, `audit`, `vocabulary`, `errors`, `common`).
- **Provider integration:** still **none** — TAP / ActionGate wiring is H2/H3 work (unchanged
  by H0). H0 was import-surface stabilization only.
- **Backward-compat shims** (`ai_hiring.decision_cases`, `.action_requests`, `.executions`,
  the `_kernel_module` service/repository/authz aliases, `policies.evidence_access_policy`)
  remain as a tested compatibility layer that aliases historical `ai_hiring.*` paths to the
  identical kernel modules. They are not consumer code. See `H0_API_GAP_REPORT.md`.

## Dependency diagram

```
   applications.ai_hiring  ──▶  domains.hiring  ──▶  decision_governance.api
            │                        │                      │  (public, frozen surface)
            └────────────────────────┴──────────────────────┘
                         (consumer code: api-only)

   decision_governance.api ──▶ decision_governance.<internal>   (kernel-internal; frozen)
                                        ▲
   ai_hiring.* compat shims ───────────┘   (path/identity aliases only — not consumer code)

   Reverse edges never exist: decision_governance never imports
   ai_hiring / domains / applications  (verified: dependency_report + freeze).
```

- **Direction:** `applications.ai_hiring → domains.hiring → decision_governance.api → (frozen kernel internals)`.
- The frozen platform never imports hiring (F20 / dependency-direction check: **0 violations**).

## Confirmation: active AI Hiring code consumes only the frozen public API

> **Authoritative status.** All active AI Hiring application, domain, service, adapter,
> repository, policy, API, and composition-root code now consumes the frozen
> `decision_governance.api` surface exclusively. Historical compatibility shims remain as an
> explicit, test-enforced exemption and are not used by active application code.

- **Active code:** 0 imports of `decision_governance` internals remain (all 22 active files migrated).
- **Object identity preserved:** governed record/service types still resolve to
  `decision_governance.*` (public API re-exports the same objects) —
  `test_direct_kernel_adoption` green.
- **Behavior unchanged:** `pytest ai_hiring` → **553 passed** (identical to baseline).
- **Frozen platform untouched:** freeze verification **PASS** (core-tree hashes + API snapshots).
- **Exemption:** 23 backward-compat shim modules intentionally mirror kernel internals
  (documented, test-enforced) — not consumer code.

### Baseline limitations (carried forward — not a clean whole-repo baseline)

The green results above are scoped to the platform-relevant packages. Two pre-existing,
unrelated conditions remain and must stay visible so later phases do not claim a clean
whole-repository baseline (detail in `H0_MIGRATION_REPORT.md` §7):

1. `classify_change` freeze-tooling self-test failure (out-of-band tooling; pre-existing).
2. Full-repository `_SymboluFinder` collection errors in unrelated experimental modules
   (temporal / trading2 / voice / tools; pre-existing).

## Readiness to begin H1

**Ready.** The stable foundation is in place:

- Consumer code depends only on the frozen, versioned public surface, so platform evolution
  behind `decision_governance.api` will not silently break hiring.
- The `domains.hiring` / `applications.ai_hiring` boundary is clean and the dependency
  direction is enforced by tests.
- No platform change is required for H1–H6 (every dependency is satisfied by the frozen
  public API; see the gap report for one optional, additive, non-blocking future
  recommendation).

Proceed to **H1 — Hiring Domain Completion** per `AI_HIRING_COMPLETION_ROADMAP.md`. Every
hiring change should still classify as `APPLICATION_LOCAL` (or `PATCH` for docs/tests) via
`python -m platform_freeze.classify_change`.
