# Predictor-Trust Track — Closure Note

**Scope:** closes the LLT-Kalman line of amendments (A0–A3) on the
predictor-trust redesign. Sources: `ROBOTICS_LLT_KALMAN_TRUST_RESULTS.md`
§7–§10; `PREDICTOR_TRUST_V2_PREREGISTRATION.md` §7 (D1, A1, A2, A3);
`robotics_reliability_bench/results/`. No code, frozen config, or committed
result is changed by this note.

## Question

Which statistic does PTR-V2 carry forward as primary?

**The frozen deterministic baseline** (`predictor_trust_baseline.
DeterministicTrustBaseline`: pooled robust scale, 12-tick window, 8-tick
sustain). `[V]` It is the only detector that held zero false alarms under
every noise model tested: white (FA 0.040 on the held-out corpus, all from
`noisy_unbiased`), AR(1)-correlated (0.00 in the A2 ablation), and the full
realistic pipeline (0.156, the lowest of any system). `[V]`

## What A1 is retained as

`LLTKalman-A1` (`llt_kalman_trust.A1_CONFIG`) is retained as a
**white-noise-only detection accelerator**, not a primary statistic. `[V]`
On the held-out white-noise corpus it dominates the baseline: recall 1.00,
false-alarm 0.000, common-mode 0.00, delay 6.3 vs 17.0 ticks (`A1_ADOPT`).
On AR(1)-correlated noise it fails the preregistered pilot (`A2_FAILS`:
false-alarm 0.222, common-mode false detection 0.233, 83 % of benign
400-tick scenes flagged). `[V]` The assumption under which A1 may run is
therefore: residual noise white at the tick scale, or a calibrated
per-predictor covariance supplied externally. `[I]` BCVF's role is
unchanged: an optional latency feature over whichever primary is used. `[V]`

## Open blockers

1. **Real-sensor data access** `[G]`. `NuScenesAdapter` is unimplemented
   scaffolding; no dataset is on disk; nuscenes.org is unreachable from the
   execution environment. Every result in this track is synthetic. The
   migration gate "real-sensor pilot" is not discharged by A0–A3.
2. **The sustain-length trade-off** `[I]`. A1's delay win comes from
   `bias_sustain=4`. Under correlated noise, four ticks is shorter than the
   noise correlation time, and A3 showed the coloured-noise parameters are
   not causally identifiable inside that window (108 configs, 0 survivors;
   `φ̂` collapses on the heading axis). `[V]` The baseline's 8-tick sustain
   and 12-tick window are the implicit fix. Any faster detector must reopen
   this frozen parameter, which is a new amendment.

## The one experiment worth funding

Implement `NuScenesAdapter.load_scene` on nuScenes-mini and re-run
`a2_realistic_pilot.py` unchanged, frozen systems only, preregistered as
A4. `[R]` The synthetic track has now shown three times that each gain over
the baseline vanished at the next layer of realism; only real residual
noise can settle whether the baseline's margins are conservative or
necessary. Further synthetic amendments are not recommended.

## Recommendation

Carry the deterministic baseline forward as PTR-V2 primary. Record A1 as
an opt-in accelerator gated on a white-noise check. Close the LLT-Kalman
amendment line pending real-sensor data. `[R]`
