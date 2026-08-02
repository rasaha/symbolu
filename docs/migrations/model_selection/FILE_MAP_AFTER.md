# Model Selection — File Map (AFTER)

## Canonical package `packages/capabilities/model-selection/`

| File | Role |
|---|---|
| `src/ugence_model_selection/gate.py` | **PRODUCT** — `ExecutionGate` (moved verbatim; relative imports) |
| `src/ugence_model_selection/policy.py` | **PRODUCT** — `select`, `PolicyWeights`, `Selection` (moved verbatim) |
| `src/ugence_model_selection/states.py` | **CONTRACT** — states/verdicts/criticality/evidence/`EligibilityDecision` (moved verbatim) |
| `src/ugence_model_selection/model.py` | **CONTRACT** — `Request`/`Candidate`/`Signal`/`GateConfig` (moved verbatim) |
| `src/ugence_model_selection/registry.py` | **PRODUCT** — `ExecutableRegistry`/`ModelRecord`/`ExecStatus` (moved verbatim) |
| `src/ugence_model_selection/reason_codes.py` | **CONTRACT** — `ReasonCode`/`normalize_raw` (moved verbatim) |
| `src/ugence_model_selection/api.py` | **NEW** — curated public surface (grouped eligibility/selection/contracts) |
| `src/ugence_model_selection/version.py` | **NEW** — `__version__=0.1.0`, `POLICY_VERSION="exec_gate_v1"` |
| `src/ugence_model_selection/fingerprint.py` | **NEW** — deterministic record fingerprint (no new selection logic) |
| `src/ugence_model_selection/__init__.py` | **NEW** — package docstring + version re-export |
| `pyproject.toml`, `README.md`, `LICENSE`, `.gitignore`, `conftest.py` | packaging/metadata |
| `verify_model_selection_distribution.py` | packaging verifier |
| `tests/test_model_selection_core.py` | canonical package tests (7) |

## Legacy compatibility namespace `execution_gate/`

| File | Role |
|---|---|
| `__init__.py` | **COMPAT** — logic-free `sys.modules` alias of the 6 canonical product modules (identity preserved) |
| `harness.py`, `baselines.py`, `scenarios.py`, `common_io.py` | **RESEARCH** — retained local eval harness (now consume the canonical core through the aliased names) |
| `frozen/replay_v1/**` | **EVIDENCE** — untouched (replay aggregate `8b05b2da798a6222`) |
| `tests/test_execution_gate.py` | 21 behavior tests (via compat surface) |
| `tests/test_legacy_compat.py` | **NEW** — 4 identity/compat tests |

*(The product-core module files `gate.py`/`policy.py`/`states.py`/`model.py`/`registry.py`/`reason_codes.py`
no longer exist here — they were moved to the canonical package and are aliased.)*

## Sibling research dirs (unchanged behavior; classification header added)

`model_selection_experiment/`, `model_selection_pilot/`, `model_selection_reconciliation/` — each
`__init__.py` now carries a header classifying it as an intentionally-separate research algorithm. No
code behavior changed.

## Consumers

`control_plane/adapters.py` and `governed_inference_pilot/adapters/execution_gate.py` now import
`ugence_model_selection` directly. `execution_gate_shadow/*` and `control_plane_shadow` keep the
`execution_gate` surface.
