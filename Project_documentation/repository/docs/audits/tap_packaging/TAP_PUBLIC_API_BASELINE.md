# TAP public-API baseline & equivalence

Artifacts: `artifacts/tap_public_api_baseline.json` (before),
`artifacts/tap_public_api_after.json` (canonical),
`artifacts/tap_public_api_after_legacy.json` (legacy),
`artifacts/tap_equivalence_summary.json`.

- **`.api` export count:** 32 (before) → 32 (after). The `.api` symbol surface is
  **byte-identical** across before / canonical / legacy (the freeze snapshot records
  no `__module__`, so relocation is invisible).
  - baseline `.api` snapshot sha256 `64d0ddea…4cd44f09`
  - canonical/legacy `.api` snapshot sha256 `08a21a5d…0e75bc89` (differs from baseline
    only by the additive top-level `version_info` helper, not on `.api`).
- **Compatibility classification:** `.api` surface **PATCH_EQUIVALENT**; overall
  **MINOR_COMPATIBLE** (additive `version_info`). No missing exports, no changed
  signatures/fields/enum values/exception bases, all deep-import paths preserved.
- **Object identity:** legacy and canonical resolve to the **identical** modules,
  classes, functions, and `__all__` (proven in
  `tests/compatibility/test_legacy_namespace.py`).
- **Behavioral equivalence:** `before == after_canonical == after_legacy`
  (`artifacts/tap_equivalence_*.json`; before and after_legacy are byte-identical,
  sha256 `ed920e85…6fc6e3d0`). Verdict: **BEHAVIORALLY_EQUIVALENT**.
