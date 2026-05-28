# Phase 6G — Sidecar audit findings (Step 1 deliverable)

> **Status:** MEASURED. Audit landed; no code changes proposed. The
> data argues against pursuing the sidecar diet in isolation — the
> realistic savings ceiling (~2.5 GB) cannot close the observed
> ~5 GB HBM delta to bf16. Recommendation at bottom.
>
> **Bench artifact:**
> `bench_out/phase6g_sidecar_audit/audit_mml{8192,16384,32768}.json`
> + `sidecar_audit_report.{json,txt}`.

## Audit configuration

* Model: Qwen2.5-7B-Instruct (28 layers, H=4, D=128).
* Hardware: A100 80GB.
* `gpu_memory_utilization=0.5`, `max_num_seqs=16`,
  `PHASE6E_FUSED_WRITER=1`.
* Three independent loads at `max_model_len ∈ {8K, 16K, 32K}`.

## Total breakdown across max_model_lens

| mml | NB blocks | max_conc | KV cache GB | Sidecar GB | Sidecar % of cache | Non-PyTorch GB (CUDA graphs etc.) | HBM total |
|---|---|---|---|---|---|---|---|
| 8192  | 28310 | 110.6 | 24.19 | **3.98** | 16.4% | 0.62 | 43.81 |
| 16384 | 27039 | 52.8  | 23.11 | **3.80** | 16.4% | 0.62 | 42.71 |
| 32768 | 24497 | 23.9  | 20.93 | **3.44** | 16.4% | 0.62 | 40.51 |

**Key invariant: sidecars are exactly 16.4% of KV cache size at every
mml.** This is forced by the architecture — sidecars scale with NB
(the same denominator the cache scales with), so the ratio is
fixed. At smaller mml, NB is larger (more blocks fit in the budget),
so sidecars are bigger in absolute terms.

## Per-tensor inventory (at mml=32K)

| Tensor | Scaling | Per-layer shape | Total GB (28 layers) | Share |
|---|---|---|---|---|
| `k_protect_ext` | per_token | `(NB, 32, 4, 5)` bf16 | **0.82** | 23.8% |
| `v_scale_ext`   | per_token | `(NB, 32, 4, 4)` bf16 | **0.65** | 19.0% |
| `v_xmin_ext`    | per_token | `(NB, 32, 4, 4)` bf16 | **0.65** | 19.0% |
| `k_scale_ext`   | per_block | `(NB, 4, 128)` bf16    | **0.65** | 19.0% |
| `k_xmin_ext`    | per_block | `(NB, 4, 128)` bf16    | **0.65** | 19.0% |
| `_k_stage_pool` | per_slot  | `(8, 32, 4, 128)` bf16 | 0.007 | 0.2% |
| pool counters + lookup tables | per_slot / fixed | various small | <0.001 | <0.1% |

**No single tensor dominates.** The top 5 are within a factor of 1.25×
of each other. There's no "kill this one thing" win.

## Scaling-law decomposition

| Category | At mml=32K | % | Meaning |
|---|---|---|---|
| `per_token` | 2.13 GB | **61.8%** | v_scale_ext, v_xmin_ext, k_protect_ext — scale with NB×BS (total cache token count) |
| `per_block` | 1.31 GB | **38.0%** | k_scale_ext, k_xmin_ext — scale with NB only, amortize over BS=32 per block |
| `per_slot`  | 0.007 GB | 0.2% | _k_stage_pool + counters — scale with max_active_slots≈16, essentially fixed |
| `fixed`     | <0.001 GB | <0.1% | protect_mask + lookup tables — per-model, one-shot |

**61.8% of sidecars are per-token**, meaning they grow proportionally
with cache utilization. **38% are per-block**, which would be smaller
if we could increase BS (but BS=32 is fixed by the kernel's
compile-time constexpr).

## Per-cached-token marginal cost

| Component | Bytes / token / layer | Ratio to cache |
|---|---|---|
| KV cache (vLLM-managed) | 1024.0 | 1.000× |
| Sidecars                | 104.0  | 0.102× |

**Sidecars add 10.2% on top of every cached token.** This is the
per-token "tax" of the protect-mask design — it does not go away
at any context length; it's a fixed multiplicative overhead.

## What this means for the +5 GB HBM delta vs bf16

The long-context bench (commit `1fb05f6`) measured int4 captured
using +5 GB more HBM than bf16 at every tested mml. The audit
breaks that down:

| Component | Bytes | Diet-addressable? |
|---|---|---|
| Sidecars (audit-measured at mml=8K) | **3.98 GB** | **YES** — via Phase 6G options |
| CUDA graph private pools | ~0.62 GB | No — inherent to int4 writer's op count |
| Misc backend buffers (`_phase5b_slot_idx_buf` etc.) | ~0.4 GB | No — small, persistent |
| **Total observed delta** | **~5.0 GB** | |

**Maximum theoretical diet ceiling: 3.98 GB** (i.e. eliminating ALL
sidecars). After CUDA graph + misc overhead, even a perfect diet
leaves int4 ~1 GB heavier than bf16 at low B.

## Diet options — measured savings

| ID | Option | Targets | Measured savings (raw) | Quality risk | Impl cost |
|---|---|---|---|---|---|
| **C** | fp8 sidecars (bf16 → e4m3) | all 5 sidecars | **1.72 GB** (49.9%) | High (compounds with int4 quant noise) | ~3 days kernel work |
| **D** | Eliminate `k_protect_ext` | `k_protect_ext` | **0.82 GB** (23.8%) | Low semantically, high impl risk | ~5 days flash_attn surgery |
| **A** | `group_size` 32→64 | `v_scale_ext` + `v_xmin_ext` | **0.65 GB** (19.0%) | Moderate (coarser V quant) | ~2 days CUDA kernel work |
| **F** | `n_protect` 5→3 | `k_protect_ext` | **0.33 GB** (9.5%) | Moderate (depends on calibration) | ~1 day calibration only |

