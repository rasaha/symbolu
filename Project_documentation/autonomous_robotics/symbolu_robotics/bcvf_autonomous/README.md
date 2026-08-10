# BCVF Autonomous

**A safety-cased predictor-arbitration kernel for autonomous systems.**

Status: pre-1.0 (current `0.4.0`). API stability commitment is documented
in [`API_STABILITY.md`](./API_STABILITY.md). The math kernel, the
per-tick arbitration surface, and the safety-case mapping are stable;
deployment-partner surfaces (ROS 2 node, replay framework, calibration
bundle, sensor attestation) are provisional and are graduated as
integrators load-test them.

## What this is

BCVF Autonomous is a small layer that sits between a multi-predictor
stack (IMU+wheel odometry, lidar SLAM, visual odometry, GNSS+map, …)
and the planner. Per tick:

1. The kernel computes a **second-order cross-model coherence cost**
   over the predictor outputs (Lemma 1 invariance — the cost depends
   only on pairwise disagreement, not on which predictor you call
   "predictor 1").
2. A **trust computer** turns disagreement + per-predictor exclusion
   masks into a per-predictor weight vector.
3. **Composable exclusion sources** stack into a single boolean mask:
   deadline misses, safety-state-machine triggers, sensor-attestation
   failures — all union via `np.logical_or`.
4. The arbitrated state goes downstream to the planner; an **episode
   record** captures every input, mask source, and decision so a
   bit-identical replay can reconstruct the tick later.

The framework is **NumPy-stdlib only** (no `cryptography`, no `scipy`)
and ships with a machine-checked **ISO 21448 / SOTIF + ISO 26262 Part 6
traceability matrix**.

## Why a safety case first

A predictor-arbitration layer in an autonomous stack is in the safety
path. The integrator-facing question isn't "does the math work" — it's
"can the safety case be closed against this code." The repository is
laid out so that question can be answered without reading the kernel:

- [`safety_case/SOTIF_TRACEABILITY.md`](./safety_case/SOTIF_TRACEABILITY.md)
  — clause-by-clause map from ISO 21448 + ISO 26262 Part 6 to the
  importable BCVF surfaces that ground each clause. 69 indexed
  artifacts across 13 clauses (41 SOTIF + 28 ISO 26262 Part 6).
- [`safety_case/traceability.py`](./safety_case/traceability.py) —
  the same matrix as machine-readable data. Every artifact's
  importability is pinned by `tests/test_safety_case*.py` so a refactor
  that moves a symbol fails the suite loudly rather than silently
  invalidating the safety-case mapping.
- [`safety_case/SBOM.cdx.json`](./safety_case/SBOM.cdx.json) —
  CycloneDX 1.5 software bill of materials, regenerated deterministically
  per release for UN ECE R155 §7.3.4 traceability.

## Architecture summary

| Layer | Module | What it does | Stability |
|---|---|---|---|
| Math kernel | `core` | BCVF cost + Lemma 1 invariance | **Stable** |
| Manifold ops | `manifold` | SE(2) compose / log / wrap | **Stable** |
| Predictors | `predictors` | 4 reference predictors + failure-injection harness | **Stable** |
| Trace characterisation | `traces`, `analysis` | Failure-family sweep + sensitivity report | **Stable** |
| Simulator | `simulator` | Headless single-vehicle simulator | **Stable** |
| Trust + diagnostics | `trust`, `trust_diagnostics`, `runner` | Per-tick weights + episode records | **Stable** |
| Safety state machine | `safety_state` | NORMAL / DEGRADED / FAULT / FAILSAFE four-state contract | Provisional |
| ROS 2 / DDS adapter | `bcvf_ros2` (sibling pkg) + `ros2.py` shim | Framework-agnostic node + DDS QoS profile | Provisional |
| Replay framework | `replay` | SHA-256-identified tick bundles + bit-identity reconstructor | Provisional |
| Real-time budget | `realtime` | Latency monitor + p99/p999/p9999/max tier classifier | Provisional |
| Calibration bundle | `calibration` | 8-config bundle + drift detector over fleet summary | Provisional |
| Sensor attestation | `attestation` | HMAC-SHA256 7-check verifier | Provisional |
| Safety case | `safety_case` | Traceability matrix + SBOM generator | Provisional |

