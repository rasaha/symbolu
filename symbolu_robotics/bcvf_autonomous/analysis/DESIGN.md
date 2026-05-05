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

* ~~No CSV / Markdown writer.~~ **Landed post-v0.7 (see §8).**
  ``FleetSummary.to_csv(path)`` and
  ``FleetSummary.to_markdown_report(path)`` emit auditor-facing
  frozen artifacts; both are pure stdlib and operate on either the
  batch ``aggregate_fleet`` output or
  ``StreamingFleetMonitor.summary(window=...).fleet``.
* ~~No real-time alerting. The harness is offline / batch. A
  streaming version is a separate project.~~ **Landed post-v0.7
  (see §7).** `StreamingFleetMonitor` provides rolling-window
  summaries and threshold alert rules.
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

## §7 StreamingFleetMonitor — online aggregation + alerting

`aggregate_fleet` answers *"summarise these N records"*. Production
SRE asks the harder question: *"what did the last 24 hours look
like across the whole fleet, and alert me if a metric crossed a
threshold."* `StreamingFleetMonitor` (in `analysis/streaming.py`)
serves that question.

### §7.1 What the streaming monitor stores

For every observed episode, the monitor keeps:

* `observed_at: datetime` — the wall-clock time the episode landed.
* The `EpisodeSummary` (a few KB) — already carries the cached
  detector outputs (argmax flips, V2 state flips, near-vetoes).
* A small per-predictor exclusion vector `(M,) int 0/1` — the only
  field `aggregate_fleet` needs that isn't on `EpisodeSummary`.

The raw `TrustShapedEpisodeRecord` (potentially MB) is **not**
retained — that's the whole point of streaming. A monitor running
on a 10k-trip-per-day fleet stores roughly 10 MB of summaries per
day, not 10 GB of records.

### §7.2 Ingestion paths

* `observe_episode(record, ...)` — convenience: take a raw record,
  summarise on the way in, store. Returns the `EpisodeSummary` so
  the caller can persist / inspect without re-summarising.
* `observe_summary(summary, per_predictor_excluded_ever, ...)` —
  fast path for distributed deployments. Each vehicle (or regional
  aggregator) summarises locally and ships the small payload to the
  central monitor; the central monitor never sees the raw record.

Both paths accept an optional `observed_at: datetime`; absent that
the configured `clock` callable is invoked. The clock is injectable
so tests don't need to monkey-patch wall time.

### §7.3 Eviction policy

Two independent caps, both default off:

* `retention: timedelta` — drop observations older than
  `now - retention` on every ingest. Bounds memory by time.
* `max_retained: int` — drop the oldest observation when the count
  exceeds the cap. Bounds memory by row count.

`prune(older_than)` lets a caller drive its own retention without
configuring the monitor (e.g. mirroring an external store's TTL).

### §7.4 Windowed summary — batch parity invariant

`summary(window=timedelta(hours=24))` returns a
`WindowedFleetSummary` covering `[now - window, now]`. `now`
defaults to the latest observation's timestamp (so tests don't
need a clock fake). `window=None` returns the entire retained
buffer.

The streaming monitor's load-bearing contract is **batch parity
within the window**: for any sequence of episodes fed to both the
monitor (`observe_episode` × N) and `aggregate_fleet` (batch),
the resulting `FleetSummary` is byte-identical. A buyer comparing
rolling-window numbers to historical batch numbers must see the
same aggregation logic — `tests/test_streaming_fleet.py` pins
this invariant directly.

### §7.5 Alert rules

```python
rule = AlertRule(
    name="chatter_p95_high",
    metric="argmax_flips_per_step.p95",   # dotted path into FleetSummary.to_dict()
    threshold=0.10,
    direction="above",        # or "below"
    min_episodes=20,          # suppress on undersampled windows
)
alerts = monitor.evaluate_alerts([rule], window=timedelta(hours=24))
```

`metric` is a dotted-path key into `WindowedFleetSummary.to_dict()`'s
`"fleet"` block — the same shape a downstream Prometheus textfile
exporter or alertmanager rule would index. A typo'd path raises
`KeyError` at evaluation time so a misconfigured rule fails loudly
rather than silently never firing. A path that legitimately resolves
to `None` (e.g. `v2_engaged_fraction.mean` when V2 was never
enabled in the window) is treated as a data-availability issue —
the rule simply doesn't fire.

### §7.6 What the streaming monitor is NOT

* Not multi-writer-safe. One ingest thread per monitor; multi-vehicle
  ingest fans summaries through `observe_summary` from one writer.
* Not a time-series database. The monitor keeps summaries; long-term
  history goes to an external TSDB / log warehouse.
* Not an alertmanager. The monitor evaluates rules and returns
  `Alert` objects with `to_dict()` payloads; routing /
  rate-limiting / deduplication is the caller's job.

## §8 Frozen artifacts — FleetSummary CSV + Markdown writers

`FleetSummary` exposes two regulator-facing writers so the SOTIF
clause-10 (operational design + field monitoring) audit pack ships
frozen deliverables, not a Python dataclass:

* `fleet_summary.to_csv(path)` — one row per episode with the
  headline metrics (id, classification, n_steps, M, argmax-flips +
  flip rate, V2 state flips, near-vetoes, fraction engaged,
  deadband-fired rate, BCVF totals, excluded-ever count). RFC-4180
  quoted via stdlib `csv`; column order pinned in
  `analysis.FLEET_CSV_FIELDS`.
* `fleet_summary.to_markdown_report(path, label=..., generated_at=...)`
  — fleet-level narrative with six sections: headline aggregates,
  classification breakdown, per-predictor exclusion incidence,
  near-veto roster, V2 state-flip roster, and a top-K per-episode
  index sorted by argmax-flip rate. Deterministic up to
  `generated_at`.

`render_fleet_csv` / `render_fleet_markdown` produce strings without
writing to disk; `write_fleet_csv` / `write_fleet_markdown` write
files (and `mkdir(parents=True, exist_ok=True)` on the way down).

Both writers are pure stdlib (no extra dependencies) and operate
on duck-typed inputs — the same renderer works on a `FleetSummary`
returned by `aggregate_fleet` or by
`StreamingFleetMonitor.summary(window=...).fleet`. SOTIF audits of
both batch (recall triage) and streaming (live SRE) pipelines emit
identically-shaped artifacts.
