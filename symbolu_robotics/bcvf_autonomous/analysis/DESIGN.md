# BCVF Autonomous — Post-hoc Analysis Harness

Fleet-scale aggregator over per-episode trust diagnostic records.
Pays for itself the first time you need to triage a recall: a
SOTIF / ISO 26262 audit of a fielded vehicle population usually
turns into "give me, for the last 10 000 trips, every tick where
trust flipped between predictors and every tick where a predictor
came close to being vetoed but wasn't." This module turns that
question into a one-liner.

## §1 What the harness operates on

* A list of `TrustShapedEpisodeRecord` instances (the typed
  per-tick artifact emitted by `TrustDiagnosticsRecorder.finalize()`).
* Optional per-episode classification labels (free-form strings —
  typically `"collision"` / `"no_collision"`, but any taxonomy works).
* Optional per-episode metadata dicts (scenario, seed, vehicle id,
  whatever the fleet logger bolts on).

Records are pure dataclasses with NumPy arrays — no dependency on
the simulator, planner, or BCVF kernel. Loaded from disk via
`load_episode_from_json` if they were dumped by `Runner.run()` with
`trust_diagnostics_path` set; constructed in-memory in tests.

## §2 What the harness reports

Three event detectors plus two aggregators.

### 2.1 Argmax flips (`find_argmax_flips`)

A flip is a tick where `argmax(per_step_weights[t])` differs from
`argmax(per_step_weights[t-1])`. In V1 this is the chatter signal
the audit explicitly flagged: each flip means the trust-weighted
consensus picked a different lead predictor that tick. With V2
engaged the flip count drops sharply (Schmitt trigger holds);
without V2 it can spike on borderline disagreements.

For each flip, the harness records: episode id, tick, from-predictor,
to-predictor, and the weight vector at the tick (so a reviewer can
see whether the flip was a clean handoff or a marginal tie).

### 2.2 V2 state flips (`find_v2_state_flips`)

A V2 state flip is a transition `UNIFORM ↔ ENGAGED`. The harness
counts them, captures the engage signal at the transition, and
flags episodes that flipped suspiciously many times — a sign that
the engage / disengage thresholds are mistuned for the dynamics
seen by that vehicle / scenario.

### 2.3 Near-vetoes (`find_near_vetoes`)

A near-veto is a predictor that reached `near_veto_fraction ×
exclusion_T` consecutive-suspect ticks during the episode without
ever being excluded. Default fraction `0.7` — the predictor was 70 %
of the way to a hard veto.

Near-vetoes are the SOTIF tell: a predictor that keeps almost-failing
across many trips is the next one to actually fail in the field. A
fleet-scale near-veto histogram tells the platform team where to
look before a customer-facing incident forces them to.

### 2.4 EpisodeSummary

Per-episode roll-up:

* `n_steps`, `M`, classification label
* `n_argmax_flips`, `n_v2_state_flips`, `n_near_vetoes`
* `fraction_engaged` — fraction of ticks where V2 was ENGAGED.
  When V2 is disabled, this is left as None.
* `excluded_ever_count` — predictors excluded at any tick.
* `mean_bcvf_total`, `max_bcvf_total`
* `deadband_fired_rate` — fraction of ticks dominated by deadband.
* `near_veto_peak_fraction` — for each predictor, the peak
  `consec_suspect / exclusion_T` seen during the episode.

### 2.5 FleetSummary

Roll-up across many `EpisodeSummary` rows:

* Counts per classification label.
* Aggregate flip rates: mean / p50 / p95 / p99 of argmax flips per
  step across episodes.
* Mean / p95 of `fraction_engaged` (when V2 was enabled).
* Per-predictor exclusion-incidence rate.
* Near-veto roster — every predictor in every episode that crossed
  `near_veto_fraction × exclusion_T`.

## §3 Polarity / consumer of the report

The harness returns dataclasses; serialization to CSV / Markdown is
left to the caller because formats differ between regulators
(NHTSA OTA reporting differs from a UN ECE R155 packet). The
canonical use cases are:

1. **Recall triage**: load all post-incident vehicles' episode
   records, group by classification, find the most-flipping
   predictors and most-frequent near-vetoes — points the
   investigation at the sensor stack. Without this, a recall team
   spends weeks correlating dashcam footage with raw logs.

2. **Pre-launch readiness**: aggregate every test-track and
   simulator episode; assert that the FleetSummary's collision-rate
   regression bound holds. Done as a CI step before each release.

3. **Continuous deployment regression**: run the harness against a
   sliding window of fleet trips weekly; alert when `argmax_flips
   per step` drifts up — a signal that the trust pipeline is
   beginning to chatter under live conditions before customer
   complaints arrive.

## §4 What is intentionally not in scope

* No CSV / Markdown writer. The report is a dataclass; writing it
  to a particular regulator's format ties the module to that
  regulator's spec. The tests show the dataclass-to-dict pattern.
* No real-time alerting. The harness is offline / batch. A
  streaming version is a separate project.
* No statistical-significance testing on the deltas (e.g.,
  "is the flip rate significantly higher this week than last
  week?"). The aggregator returns rates; the caller picks a test.
* No implicit fleet schema. The harness takes `(records,
  classifications, metadata)` lists and returns aggregates.
  Callers wire their own provenance.

## §5 Public surface

```python
from symbolu_robotics.bcvf_autonomous.analysis import (
    # event detectors
    find_argmax_flips,
    find_v2_state_flips,
    find_near_vetoes,
    # aggregators
    summarize_episode,
    aggregate_fleet,
    # io
    load_episode_from_json,
    # types
    ArgmaxFlip, V2StateFlip, NearVeto,
    EpisodeSummary, FleetSummary,
)
```

All event-detector functions accept a `TrustShapedEpisodeRecord`
plus an optional `episode_id` string. All aggregator functions
return dataclasses with `.to_dict()` methods for downstream JSON
serialization.

## §6 Performance budget

* Linear in `n_steps × M` for every detector — no quadratic ops.
* `aggregate_fleet` is O(N_episodes) plus per-episode O(T × M);
  for 10 000 episodes × 1 000 ticks × 4 predictors that's 40 M
  cell touches in NumPy, ~1 s on a laptop. Suitable for nightly
  CI; not the hot path.
* The harness allocates one EpisodeSummary per episode plus one
  FleetSummary; memory bounded by the input records.
