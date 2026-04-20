# §6.2 Real-Sensor Pilot Plan

**Status.** Design landed; execution pending dataset access and
3–4 weeks of integration work per the §6.2 design-doc estimate.

## Goal

Validate the V1 trust-shaping configuration against **real sensor
traces** rather than the synthetic M1–M4 SE(2) predictors used in
§6.1. Closes the "synthetic predictors only" scope caveat from the
§6.1 final report (`phase_6_1_multiscenario.md`).

## Dataset choice — nuScenes primary, KITTI fallback

Recommending **nuScenes** as the primary pilot dataset.

| Axis | nuScenes | KITTI |
|---|---|---|
| Scene complexity | Urban (dense, diverse) | Highway-dominant |
| Annotations | 3D boxes, HD map, CAN bus, 6-camera rig | 2D/3D boxes, stereo, velodyne |
| Prediction benchmark | nuPrediction (published baselines) | KITTI tracking; prediction via subsets |
| Dataset size | ~350 GB full, ~15 GB nuScenes-mini | ~180 GB raw |
| Year | 2019, urban AV era | 2012, pre-modern AV |
| Failure-injection realism | Higher (urban edge cases) | Lower (highway is simpler) |
| Fundraising relevance | Higher (production AV stack match) | Lower (legacy benchmark) |

**Recommendation:** nuScenes-mini first (~15 GB, tractable local
disk), then full nuScenes once the pipeline is validated. KITTI
remains a fallback if nuScenes integration stalls on licensing or
tooling issues.

## Predictor construction from nuScenes

Build M = 4 predictors per scene, each producing SE(2) trajectory
predictions over a planning horizon H:

1. **M1 — HD-map prior.** Projects the ego's current pose onto the
   lane-centerline from the nuScenes map API, propagates at current
   velocity. Minimal state, robust to perception failure, weak under
   unusual geometry.
2. **M2 — Kalman kinematic extrapolation.** Constant-turn-rate
   constant-velocity (CTRV) filter on the ego's CAN-bus state
   (position, heading, velocity, yaw rate). Stateful, robust to
   single-frame sensor glitches, fails under fast maneuvers.
3. **M3 — Learned forecaster.** A lightweight trajectory forecaster
   trained on nuScenes-mini. Options in priority order:
     (a) nuPrediction baseline (CoverNet / MTP) — most
         reproducible, published weights.
     (b) Trajectron++ — stronger but more integration work.
     (c) A minimal in-house LSTM forecaster — fallback if (a)/(b)
         prove too heavy.
4. **M4 — "Failing" predictor.** M1 / M2 / M3 with an explicit
   failure injection pattern (see next section). Required so we have
   a ground-truth-labeled outlier BCVF should detect.

All four predictors must produce `(H, 3)` SE(2) trajectories (x, y,
θ) at 10 Hz over H = 20 steps (2 s horizon). The existing
`BasePredictor` interface is the extension point — each of M1–M4 is a
new `BasePredictor` subclass that wraps the nuScenes-specific data
access.

## Failure-injection protocol

To preserve methodological parity with §6.1, we need a **paired
scenario structure** — same ego trace, same M1–M3, but M4 exhibits
a controlled failure at a known time.

Four failure patterns (mirroring S2/S3/S4/S5 synthetic scenarios):

1. **GPS multipath** — M4 inherits M2's Kalman state, but the
   position update is corrupted by a 3 s windowed bias (~2 m lateral
   drift). Detection: pairwise disagreement between M4 and M1/M3
   grows over the 3 s window.
2. **Map misalignment** — M4 uses M1's map prior but with the lane
   centerline shifted 1 m laterally for the duration of the scene.
   Constant bias; Lemma 1 guarantees BCVF does not fire on this
   alone. Combined with the acceleration variant (§5: map shift
   that grows in magnitude) for the BCVF-responsive case.
3. **Camera degradation** — perception confidence drops in a 2 s
   window, causing M3 (learned forecaster) to emit unstable
   predictions. Should be detectable as increased 2nd-order
   disagreement in M3 even if M4 stays clean.
4. **Constant bias sanity** — M4 has a fixed yaw offset for the
   whole scene. BCVF should not fire (Lemma 1 benign). Negative
   control.

The failure window start time is the "onset time" analogous to
autonomy S3's 5 s failure onset. Each scene pairs (A0 trace, A3
trace) by using the same ego state sequence and M1–M3 outputs, with
A3 additionally running the trust computer and consensus planner.

## Planner integration

