# Governance Studio API — Testing (P3B)

`python -m pytest apps/ugence-governance-studio/backend/tests` — 142 tests:

| Suite | Tests | Focus |
|-------|------:|-------|
| operational | 6 | health, ready, not-ready, version, build, maturity |
| scenarios | 19 | catalog, real execution, verification, immutability |
| workflows | 13 | v1/v2 adapt, unknown contract, node accounting, comparison |
| eligibility_ranking | 13 | accounting, states, deterministic order, fingerprints |
| composition | 9 | complete/no-feasible, concentration, permissions, fallbacks |
| explanations | 6 | conditions, reconstruction, selection states, no invented reasons |
| replay_comparison | 10 | match/mismatch, cross-process, assignment/policy/registry diffs |
| whatif | 14 | all 9 perturbations, immutable baseline, determinism, diff |
| validation | 9 | malformed/unknown/oversized/enum/media-type/unsafe-path |
| security | 9 | network isolation, no shell, headers, CORS, seams, no creds |
| architecture | 5 | public-AWC-only imports, no duplicated logic, no frontend/db |
| concurrency | 4 | concurrent determinism, no state leak, no mutation |
| determinism | 4 | canonical JSON, frozen fingerprints, stable export |
| freeze | 4 | OpenAPI/public-API drift, bundled-fixture drift |
| awc_version_range (P1) | 12 | bounded dep, ==0.2.1 lock, range boundaries, readiness fails out-of-range |
| fixture_bundle (P2) | 5 | three-way source==packaged==recorded incl. v2 conformance |

## Packaging protections (P3B P1/P2)

- **P1 — supported AWC range**: `pyproject` bounds AWC to `>=0.2.1,<0.3.0`;
  `constraints.txt` locks `==0.2.1`; `/ready` fails closed (503) when the
  installed AWC is outside the range.
- **P2 — bundled-fixture drift**: `scripts/verify_fixture_bundle.py` +
  `tests/test_fixture_bundle.py` prove `canonical source == backend-packaged ==
  recorded manifest` for every bundled scenario manifest, workflow, registry,
  policy, expected output, replay record and v2 conformance artifact
  (`data/BUNDLED_FIXTURE_MANIFEST.json`). Readiness enforces the packaged==recorded
  leg at runtime.

Distribution: `python backend/scripts/verify_distribution.py` builds a wheel,
installs it in a clean venv OUTSIDE the repo, and drives the installed package.
