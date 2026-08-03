# Downstream Compatibility — P2

P2 is additive and preserves every downstream consumer of `workflow_ir.v1`.

## Compiler P1
- P1 test suite: **78 passed, 1 skipped** (unchanged before/after).
- P1 public API: all 71 names preserved (surface grows to 101 additively).
- P1 CLI: `version validate compile verify diff inspect demo` behave identically;
  `compile` gains an optional `--contract` flag defaulting to `workflow_ir.v1`.
- v1 fingerprints byte-stable: release digest `sha256:fb9fd4b9…` and IR-only digest
  `sha256:169ad24c…` pinned and unchanged.
- P1 release validation (`verify_compiled_package`) unchanged.

## Agent Workforce Composer (AWC P1/P2)
- AWC consumes serialized `workflow_ir.v1` via its data-only adapter. That contract
  is unchanged, so AWC is unaffected.
- AWC P1/P2 suite: **158 passed** with the P2-built compiler installed (the optional
  `test_compiler_reference` path feeds a real v1 release through the AWC adapter and
  still passes).
- **The AWC adapter is NOT modified in this PR.** Consuming the enriched v2 contract
  and reducing the temporary overlay fields is the next phase (AWC P2.1).

## Governance Studio P3A
- P3A fixtures/expected-outputs are **not** modified. P3A suite: **94 passed**.

## Platform freeze
- Digest **unchanged**: `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`
  before and after. P2 touches only the compiler package, its own audit directory,
  and a scoped CI workflow — no frozen governance artifact, no `platform/` manifest.

## Unknown-version safety
A v2 artifact is never mislabeled as v1; unknown contract versions fail closed
(`UNSUPPORTED_VERSION`). A v1 IR can be losslessly upgraded to v2 on explicit
request; v1 artifacts are never auto-upgraded.