nuScenes provides the ego trace and sensor state; the planner does
not close the loop in simulation (we're replaying recorded data).
Two possible modes:

### Mode A — Open-loop planner evaluation

Replay the ego trace as ground truth; at each timestep, feed M1–M4
into the planner and record what plan it produces. Compare the
**consensus trajectory** against the next ~2 s of ground-truth ego
motion.

- Pros: simplest; no closed-loop dynamics.
- Cons: doesn't test whether the planner's output would recover the
  ego from a failure state.

### Mode B — Closed-loop with synthetic ego dynamics

Replay nuScenes ego state up to the failure onset, then switch to
the planner's output as the active control. Use the existing
`Simulator` from the autonomy kernel to propagate the ego forward
under the planner's control. This is the closest analogue to the
S1–S6 synthetic scenarios.

- Pros: same evaluation protocol as §6.1 — directly comparable.
- Cons: requires fitting the nuScenes ego dynamics to a bicycle
  model (approximation; loses some real-vehicle fidelity).

**Recommendation:** Mode B. The § 6.1 / §6.6a pipeline already
consumes `Simulator`-produced ground-truth trajectories, and the
statistical tests (sign-test, catastrophe count) assume simulator
dynamics. Switching to real vehicle dynamics would require a new
metric framework.

## Acceptance criteria

Mirror the §6.1 structure exactly:

- **Scope bar**: "All RESPONSIVE scenarios clear p < 0.05 at N ≥ 19
  paired under the V1 validated config."
- **Responsive = nuScenes scenes where M4's failure pattern
  produces an A0 catastrophe** (final |y| > 2 m lateral deviation).
- **Minimum scene count**: 21 paired scenes from nuScenes-mini's
  ~850 scenes, selected for diversity of failure pattern.

If at least one failure pattern type achieves p < 0.05 on 21 scenes,
§6.2 passes. If all four pattern types fail, §6.2 documents the
boundary of BCVF applicability in real-data context.

## Scope caveats (explicit, to preserve credibility)

- **nuScenes-mini only for the first pilot.** Full nuScenes is a V2+
  task.
- **Single city** (nuScenes = Boston + Singapore; scope to one city
  in the first pilot to reduce variance from map-quality differences).
- **Synthetic ego dynamics.** Real vehicle responses require V2
  vehicle-model calibration work.
- **Learned-forecaster as M3** inherits its training distribution.
  Predictions on out-of-distribution scenes may be unreliable and
  will be reported as a scope caveat, not masked.

## Implementation scaffold shipped in this session

Code plumbing in this session (`169dcd5`-range commits):

- `symbolu_robotics/bcvf_autonomous/datasets/__init__.py` —
  package with `DatasetAdapter` base class.
- `symbolu_robotics/bcvf_autonomous/datasets/base.py` — abstract
  interface: `load_scene(scene_id) -> SceneRecord` where
  `SceneRecord` carries ego state trace, M1–M4 predictor outputs
  at each timestep, and the failure-injection metadata.
- `symbolu_robotics/bcvf_autonomous/datasets/synthetic_realistic.py` —
  a drop-in adapter that produces **realistic-noise** synthetic
  traces: correlated Gaussian noise, non-Gaussian tails, bursty
  sensor dropouts. Bridges the gap between pure-SE(2) synthetic
  (§6.1) and real nuScenes data (§6.2). Useful as a pre-pilot
  sanity test the trust computer's numerics survive real-like
  noise without actual nuScenes access.

Execution (out of scope for this session, pending dataset access):

- `symbolu_robotics/bcvf_autonomous/datasets/nuscenes.py` — the
  real nuScenes adapter. Implementation: ~1 week. Requires
  `nuscenes-devkit` and nuScenes-mini on local disk.
- Predictor implementations (M1 HD-map, M2 Kalman, M3 learned,
  M4 failure-injected) — ~2 weeks.
- Pilot execution + analysis — ~1 week.
- **Total execution estimate:** 3–4 weeks after pipeline scaffold
  lands (this session).

## Timeline to first reportable pilot

Gated on dataset download + devkit integration; assuming one FTE
working on it:

| Week | Work | Deliverable |
|---|---|---|
| 1 | nuScenes-mini download; `DatasetAdapter` implementation; M1 HD-map predictor | Scene loading works end-to-end |
| 2 | M2 Kalman predictor; M3 learned forecaster integration (via nuPrediction baseline); M4 failure-injection harness | All 4 predictors produce (H, 3) trajectories |
| 3 | Mode-B simulator bridging; paired scene selection; N=21 sweep | First run of the V1 pipeline on real data |
| 4 | Analysis; sign-test; `phase_6_2_multiscenario.md` | Pilot report + decision gate |

## Risks and fallbacks

- **nuScenes licensing / access delays**: fall back to KITTI. Spec
  in this document is dataset-agnostic where possible; KITTI-specific
  adapter is ~3 days of incremental work.
- **nuPrediction baseline reproducibility**: fall back to Trajectron++
  (more integration work but better-maintained) or a lightweight
  in-house LSTM (fast but weaker).
- **Closed-loop mode B proves intractable**: drop to Mode A
  (open-loop evaluation) and rework the metric framework to use
  ground-truth-trajectory prediction error instead of simulator
  catastrophe rate.

## What §6.2 is NOT trying to prove

- **Not trying to beat Waymo / Cruise performance.** The V1 runtime
  is an arbitration layer, not a full AV stack.
- **Not claiming generalization to all AV scenarios.** nuScenes-mini
  is one city, one weather condition, one vehicle class. Broader
  claims require §6.2 follow-up with full nuScenes + cross-dataset
  validation.
- **Not replacing real-world road tests.** Simulation-based
  validation at N=21 paired is a statistical-significance result
  for the trust-shaping math; real-world certification is §6.8 +
  Series-A territory.

## Next step after this session

Assign an engineer to Week 1 of the timeline above. The scaffold
shipped here should compile and pass import tests immediately; the
gap to a first real-data pilot is pipeline work, not design work.
