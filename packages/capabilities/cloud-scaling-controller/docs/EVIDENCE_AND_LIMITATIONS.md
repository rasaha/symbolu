# Evidence & Limitations

Claims are separated by evidence tier. Only tiers backed by executed evidence in this
repository are marked true. Design-document claims are **not** promoted to measured
claims.

## Evidence tiers

| Tier | Status | Evidence |
|------|--------|----------|
| Implemented | ✅ | The control algorithm, contracts, facade, CLI, and packaging exist in `src/ugence_cloud_scaling_controller`. |
| Unit-tested | ✅ | Package-local suite (`tests/`, 61 tests) + the pre-existing regression suite (`tests/cloud_controller`, 760 passed / 4 skipped). |
| Simulation-tested | ✅ | Synthetic scenario/benchmark/edge-case harnesses (`observability/benchmark.py`, `observability/edge_cases.py`) exercised by the regression suite (seeded). |
| Trace-replay tested | ✅ | Replay harness + adapters (`replay/`) exercised by `tests/cloud_controller/test_replay.py` and `test_tier_a.py` on synthetic/recorded traces. |
| Shadow-mode capable | ✅ (capability) | Read-only HPA/shadow components (`shadow/`) exist and are unit-tested with mocks; live shadow runs are **not** part of this package's evidence. |
| Behavior-baseline verified | ✅ | Post-packaging output reproduces the frozen pre-packaging baseline exactly (deterministic projection hash `bd5a367c…`). See `artifacts/prepackaging_behavior_baseline.json` and `tests/behavior/test_baseline_parity.py`. |
| Clean-wheel installable | ✅ | `verify_cloud_scaling_controller_distribution.py` (24 checks) builds a wheel and installs it in an isolated venv outside the repo. |
| Live-cluster validated | ❌ | Not performed by this package. |
| Production-certified | ❌ | Not performed. |

## Pre-existing nondeterminism

`core/identity_ema.py` initializes the identity baseline with **unseeded**
`np.random.randn(dim)`. Consequently the `identity_deviation` observability output
(and the "Identity Drift" line of the human-readable explanation) varies between
`Controller` constructions. This was verified to **not** affect any decision field —
`action_score`, `recommendation`, `replica_delta`, `pressure`, `plasticity`, `gain`,
`damping`, and `coherence` are bit-stable across repeated runs. Per the packaging
rule on pre-existing nondeterminism, `identity_deviation` is excluded from the
behavior-baseline parity projection and the algorithm was **not** modified (seeding
it would be an algorithm change).

## Limitations

- **Advisory only.** Produces recommendations; does not scale infrastructure, replace
  the HPA, authorize changes, or make cloud-provider API calls.
- **Not production-safe by default.** No live-cluster validation or production
  certification is claimed.
- **Conservative by design.** With default gain, steady synthetic loads settle at
  `observe_*` rather than emitting replica deltas; genuine deltas arise from real
  dynamics or amplified gain (`G_base`).
- **No cost/customer claims.** No cost-savings, customer-validation, or real-cluster
  superiority is claimed; none is measured here.
- **Optional adapters are opt-in.** Prometheus/Kubernetes/OpenTelemetry integrations
  require extras and explicit, separately-authorized enablement.

## What was NOT changed during packaging

No scaling actuation was added. No control parameters (thresholds, gains, damping,
floors, cooldowns) were tuned. No benchmark numbers were altered. The change set is
mechanical import-path relocation + API/contract wrappers + packaging, verified by
exact behavior-baseline parity.
