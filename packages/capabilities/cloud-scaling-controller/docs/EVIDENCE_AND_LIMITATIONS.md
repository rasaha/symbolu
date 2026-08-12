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

## Predictive Capacity Intelligence (Phase 2) — evidence & maturity

**Implementation maturity: IMPLEMENTED_AND_LOCALLY_VERIFIED.** New in v0.3.0.
**Model quality: BASELINE_FORECASTING_IMPLEMENTED · PREDICTIVE_QUALITY_NOT_ESTABLISHED.**

The `forecasting` subpackage is a deterministic, provider-neutral, **shadow-only**
forecasting and replay-evaluation layer (`CanonicalCapacitySeries` → `ForecastInputWindow`
→ baseline forecaster → `CapacityForecast` → `CapacityForecastEvidence` →
`ForecastEvaluationRecord`). It is pure-stdlib, adds no dependency, performs no
actuation/network/subprocess/credential/LLM activity, and **never** feeds the controller.

| Concern | Status | Evidence |
|---------|--------|----------|
| Implemented | ✅ | `src/ugence_cloud_scaling_controller/forecasting/` — series, window, targets, baselines, uncertainty, forecast/evidence, evaluation, replay. |
| Unit-tested | ✅ | `tests/forecasting/` (90 tests): series policy, leakage-safe windows, baselines, empirical uncertainty, forecast/evidence + digest boundary, evaluation/aggregate, adversarial replay/leakage, demand scenarios, boundary. |
| Leakage-prevented | ✅ | Windows contain only `event_time <= cutoff` (invariant-checked); replay matches strictly-later actuals; harness fails closed on residual leakage (adversarial tests). |
| Shadow-only / advisory-only | ✅ | Every forecast + evidence: `advisory_only=True`, `shadow_only=True`, `actuation_performed=False`, `authority_class="ADVISORY"`, `execution_capability="NONE"`. |
| Evidence identity | ✅ | `sha256:` digest over all authoritative fields; excludes production time + non-authoritative annotation. |
| **Forecast accuracy** | ❌ **NOT established** | Baselines (persistence/linear-trend) are **not** evaluated on representative external workloads against preregistered acceptance thresholds. Passing tests prove implementation correctness, **not** production accuracy → **PREDICTIVE_QUALITY_NOT_ESTABLISHED**. |

## Canonical Capacity Intelligence (Phase 1) — evidence & determinism

**Status: IMPLEMENTED_AND_LOCALLY_VERIFIED.** New in v0.2.0.

| Concern | Status | Evidence |
|---------|--------|----------|
| Implemented | ✅ | `src/ugence_cloud_scaling_controller/canonical/` — canonical state, measurement/units, provenance, normalization, projection, evidence, read-only sources. |
| Unit-tested | ✅ | `tests/canonical/` (88 tests): serialization/digest, state validation, normalization, projection, evidence integrity, RA/authority boundary, provider-neutrality & side-effects. |
| Additive / non-regressive | ✅ | The controller decision kernel is unchanged; the behavior-baseline parity suite still passes byte-for-byte. |
| Distribution | ✅ | The canonical modules ship in the wheel and pass the advisory distribution verifier (forbidden-symbol/path/mutation scans, isolated install). |
| Live-cluster validated | ❌ | Not performed. |
| Production-certified | ❌ | Not performed. |

### Determinism scope (canonical layer)

For identical `(CanonicalCapacityState, NormalizationPolicy, ControllerConfig, controller
history)`, the following are reproducible: normalization results, the projected
`ScalingObservation`, the controller decision fields, and the **evidence content digest**.

The evidence digest is computed over a documented, domain-separated canonical form
(sorted keys; NFC strings; RFC3339-UTC timestamps; floats round-tripped with NaN/inf
rejected and `-0.0` normalized; nulls preserved; `sha256:`-prefixed hex). It **excludes**:

- `evidence_produced_at` — an evidence-production timestamp isolated from the deterministic
  decision path (caller-supplied trusted time; defaults to `observed_at` to stay
  clock-free);
- `controller_explanation` — a human rendering that embeds the controller's **disclosed**
  nondeterministic `identity_deviation` "Identity Drift" line;
- the digest field itself.

The controller's `identity_deviation` diagnostic is never carried in the evidence. This
preserves the existing distinction between **decision determinism** and diagnostic/
externally-sourced nondeterminism: projection being deterministic does **not** imply the
raw operational world is deterministic. Observation time (`observed_at`) and
evidence-production time (`evidence_produced_at`) are kept distinct and never conflated.

### What Phase 1 does NOT prove

Production quality of future cloud collectors; better scaling outcomes; cost savings;
forecasting accuracy; dependency-awareness; safe autonomous execution; Risk Authority
integration; provider mutation safety; post-execution effectiveness. These require
downstream execution receipts and observed-effect reconciliation that Phase 1 does not
implement.
