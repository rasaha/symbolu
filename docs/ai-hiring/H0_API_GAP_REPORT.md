# H0 — API Gap Report

Filed per the H0 discipline: where AI Hiring depends on a capability **not exposed
through the frozen public API**, no internal import was introduced, no workaround was
added, and the frozen platform was **not** modified. This report documents the one gap
encountered and its recommended future resolution.

## Summary

**Active/consumer code has no API gap.** Every governance symbol used by AI Hiring's
composition root, domain layer, application services, API facades, adapters, policies,
and domain models is available on `decision_governance.api`. All 22 consumer files were
migrated cleanly.

**The gap is confined to the backward-compatibility shim layer**, which is not consumer
code and is not newly introduced by H0.

## Gap 1 — Lifecycle transition tables & private authz modules are not public

### Missing API capability
The public API (`decision_governance.api.contracts`) deliberately **does not flatten** the
per-package lifecycle transition tables and internal helper constants. Absent from the
public surface:

- `ALLOWED_TRANSITIONS`, `is_legal_transition`, `TERMINAL_CASE_STATUSES`,
  `TERMINAL_REQUEST_STATUSES`, `TERMINAL_EXECUTION_STATUSES`, `HUMAN_AUTHORITIES`,
  `AUTHORIZED_STATUSES`, `RETRYABLE_STATUSES`, `OUTCOME_TO_STATUS`,
  `BUSINESS_OUTCOME_TO_STATUS`, `EXECUTABLE_AUTHORIZATION_OUTCOMES` (decisions / actions / execution)
- the private kernel service modules `_case_authz`, `_action_authz`, `_execution_authz`

This is **intentional**: `api/contracts.py` states the lifecycle tables "are enforced
inside the services and remain available on the internal modules for advanced use; the
lifecycle itself is frozen." The private `_authz` modules are implementation detail.

### Current internal dependency
Three groups of **backward-compatibility shim modules** (23 total) under `ai_hiring/`
re-export the *full* internal `__all__` (including the tables above) and/or alias private
kernel modules into `sys.modules` to preserve historical import paths:

- `ai_hiring.decision_cases`, `ai_hiring.action_requests`, `ai_hiring.executions`
  — `from decision_governance.{decisions,actions,execution} import *` + submodule aliasing
- `ai_hiring.services.<name>_service` (12) + `ai_hiring.services.audit_service`,
  `ai_hiring.repositories.<name>_repository` (3), `ai_hiring.policies.evidence_access_policy`
  — `sys.modules[__name__] = <kernel_module>` aliases
- `ai_hiring.services._case_authz` / `_action_authz` / `_execution_authz`
  — `sys.modules` aliases of private kernel modules

### Why the application needs it
It doesn't — for *behavior*. The shims exist only for **import-path compatibility** and
**object identity**: historical `ai_hiring.*` paths (and the historical test suite) resolve
to the identical kernel objects. `test_direct_kernel_adoption` asserts these shims exist and
resolve correctly; `test_action_request_lifecycle_audit` imports `is_legal_transition` /
`ALLOWED_TRANSITIONS` *through* the historical paths. Removing or re-pointing the shims at
`api` would (a) drop the non-public symbols those tests require, and (b) break the
`sys.modules` object-identity aliasing (the flattened API exposes symbols, not submodule
module objects).

### Can it be solved within application code?
**Yes — by leaving the shims exactly as they are.** They are a self-contained compatibility
layer, not consumption of platform behavior. No workaround is required and none was
introduced. The distinction is already codified in the platform architecture:
`test_direct_kernel_adoption` explicitly separates **active/canonical code** (which must
adopt the kernel directly — now via `api`) from the enumerated `KERNEL_SHIM_PREFIXES`
(which may mirror internals). H0 satisfies the former; the latter is out of scope by design.

### Recommendation for future platform evolution (optional, non-blocking)
No platform change is required for AI Hiring to proceed. If the platform team later wishes to
retire these shims entirely, a **purely additive, backward-compatible** option is:

- Expose **read-only lifecycle predicates** on the public API (e.g.
  `decision_governance.api.lifecycle` with `is_legal_transition(...)` and frozen,
  read-only views of the terminal-status / human-authority sets) — *without* exposing the
  mutable internal tables. Consumers and the historical tests could then depend on the public
  predicate rather than the internal table.
- This would be a **MINOR** platform change (additive surface), to be filed via
  `docs/platform-v1/MIGRATION_POLICY.md` and evaluated on its own merits. It is **not** a
  prerequisite for H1–H6.

Until then, the compat shims remain the correct, tested home for these internal references.

## Conclusion

- **Consumer-code API gap: none.** Migration is complete and clean.
- **Shim-layer internal references: expected, tested, and out of H0 scope.** No frozen-
  architecture workaround was introduced.
- **Completion criterion interpretation:** "AI Hiring imports exclusively from
  `decision_governance.api`" is satisfied for all **active/consumer** code. The 23
  compatibility shims are a documented, test-enforced exemption, consistent with the
  platform's own `test_direct_kernel_adoption` boundary.
