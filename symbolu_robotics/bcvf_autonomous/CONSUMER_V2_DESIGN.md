# Consumer V2 — Schmitt-triggered softmin (§14a port)

Design notes for the V2 consumer pattern in `trust.py` — port of the
BCVF LLM §14a Scout consumer.

## §1 The chatter problem the V1 softmin has

V1 (the current default) is a smooth softmin over per-predictor BCVF
costs. Smoothness is a virtue when the input signal is noisy and the
output is a logit-blend in an LLM — neighboring tokens differ by
fractions of a logit and the softmin's gradient propagates the
information cleanly.

It is not a virtue when the output drives a physical actuator.
Borderline disagreements among predictors — e.g., two healthy
sensors at the noise floor with one very slightly louder — cause
the softmin's argmax to drift between predictors tick-to-tick, even
though no real failure has occurred. That drift becomes steering
chatter, throttle dither, or audible LiDAR-handoff in the SLAM
stack. Every actuator engineer has war stories about removing this
class of oscillation from production code.

The standard control-safety pattern for this is a **Schmitt
trigger**: hysteresis with two thresholds. A signal must rise above
`engage_threshold` for `T_engage` consecutive ticks to engage the
shaping; once engaged, it must drop below a strictly lower
`disengage_threshold` for `T_disengage` consecutive ticks to revert
to uniform weights. The asymmetric thresholds and the consecutive-
tick counters together kill chatter at the cost of slightly delayed
engagement and slightly delayed disengagement — both acceptable in
exchange for monotonic actuator behavior.

## §2 V2 = V1 + one top-level state machine

V2 does not replace any V1 mechanism. EMA centering, per-rollout
deadband, and §6.6a exclusion all stay exactly as they are. V2 wraps
the entire pipeline in a top-level state machine:

```
state ∈ {UNIFORM, ENGAGED}

if state == UNIFORM:
    weights = 1/M  (no shaping)
    if signal >= engage_threshold for T_engage consecutive ticks:
        state ← ENGAGED

if state == ENGAGED:
    weights = run_v1_pipeline(trajectories)  (EMA + deadband + softmin + exclusion)
    if signal <= disengage_threshold for T_disengage consecutive ticks:
        state ← UNIFORM
```

The engage signal is `bcvf_total.mean(axis=0)` — the population view
of disagreement across all K rollouts. Signal magnitudes follow the
characterization sweep numbers: nominal families produce near-zero,
failure families produce O(1) BCVF cost on the autonomous SE(2)
defaults. Setting `engage_threshold ≈ 0.5` and
`disengage_threshold ≈ 0.2` gives a clean separation with hysteresis
of `0.3`.

## §3 Veto

The existing `set_exclusion` mechanism (§6.6a — dynamic predictor
exclusion) already implements the veto piece of the §14a pattern: a
predictor whose mean cost exceeds `r × min_other_cost` for `T_exclude`
consecutive ticks is zeroed in the weight matrix and re-instated
after `T_reinstate` consecutive OK ticks. V2 reuses it as-is.

What V2 changes about exclusion: when the consumer is in `UNIFORM`
state, exclusion is **suspended** — neither the suspect nor OK
counters advance. This prevents a transient spike from accumulating
toward exclusion while the top-level state machine is still in the
"don't trust the signal" regime. Exclusion resumes the moment the
state transitions to `ENGAGED`.

## §4 Backward compatibility

V2 is opt-in via `set_v2_consumer(ConsumerV2Config(enabled=True))`.
The default (`enabled=False`) keeps the existing V1 behavior bit-for-
bit. Tests cover the regression: with V2 disabled the
TrustWeightResult is identical to the pre-V2 implementation.

## §5 Where the diagnostics live

`TrustWeightResult` gains two optional fields:

* `v2_state` — `"uniform"` or `"engaged"` or `None` if V2 is off.
* `v2_signal` — the scalar engage signal that drove this tick's
  state transition (or stay-in-state).

`TrustStepRecord` and `TrustShapedEpisodeRecord` propagate both
fields so an incident replay can answer "was the consumer in uniform
mode at tick 142, and if so what was the engage signal?" without
rerunning the simulation.

## §6 Tunables and defaults

| Knob | Default | Rationale |
|---|---:|---|
| `enabled` | `False` | Don't change V1 behavior unless asked. |
| `engage_threshold` | `0.5` | Above noise-floor cost; below sustained-failure cost. |
| `disengage_threshold` | `0.2` | Hysteresis of `0.3` keeps chatter in check. |
| `T_engage` | `3` | Three consecutive ticks ≈ 0.3 s at dt=0.1 — matches reaction-time budget. |
| `T_disengage` | `5` | Slightly slower disengage than engage — biases toward keeping the safety mode active. |

The thresholds match the magnitudes seen in
`characterization.run_primary_grid` — the `accelerating` and
`outlier` failure families produce BCVF totals well above 0.5; the
`baseline` and `noise_floor` families produce near-zero costs that
stay below 0.2.

## §7 What is intentionally not in scope

* No port of the LLM §14a "Scout" V1 vs V2 A/B framework. That's an
  experimental harness; the autonomous port lands the V2 mechanism
  itself, not the harness around it.
* No new veto axis. `set_exclusion` is the veto.
* No automatic threshold tuning. Thresholds are pre-committed; a
  caller running on different dynamics (highway vs urban) tunes via
  the config object.
