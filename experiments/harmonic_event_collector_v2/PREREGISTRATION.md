# HarmonicEventCollector V2 — Preregistration

**Question:** do two targeted detector corrections — protected reference
updates after disturbances, and sequential accumulated evidence for
slow-reveal changes — lift eventization past the unchanged E-GATE that V1
failed?

**Status:** preregistered before any V2 implementation; frozen at the commit
introducing this file. Owner-ratified terminal rule: **if Stage A fails any
E-GATE condition on the fresh held-out set, this line of work stops
permanently — no Stage B, no V3, no threshold changes, no reasoning verdict.**
If Stage A passes, Stage B runs exactly as preregistered in
`experiments/harmonic_event_collector/PREREGISTRATION.md` (arms, V-GATE,
H-GATE, seeds, metrics), with the execution details fixed below.

**Contracts (all owner-ratified):** V1 is not modified and its held-out data
(seed 61000) is never reused for fitting, selection, or evaluation. Stream
generation and the StatChangeDetector baseline are IMPORTED UNCHANGED from V1.
The ±24/±8 ground-truth matching tolerances are unchanged. Nothing under
`symbolu/lightweight_phase/` is imported or modified; the collector is never
called Phase; no outcome reverses `experiments/phase_lc`. Hardware: 4 CPU
cores, no GPU; verdicts capped at PROVISIONALLY SUPPORTED.

## Stage A — fresh data, unchanged gate

Streams: V1's `gen_stage_a` (identical distribution), fresh seeds — training
64 streams (seed **70000**), held-out 128 streams (seed **71000**).

**E-GATE (unchanged from V1):** rare_aperiodic recall ≥ 0.95; macro recall
≥ 0.90; no family recall < 0.85; reduction ≥ 100×. Held-out is evaluated
exactly once per detector after parameters and thresholds are frozen from
training streams only (fit constraint: training reduction ≥ 110×; gate-aware
selection as in V1).

**The two targeted corrections (the only detector changes):**

1. **Protected reference updates.** The seasonal reference reads from a
   parallel clean history: a sample whose residual exceeds 3× the robust
   residual scale is flagged disturbed and stored as the expected value
   (imputed) instead of the observation, so a past event cannot contaminate
   the reference one period later. To let genuinely persistent changes be
   adopted, imputation runs at most `protect` consecutive samples (grid
   {8, 16, 32}); after that the observations are accepted and the reference
   heals. The 3× flag threshold is fixed, not fitted.
2. **Sequential accumulated evidence.** Two accumulator channels for
   slow-reveal changes, both edge-triggered like every channel: a CUSUM on the
   seasonal surprise (as in V1) and a new CUSUM on the signed seasonal
   envelope log-ratio (grid {4, 7, disabled}), which integrates a gradual
   amplitude decline past threshold well inside the ±24 tolerance.

Everything else (clock bank K=8, period refinement, median-of-3 seasonal
reference, robust variance, quiet-window edge triggering, refractory) carries
over from V1. Declared threshold grids: res {3,4,5} · mag {0.6, disabled} ·
ang {0.8, disabled} · env {0.35, 0.5, 0.7} · cus {6, 10, disabled} ·
ecus {4, 7, disabled} · refractory {12, 16, 24} · protect {8, 16, 32}.

## Stage B — execution details (only if E-GATE passes)

Protocol, arms A–D, V-GATE, and H-GATE exactly as frozen in V1's
preregistration. Execution details fixed now: training uses a precomputed pool
of 512 Stage-B streams (seed **64000**) with the frozen common event set and
summary-token tracks computed once (the collector and summaries are
deterministic and frozen, so this is exact); query positions are sampled fresh
each step (8 per stream from [128, 700], batch 12 streams); arm D trains with
dense per-position supervision on positions [64, 700] of the same pool.
1500 steps, Adam lr 2e-3 cosine, loss = forecast MSE + 0.5·outcome BCE,
validation every 150 steps on the frozen val set (seed 62000, 100 streams),
selection by validation loss, final evaluation on the frozen test set (seed
63000, 200 streams) at queries {384, 512, 640}. Statistical and harmonic
summary tokens are the imported Sweep-3 arm-B/arm-C collectors of
`experiments/phase_temporal_collector` (unchanged). Parameters matched across
arms to <1%; seeds {0, 1, 2}.

## Outcomes (frozen)

- E-GATE fails → **permanent stop** (terms above); eventization NOT SUPPORTED
  at tested scale stands as the final micro-scale answer.
- E-GATE passes, V-GATE fails → Stage B INVALID AT TESTED SCALE; the Stage A
  pass stands alone.
- V-GATE passes, H-GATE fails → harmonic summaries add no reasoning value
  beyond statistics at tested scale.
- All pass → PROVISIONALLY SUPPORTED (micro scale); stop, and real-telemetry
  validation is the recorded next experiment.
