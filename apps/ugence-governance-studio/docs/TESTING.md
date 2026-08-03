# Governance Studio API — Testing (P3B)

`python -m pytest apps/ugence-governance-studio/backend/tests` — 125 tests:

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

Distribution: `python backend/scripts/verify_distribution.py` builds a wheel,
installs it in a clean venv OUTSIDE the repo, and drives the installed package.
