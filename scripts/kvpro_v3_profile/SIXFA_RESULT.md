# KVPro V3 6F-A — page-local (store-as-consumed) layout: MEASURED RESULT

> **FINAL VERDICT (measured, A100-SXM4-80GB): STOP 6F-C.** Measurement #1 resolved the one open
> gate against the layout: the improved read/copy is only **α = 15.7%** of the (copy + decode-kernel)
> block, and the aggregate gate needs **β > 1 (impossible)** to clear 15%. The 6F-A component wins
> were real — read **+44.8%**, write **negligible**, output **byte-exact** — but they do NOT aggregate
> to a throughput win, because the KV read/copy is a *minority* of decode-kernel time. **The decode
> KERNEL (~5× the copy) is the real cost, not the storage layout.** See "Measurement #1" below; the
> 6F layout line is CLOSED on measured evidence.

> **(Superseded) intermediate verdict:** 3 of 4 gates PASS; aggregate PROVISIONAL. The
> per-head-contiguous layout cuts the unzip **fetch by 44.8%**, output **byte-identical** (oracle 0.0),
> write-side cost **negligible (0.02%)** — the 6E-style write regression did NOT materialise. The open
> gate was the ≥15% aggregate projection (~10% central), resolved to STOP by measurement #1.

Measured on A100-SXM4-80GB (108 SMs), driver 550.127.05 / CUDA 12.4, ctx sweep 4096/16384/32768,
ITERS=100 (append spike ITERS=200, B∈{1,32,128,256}). Kernel correctness (page-local == current)
CPU-proven exact via the Triton interpreter before the run.

## Gate summary (frozen thresholds — DECISION_THRESHOLDS.md Part 6F-A)

| Gate | Threshold | Measured (ctx=32768) | Verdict |
|---|---|---|---|
| **Read improvement** | ≥ 20% | **44.8%** (fetch 0.347 → 0.192 ms) | ✅ **PASS** |
| **Oracle exact** | 0 | **0.0** (byte-identical, both layouts) | ✅ **PASS** |
| **Write < 25% of read gain** | < 25% | **0.02%** (append +0.008 ms vs 39.8 ms/step read gain) | ✅ **PASS** |
| **Aggregate-TPS projection** | ≥ 15% | **10.2% central** (opt 23.6% / cons 3.75%) | ⚠️ **PROVISIONAL** |

**6F-C authorisation requires ALL four → currently BLOCKED on the aggregate gate.**

## 1. Read improvement (page-local vs current (S,H,·))

| ctx | current fetch | page-local fetch | improvement | current BW | page-local BW |
|---:|---:|---:|---:|---:|---:|
| 4096  | 0.0514 ms | 0.0492 ms | 4.3% (overhead floor) | — | — |
| 16384 | 0.1897 ms | 0.1054 ms | 44.4% | — | — |
| **32768** | **0.3469 ms** | **0.1915 ms** | **44.8%** | 64.2 GB/s | **116.4 GB/s** |

The layout change nearly **doubles achieved bandwidth** (64 → 116 GB/s) and the win **scales with
context** (negligible at 4k where the kernel is overhead-bound; ~44–45% once memory-bound at 16k+).
Full-unzip improvement (fetch+math) = **41.6%**. Oracle diff = **0.0** at every context.

## 2. Write-side (append feasibility spike) — the risk that did NOT materialise

The page-local layout makes a per-token append scatter across heads (vs one contiguous run in the
current layout). Measured added write cost (ctx=32768, all batch sizes):

| case | added write Δ (per step) | notes |
|---|---:|---|
| append (no repack) | **+0.008 ms** | plain slot-write — **no re-transpose needed**; flat across B=1…256 |
| block rollover | +0.017 ms | adds the once-per-block K-scale write; still trivial |
| mixed tail lengths | +0.009 ms | fill-independent (confirms slot-write semantics) |

Gate: a token is **written once but read every later step**, so `ΔW_per_step / (B·ΔR_per_seq)` =
**0.0002 ≪ 0.25** at B=256 (added write 0.008 ms vs per-step read gain 39.8 ms). **PASS by ~1000×.**
The concern that a store-as-consumed layout would regress the write path the way 6E did is
**falsified for a slot-write scheme** — this is the most important de-risking of the milestone.

## 3. Aggregate-TPS projection — the one open gate (MODELED)

