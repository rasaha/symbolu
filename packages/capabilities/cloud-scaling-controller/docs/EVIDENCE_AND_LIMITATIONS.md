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
| Shadow-mode capable | ✅ (capability) | Read-only shadow primitives (`shadow/` divergence tracker, HPA/state watcher, reporter) exist and are unit-tested with mocks; the HPA watcher reads via the Prometheus client, not the Kubernetes SDK. Live shadow runs are **not** part of this package's evidence (the live runners are monorepo-only operations code). |
| Behavior-baseline verified | ✅ | Post-packaging output reproduces the frozen pre-packaging baseline exactly (decision-deterministic projection hash `bd5a367c…`). See `artifacts/prepackaging_behavior_baseline.json` and `tests/behavior/test_baseline_parity.py`. |
| Clean-wheel installable | ✅ | `verify_cloud_scaling_controller_distribution.py` (40 checks) builds a wheel, inspects packaged source, installs it in an isolated venv outside the repo, and generates build provenance. |
| Live-cluster validated | ❌ | Not performed by this package. |
| Production-certified | ❌ | Not performed. |

## Determinism (honest scope)

- **DECISION-DETERMINISTIC.** For a fixed config + input sequence, the decision
  fields are identical across repeated fresh instances: `recommendation`,
  `replica_delta`, `recommended_replicas`, `action_score`, `pressure`, and the
  `plasticity` / `gain` / `damping` / `coherence` component breakdowns.
- **DIAGNOSTICALLY NONDETERMINISTIC BEFORE BOOTSTRAP.** `core/identity_ema.py`
  initializes the identity baseline with **unseeded** `np.random.randn(dim)`, so
  `identity_deviation` (and the "Identity Drift" line of the explanation) varies
  between fresh `Controller` instances. It affects **no** decision field.

Each `ScalingRecommendation` discloses this in a `determinism` block
(`scope`, `identity_bootstrapped`, `nondeterministic_fields`). The complete JSON
result / explanation is **not** claimed fully deterministic. `identity_deviation` is
excluded from the behavior-baseline parity projection. The IdentityEMA algorithm was
**not** modified (seeding it would change historical behavior).

## Limitations

- **Advisory only.** Produces recommendations; the wheel contains no code capable of
  applying them (no actuator, approver, orchestrator, or executor).
- **Not production-safe by default; not a production autoscaler.** No live-cluster
  validation or production certification is claimed.
- **Conservative by design.** With default gain, steady synthetic loads settle at
  `observe_*` rather than emitting replica deltas; genuine deltas arise from real
  dynamics or amplified gain (`G_base`).
- **No cost/customer claims.** No cost-savings, customer-validation, or real-cluster
  superiority is claimed; none is measured here.
- **Optional adapters are opt-in and read-only.** The `prometheus` / `shadow` extras
  add only `requests` for read-only Prometheus/kube-state-metrics queries.
- **Operations code is not included.** Execution/approval/orchestration lives in the
  monorepo-only `cloud_scaling_operations` namespace, pending separate packaging and
  governance.

## What was NOT changed during correction

No scaling actuation was added. No control parameters (thresholds, gains, damping,
floors, cooldowns) were tuned. No benchmark numbers were altered. The IdentityEMA
randomness was not seeded. The change set is: moving execution/operations code OUT of
the wheel, adding the determinism disclosure + build provenance, and correcting
metadata/docs — verified by exact decision-baseline parity.
