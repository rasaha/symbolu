# Consumer V2 Promotion Decision — v0.6 Sweep Result

**Decision: V2 not promoted. Threshold recalibration scoped to Q2.**

This document records the empirical finding from the v0.6 V2
chatter-reduction sweep. It is the artifact a future engineer (or
SOTIF auditor) needs to understand *why* V2 stayed opt-in even
though the audit's #3 next-step recommended evaluating promotion.

## §1 The audit recommendation

> "Run the §6.1 S3_accel sweep with V2 enabled vs V1, quantify
> per-step argmax-flip rate reduction, then promote V2 to default
> if (a) chatter rate drops materially and (b) the rescue pattern
> is preserved."

Acceptance gates encoded in `v2_chatter_sweep.py`:

| Gate | Bar | Why |
|---|---|---|
| Chatter | Median per-seed flip-rate reduction ≥ 50% AND V2-wins-per-seed rate ≥ 70% | "Materially" means the per-step argmax noise that drives actuator chatter visibly drops |
| Rescue | V2 collisions on V1-rescues ≤ V2-rescues on V1-collisions AND McNemar one-sided p > 0.05 | V2 must not introduce more catastrophes than it prevents |

## §2 What was measured

Two paired V1-vs-V2 sweeps via `v2_chatter_sweep.py`:

1. **Chatter scenario:** `S1_normal_driving` (no failure injected).
   N=5 paired seeds at K=64 rollouts, H=50 horizon.
2. **Rescue scenario:** `S3_map_error_accel` (the §6.1 responsive
   case). N=5 paired seeds at K=128 rollouts.

Per seed both V1 (V2 disabled) and V2 (Schmitt-triggered consumer
on) ran the full simulator + planner + trust pipeline. The
trust-diagnostics recorder captured per-step argmax flips and V2
state distribution; the simulator captured collision outcomes.

A second chatter sweep at 50×-lower V2 thresholds
(`engage_threshold=0.01`, `disengage_threshold=0.005`) was added to
distinguish "design wrong" from "thresholds wrong."

## §3 The result

### Chatter scenario (`S1_normal_driving`)

| Tuning | Median V1 rate | Median V2 rate | Reduction | V2 ENGAGED ticks | Gate |
|---|---:|---:|---:|---:|---|
| Default (engage=0.5, disengage=0.2) | 0.7739 | 0.7739 | **0.6%** | 198/200 (99%) | **FAIL** |
| Recalibrated (engage=0.01, disengage=0.005) | 0.7688 | 0.7739 | **0.5%** | 198/200 (99%) | **FAIL** |

The per-seed flip-rate distributions for V1 and V2 are
indistinguishable — every seed shows V2 within 1% of V1's flip
rate, in both directions, regardless of the threshold setting.

### Rescue scenario (`S3_map_error_accel`, K=128, N=5)

| Metric | V1 | V2 |
|---|---:|---:|
| Median argmax-flip rate | 0.7995 | 0.7970 |
| Collisions | 0 / 5 | 0 / 5 |
| ENGAGED ticks (V2) | — | 398 / 400 |

| Gate | Value |
|---|---|
| V2 broke a V1 rescue | 0 |
| V2 fixed a V1 collision | 0 |
| McNemar one-sided p (V2 worse) | 1.0000 |
| Rescue gate | **PASS** (trivially — no deviation) |

V2 stayed ENGAGED on S3_accel as predicted by the structural
finding. With identical engaged-mode behavior, V1 and V2 produced
identical collision outcomes — neither rescued (no collisions to
rescue at K=128 — the §6.1 production result was at K=1000), and
neither introduced a new collision. The rescue gate trivially
passes because V2 didn't deviate from V1 on this scenario.

**Two takeaways:**
* V2 is provably non-harmful on the §6.1 responsive scenario at
  this K — the rescue gate would still pass at K=1000 as long as
  V2 keeps reducing to V1.
