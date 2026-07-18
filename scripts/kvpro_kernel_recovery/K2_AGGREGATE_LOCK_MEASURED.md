# K2 aggregate lock — MEASURED whole-step decode profile on the recovered kernel

> **Result (A100, recovered K0 kernel, 2026-07-17):** the final whole-step profile is in. It
> **confirms 6F/gather-fusion clears the 15% build gate** (the removable gather+copy is ~36–38% of
> the decode step → a **measured ~1.4× decode speedup**, ρ-discounted). But it also overturns the
> project's working assumption: at long-context saturation the decode step is **~96% int4 read path,
> not GEMM-bound**, and the single dominant cost is the **int4 decode ATTENTION kernel itself — 12×
> the bf16 kernel's GPU time (12.46 s vs 1.02 s)**, which 6F does *not* touch. So the honest decision
> is **BUILD_K2 but RE-SCOPED**: the paged gather should be fused *inside* a rewrite of the int4
> decode attention kernel (they are one kernel), and the whole thing should be gated on one cheap
> diagnostic — an occupancy/Speed-of-Light read of why that kernel is 12× bf16.

Operating point: `Qwen/Qwen2.5-7B-Instruct`, `--max-model-len 16384 --batch-size 32 --prompt-frac
0.9` (prompt ≈ 14 745 tok) `--max-tokens 64`, `gpu-memory-utilization 0.7`. int4 cell =
`int4_captured` (CUDA graphs; the **recovered production path** — the trace shows
`_vllm_fa2_C::fwd_kvcache_int4`, so this is the K0 kernel, not a fallback). bf16 cell = `bf16_stock
--bf16-eager`.

---

## Two corrections applied before reading the numbers

**(1) Use self-CUDA leaf kernels, not the analyzer's bucket totals.** `analyze_phase6d_profile.py`
sums `device_time_total`, which for `aten::mm` / `aten::linear` / `aten::index` **includes their
child kernels** → its `int4=195 699 ms` total triple-counts. The profiler's own
`Self CUDA time total: 56.916 s` is the truth; the per-kernel **Self CUDA** column partitions it.
All numbers below come from the leaf device kernels (`void …`, `ampere_…`), which sum to ≈ 56.9 s.

**(2) Isolate decode from prefill.** A single `generate()` profile mixes one big prefill (32 prompts
× ~14.7k tok = ~472k token-forwards) with 64 decode steps (~2k token-forwards). The kernels
self-identify, so decode is isolated by name, not by subtraction:
- prefill attention = `flash_fwd_kernel` (varlen), 896 calls = 28 layers × 32 prefill steps;
- decode attention = `flash_fwd_splitkv_kernel` (`fwd_kvcache_int4`), 1792 calls = 28 × 64;
- prefill GEMMs = the `ampere_*s16816gemm*` family, 3584 calls = 28 × 32 × 4 (all ~8 ms each → prefill-shaped);
- decode GEMMs are tiny (bf16 shows them as `ampere_*256x64`, 3591 calls × 143 µs ≈ 0.5 s total).

**Consequence:** at this operating point the GEMMs the project feared (the "~66% at saturation"
input to the old 0.22× model) are **almost entirely prefill**. During a *decode step* at long
context B=32, GEMMs are ~0.5 s while attention+gather is ~20 s. The decode step is read-path-bound.

## Measured decode-step breakdown (self-CUDA, decode kernels only)

| decode-step component | kernel (leaf) | int4 self-CUDA | share of decode step |
|---|---|---:|---:|
| **int4 attention (reconstruct-in-kernel)** | `flash_fwd_splitkv_kernel` | **12.46 s** | **~58 %** |
| gather (paged int4 + 5 sidecars) | `index_elementwise_kernel` | 6.52 s | ~30 % |
| bf16-backing / prep copy | `elementwise_kernel` (clone) | 1.66 s | ~8 % |
| decode GEMMs + norm/rotary/silu + sampling | (small) | ~0.9 s | ~4 % |
| **decode step total** | | **~21.6 s** | 100 % |

- **read path** (attn + gather + copy) = 20.6 s = **~96 % of the decode step**.
- **FUSEABLE** (what 6F removes: gather + copy) = 8.18 s = **~38 % of the decode step**.
- **KERNEL** (int4 attention, irreducible *to gather-fusion*) = 12.46 s = **~58 %**.
- read-path internal split = 40 % fuseable / 60 % kernel — **cross-validates** the independent
  gather-fusion bench (43 % / 57 % at B=32), which is why the full `index_elementwise` is attributed
  to decode gather.

### The load-bearing new fact: the int4 decode attention kernel is 12× bf16

| decode attention kernel | per-call self-CUDA | vs bf16 | vs bandwidth-optimal |
|---|---:|---:|---:|
| bf16 `flash_fwd_splitkv` | 0.58 ms/call | 1× | ~1.2× (near-optimal, memory-bound) |
| **int4 `flash_fwd_splitkv`** | **6.96 ms/call** | **12×** | **~15–45× off** |

