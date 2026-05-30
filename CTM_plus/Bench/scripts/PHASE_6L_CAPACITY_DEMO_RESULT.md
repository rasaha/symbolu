# Phase 6L — capacity demo RESULT (Qwen-7B, A100-80GB): DEMONSTRATED

> **Verdict: the ~1.8× live-concurrency-per-GB claim is DEMONSTRATED.**
> First empirical confirmation that int4_protected's block-budget advantage
> translates into observed sustained concurrency under real KV-block pressure.
> One major caveat surfaced: a steep **throughput cost at saturation** (see §3).

## 1. Run configuration

- Model: `Qwen/Qwen2.5-7B-Instruct`, A100-80GB, vLLM 0.7.3
- `mml=8192`, `max_tokens=512`, `prompt_frac=0.95`, `gpu_util=0.5`
- `--b-list 96,128` (2-point bracket straddling both cells' estimated ceilings)
- Both cells reached **100% peak KV-block utilization** with preemption →
  genuine saturation, not queue-drain. `ceiling_not_reached=False` for both.

## 2. Headline result

| metric | bf16 | protected |
|---|---:|---:|
| submitted_b_max | 128 | 128 |
| total_blocks | 28,310 | 28,310 |
| est_max_conc (vLLM) | 55.3 | 110.6 |
| peak_kv_util_% | 100.0% | 100.0% |
| saturation_observed | True | True |
| n_preemptions | 8 | 6 |
| **demonstrated_live** | **58** | **117** |
| seq_per_kblock | 2.049 | 4.133 |
| hbm_gb | 42.44 | 46.83 |
| tokens/sec | 597.3 | 130.4 |

**`demonstrated_density_ratio = 2.02×` (within the [1.5–2.5] window) → DEMONSTRATED.**

### The honest per-GB number (net of the sidecar tax): 1.83×

> **Now computed and printed directly by the script** (`sidecar_tax` + `density`
> sections in stdout and `report.json`) — no manual post-calc. The `net_density_
> ratio` is the headline; the raw `seq_per_kblock` ratio is kept as a secondary.

Both cells report the **same `total_blocks` (28,310)** — vLLM allocated an equal
number of blocks, with protected's blocks each holding ~2× the tokens (4-bit
packing). So `seq_per_kblock` is effectively the **raw live-concurrency ratio**
(117/58 = 2.02×) and does **not** subtract the +4.4 GB sidecar tax — the tax
lands in `hbm_gb` (46.83 vs 42.44), not in the block count.

The claim says "per GB, net of tax", so the honest denominator is actual HBM:

| | bf16 | protected | ratio |
|---|---:|---:|---:|
| live seqs / total HBM GB | 58/42.44 = **1.367** | 117/46.83 = **2.498** | **1.83×** |

**1.83× seq per actual GB of HBM, net of the +4.4 GB tax** — landing almost
exactly on the original ~1.8× block-budget estimate. The two numbers bracket the
truth: **2.02× raw concurrency, 1.83× per real GB.** Both inside the window;
the claim holds on either reading.

### Sidecar tax breakdown (live-measured this run, mml=8192, B=128)

The worker enumerates the protected writer's sidecar tensors and sums their bytes
live during the run. Of the **+4.39 GB** absolute HBM delta vs bf16:

| component | GB | share of delta |
|---|---:|---:|
| `k_protect_ext` | 1.015 | |
| `k_scale_ext` | 0.812 | |
| `k_xmin_ext` | 0.812 | |
| `v_scale_ext` | 0.812 | |
| `v_xmin_ext` | 0.812 | |
| `_k_stage_pool` | 0.117 | |
| **measured sidecar tax** | **4.38** | **99.8%** |
| non-sidecar residual (PyTorch-tracked) | 0.01 | 0.2% |

So the +4.39 GB delta is **~99.8% sidecars** within `max_memory_allocated`. CUDA-
graph private pools live OUTSIDE PyTorch's caching allocator and so do not appear
in this delta (they are a separate ~0.6 GB per the 6G audit).

