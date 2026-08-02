# Model Selection — Packaging & Distribution

## Distribution

| | |
|---|---|
| Name | `ugence-model-selection` |
| Import namespace | `ugence_model_selection` |
| Version | `0.1.0` (static, read from `version.py` literal by the build backend) |
| Layout | `src/` (setuptools; `packages.find` where `src`, include `ugence_model_selection*`) |
| Runtime dependencies | **none** (Python standard library only) |
| Optional | `test = ["pytest>=7.0"]` |

Follows the established canonical-package conventions (Governance Contracts, StoryGraph, Decision
Authority, Governance Provider Framework): `pyproject.toml` + `src/` + `version.py` + `README.md` +
`LICENSE` + `conftest.py` + `.gitignore` + a distribution verifier; the package `src` is added to the
root `conftest.py` path list for source-checkout resolution.

## Verifier

`packages/capabilities/model-selection/verify_model_selection_distribution.py`:

1. **Builds the wheel** (`python -m build`, falling back to `pip wheel`).
2. **Inspects wheel contents** — only `ugence_model_selection/*` source + dist-info metadata; asserts NO
   `model_selection_experiment` / `model_selection_pilot` / `model_selection_reconciliation` /
   `governed_inference_pilot` / `control_plane` / `provider.py` / `execute.py` / `benchmark` /
   `simulator` / `corpus` / `harness` / `scenarios` / `baselines` members.
3. **Clean-venv install + run** — creates a fresh virtualenv (no monorepo path), installs the wheel,
   then imports `ugence_model_selection` + `.api` from site-packages and runs: an ELIGIBLE selection, a
   `NO_ELIGIBLE_MODEL` abstain, and a deterministic fingerprint — asserting `"/symbolu"` is absent from
   `sys.path`.

**Result: ALL MODEL-SELECTION DISTRIBUTION CHECKS PASSED.**

## Scenario coverage (§17)

| Scenario | Where proven |
|---|---|
| Canonical-wheel-only: installs (stdlib only), imports, runs eligibility + selection + abstain | verifier clean-venv step ✅ |
| Wheel contains only canonical source (no research/pilot/provider/benchmark) | verifier content inspection ✅ |
| Legacy source-checkout imports resolve to the same canonical objects | `execution_gate/tests/test_legacy_compat.py` + equivalence capture ✅ |
| Product/control-plane consumer runs against the canonical core | `control_plane` (65) + `governed_inference_pilot` (27) suites, repointed to `ugence_model_selection` ✅ |
| Research consumer | The research engines are **independent** of the canonical package by design (distinct I/O), so there is no research consumer *of the wheel*; they run standalone (41 tests) ✅ |

Build artifacts (`build/`, `dist/`, `*.egg-info/`) are git-ignored via the package `.gitignore`.
