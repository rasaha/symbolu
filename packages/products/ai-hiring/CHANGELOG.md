# Changelog — `ugence-ai-hiring`

All notable changes to the independent AI Hiring distribution. This file tracks
the **distribution** (wheel packaging) version, which is distinct from the
**product** capability-maturity version (`PRODUCT_VERSION`, currently `0.6.0`).

The format follows [Keep a Changelog](https://keepachangelog.com/); the
distribution uses pre-1.0 semantic versioning.

## [0.1.0] — Independent extraction

First independent packaging of the AI Hiring product, extracted from the
monolithic `symbolu` distribution into `packages/products/ai-hiring/` with the
canonical import surface `ugence_ai_hiring`.

### Added
- Independent, pure-Python distribution `ugence-ai-hiring` (canonical import
  `ugence_ai_hiring`), built from `packages/products/ai-hiring/`.
- Distribution/product version split: `__version__` (distribution `0.1.0`) vs
  `PRODUCT_VERSION` (`0.6.0`), surfaced by `version_info()` alongside contract
  versions, dependency versions, release classification, and optional-integration
  availability. `production_certified` is hard-coded `False`.
- Top-level CLI: `python -m ugence_ai_hiring version|verify|demo|report` and the
  `ugence-ai-hiring` console script.
- Logic-free `ai_hiring` compatibility facade (re-exports the canonical objects
  with object identity and deep submodule paths preserved) for clean-environment
  installs.
- Minimal core dependency set: `pydantic>=2`, `ugence-decision-authority`,
  `ugence-governance-provider-framework`, `ugence-governance-contracts`. NumPy
  and all vendor AI SDKs are intentionally **not** dependencies.
- Optional `api` extra (FastAPI adapter); no extra is declared without
  corresponding code.
- Migrated behavioral test suite plus new packaging, dependency-boundary,
  import-isolation, compatibility-facade, governance-invariant, and determinism
  tests.
- Distribution verifier (`scripts/verify_ai_hiring_distribution.py`) and scoped
  CI (`.github/workflows/ai-hiring-package-ci.yml`).
- Provenance artifacts (`artifacts/source_manifest.json`,
  `artifacts/source_hashes.json`, `artifacts/public_api_baseline.json`,
  `artifacts/test_migration_manifest.json`).

### Preserved / unchanged
- Product semantics and governance invariants are unchanged; no new hiring
  algorithm, scoring/ranking/fairness model, or LLM inference was introduced.
- The original monorepo `ai_hiring/` source tree is preserved unchanged (the
  in-repo facade conversion is deferred to a later cleanup PR to keep the
  platform freeze intact).
- No production HRIS/ATS/offer/payroll adapter is included.

### Notes
- The pure-Python wheel is bit-for-bit reproducible with `SOURCE_DATE_EPOCH`
  pinned; the sdist is content-reproducible.
- Not production certified; controlled-pilot maturity only.
