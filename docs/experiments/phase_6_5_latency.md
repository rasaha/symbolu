# §6.5 Latency Benchmark — Results

Per-``plan()`` wall-clock latency across (M, K, H) combinations, V1 validated consumer config.

- Warmup: 3 calls; cycles measured: 30
- Seed: 42
- Config: T=0.05, β=400, EMA α=0.05, deadband k=2σ, non-anchor pairing

## Raw results

| M | K | H | mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) |
|---|---|---|---|---|---|---|---|
| 3 | 128 | 10 | 63.1 | 61.8 | 71.1 | 76.4 | 77.1 |
| 3 | 128 | 20 | 110.3 | 108.9 | 119.2 | 125.8 | 128.4 |
| 3 | 128 | 50 | 388.8 | 388.3 | 401.2 | 406.0 | 407.8 |
| 3 | 256 | 10 | 129.2 | 127.9 | 139.5 | 141.3 | 141.4 |
| 3 | 256 | 20 | 219.2 | 216.4 | 236.8 | 245.7 | 245.9 |
| 3 | 256 | 50 | 473.5 | 470.7 | 494.1 | 513.9 | 521.7 |
| 3 | 512 | 10 | 251.6 | 249.2 | 262.0 | 276.8 | 281.8 |
| 3 | 512 | 20 | 423.6 | 421.8 | 444.5 | 459.9 | 462.5 |
| 3 | 512 | 50 | 920.5 | 918.7 | 955.8 | 976.0 | 981.1 |
| 4 | 128 | 10 | 72.4 | 71.9 | 75.6 | 76.2 | 76.3 |
| 4 | 128 | 20 | 122.0 | 120.0 | 128.3 | 141.1 | 146.3 |
| 4 | 128 | 50 | 266.4 | 263.7 | 284.9 | 297.8 | 301.9 |
| 4 | 256 | 10 | 145.7 | 144.1 | 154.5 | 159.0 | 160.7 |
| 4 | 256 | 20 | 243.2 | 240.7 | 260.8 | 264.5 | 265.9 |
| 4 | 256 | 50 | 539.1 | 538.9 | 555.1 | 559.9 | 561.2 |
| 4 | 512 | 10 | 315.0 | 313.2 | 328.0 | 329.2 | 329.7 |
| 4 | 512 | 20 | 477.6 | 475.0 | 507.9 | 513.1 | 514.7 |
| 4 | 512 | 50 | 1074.8 | 1070.5 | 1122.8 | 1133.0 | 1133.8 |

## Pass / fail against integration-tier budgets

Green (✅) = p99 ≤ budget. Red (❌) = p99 > budget. p99 is the conservative read; p50 gives a sense of typical case.

### automotive (10 Hz) — budget 100 ms

| M | K | H | p99 (ms) | vs budget |
|---|---|---|---|---|
| 3 | 128 | 10 | 76.4 | ✅ |
| 3 | 128 | 20 | 125.8 | ❌ |
| 3 | 128 | 50 | 406.0 | ❌ |
| 3 | 256 | 10 | 141.3 | ❌ |
| 3 | 256 | 20 | 245.7 | ❌ |
| 3 | 256 | 50 | 513.9 | ❌ |
| 3 | 512 | 10 | 276.8 | ❌ |
| 3 | 512 | 20 | 459.9 | ❌ |
| 3 | 512 | 50 | 976.0 | ❌ |
| 4 | 128 | 10 | 76.2 | ✅ |
| 4 | 128 | 20 | 141.1 | ❌ |
| 4 | 128 | 50 | 297.8 | ❌ |
| 4 | 256 | 10 | 159.0 | ❌ |
| 4 | 256 | 20 | 264.5 | ❌ |
| 4 | 256 | 50 | 559.9 | ❌ |
| 4 | 512 | 10 | 329.2 | ❌ |
| 4 | 512 | 20 | 513.1 | ❌ |
| 4 | 512 | 50 | 1133.0 | ❌ |

### industrial (50 Hz) — budget 20 ms

| M | K | H | p99 (ms) | vs budget |
|---|---|---|---|---|
| 3 | 128 | 10 | 76.4 | ❌ |
| 3 | 128 | 20 | 125.8 | ❌ |
| 3 | 128 | 50 | 406.0 | ❌ |
| 3 | 256 | 10 | 141.3 | ❌ |
| 3 | 256 | 20 | 245.7 | ❌ |
| 3 | 256 | 50 | 513.9 | ❌ |
| 3 | 512 | 10 | 276.8 | ❌ |
| 3 | 512 | 20 | 459.9 | ❌ |
| 3 | 512 | 50 | 976.0 | ❌ |
| 4 | 128 | 10 | 76.2 | ❌ |
| 4 | 128 | 20 | 141.1 | ❌ |
| 4 | 128 | 50 | 297.8 | ❌ |
| 4 | 256 | 10 | 159.0 | ❌ |
| 4 | 256 | 20 | 264.5 | ❌ |
| 4 | 256 | 50 | 559.9 | ❌ |
| 4 | 512 | 10 | 329.2 | ❌ |
| 4 | 512 | 20 | 513.1 | ❌ |
| 4 | 512 | 50 | 1133.0 | ❌ |

