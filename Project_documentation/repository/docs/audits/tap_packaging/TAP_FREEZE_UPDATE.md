# Platform-freeze structural update (TAP canonical migration)

The freeze was **PASS** before and **PASS** after. Because TAP's physical source
tree moved (to the canonical package) and the legacy namespace became a shim, two
**structural** hashes changed. **No semantic freeze artifact changed.**

## Fields changed (structural only)

| manifest field | old | new | why |
|---|---|---|---|
| `core_tree_hashes["tap_provider"]` | `4209eb87…66d074` | `53b7abf7…c938249` | the `tap_provider` tree became a logic-free facade (`__init__.py`) + retained monorepo tests; the implementation relocated to `packages/providers/tap/src/ugence_tap_provider`. |
| `conformance_hashes` key `tap_provider` → `packages/providers/tap/src/ugence_tap_provider` | `c3ecf91b…e8736` | `f52903dc…fe5d5a` | the TAP conformance suite physically relocated; the freeze now hashes it at its canonical home (coverage **preserved**, not dropped). |
| `manifest_digest` | `bd346cb2…54808f` | `815a9250…c524c6` | derived from the two fields above. |

## Fields proven UNCHANGED (semantic)

- `public_api_manifests` (the `tap_provider.api` snapshot) — **byte-identical**;
  the API-snapshot JSON files under `platform/api-snapshots/` did not change.
- `components` (all distribution versions still 0.1.0 / 1.0.0).
- `dependency_rules` (TAP still forbidden from importing ActionGate, AI Hiring, …).
- `frozen_invariants` (F1–F20 unchanged; all pass, including F4/F6/F12 whose
  authoritative tests remain at `tap_provider/tests/…`).
- `behaviour_tree_hashes`, benchmark identity, documentation presence.

## Classification

`PACKAGING_ONLY` / structural. The behavioral capture is unchanged
(`before == canonical == legacy`) and the API snapshot is unchanged, so the change
is a physical relocation, not a semantic change. Semantic promotion of uncertainty
or failure to "supported" remains impossible.

## One tooling change

`platform_freeze/manifest.py` `_PROVIDERS_WITH_CONFORMANCE` now references the TAP
conformance suite at its canonical path so freeze coverage of TAP conformance is
preserved rather than emptied. No freeze semantics, invariants, or dependency rules
were altered.

## Rollback

To roll back the entire migration: `git revert` the migration commits (or check out
the parent of this branch). The freeze then reverts automatically —
`platform_freeze/manifest.py` and `platform/PLATFORM_FREEZE_V1.json` return to their
prior state and `python -m platform_freeze.verify` passes against the restored
manifest. Because the canonical package lives entirely under `packages/providers/tap`
and the only in-place edits are the `tap_provider/__init__.py` facade, the
`dgm-tap-provider` pyproject, the one-line `_PROVIDERS_WITH_CONFORMANCE` reference,
the regenerated manifest, and `conftest.py`, reverting is mechanical and complete.
