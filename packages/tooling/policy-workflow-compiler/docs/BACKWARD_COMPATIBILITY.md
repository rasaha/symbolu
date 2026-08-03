# Backward Compatibility

P2 is strictly additive.

- All P1 tests pass; all `workflow_ir.v1` fixtures remain readable.
- All P1 public API names remain available (surface grows additively 71 → 101).
- P1 CLI commands are unchanged; `compile` gains an optional `--contract`
  (default `workflow_ir.v1`).
- v1 canonical fingerprints are byte-stable (pinned: release `sha256:fb9fd4b9…`,
  IR `sha256:169ad24c…`). The v1 logical digest commits to a FROZEN v1 semantic
  identity (`0.1.0`) that is decoupled from the package version
  because it feeds the v1 release digest.
- P1 release verification is unchanged.
- AWC P1/P2 remains installable and green against existing v1 fixtures.

## Introducing workflow_ir.v2

- Explicit v2 compilation (`compile_workflow_v2`, `compile --contract workflow_ir.v2`)
  and validation (`validate_compiled_release`).
- Unknown versions are rejected (`UNSUPPORTED_VERSION`).
- Clear v1/v2 reporting via `version_info().supported_workflow_ir_versions`.
- v1 artifacts are **not** auto-upgraded. `upgrade-v1` is explicit and performs a
  **deterministic, non-destructive v1->v2 enrichment**: it preserves all v1
  information and explicitly labels semantics that are derived, defaulted, deferred
  or unresolved (via the provenance derivation class). It is "lossless" only in the
  narrow sense that no v1 information is discarded — it does **not** recover
  original source-policy facts that were absent from v1.
