# §6.2 Real-Sensor Pilot Runner

The executable harness for the §6.2 pilot. The scaffold (dataset
adapter interface + `RealisticNoiseAdapter`) has been ready for
months; this module is the missing piece that turns "we have a
scaffold" into "we have a paired-comparison result + a `FleetSummary`
artifact."

## §1 What the runner does

For each `SceneRecord` from a `DatasetAdapter`, the pilot runs **two
configurations end-to-end** and records per-scene metrics:

* **A0** — equal-weight (uniform) consensus over M predictors. The
  no-trust-shaping baseline.
* **A3** — V1 trust shaping (EMA centering + deadband + softmin) over
  the same predictors. Optionally with V2 Schmitt trigger.

Per scene, both configurations produce:

1. A **consensus trajectory** at every simulator step. The consensus
   is what a planner would consume.
2. A **forecast-error metric** — mean lateral and longitudinal error
   between the consensus and the ground-truth ego trace one horizon
   ahead.
3. A **per-predictor weight time series** — for A3 only; uniform
   1/M for A0.
4. A **`TrustShapedEpisodeRecord`** for A3 — directly consumable by
   the v0.4 fleet analysis harness.

The runner is **open-loop (Mode A)** in the v1 pilot — Mode B
(closed-loop with the simulator) requires non-trivial vehicle-model
calibration that the pilot plan recommends as a follow-on.

## §2 The paired comparison

Each scene yields one paired observation:
`(forecast_error_A0, forecast_error_A3)`. The pilot's headline
question is *"on responsive scenes, does A3 reduce forecast error
vs A0?"* — answered by a one-sided sign test on the per-scene
delta `delta_i = err_A0_i - err_A3_i`. The sign test rejects the
null `delta == 0` if a meaningful majority of scenes have positive
delta.

Wilson-CI gives a confidence interval on the win rate for the press
release.

## §3 Per-failure-class breakdown

Because each scene carries its `failure_metadata.type`, the
aggregator naturally produces:

* Per-failure-class win rate (gps_multipath, map_misalignment,
  camera_degradation, constant_bias_sanity).
* Per-failure-class attribution accuracy — the fraction of A3 scenes
  where M4 (the injected outlier) ends up rank-1 in BCVF
  per-predictor cost during the failure window.
* `constant_bias_sanity` is the Lemma-1 negative control: BCVF
  must NOT fire (otherwise the kernel is broken). The pilot
  asserts this as a hard gate.

## §4 Artifact contract

`Runner.run()` writes three files to `output_dir`:

1. `paired_comparison.csv` — one row per scene with
   `scene_id, failure_type, err_A0, err_A3, delta, attribution_hit`.
2. `fleet_summary.json` — the v0.4 `FleetSummary.to_dict()` output
   over all A3 episode records. Contains argmax-flip rates, near-
   vetoes, V2 state distribution, per-predictor exclusion
   incidence — same artifact a fleet-scale recall triage tool
   would consume.
3. `pilot_report.md` — human-readable summary: headline win rate,
   per-failure-class breakdown, sign-test result, scope caveats.

The CSV + JSON are the inputs an investor / safety auditor wants;
the markdown is the press-release narrative.

## §5 Adapter swap — RealisticNoise → NuScenes

The runner is dataset-agnostic. The first execution runs against
`RealisticNoiseAdapter` (correlated AR(1) noise + non-Gaussian
outliers + the four documented failure patterns) — the bridge the
pilot plan calls out as *"if the trust pipeline passes §6.1-style
significance under realistic-noise synthetic, we have high
confidence the numerics are ready for real-data integration."*

When the nuScenes-mini dataset is on local disk and `nuscenes-devkit`
is installed, swap:

```python
# from
adapter = RealisticNoiseAdapter()
# to
adapter = NuScenesAdapter(dataroot="/path/to/nuscenes-mini")
```

The runner, the metrics, the FleetSummary, the sign test, the
artifacts — all unchanged. The `datasets/nuscenes.py` stub
documents the integration path; implementation requires
authenticated dataset download and is out of sandbox scope.

## §6 Acceptance criteria

* **Numerical correctness:** A3 produces well-formed `(K=1, M, H, 3)`
  outputs through the trust computer at every scene's every
  simulator step. Pilot fails if any scene errors out.
* **Lemma-1 negative control:** on `constant_bias_sanity` scenes,
  A3 must produce per-step BCVF cost ≤ 1e-6 (Lemma 1 invariance
  exactly). Pilot fails if this gate is breached.
* **Headline result:** at N ≥ 21 paired scenes across responsive
  failure classes, A3's win rate against A0 has a Wilson-CI lower
  bound > 0.5. Pilot is *informative* if the lower bound exceeds
  0.5; it doesn't have to be statistically significant on the
  realistic-noise pre-pilot — the bar is "the runner produces an
  honest signed result."