The decode-kernel-time breakdown is UNAVAILABLE without `ncu`/`nsys`, so aggregate is projected:
`aggregate ≈ unzip_full_improvement (41.6%) × α × β × realizable`, where α = unzip-read share of
the decode-attention kernel and β = decode-attention share of the whole step.

| scenario | α · β · realizable | projected aggregate |
|---|---:|---:|
| conservative | 0.09 | 3.75% |
| **default (central)** | **0.245** | **10.2%** |
| optimistic | 0.567 | 23.6% |

Central **10.2% < 15%** (misses); optimistic **23.6% ≥ 15%** (clears) → **PROVISIONAL**. To clear 15%
the unzip-read must be ≥ ~36% of the decode step (`0.15 / 0.416`). That is plausible for long-context
decode (attention KV-streaming dominates), but it is **not measured here** — α and β are labelled
assumptions, never fabricated as measurements.

## Decision (frozen rule) & what resolves it

**6F-C is NOT authorised yet.** Read + write + oracle pass decisively; the aggregate gate is
PROVISIONAL. Per the pre-registered rule (all four must PASS), the next step is **one measurement**,
not a build:

1. **α — unzip-read share of the decode-attention kernel:** time the full in-repo decode kernel
   (`int4_fused_attention_kernel.fused_protected_k_decode_attention`, which adds QK/softmax/PV on top
   of the unzip) vs the unzip probe on identical inputs. Available now, no new hardware access.
2. **β — decode-attention share of the decode step:** an `nsys` decode trace with the real model
   (kernel-timeline wall-time, NOT counter-blocked) → attention-kernel time / step time.

Feed the measured shares back with `--unzip-share α --decode-attn-share β` (or a `stage_summary.json`)
and the projection converts PROVISIONAL → PASS or FAIL. **If `α·β·realizable ≥ 0.36`, authorise 6F-C;
else stop at 6F-A.**

## Honest caveats
- **Absolute BW is probe-pessimistic** (small `(BS,D)` tiles, H_kv=4, default warps): even the
  coalesced page-local layout reaches only ~5.7% of peak, so a *tuned* kernel would be faster in
  both layouts and the 44.8% is the layout's contribution **at this probe's structure** — a robust,
  apples-to-apples relative number, not a claim that a production kernel gets exactly 44.8%.
- **Short context (4k) is overhead-bound** (4.3%); the win is a long-context property (the regime KV
  cost dominates anyway).
- The Part-H bound reproduced cleanly: MEMORY-BOUND, f/m=7.9, 64.2 GB/s = 3.1% HBM, fp16-pool penalty
  0.25% (a ~7% side-lever at most on the first run; not the primary optimisation).
- This is the unzip **read** + a **write-delta** microbench; the aggregate projection is the only
  MODELED step and is explicitly gated on a real decode share before any 6F-C authorisation.

## Reproduce
```bash
cd scripts/kvpro_v3_profile
python3 validate_kernel_interp.py
CONTEXTS="4096 16384 32768" ITERS=100 bash 07_unzip_bound_probe.sh   # auto-runs the append spike
cat runs/unzip_bound_verdict.json ; cat runs/append_spike.json
```
Raw artifacts: `runs/unzip_bound.json`, `runs/unzip_bound_verdict.json`, `runs/append_spike.json`
(on the run pod; decisive numbers recorded above).

---

# Measurement #1 — α (decode-path share): RESOLUTION → STOP 6F-C

**Measured on A100-SXM4-80GB, ctx sweep 4096/16384/32768, ITERS=100, median + p95.** Grounded in the
real production decode path (`int4_protected_k_cache.py:520-548`): the standard `kernel_inputs`
permute-copies the whole KV native `(S,H,*)` → head-major every step, and the decode kernel reads that
coalesced. Page-local eliminates the copy; the kernel is unchanged. So `α = copy / (copy + kernel)`.

| ctx | permute_copy (med/p95) | decode_kernel (med/p95) | **α_copy** | unzip cur→pl | oracle cos |
|---:|---:|---:|---:|---:|---:|
| 4096  | 0.054 / 0.062 ms | 0.324 / 0.325 ms | 0.143 | 0.077→0.079 | 0.9940 |
| 16384 | 0.102 / 0.104 ms | 0.641 / 0.643 ms | 0.137 | 0.190→0.113 | 0.9942 |
| **32768** | **0.182 / 0.183 ms** | **0.973 / 0.974 ms** | **0.157** | 0.370→0.218 | **0.9945** |