> **Do not confuse with the old "3.42 GB" figure.** 3.42 GB is the **Phase 6G
> audit inventory at mml=32K, in binary GiB** — a *different config*, NOT the live
> 8K Phase 6L result. At 8K there are more KV blocks and bytes are decimal GB, so
> e.g. `k_protect_ext` is **1.015 GB (8K)** vs 0.82 GiB (32K). The live 8K sidecar
> tax is **4.38 GB** (= ~99.8% of the +4.39 GB delta).

The script also emits a **counterfactual** "no-sidecar" density ratio (2.02×) but
explicitly labels it NOT a serving number — sidecars are mandatory for int4
dequant, so it can never be the headline. (The headline stays **1.83× net seq/GB**
and **2.02× raw** concurrency — both unchanged by this correction, since they come
from `hbm_gb` + `peak_live`, not the tax decomposition.)

## 3. The major caveat: throughput collapses at saturation

| | bf16 | protected | ratio |
|---|---:|---:|---:|
| aggregate tokens/sec | 597.3 | 130.4 | **0.22×** |
| per-sequence tok/s (agg / live) | ~10.3 | ~1.1 | **~0.11×** |

At saturation, protected produces tokens at **0.22× bf16's aggregate rate** —
i.e. it serves 2× the users but each user's tokens arrive ~9× slower. This is
the **known-unoptimized int4_protected decode path** (throughput optimization
was explicitly **out of scope** for Phase 6L). It is consistent with the VC
brief's "throughput pending" note, and it is now **quantified at the saturated
operating point**, which is more adverse than the earlier non-saturated high-B
measurement (1.2–1.5×). Saturation + per-token dequant cost is where it bites.

**Implication:** the density win is real but currently **costs per-user latency
at saturation.** Fine for batch/offline throughput-insensitive workloads; a
problem for interactive serving until the decode kernel is optimized.

## 4. What this changes

- The single open claim in the VC brief is now **demonstrated, not estimated.**
- The full story is now three-part:
  - **Quality-positive** (locked): +20.4 pt token-agreement over naive int4.
  - **Density-positive** (NOW DEMONSTRATED): 1.83× seq/GB net of tax, under
    real block-pressure with observed saturation.
  - **Throughput-negative at saturation** (newly quantified): 0.22× aggregate
    tok/s — the deferred kernel-optimization cost.

## 5. Validity (why this is a real demonstration)

- `peak_kv_util=100%` on both → the block pool was the binding constraint.
- `demonstrated_live` (58, 117) `< submitted_b` (128) on both → genuine
  eviction/queueing, not queue-drain inflation. peak_live IS the measured ceiling.
- preemptions observed on both → real backpressure.
- no slot-exhaustion → 6K.14 slot lifecycle held at B=128 (corroborates that fix).
- COLLAPSE not re-checked here, but the cells are the same backends validated in 6J/6K.

## 6. Not yet done

- **Robustness across mml**: this is mml=8192 only. Confirming at 16,384 and
  32,768 would show the ratio holds as context (and the tax's amortization) grows.
- **The throughput/density tradeoff curve**: a non-saturated sweep (B below each
  ceiling) would show whether protected throughput recovers off-saturation.
- **Raw artifacts (committed)**: `bench_out/phase6l_result/` now holds the
  per-cell JSONs + `report.json`, plus the `_captured` and `_eager`
  reproductions (`report_captured.json` / `report_eager.json`). The
  `ENFORCE_EAGER=1` reproduction confirms CUDA graphs are ~neutral at
  saturation: protected **125.5 tok/s / 1.81×** (eager) vs **130.4 / 1.83×**
  (captured) — the headline holds in both modes. Re-derive any table with
  `phase6l_capacity_demo.py --from-jsons bench_out/phase6l_result/*_captured.json`
  (or `*_eager.json`).
