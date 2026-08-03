# Changelog — ugence-tap-provider

All notable changes to the canonical TAP distribution are documented here.

## [0.1.0] — canonical package migration

First independent distribution of the TAP assertion-governance provider.

### Migration (no behavior change)

- Established the single canonical source tree
  `packages/providers/tap/src/ugence_tap_provider` (history-preserving relocation
  from the monorepo `tap_provider/` tree; internal framework imports rewritten to
  `ugence_governance_provider_framework.api`).
- New distribution **`ugence-tap-provider`** (import namespace
  `ugence_tap_provider`). Provider **implementation version stays `0.1.0`** — only
  the package location changed. Initial **distribution version `0.1.0`**.
- Legacy `tap_provider` namespace converted to a logic-free compatibility facade
  (object identity preserved). Legacy `dgm-tap-provider` converted to a
  compatibility distribution depending on `ugence-tap-provider[decision-authority]`.
- Added `version_info()`, a `python -m ugence_tap_provider` CLI
  (`version`/`verify`/`demo`) and the `ugence-tap-provider` console script.

### Equivalence (proven)

- Public `.api` surface **byte-identical** (32 exports); the only additive change
  is the top-level `version_info` helper (MINOR-compatible).
- Behavioral capture **identical** before == canonical == legacy.
- Platform-freeze API snapshot unchanged; only structural tree/conformance hashes
  updated for the relocation.

### Boundary (unchanged)

- Assertion-support evaluation only. No authorization/execution surface. No
  ActionGate dependency. Fail-safe: infrastructure failure → INDETERMINATE.

Not production certified.
