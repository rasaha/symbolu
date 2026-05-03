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
