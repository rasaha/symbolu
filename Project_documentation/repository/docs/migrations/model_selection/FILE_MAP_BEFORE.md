# Model Selection — File Map (BEFORE)

State at the pre-migration default tip `2a5a8efc`. The product core lived inside
`execution_gate/` intermixed with a local research harness; three sibling research dirs held
independent engines.

## `execution_gate/` (canonical source — product core + local research)

| File | Role |
|---|---|
| `gate.py` | **PRODUCT** — `ExecutionGate` eligibility engine |
| `policy.py` | **PRODUCT** — `ModelPolicy.select`, `PolicyWeights`, `Selection` |
| `states.py` | **PRODUCT/CONTRACT** — eligibility states, verdicts, criticality, evidence, `EligibilityDecision` |
| `model.py` | **PRODUCT/CONTRACT** — `Request`, `Candidate`, `Signal`, `GateConfig` |
| `registry.py` | **PRODUCT** — `ExecutableRegistry`, `ModelRecord`, `ExecStatus` |
| `reason_codes.py` | **PRODUCT/CONTRACT** — `ReasonCode`, `normalize_raw` |
| `harness.py`, `baselines.py`, `scenarios.py`, `common_io.py` | **RESEARCH** — evaluation harness/battery |
| `frozen/replay_v1/**` | **EVIDENCE** — replay determinism freeze (aggregate `8b05b2da798a6222`) |
| `__init__.py` | 1-line docstring |
| `tests/test_execution_gate.py` | 21 behavior tests |

## Sibling research dirs (independent engines; do NOT import `execution_gate`)

| Dir | Role |
|---|---|
| `model_selection_experiment/` | dict-based `policy.route` engine + simulator/oracle/baselines/metrics/harness |
| `model_selection_pilot/` | dict-based forked engine (F1/F2/G) + provider execution (blocked) + counterfactual runner |
| `model_selection_reconciliation/` | Policy A/B/C objective study over the experiment |

## Consumers (import `execution_gate`)

`control_plane/adapters.py`, `control_plane_shadow/adapters/execution_gate_adapter.py` +
`model_policy_adapter.py`, `execution_gate_shadow/*`, `governed_inference_pilot/adapters/execution_gate.py`.