* The chatter gate result on the nominal scenario is the binding
  constraint, and that gate failed (0.6% reduction vs the 50%
  bar). Decision: non-promotion is the right call.

## §4 Why this happened — the structural finding

V2's promotion is gated on UNIFORM-mode behavior (forced uniform
weights → zero argmax flips). To stay UNIFORM, the engage signal
`bcvf_total.mean(axis=0)` must stay below `engage_threshold`
across most ticks. The empirical reality on autonomy data:

* On `S1_normal_driving` (no failure injected) at K=64, mean
  BCVF cost across rollouts is *already* > 0.5 — driven by
  AR(1)-correlated predictor noise + the second-difference
  amplification 1/dt² that makes BCVF sensitive to even small
  per-step disagreements.
* Lowering the threshold to 0.01 doesn't help — mean BCVF cost
  routinely exceeds even that bound on K=64 nominal-driving
  rollouts.
* V2 therefore engages within the first 2 ticks and stays
  engaged for the entire scenario. With V2 ENGAGED, the V1
  pipeline runs unchanged and V2 has no chatter effect.

The Consumer V2 design (Schmitt-triggered hysteresis around an
engage signal) is sound for domains where the signal magnitude
on quiet inputs is bounded *below* the engage threshold. That
holds for the LLM-domain analog the design ports from. It does
not hold for autonomy BCVF on K≥64 rollouts at the thresholds
calibrated against LLM-domain magnitudes.

## §5 What this means for the brief

* The v0.5 caveat *"Consumer V2 is opt-in, not the default"*
  upgrades from defensive to **evidence-backed**. We measured;
  default-on V2 reduces to default-on V1 in autonomy practice.
* V2 stays an opt-in safety feature for integrators whose BCVF
  magnitudes match the LLM-domain hysteresis design (e.g., a
  smaller K, a very-low-noise sensor stack, or a different
  engage signal).
* The v0.5 brief's **"V2 chatter-reduction sweep"** roadmap item
  (Q1) is moved off the roadmap as **landed-with-non-promotion**.

## §6 Recalibration paths for Q2

Three concrete next moves the next engineer can investigate, in
priority order:

1. **Replace the engage signal with `bcvf_total.min(axis=0)`** —
   the *least-noisy* rollout's BCVF cost, instead of the
   population view. On nominal data, the minimum across K=64
   rollouts is much smaller than the mean (one rollout gets
   lucky control noise that produces small predictor
   disagreement). V2 might stay UNIFORM on those quiet-min
   rollouts and only engage when *every* rollout reports
   meaningful BCVF.
2. **Threshold against a trailing-window median** — instead of
   a fixed magnitude, track the median engage signal over the
   last N ticks and engage only when the current signal is some
   multiple above that floor. Adapts to the scenario's
   noise level.
3. **Per-scenario-class threshold ladder** — different scenarios
   produce different BCVF magnitudes (urban vs highway, rainy
   vs dry). A scenario-classifier upstream of V2 could pick a
   threshold appropriate to the operating regime.

Any of these is ~1 week of work. None requires real-data access.

## §7 Reproducer

```bash
cd /workspace/symbolu       # or local clone
source venv/bin/activate
python -c "
from symbolu_robotics.bcvf_autonomous.v2_chatter_sweep import (
    V2ChatterSweepConfig, run_v2_chatter_sweep,
)
cfg = V2ChatterSweepConfig(
    scenario_name='S1_normal_driving', N=5, mppi_rollouts=64,
    output_dir='results/v2_chatter_S1_n5',
)
r = run_v2_chatter_sweep(cfg)
print(r.median_flip_rate_reduction, r.chatter_gate_pass)
"
```

Wall time: ~3.5 min for N=5, ~14 min for N=21 at K=64. Reproduces
the result above bit-for-bit because `RealisticNoiseAdapter`-style
trajectories don't enter — the scenario's predictor RNG is
seeded.

---

*Recorded May 2026. Decision is honest non-promotion; recalibration
work scoped to Q2.*
