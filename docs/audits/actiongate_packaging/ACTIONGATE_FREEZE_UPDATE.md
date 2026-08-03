# ActionGate Platform-Freeze Update

The ActionGate canonical-package relocation changes **only structural** freeze
fields. No public API, semantic invariant, dependency rule, or component version
changed. This mirrors the TAP freeze update from PR #1297.

## Fields changed (analyzed, not blindly regenerated)

| Field | Old | New | Why |
|---|---|---|---|
| `core_tree_hashes.actiongate_provider` | `f40f0cf3…` | `9cbeb833…` | `actiongate_provider/` became a logic-free facade (impl moved out) |
| `conformance_hashes` key | `actiongate_provider` = `8d4a5d35…` | `packages/providers/actiongate/src/ugence_actiongate_provider` = `07e08bd4…` | the conformance suite physically relocated to the canonical package; the freeze now hashes it at its canonical home (coverage preserved, not dropped) |
| `manifest_digest` | `815a9250…` | `05fdb1ca…` | recomputed over the two structural changes above |

`platform_freeze/manifest.py` `_PROVIDERS_WITH_CONFORMANCE` was updated to point at
the canonical ActionGate conformance path (the facade has no `conformance/` dir).

## Fields explicitly UNCHANGED

- `public_api_manifests.actiongate_provider.api` = `9eeb66e3…` — the `.api` snapshot
  is **byte-identical** through the facade (proven).
- `components`, `dependency_rules`, `core_trees`, `behaviour_tree_hashes`, and the
  F1–F20 frozen invariants — unchanged.

## Digests

| Digest | Old | New |
|---|---|---|
| `manifest_digest` | `815a9250f833a253a621f26b341cd5b0a7cb8d283165fc9142013ff109c524c6` | `05fdb1caace9216a9b42b979c66eb144e17d8a0032aae3500ab668a446094402` |
| substantive digest (`python -m platform_freeze.verify`) | `ee7f083ebb21111cb01e3fdb0fb3f37f39cc0fcf00238ef918a9a5d5984ec47a` | `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036` |

`python -m platform_freeze.verify` → **PASS** (all 11 checks).

## Frozen security invariants — re-verified unchanged

- unknown never authorizes; provider failure never authorizes;
- DENIED never dispatches; INDETERMINATE never dispatches;
- constraints and obligations preserved;
- provider owns authorization only; execution remains external;
- TAP remains an independent peer;
- kernel and framework do not import ActionGate; the ActionGate core imports neither
  the kernel nor the framework.

F5 (`actiongate_provider/tests/test_conformance.py`) and F7
(`actiongate_provider/tests/test_dependency_boundaries.py`) still resolve through the
facade; F9/F10 direct freeze-checks (`_f9_f10_denied_indeterminate_never_dispatch`)
still pass through the facade.

## Pre-existing baseline failures (NOT caused by this migration)

`platform_freeze/tests/test_freeze.py::test_hiring_baseline_discovery` and
`::test_classify_change_reports_evidence` fail on the **untouched baseline** (verified
by stashing every platform change and re-running). They assert a stale "AI Hiring does
not yet use the provider framework" finding that a prior AI-Hiring phase invalidated.
They are AI-Hiring-specific and out of scope here (AI Hiring must not be modified).

## Rollback

1. `git checkout <base> -- platform/PLATFORM_FREEZE_V1.json platform_freeze/manifest.py`
   (restores `manifest_digest` `815a9250…`, the `actiongate_provider` conformance key,
   and the old `core_tree_hashes.actiongate_provider`).
2. `git checkout <base> -- actiongate_provider/ conftest.py`
   (restores the pre-facade implementation tree).
3. `git rm -r packages/providers/actiongate` and restore
   `packaging/dgm-actiongate-provider/pyproject.toml` + `README.md`.
4. `python -m platform_freeze.verify` → PASS on the restored baseline.