### Combined-stack reality check

The audit's naive sum (`C + D + A = 3.19 GB`) **double-counts** because
C halves the same tensors that A and D target. Correctly accounting
for overlap:

* **C alone**: 1.72 GB (halves all 5 sidecars)
* **+ D** after C: 0.82 / 2 = **+0.41 GB** (eliminates the
  already-halved k_protect_ext)
* **+ A** after C: 0.65 / 2 = **+0.325 GB** (halves the
  already-halved v_scale + v_xmin)

**Realistic combined: 1.72 + 0.41 + 0.325 = ~2.46 GB**

Against the ~5 GB delta, this closes about half. **int4 would still
use ~2.5 GB more HBM than bf16 at low B even with the full diet
stack.**

## Conclusion: the sidecar diet has a ceiling

The audit demonstrates that the protect-mask design's per-token
sidecars are a STRUCTURAL feature of the int4 quantization scheme,
not a fixable inefficiency. The 10.2% per-token tax is invariant
across context lengths and represents fixed encoding overhead
(asymmetric scale + xmin per group + per-channel protect dims).

**Sidecar diet can shrink the delta but cannot eliminate it.** The
practical ceiling is ~2.5 GB of savings against a ~5 GB observed
delta. After diet:

* At low B: int4 still loses HBM by ~2.5 GB.
* At high B (saturation): int4 KV cache equals bf16's, but sidecars
  add a fixed 1.5 GB (~half of pre-diet). int4 capacity per GB
  remains 2× bf16's, just with less headroom.

## Two paths forward — recommendation: Phase 6H first

Given the diet ceiling, the project's value proposition is **NOT** the
low-B memory crossover. It's the **high-B capacity advantage** that the
2× max_concurrency suggests. We have not yet measured whether that 2×
is honest (vLLM serves 2× the requests in practice) or
bookkeeping-only (sidecar OOMs at int4's reported limit).

### Recommended sequencing

1. **Phase 6H FIRST** (high-load capacity bench, design doc already
   landed):
   - Run pre-diet, with the current sidecars.
   - Measure: does int4 actually complete more requests than bf16 at
     high B where bf16 OOMs?
   - If YES → diet becomes worth doing (it makes the capacity
     advantage cleaner). If NO → diet doesn't help; the 2× was
     bookkeeping.

2. **Phase 6G implementation AFTER 6H lands data**:
   - If 6H shows real high-load advantage, do option **C** (fp8
     sidecars) — biggest measured win, modest risk, contained scope.
     Re-run 6H post-diet to measure improvement.
   - Skip D and A unless C alone doesn't shift 6H meaningfully.
   - F (n_protect=3) is the cheapest option (~1 day, calibration-only)
     and can be done in parallel with C.

### Why this ordering

Doing the diet first would consume 3-8 days of engineering effort
for a maximum 2.5 GB savings that doesn't crack the low-B HBM
crossover anyway. The high-load test is cheaper (3 days of bench
work, no code surgery) and tells us whether the project's
underlying value proposition (capacity) is real.

If 6H comes back NOT_JUSTIFIED (sidecars cause OOM at int4's
reported limit), the diet doesn't rescue it — we'd need a
fundamentally different quantization design. That's a Phase 6I
scope, not 6G.

## What this does NOT change

* **Phase 6E** remains shipped behind `PHASE6E_FUSED_WRITER=1`.
* **Phase 6F kernel surgery** remains halted.
* **VC brief** stays unedited until 6H (and possibly post-6H 6G)
  measured outcomes land.
* **No HBM win claim**: the audit confirms int4 does not win at low B
  and the diet cannot close that fully.

## Out-of-band note: bigger fixes beyond the diet

If post-6H we decide to pursue HBM parity at low B, the structural
options are:

1. **Move int4 logic into flash_attn itself** — sidecars become
   inline state inside the int4 cache, not separate tensors. The
   bf16 backing pool concept disappears. This is the Phase 6F
   kernel surgery, multi-week. ~3-4 GB potential savings (full
   sidecar elimination via interleaved layout).

2. **Share scale/xmin across multiple blocks** — quantization
   accuracy drops; need calibration data to bound the impact.
   ~50% reduction in v_scale+v_xmin (= 0.65 GB), but requires
   kernel-level changes.

3. **Tell vLLM about sidecars** so it accounts for them in
   `num_gpu_blocks` calculation. This DOESN'T save memory — it just
   makes the budget honest. Worth doing for accurate
   `max_concurrency` reporting anyway.

Neither of these is in scope for 6G; documenting for posterity.

## Files audited (no changes made)

```
CTM_plus/KVPolicy/kv_policy/phase5b_4c_paged_writer.py    (read-only walk)
CTM_plus/KVPolicy/kv_policy/phase5b_backend_install.py    (read-only walk)
```

## Files produced

```
CTM_plus/Bench/scripts/audit_phase6g_sidecar_overhead.py  (audit script)
CTM_plus/Bench/scripts/PHASE_6G_SIDECAR_DIET_FINDINGS.md  (this doc)
bench_out/phase6g_sidecar_audit/audit_mml{8192,16384,32768}.json
bench_out/phase6g_sidecar_audit/sidecar_audit_report.{json,txt}
```
