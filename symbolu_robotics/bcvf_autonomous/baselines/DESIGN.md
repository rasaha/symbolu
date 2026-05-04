# BCVF Autonomous — Apples-to-apples Baseline Shootout

Implements the audit's #4 next-step recommendation: ship a fair
comparison of BCVF against the alternatives a production integrator
would consider — Kalman-style EKF fusion, majority-vote arbitration,
and the always-trust-anchor null baseline. The deliverable is a
markdown table the BD team can hand to a buyer asking *"how does
this compare to what we already have?"*

## §1 What the shootout measures

For each combination of (arbitrator, scenario family, seed), the
shootout records four metrics:

| Metric | Definition | Higher / lower? |
|---|---|---|
| **Consensus XY error** | Mean Euclidean distance between the arbitrator's `(H, 3)` consensus output and the ground-truth trajectory | Lower better |
| **Attribution hit rate** | On failure families (outlier / sensor_dropout / accelerating), fraction of seeds where the arbitrator ranks the injected outlier predictor in the top half of attribution scores | Higher better |
| **False-attribution rate** | On Lemma-1 benign families (constant_bias / linear_drift), fraction of seeds where the arbitrator gives ANY predictor a non-negligible attribution score | Lower better |
| **Per-tick wall time** | Median across seeds of the per-tick arbitrator runtime in microseconds | Lower better |

Failure families test the arbitrator's ability to detect a known
miscalibrated predictor; benign families test whether the
arbitrator falsely flags healthy predictors that happen to disagree
in Lemma-1-invariant ways (constant offset, linear drift).

## §2 The four arbitrators

### 2.1 `BCVFArbitrator`
Wraps the existing `compute_bcvf_per_step` kernel + the V1 trust
shaper (`TrustWeightComputer`). Per-predictor attribution is the
sum-across-horizon of per-step BCVF cost attributed to each
predictor. Consensus is the trust-weighted mean of the M trajectories.

### 2.2 `EKFArbitrator`
A standalone NumPy EKF implementation operating at the predictor-
arbitration interface. At each horizon step, treats each predictor's
pose as a noisy measurement with covariance `R_i`, applies a Kalman
update with **Mahalanobis outlier rejection** (per-measurement
3-sigma gate — the standard mechanism `robot_localization` uses).
Per-predictor attribution = max-across-horizon Mahalanobis distance.
Consensus = filtered state at each horizon step.

### 2.3 `MajorityVoteArbitrator`
At each horizon step, clusters the M predictor positions
(threshold-based, default 0.5 m). Picks the largest cluster as the
"majority." Consensus = mean of majority cluster. Per-predictor
attribution = Euclidean distance from majority-cluster centroid,
summed across horizon.

### 2.4 `AnchorArbitrator`
The null baseline: always trust the anchor predictor (default
index 0). Consensus = `trajectories[anchor_idx]`. Attribution =
all zeros (no arbitration). This is what running with no
arbitration layer at all looks like.

## §3 Scope caveats — read before quoting numbers

The EKF here is a **standalone NumPy implementation** with the same
mechanics `robot_localization` uses (Kalman update +
Mahalanobis outlier rejection per measurement) operating at the
predictor-arbitration interface BCVF defines. It is **not** the
literal `robot_localization` package.

Justifications:

1. `robot_localization` is a sensor-fusion package — it ingests
   raw sensor messages (IMU, GPS, odometry) and outputs a state
   estimate. It does not arbitrate between *predictors* whose
   outputs were already produced by upstream stacks. Comparing
   `robot_localization` directly to BCVF would be category-mixing.
2. The fair comparison is: *given M predictor trajectories at the
   same interface BCVF consumes, what does a Kalman-style fusion
   produce?* Mahalanobis-rejection EKF over predictor outputs is
   that fair comparison.
3. A production integrator may run `robot_localization` *under*
   our predictor stack — its output is then one of the M predictor
   inputs. The shootout doesn't displace `robot_localization`; it
   asks *"does our arbitrator do better than running a simpler
   arbitrator on top of any sensor fusion?"*

A production integrator running their actual `robot_localization`
stack should re-execute the shootout on their own predictor
outputs to produce numbers calibrated to their setup. The shootout
runner is dataset-agnostic by design.

## §4 Reproducibility

The shootout is pure NumPy + stdlib. No ROS install, no real-data
access, no GPU. One command:

```python
from symbolu_robotics.bcvf_autonomous.baselines import run_shootout
result = run_shootout(N=10, output_dir="results/baseline_shootout")
```

Wall time at N=10: ~30 s on a CPU laptop. Output: `shootout.csv`,
`shootout.json`, and `shootout_report.md` in `output_dir`.

## §5 What "passing" looks like for BCVF

The shootout doesn't pre-commit to a "BCVF wins" outcome. It
passes if, on the failure families where BCVF is designed to
help (outlier, sensor_dropout, accelerating), BCVF's attribution
hit rate **strictly exceeds** the alternatives — otherwise the
brief's "BCVF is the right arbitration layer" claim has no
evidence behind it.

Where BCVF doesn't strictly beat the alternatives — for example, if
EKF's Mahalanobis rejection is comparable on `outlier` — the result
is documented honestly. The point of the shootout is to surface
real signal about where BCVF helps, not to manufacture a marketing
table.