When run on real nuScenes data, the bar tightens to one-sided
sign-test p < 0.05 at N ≥ 21 paired (matching the §6.1 protocol).

## §7 Verification protocol

This section is the formal runbook for verifying the pilot end-to-
end. It records what has been verified in the trunk environment
(automated CI) and what remains to be verified at execution time
(manual, on RunPod or equivalent host with internet + dataset
access). Anyone returning to this work later — a new engineer, a
SOTIF auditor, an investor's diligence team — should be able to
follow §7.2 step-by-step and produce a reportable result without
re-deriving the design.

### §7.1 Verification status — landed in trunk (automated)

The following gates are enforced by the test suite and run on
every commit. They establish that the pilot harness numerics are
correct *before* any real-data execution.

| ID | Gate | How verified | Status |
|---|---|---|---|
| V-01 | `predict_batch` produces bit-equivalent output to the per-rollout loop on M1, M2, M3, M4 (all failure modes) | `tests/test_predict_batch.py` — 11 parametrized equivalence tests | ✅ pinned |
| V-02 | `compute_bcvf_cost` per-step kernel sum reproduces the aggregate `total_cost` | `tests/test_observables.py::test_compute_bcvf_per_step_reproduces_aggregate` | ✅ pinned |
| V-03 | `TrustWeightComputer` weights sum to 1 over M for every rollout | `tests/test_consumer_v2.py` + `tests/test_pilot.py` | ✅ pinned |
| V-04 | `RealisticNoiseAdapter` produces 21 deterministic scenes covering all four failure types | `tests/test_datasets.py` — 11 tests | ✅ pinned |
| V-05 | Lemma-1 negative control on `constant_bias_sanity` scenes: max BCVF cost ≤ 1e-3 | `tests/test_pilot.py::test_evaluate_scene_a3_lemma1_invariance_on_constant_bias` | ✅ pinned |
| V-06 | A3 attribution accuracy ≥ 0.5 on `camera_degradation` (the responsive failure class) | `tests/test_pilot.py::test_evaluate_scene_a3_attribution_hits_failing_predictor_on_camera_degradation` | ✅ pinned |
| V-07 | `run_pilot` writes the three documented artifacts (CSV, FleetSummary JSON, markdown report) | `tests/test_pilot.py::test_run_pilot_end_to_end_on_realistic_adapter` and three sibling tests | ✅ pinned |
| V-08 | Sign-test correctness: monotone deltas, ties, balanced inputs, Wilson-CI shape | `tests/test_pilot.py::test_sign_test_*` — 4 tests | ✅ pinned |
| V-09 | `NuScenesAdapter` stub imports cleanly without `nuscenes-devkit`; constructor raises a clear remediation message | `tests/test_pilot.py::test_nuscenes_adapter_*` — 2 tests | ✅ pinned |

Reproducer for V-01 through V-09:

```bash
python -m pytest \
  symbolu_robotics/bcvf_autonomous/tests/test_predict_batch.py \
  symbolu_robotics/bcvf_autonomous/tests/test_observables.py \
  symbolu_robotics/bcvf_autonomous/tests/test_consumer_v2.py \
  symbolu_robotics/bcvf_autonomous/tests/test_datasets.py \
  symbolu_robotics/bcvf_autonomous/tests/test_pilot.py \
  -q
```

Expected: all pass on a clean checkout, CPU-only, in under 90 s.

### §7.2 Verification protocol — pending real-data execution (manual)

This is the **acceptance protocol for the §6.2 real-data milestone**.
Execute these steps once the sandbox-blocked work (dataset access +
predictor implementations) is complete. Each step has a numbered
gate; record the observed value next to the gate to produce a
reportable record.

The full execution runbook is `docs/experiments/phase_6_2_runpod_runbook.md`;
this section is the *verification* checklist that runs on top of it.

#### §7.2.1 Environment preflight

| Step | Command | Expected | Observed |
|---|---|---|---|
| P-01 | `python --version` | Python ≥ 3.10 | _____ |
| P-02 | `pip show nuscenes-devkit` | Package version present | _____ |
| P-03 | `git log --oneline -1` | Top commit ≥ `dad7ca4` (or branch tip) | _____ |
| P-04 | `python -m pytest symbolu_robotics/bcvf_autonomous/tests/test_pilot.py -q` | `16 passed` | _____ |
| P-05 | `ls -lh /workspace/nuscenes-mini` | Subdirs `maps`, `samples`, `sweeps`, `v1.0-mini` present | _____ |
| P-06 | nuScenes devkit smoke (see `phase_6_2_runpod_runbook.md` §4) | `Scenes available: 10` | _____ |

