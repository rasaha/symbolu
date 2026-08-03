# Changelog — ugence-actiongate-provider

All notable changes to the canonical ActionGate distribution are documented here.

## [0.1.0] — canonical package migration

First independent distribution of the ActionGate action-governance provider.

### Migration (no behavior change)

- Established the single canonical source tree
  `packages/providers/actiongate/src/ugence_actiongate_provider` (history-preserving
  relocation from the monorepo `actiongate_provider/` tree; internal framework
  imports rewritten from `governance_providers.api` to
  `ugence_governance_provider_framework.api`).
- New distribution **`ugence-actiongate-provider`** (import namespace
  `ugence_actiongate_provider`). Provider **implementation version stays `0.1.0`** —
  only the package location changed. Initial **distribution version `0.1.0`**.
- Legacy `actiongate_provider` namespace converted to a logic-free compatibility
  facade (object identity preserved). Legacy `dgm-actiongate-provider` converted to a
  compatibility distribution depending on
  `ugence-actiongate-provider[decision-authority]`.
- Dropped the unused `decision-governance` core dependency (ActionGate does not
  import the kernel directly); the kernel remains reachable via the optional
  `decision-authority` extra through the framework adapter.
- Added `version_info()`, a `python -m ugence_actiongate_provider` CLI
  (`version`/`verify`/`demo`) and the `ugence-actiongate-provider` console script.

### Equivalence (proven)

- Public `.api` surface **byte-identical** (26 exports); the only additive change is
  the top-level `version_info` helper (MINOR-compatible overall; frozen `.api`
  snapshot unchanged).
- Behavioral capture **identical** before == canonical == legacy.
- Platform-freeze API snapshot unchanged; only structural tree/conformance hashes
  updated for the relocation.

### Boundary (unchanged)

- **Authorization only.** No dispatch/execute/observe/reconcile surface. No TAP
  dependency. Fail-closed: unknown outcomes and infrastructure failure →
  INDETERMINATE, and DENIED/INDETERMINATE never dispatch.

Not production certified.
