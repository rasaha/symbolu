# HarmonicEventCollector — Preregistration

**Question:** can a fixed-clock harmonic collector turn long raw streams into a
small set of temporally meaningful events (Stage A), and do harmonic temporal
summaries then improve event-based quadratic reasoning over ordinary event
fields and statistical summaries (Stage B)?

**Status:** preregistered before any implementation or run; gates and failure
conditions are frozen at the commit that introduces this file. Hardware: 4 CPU
cores, no GPU — micro scale; no verdict here can exceed PROVISIONALLY
SUPPORTED. Owner-ratified stop rule: **if Stage A and Stage B both pass, the
synthetic study stops here** and real-telemetry validation is recorded as the
next experiment; **no extension of this synthetic study through amendments.**

**Isolation and naming contract:** nothing under `symbolu/lightweight_phase/`
is imported or modified. The collector is named `HarmonicEventCollector` and is
a classical fixed-frequency mechanism (per `experiments/phase_temporal_collector`
Sweep 3, G1); it is never called Phase. No outcome here reverses the closed
`experiments/phase_lc` semantic-retrieval verdict or validates the frozen Phase
equations. Deferred by ratification: the explicit cos(φ_q − φ_e) attention
bias, generated-explanation evaluation, and cross-signal coherence — streams
are single-signal.

---

## Stage A — eventization on event-labelled streams

**Streams.** T_A = 4096 samples, regular Δt = 1. Base signal: one sinusoid,
period from the pools of `experiments/phase_temporal_collector`
([6,12]∪[20,36]∪[64,96]), amplitude ∈ [0.7, 1.3], plus Student-t (df = 5)
observation noise at 0.05·amplitude and a slow random-walk drift (σ = 0.01) as
distractors that must NOT produce events. Ground-truth labelled event families
injected per stream (onsets separated by ≥ 32):

| Family | Count/stream | Nature | Match tolerance |
|---|---|---|---|
| `periodic_deviation` | 2–4 | one-off bump near a cycle peak, shifted ±0.25 P, amp 0.8–1.2× base | ±8 |
| `phase_shift` | 1–2 | persistent phase jump ∈ [0.5π, 1.5π] | ±24 |
| `regime_change` | 1–2 | persistent period ×[1.3, 1.8], or amplitude ×[0.4, 0.6], or oscillation collapse | ±24 |
| `quasi_periodic_event` | ~11–16 | decaying spikes, quasi-period ∈ [256, 384] (±10% jitter), amp ~2.5 | ±8 |
| `rare_aperiodic` | 1–3 | isolated non-periodic transient (pulse/step-decay, amp 1.5–3, width 4–10) | ±8 |

**Detectors.** (1) `StatChangeDetector` baseline: multi-timescale decayed
mean/variance z-scores plus a CUSUM-style change statistic, refractory period.
(2) `HarmonicEventCollector`: the fixed clock bank of Sweep 3 (K = 8 periods
log-spaced 4→128, reimplemented here) maintaining decayed complex accumulators;
expected-value reconstruction; event triggers from residual-vs-expectation,
per-clock magnitude change, and per-clock angle change; emits typed events
carrying the temporal-profile fields (event_time, family guess, current value,
trend, dominant period, phase position, cycle amplitude, phase shift, residual,
confidence, raw-evidence index). Both detectors are streaming with bounded
state.

**Threshold discipline.** All thresholds (and the declared coarse grids they
are searched over) are fit ONLY on 64 training streams (generator seed 60000),
maximizing macro recall subject to a training reduction ≥ 110× (fitted with
margin over the 100× gate), then **frozen** and evaluated once on 128 held-out
streams (generator seed 61000). Iteration on training streams is permitted
until the freeze; the held-out set is evaluated exactly once per detector.

**E-GATE (frozen; applies to HarmonicEventCollector on the held-out set):**
1. `rare_aperiodic` recall ≥ **0.95**;
2. macro recall (unweighted mean over the 5 families) ≥ **0.90**;
3. no family recall < **0.85**;
4. reduction = raw observations / emitted events ≥ **100×**.

**Failure of any E-GATE condition stops Stage B entirely and issues no
reasoning verdict** — the outcome is then "eventization NOT SUPPORTED at
tested scale," full stop. The StatChangeDetector comparison, precision, and
per-family false-positive counts are reported informationally and are not
gated.

## Stage B — event-based reasoning on one frozen common event set

Runs only if E-GATE passes. **Common event set:** HarmonicEventCollector with
the Stage-A frozen thresholds is run once over each Stage B stream; the
resulting event set (times, families, fields) is identical for arms A–C by
construction, so detection differences cannot contaminate reasoning
comparisons.

**Streams.** T_B = 768; same families and distractors, with causal structure:
quasi-periodic spikes (quasi-period ∈ [96, 160]) recur predictably; after each
`phase_shift` or `regime_change` onset, with probability 0.8 a `rare_aperiodic`
event fires at +[20, 60] samples (otherwise rare events are uniform).
**Targets at a query time t_q:** forecast x[t_q+1 .. t_q+8] (nMSE), and
outcome = does any ground-truth onset occur in (t_q, t_q+64] (BCE; AUC
informational). Training queries: 8 positions sampled per stream from
[128, 700]; **evaluation queries frozen at {384, 512, 640}**. Val/test stream
sets frozen by generator seeds (62000 / 63000; 100 / 200 streams).

**Arms** (shared 2-layer quadratic reader d=64, 4 heads; total parameters
matched across arms to <1% via FFN width; 3 seeds {0,1,2}; identical data,
optimizer, steps):

- **A `event_plain`:** attention over emitted-event tokens (relative time,
  family one-hot, onset value) + query token (with the 8 future offsets).
- **B `event_stats`:** A + the multi-timescale decayed statistical summary
  tokens of Sweep 3's arm B, computed at t_q.
- **C `event_harmonic`:** B + the K=8 fixed harmonic summary tokens of Sweep
  3's arm C at t_q, and two per-event profile fields (phase position within
  the dominant clock at onset; residual magnitude at onset).
- **D `raw_quad`:** full-raw-timeline causal transformer reference with dense
  per-position supervision and clock-bank sinusoidal time encoding (the
  Sweep 1–2 validity lesson, carried forward).

**V-GATE (frozen, ratified wording — D must beat A):** seed-averaged forecast
nMSE(D) < nMSE(A) AND seed-averaged outcome BCE(D) < BCE(A). Failure → Stage B
INVALID AT TESTED SCALE; no H-GATE verdict.

**H-GATE (frozen):** in **3/3 seeds**, per-seed relative improvement of C over
B ≥ **0.05** on forecast nMSE AND ≥ **0.05** on outcome BCE
(RI(a vs b) = (m_b − m_a)/m_b, lower-is-better metrics).

**Reported separately, never gated:** carried state memory (floats), attention
item counts (events + summaries vs raw T), wall-clock computation, AUC,
per-family tables, StatChangeDetector comparison.

## Outcomes (frozen)

- E-GATE fails → eventization NOT SUPPORTED at tested scale; stop.
- E-GATE passes, V-GATE fails → Stage B INVALID AT TESTED SCALE (reference
  did not validate); eventization result stands alone.
- V-GATE passes, H-GATE fails → harmonic summaries add no reasoning value
  beyond statistics at tested scale (eventization result stands).
- All pass → both PROVISIONALLY SUPPORTED (micro scale); **stop** and record
  real-telemetry validation as the next experiment.
