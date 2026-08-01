# Changelog — ugence-storygraph

All notable changes to the StoryGraph capability package. SemVer.

## [2.0.0] — canonical-package migration

**This release is a physical restructuring and packaging change with ZERO
semantic change.** All StoryGraph matching, node/edge, mandatory-edge completion,
partial-story, legitimate counter-story, trusted-context, contradiction,
proposed-action, witness canonicalization, equivalence-class minimality,
evaluation-binding, staleness, Policy Pack, replay, evidence, advisory-authority,
verdict, and acceptance-threshold semantics are **unchanged**. All frozen graph,
policy, replay, and pre-registration digests are **byte-for-byte identical** to
the pre-migration baseline.

### Changed (packaging / structure only)
- Canonical home is now `packages/capabilities/storygraph/`; canonical namespace
  is `ugence_storygraph` (distribution `ugence-storygraph`).
- The former sibling packages `evaluation/` and `demos/` are now internal
  subpackages of `ugence_storygraph`.
- Added `pyproject.toml` — the capability now builds and installs as a single,
  self-contained wheel with **no third-party and no other Ugence dependency**.
- Added the curated `ugence_storygraph.api` public surface (identity-preserving).
- Schemas, fixtures, and replay-intake templates ship as package data.

### Added (compatibility & verification)
- Legacy import path `composite_threat_detector[.<sub>]` preserved via a
  logic-free redirect shim (same object identity); removal/review target v3.0.0.
- `verify_storygraph_distribution.py` — clean-venv independent-distribution proof.
- `tests/compatibility/` — legacy-import identity, digest stability, advisory-
  authority, non-mutation, and dependency-boundary contract tests.

### Migration
See `MIGRATION.md` and `docs/migrations/storygraph/`.

## [2.0.0] — prior (in `cyber_security/composite_threat_detector/`)
Story-graph matcher v2, witness canonicalization, equivalence-class minimality,
Policy Pack, deterministic historical replay, evidence chain. 289 tests.
(History preserved via git renames; no behavior changed by the migration.)
