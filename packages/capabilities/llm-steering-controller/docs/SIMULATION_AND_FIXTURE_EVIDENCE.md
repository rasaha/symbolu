# Simulation and Fixture Evidence

## What simulation is (and is not)

`simulation.py` runs deterministic **offline** evaluation over local JSON fixtures. It is **not** real
production routing validation. No provider is contacted and no model is executed. Every simulation
output is stamped with mandatory labels:

```json
{ "evidence_class": "FAKE_LOCAL_FIXTURE",
  "provider_status": "NO_PROVIDER_CALLED",
  "execution_status": "NO_MODEL_EXECUTED" }
```

## Fixtures

`fixtures/` contains one `scenario_*.json` per case plus a combined `suite.json`
(regenerate with `python scripts/generate_fixtures.py`). Each scenario is a self-contained
`{name, registry, request, [policy], [expect]}`. Covered cases (section 12):

single eligible · multiple eligible · no eligible · privacy-restricted · regional restriction ·
cost-limited · latency-limited · long-context · structured-output · tool-use · multimodal ·
provider prohibited · model deprecated · missing capability metadata · unknown capability ·
fallback permitted · fallback prohibited · equal-score tie · policy-version change · single-model
registry.

## Running

```bash
ugence-llm-steering simulate --fixture fixtures/suite.json
ugence-llm-steering recommend --fixture fixtures/scenario_long_context_request.json
```

or programmatically:

```python
from ugence_llm_steering_controller.simulation import run_suite
report = run_suite(scenarios)   # deterministic; run_suite(x) == run_suite(x)
```

## Determinism

Given identical fixtures, `run_suite` produces byte-identical output (asserted by
`tests/simulation/`). Scenarios with an `expect` block are checked; the suite reports
`expectations_met` / `checked`, and the CLI/CI return nonzero if any expectation fails.

## Evidence discipline

Simulation demonstrates deterministic policy behavior on synthetic inputs. It establishes **nothing**
about real model quality, provider reliability, cost, or latency. See `LIMITATIONS.md`.