## Quick start

```python
import numpy as np
from symbolu_robotics.bcvf_autonomous import (
    BCVFConfig, compute_bcvf_cost,
    create_predictor_set, BicycleConfig, FailureConfig,
    Runner, RunConfig,
)

config = BCVFConfig()                  # default kernel parameters
predictors = create_predictor_set(
    BicycleConfig(),
    failures={"VisualOdometry": FailureConfig(noise_sigma=0.5)},
)
runner = Runner(RunConfig(n_ticks=200))
result = runner.run(predictors)

print(f"Episode: {result.diagnostics.n_excluded_ticks} ticks excluded")
print(f"Mean trust: {result.diagnostics.mean_trust_per_predictor}")
```

For the safety-cased path (state machine + attestation + replay),
see [`DESIGN.md`](./DESIGN.md) §6 and the per-feature design docs:

- [`SAFETY_STATE_MACHINE_DESIGN.md`](./SAFETY_STATE_MACHINE_DESIGN.md)
- [`ROS2_DDS_SBOM_DESIGN.md`](./ROS2_DDS_SBOM_DESIGN.md)
- [`REPLAY_FRAMEWORK_DESIGN.md`](./REPLAY_FRAMEWORK_DESIGN.md)
- [`REAL_TIME_BUDGET_DESIGN.md`](./REAL_TIME_BUDGET_DESIGN.md)
- [`CALIBRATION_DESIGN.md`](./CALIBRATION_DESIGN.md)
- [`SENSOR_ATTESTATION_DESIGN.md`](./SENSOR_ATTESTATION_DESIGN.md)

## What this is *not*

- **Not a planner.** BCVF arbitrates between predictor outputs; the
  planner consumes the arbitrated state. The MPPI planner that ships
  in `mppi_planner.py` is a reference, not the load-bearing piece.
- **Not a sensor-fusion stack.** It does not replace an EKF / particle
  filter / factor graph. It assumes those exist upstream and wraps
  whatever the predictor stack emits.
- **Not a complete safety case.** It supplies traceable evidence
  artifacts; the safety case is closed by the integrator with their
  hazard analysis, the operational-domain definition, and the
  verification-and-validation plan that exercises the full stack.
- **Not a guarantee against upstream prediction failure.** The
  Lemma 1 invariance is a mathematical property of the kernel — if
  every upstream predictor agrees on a wrong answer, BCVF will not
  catch it. This is the explicit scope boundary documented in
  [`DESIGN.md`](./DESIGN.md) §1 and in [`NOTICE`](./NOTICE).

## Testing

The full test suite is 1100+ tests across the kernel, the predictors,
the diagnostics, and the safety-cased provisional surfaces. The CI
runs the entire suite on Python 3.10, 3.11, and 3.12.

```bash
cd symbolu_robotics
pytest bcvf_autonomous/tests -q
```

A small number of timing-sensitive tests are host-speed dependent and
are excluded from the default sweep — they're listed in the CI
workflow at [`.github/workflows/bcvf-autonomous-ci.yml`](../../.github/workflows/bcvf-autonomous-ci.yml).

## Compatibility

- **Python**: 3.10+
- **NumPy**: 1.23+
- **Optional ROS 2 / rclpy**: only required if you use the
  `bcvf_ros2` adapter. The framework is framework-agnostic; rclpy
  is loaded lazily through an adapter so the core never imports it.

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md). Pull requests are
welcome; the repo's discipline is documented there:

1. Design doc first.
2. Pinning tests before implementation.
3. Independent critical-audit pass after every feature.
4. Roadmap row strikethrough on landing.

## License

Apache License 2.0. See [`LICENSE`](./LICENSE) and [`NOTICE`](./NOTICE).

## Citation

If BCVF Autonomous contributes to academic or industry work, please
cite the project as:

```
BCVF Autonomous: a safety-cased predictor-arbitration kernel for
autonomous systems. Version 0.4.0 (2026).
https://github.com/rasaha/symbolu
```

---

**Status indicators**

- `STABLE_API`: 38 symbols. Removal requires a deprecation cycle.
- `PROVISIONAL_API`: 77 symbols. May change in a minor version with
  a release-note line.
- See [`API_STABILITY.md`](./API_STABILITY.md) §3 for the full
  semver mapping.