**α_copy = 0.157 → LIKELY_STOP.** The decode KERNEL is **~5.4× the permute-copy**. Eliminating the
copy entirely removes only ~16% of the (copy+kernel) block; with the step-share β and conservative
realizability, aggregate ≈ α·β·r, so **β_needed = 0.15/(α·r) = 1.36 (r=0.7) / 1.19 (r=0.8) — both > 1,
impossible.** Even a perfect β=1 cannot get page-local to a 15% aggregate gain. The decode-kernel
correctness oracle passed (cosine 0.994 vs the fp reference), so the kernel time is trusted. **The β
nsys trace is MOOT** (β_needed > 1), so it is not run.

## Why the read wins don't aggregate
Part-H showed the *unzip in isolation* is memory-bound. Measurement #1 shows the *full decode kernel* is
**not** read-bound: the KV read/copy is a minority of it (~14–24% by α_copy / α_unzip). The kernel's cost
is its compute + structure — QK/softmax/PV matmuls, the split-K + combine passes, GQA `G_PAD=16` padding
(56% wasted rows for G=7), and the route-A full-fp16-K protect load (line 140). **The tall pole is the
decode kernel, not the storage layout**, so a read-layout change (6F) cannot move aggregate throughput
by ≥15%.

## Decision (frozen rule) — 6F-C NOT authorised
Read ✅ / write ✅ / oracle ✅ but **aggregate ✗ (α → β_needed > 1)**. All four must PASS; the aggregate
gate fails on measured evidence. **Do not build 6F-C.** The 6F storage-layout line is CLOSED — same
falsification discipline as the query-fold line.

## Honest caveats
- The in-repo decode kernel is what the 6c.3C production cache actually calls, so 0.973 ms is the
  operative decode-kernel time and α = 0.157 is the real standard-path share. It does carry route-A
  inefficiencies (full-fp16-K load, `G_PAD=16` GQA padding) that inflate it and *understate* α; the
  fp16-pool was independently measured as a ~0–7% effect (small), so correcting for it lifts α only
  marginally (~0.16→0.17) and β_needed stays > 1. **The STOP is directionally robust.** If the decode
  kernel is later optimised on its own (compact-protect in-kernel read, tighter GQA, less split-K
  overhead — a *separate, larger* lever), the copy would become a bigger share and 6F should be
  re-evaluated then — but that is a decode-kernel project, not a storage-layout one.
- The gather path (native in-place read, no copy, scattered) nets ≈ −0.03 ms vs the standard path, so it
  does not change the conclusion.

## Reproduce
```bash
cd scripts/kvpro_v3_profile
CONTEXTS="4096 16384 32768" ITERS=100 bash 10_alpha_decode_share.sh
cat runs/alpha_decode_share.json
```
Raw artifact: `runs/alpha_decode_share.json` (on the run pod; decisive numbers recorded above).

## Why a full page-local decode-kernel prototype is UNNECESSARY (analytical)

The page-local layout `(H, n_blocks, BS, *)` is **the SAME memory layout** the production decode kernel
already reads. `int4_protected_k_cache.kernel_inputs` (line 542) permute-copies the cache to **head-major
`(H, S, *)`** before the kernel runs, and page-local is head-major with `S` factored into `(n_blocks, BS)` —
identical bytes, identical flat offsets:

```
head-major (H,S,*):        offset(h,s)      = (h·S + s)·DH
page-local (H,n_blocks,BS,*): offset(h,blk,t) = ((h·n_blocks + blk)·BS + t)·DH = (h·S + s)·DH   # s = blk·BS + t
```

Verified: `page_local.reshape(H, S, DH) == head_major` (bit-exact). So a page-local decode-kernel prototype
would read **byte-identical** memory to the current kernel → **0% kernel change by construction**. The 44.8%
fetch gain was `native (S,H,*)` → `head-major/page-local` coalescing, which the production kernel **already
realises** (via the per-step permute-copy). Page-local's *only* benefit is letting the writer emit that
layout directly, removing the copy — exactly the measured **α = 15.7%**, with **β_needed > 1**. There is no
residual "does the 45% survive inside attention" question: the kernel already reads coalesced, so the gain is
already inside it. **STOP stands; no prototype required.**
