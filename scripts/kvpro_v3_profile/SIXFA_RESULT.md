# KVPro V3 6F-A — page-local (store-as-consumed) layout: MEASURED RESULT

> **VERDICT (measured, NVIDIA A100-SXM4-80GB): 3 of 4 gates PASS decisively; the aggregate
> gate is PROVISIONAL.** The per-head-contiguous page-local layout cuts the unzip **fetch by
> 44.8%** (nearly 2× the achieved bandwidth), the output is **byte-identical** (oracle 0.0), and
> the write-side cost it imposes is **negligible (0.02% of the read gain)** — the 6E-style
> write-regression risk did NOT materialise. The only open gate is the **≥15% aggregate-TPS
> projection**, which lands at ~10% under central share assumptions (clears only under
> optimistic) — so per the frozen rule **6F-C is NOT yet authorised**; it hinges on a *measured*
> decode-attention share, not a guess.

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