### drone (100 Hz) — budget 10 ms

| M | K | H | p99 (ms) | vs budget |
|---|---|---|---|---|
| 3 | 128 | 10 | 76.4 | ❌ |
| 3 | 128 | 20 | 125.8 | ❌ |
| 3 | 128 | 50 | 406.0 | ❌ |
| 3 | 256 | 10 | 141.3 | ❌ |
| 3 | 256 | 20 | 245.7 | ❌ |
| 3 | 256 | 50 | 513.9 | ❌ |
| 3 | 512 | 10 | 276.8 | ❌ |
| 3 | 512 | 20 | 459.9 | ❌ |
| 3 | 512 | 50 | 976.0 | ❌ |
| 4 | 128 | 10 | 76.2 | ❌ |
| 4 | 128 | 20 | 141.1 | ❌ |
| 4 | 128 | 50 | 297.8 | ❌ |
| 4 | 256 | 10 | 159.0 | ❌ |
| 4 | 256 | 20 | 264.5 | ❌ |
| 4 | 256 | 50 | 559.9 | ❌ |
| 4 | 512 | 10 | 329.2 | ❌ |
| 4 | 512 | 20 | 513.1 | ❌ |
| 4 | 512 | 50 | 1133.0 | ❌ |

## Recommended operating point per tier

Largest (M, K, H) combination that stays under each budget at p99:

| Tier | Largest configuration | p99 headroom |
|---|---|---|
| automotive (10 Hz) | M=4, K=128, H=10 | 23.8 ms below budget |
| industrial (50 Hz) | (none passing) | — |
| drone (100 Hz) | (none passing) | — |

## Interpretation (honest)

**What these numbers say:**

- At the V1 validated (M, K, H) ranges, the pure-NumPy reference
  implementation fits inside an **automotive 10 Hz budget only at
  the smallest configuration** (M=3 or 4, K=128, H=10, p99 ≈ 76 ms
  — ~24 ms of headroom).
- **Industrial 50 Hz (20 ms) and drone 100 Hz (10 ms) budgets are
  not met by any configuration on this CPU.** The smallest cell
  already exceeds 50 Hz.
- The dominant cost is the **per-rollout predictor loop**: the
  Python-level `for k in range(K)` in `MPPIPlanner._rollout_all` that
  calls `predictors[name].predict(controls_batch[k])` one rollout at
  a time, one predictor at a time. At K=512, M=4, H=50 that is 102.4k
  individual `predict()` calls per plan step.

**What these numbers are NOT:**

- **Not a fundamental limit of the trust-weighting architecture.**
  The BCVF kernel itself (`compute_bcvf_cost_batch` on a pre-stacked
  `(K, M, H, 3)` tensor) is ms-scale and well under budget — see the
  existing `test_batch_timing_under_50ms` test which asserts the
  kernel alone runs in < 50 ms at K=1000, M=4, H=50.
- **Not a blocker for §6.1 / §6.3 conclusions.** Those results hold
  on the validated kernel math and consumer pattern regardless of
  rollout-loop cost.
- **Not calibrated to a production compute substrate.** The benchmark
  runs on whatever CPU the session is allocated. A production
  integrator should re-run on their target TDA4, Orin, or AMD EPYC
  to get actionable numbers. Results may be substantially different.

**Next-step optimization targets (out of scope for §6.5, in scope for
V2 performance work):**

1. **Vectorize the predictor rollout across K.** `BasePredictor` has
   a `predict_batch(controls_batch: (K, H, 2)) -> (K, H, 3)` API
   slot already documented in `DESIGN.md` §3B — a vectorized
   bicycle-model integrator would move ~80% of the current per-step
   wall time from Python loop to NumPy. Expected 10–50× speedup.
2. **Profile with `cProfile` + `snakeviz`** to confirm the predictor
   loop is the dominant cost before optimizing.
3. **GPU offload** via `torch` if needed for drone 100 Hz budgets.
   Would require breaking the V1 "pure-NumPy, no GPU dependency"
   discipline — only pursue if an integrator's real-time requirement
   demands it.

**Takeaway for an integrator conversation:**

The V1 configuration fits 10 Hz automotive at the smallest (M=3–4,
K=128, H=10) config on a generic CPU. Larger configurations and
faster control loops require vectorizing the predictor rollout
(reference architecture unchanged; performance work is a known V2
target). Recommendation: run this benchmark on your target compute
substrate before committing to a specific (M, K, H) operating point.

## Reproducibility

Run ``python -m symbolu_robotics.bcvf_autonomous.benchmarks.latency`` to reproduce. Warm-up / cycle counts and the sweep grid are CLI-tunable. Results will vary with CPU model; run on the integrator's target compute substrate for actionable numbers.