If any preflight gate fails, do not proceed — the failure root cause
must be resolved before the real-data execution result has meaning.

#### §7.2.2 Predictor + adapter implementation

| Step | Artifact | Expected check |
|---|---|---|
| I-01 | `predictors/nuscenes/m1_hdmap.py` exists | Class `HDMapPredictor` callable with a real `NuScenesMap` |
| I-02 | `predictors/nuscenes/m2_ctrv.py` exists | Class `CTRVKalmanPredictor` callable; `set_yaw_rate` accepted |
| I-03 | `predictors/nuscenes/m3_cv_baseline.py` exists | Class `CVBaselinePredictor` produces `(H, 3)` output |
| I-04 | `predictors/nuscenes/m4_failure_inject.py` exists | Class `FailureInjectedPredictor` accepts all four `failure_type` strings without error |
| I-05 | `datasets/nuscenes_real.py::NuScenesAdapter` | `len(adapter) == 10` for `v1.0-mini` |
| I-06 | `adapter.load_scene(adapter.scene_ids()[0])` returns a valid `SceneRecord` | `num_predictors == 4`, `num_steps > 0`, `horizon == 20`, `failure_metadata` populated |

Smoke command:

```bash
python -c "
from symbolu_robotics.bcvf_autonomous.datasets.nuscenes_real import NuScenesAdapter
adapter = NuScenesAdapter(dataroot='/workspace/nuscenes-mini')
print(f'scenes: {len(adapter)}')
rec = adapter.load_scene(adapter.scene_ids()[0])
print(f'steps: {rec.num_steps}, M: {rec.num_predictors}, H: {rec.horizon}')
print(f'failure: {rec.failure_metadata}')
"
```

#### §7.2.3 Pilot execution

| Step | Command / check | Expected | Observed |
|---|---|---|---|
| E-01 | `python scripts/run_phase_6_2_real.py` runs to completion | Exit code 0; runtime 5–30 minutes | _____ |
| E-02 | `results/phase_6_2_real/phase_6_2_real_paired_comparison.csv` row count | `wc -l` ≥ 11 (header + 10 scenes) | _____ |
| E-03 | `results/phase_6_2_real/phase_6_2_real_fleet_summary.json` `n_episodes` | ≥ 10 | _____ |
| E-04 | `results/phase_6_2_real/phase_6_2_real_pilot_report.md` size | Non-zero, contains "Headline result" + "Lemma-1 negative control" sections | _____ |

#### §7.2.4 Acceptance gates

The pilot is **reportable** if every gate below passes. If any gate
fails, the result is recorded as honest data — not as a pilot pass.

| Gate | Criterion | Source | Observed |
|---|---|---|---|
| **G-01: numerical correctness** | No scene errored out; CSV has one row per scene returned by `adapter.scene_ids()` | E-02 | _____ |
| **G-02: Lemma-1 negative control** | On `constant_bias_sanity` rows in the CSV, `mean_bcvf_total ≤ 1e-3` | CSV column `mean_bcvf_total` filtered by `failure_type == "constant_bias_sanity"` | _____ |
| **G-03: forecast-error sanity** | On all `failure_type` rows, A0 `err_A0` is in single-digit metres (≤ 5 m for a 2 s horizon at ~5 m/s) | CSV column `err_A0` | _____ |
| **G-04: attribution accuracy on responsive class** | Mean `attribution_hit_rate` on `camera_degradation` rows ≥ 0.5 | CSV columns filtered by `failure_type == "camera_degradation"` | _____ |
| **G-05: sign-test headline** | One-sided sign-test p-value ≤ 0.05 OR Wilson-CI lower bound on win rate > 0.5 (whichever the pilot reports as the headline) | `phase_6_2_real_pilot_report.md` headline section | _____ |
| **G-06: fleet artifact integrity** | `FleetSummary.to_dict()` round-trip reads back into Python without ValueError | `python -c "import json; from symbolu_robotics.bcvf_autonomous.analysis.io import episode_record_from_dict; ..."` | _____ |

#### §7.2.5 Sign-off

When G-01 through G-06 are all "pass":

1. Update the v0.5 brief footer to v0.6 with the headline number
   from the real-data run (replace
   `"§6.2 pilot runner executed end-to-end (N=21, ..., on RealisticNoiseAdapter)"`
   with the real-data equivalent).
2. Commit the three artifact files to `results/phase_6_2_real/` with
   the commit message stating the headline, sample size, and date.
3. Tag the commit `pilot-v6.2-real-passed-YYYY-MM-DD` so the
   downstream Series-A diligence package can reference a fixed
   point.

If any gate fails, document **which gate failed and why** in
`docs/experiments/phase_6_2_real_findings.md`. A clean negative
result is also a reportable outcome — the §6.1 protocol's
"informative null" pattern applies.
