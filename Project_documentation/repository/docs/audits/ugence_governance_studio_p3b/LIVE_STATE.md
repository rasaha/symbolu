# Governance Studio P3B — Live-State Audit

| Item | Value |
|------|-------|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Starting commit | `6a2e53cd2c7d726929eae9cc7f496156bc58b291` |
| Working tree clean at start | yes |
| PR #1312 (P3A) | merged (`8f19d17b`) |
| PR #1314 (Compiler P2) | merged (`40d19b83`) |
| PR #1316 (compiler version correction) | merged (`db10adad`) |
| **PR #1317 (AWC P2.1 v2 adapter)** | **merged** (`6a2e53cd`, head `e1dbd5f5`, merged 2026-08-03T18:10:35Z) |
| Compiler | distribution 0.2.0; contracts `workflow_ir.v1`, `workflow_ir.v2` |
| AWC | 0.2.1 / 0.2.1; contracts `awc.v1`, `awc.composition.v1`, `awc.compiler_adapter.v2`; public API 109 |
| AWC supported workflow contracts | `workflow_ir.v1`, `workflow_ir.v2` |
| P3A manifest | `governance_studio.fixture_manifest.v1`, generator `awc_version=0.2.0` (frozen, pinned) |
| AWC 0.2.1 reproduces frozen P3A outputs | yes (all four scenarios verify byte-identical) |
| Baseline AWC suite | 201 passed, 1 skipped |
| Baseline P3A suite | 94 passed |
| Platform-freeze digest | `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036` |
| Pre-existing P3B branch/PR | none |
| Pre-existing backend | none |

PR #1317 is verified merged and its merge commit is the current default-branch tip,
so the P3B stop-condition prerequisite (§37, gate P3B-A1) is satisfied.
The frozen P3A manifest remains pinned to the historical generator version (0.2.0);
the live AWC 0.2.1 reproduces the frozen logical outputs without re-baselining.
