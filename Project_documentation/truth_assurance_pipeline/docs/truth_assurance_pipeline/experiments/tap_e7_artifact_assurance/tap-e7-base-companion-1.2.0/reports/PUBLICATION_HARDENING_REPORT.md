# TAP-E7-BASE Companion Package v1.2.0 — Publication-Hardening Report

## Verdict: **1 — the package is now technically complete and fully self-describing.**

v1.2.0 adds only normative documentation to close the two gaps the independent review raised
(config-fingerprint recipe and projection-Π shape). No runtime behavior changed.

## Scope of change (docs-only, verified by diff)
- **ADDED (8):** `spec/CANONICALIZATION.md`, `spec/CONFIG_FINGERPRINT_SPEC.md`,
  `spec/PROJECTION_PI_SPEC.md`, `spec/projection-pi.schema.json`,
  `spec/INTEROPERABILITY_PROFILE.md`, `spec/EXTERNAL_IMPLEMENTER_GUIDE.md`,
  `spec/VERSIONING_RATIONALE.md`, `spec/CONSISTENCY_REVIEW.md`.
- **CHANGED (3, all derived):** `manifest/release-manifest.json`, `hashes/package-root.txt`,
  `hashes/sha256sums.txt`.
- **Behavior-file changes: 0** — no `corpus/`, `expected/`, `derivations/`, `resources/`,
  `grammar/`, or `schemas/` file changed.

## Task 8 validation (all confirmed)
| Invariant | Result |
| --- | --- |
| `config_fingerprint` unchanged | `d01e466e…` (identical) |
| `resource_root` unchanged | `a6ab8788…` (identical) |
| `schema_root` unchanged | `d1f1a95c…` (identical) |
| `corpus_root` unchanged | `f8c83c91…` (identical) |
| `package_root` changed only due to added docs | `fa22021a…` → `5ed6d7a4…` |
| Implementation A still passes | **86/86 EXACT_PASS**, fingerprint MATCH |
| Implementation B still passes | **86/86 EXACT_PASS**, fingerprint MATCH |
| No fixture / expected / derivation regenerated | confirmed (0 behavior-file changes) |

The Π schema was placed under `spec/` (not `schemas/`) precisely so `schema_root` and the runtime
fingerprint stay byte-identical.

## Task 7 versioning
Classification **B — normative clarification** (binds previously-inferred behavior). MINOR bump to
**v1.2.0** is correct: new normative surface is added, no behavior changes, and v1.1.1-conforming
implementations conform to v1.2.0 unchanged (see `spec/VERSIONING_RATIONALE.md`).

## Task 6 consistency
Every new document was checked against the Formal Spec, BASE Profile, Companion Release, the v1.1.1
bytes, and both implementations plus the independent review. The fingerprint recipe reproduces the
published value and the Π recipe reproduces sampled hashes with the documented shape. **No
contradiction found** (`spec/CONSISTENCY_REVIEW.md`).

## Task 9 statements
- **Fully self-describing:** Yes. The four roots + fingerprint, the strict-JSON profile, the
  grammar, the resources, the correspondence/taxonomy semantics, the canonicalization, the
  fingerprint recipe, and the projection-Π schema are now all published normatively in the package.
- **External reproduction without inference:** Yes. An external implementer can reproduce every
  runtime artifact — including the config fingerprint and every Π hash — from the package documents
  alone, with nothing left to infer from examples or implementation internals.
- **Technical blocker remaining:** None. The two documentation gaps are closed; two independently
  authored implementations already pass, and this release changes no behavior.
- **Only governance remains:** Yes. The path to Stable is now purely governance:
  1. a genuinely third-party (different author/team) implementation passing the mandatory corpus —
     the one remaining independence step;
  2. independent reviewer sign-off; immutable release tagging; public hash publication
     (`package_root 5ed6d7a4…`, `config_fingerprint d01e466e…`); a specification-errata process;
     conformance-report publication.

Stable promotion is **not** claimed here; v1.2.0 makes the package technically ready for that
governance process.