bf16 decode attention (0.58 ms/call for 14.7k-KV, GQA-4, B=32) is essentially at the HBM-bandwidth
floor (~0.48 ms ideal). int4 reads **less** data (compressed) yet costs **12×** — it is
compute-bound on reconstruction, ~15–45× above what its own (smaller) byte traffic would allow.
That is not inherent int4 cost (an efficient int4 kernel should be ~1.5–2× bf16); it looks like
kernel inefficiency (occupancy / serialized unpack). **This kernel — not the gather — is the gap.**

## Corrected projection (ChatGPT's formula — applied)

`X` = removable share **of the whole decode step** = (read-path share of step) × (fuseable fraction
of read path). Here fuseable is measured directly as 38 % of the decode step, so **X ≈ 0.38** (floor
~0.30 if only 2/3 of the gather is decode). New KVPro/BF16 = `base × 1/(1−ρX)`; this is *not*
`speedup` — the two quantities were conflated in the earlier `0.22/(1−X)` shorthand.

| output | ideal (ρ=1) | realizable (ρ=0.75) | gate |
|---|---:|---:|---|
| **1. relative decode speedup over current Route-C** = `1/(1−ρX)` | **1.61×** (+61 %) | **1.40× (+40 %)** | **clears 15 %** ✓ |
| **2. new KVPro/BF16 decode ratio** = `base × 1/(1−ρX)`, base ≈ 0.093× (int4 is 10.8× slower here) | 0.149× | **0.129× (still 7.8× slower)** | net loss ✗ |
| **3. build-gate verdict** | | | **PASS (worth building)** but does **not** reach bf16 |

End-to-end (prefill+decode) at this short gen=64 is prefill-dominated → 6F is only ~+13 % wall;
at realistic long generations (decode-dominated) it approaches the +40 % decode number. Steady-state
serving throughput (tok/s during generation) is the +40 % figure.

## Decision — BUILD_K2, re-scoped

6F passes its own gate on **measured** data (+40 % decode, not modeled). But the profile says the
gather was never the main penalty; the int4 attention kernel is. Therefore:

1. **Do not build gather-fusion as a standalone K2.** An in-kernel paged gather **and** an efficient
   reconstruct are the *same* kernel — fuse the gather *inside* a rewrite of the int4 decode
   attention kernel, so the 38 % (gather) and the 58 % (kernel) are attacked together.
2. **Gate the multi-week build on one cheap diagnostic first:** an ncu Speed-of-Light / Occupancy
   read (or the two-half FETCH/MATH probe, since ncu was `ERR_NVGPUCTRPERM`-blocked before) on
   `fwd_kvcache_int4` at this operating point — to confirm the 12× is reducible inefficiency, not
   inherent. If it is reducible toward ~2× bf16, int4 decode goes from ~11× → ~2–3× slower (a far
   bigger prize than 6F's 1.4×), and the gather rides along for free.
3. **If the 12× turns out inherent** (unlikely given the 15–45× bandwidth gap), int4 is
   capacity-only and 6F alone (1.4×) is a minor tweak, not a multi-week build → `POSITION_INT4_AS_CAPACITY_ONLY`.

## Caveats (do not over-read one profile)

- One operating point (ctx≈14.7k, B=32, gen=64). The regime split (decode read-bound here vs
  GEMM-bound at short-ctx/high-B) means these shares are regime-specific — re-profile before quoting
  at another point.
- int4 ran CUDA-graphs, bf16 ran eager. **Kernel self-CUDA time is graph-invariant**, so the 12×
  attention comparison is valid; end-to-end wall is *not* apples-to-apples and is not used for the
  kernel claim.
- decode GEMM/misc (~0.9 s) and the gather's decode/prefill split are estimated (bounded); `X` is
  robust to ±, and the "attention kernel is the elephant" conclusion does not depend on either
  (12.46 s decode attention is unambiguously decode and unambiguously 12× bf16).
- No modeled number is quoted as measured TPS. `base ≈ 0.093×` is this operating point's measured
  decode ratio, distinct from the earlier 0.22× saturation-model figure.

## Reproduce

```bash
# projection math (CPU, no GPU) — reproduces outputs 1–3 and ChatGPT's worked example:
python scripts/kvpro_kernel_recovery/lock_aggregate.py --selftest
# recompute from the pod CSVs (leaf-kernel self-time; isolates decode by kernel name):
python scripts/kvpro_kernel_recovery/lock_aggregate.py \
    --int4-csv CTM_plus/Bench/bench_out/phase6m_aggregate_lock/int4_kernels.csv \
    --bf16-csv CTM_plus/Bench/bench_out/phase6m_aggregate_lock/bf16_kernels.csv
```
