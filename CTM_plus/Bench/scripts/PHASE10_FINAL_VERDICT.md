# Phase 10 — Final verdict: READ-SKIP retention is a **density** play, not a decode-speed play

> **TL;DR.** With int4 KV + kernel scoring (Step 1) + GPU-native index (Step 3) +
> the Step-4 block-id cache, `retention` decode throughput at ctx ≤ 32k lands at
> **−10.6 % (30k) to −17.7 % (8–16k)** vs `off`, **quality 1.0/1.0** at every point.
> It does **not** cross above `off` within Qwen2.5-7B's native 32k window. The
> A/B *trend* shows it **converging fast** and extrapolates to a crossover at
> **~50k context** — past 32k, so unprovable here without YaRN. The realized,
> shippable value is **density**: int4 stores 4× the context per GB, and READ-SKIP
> keeps decode work **~flat as context grows** (bounded retained set), so that
> stored long context stays usable instead of slowing decode linearly.

## The deciding evidence — context sweep (refresh=0, tuned keep-set)

`INT4_READSKIP_KERNEL_SCORES=1 SINK=64 RECENT=512 BUDGET=512 REFRESH=0`, gen=128,
seeds 1–3, depths 0.1/0.5, within-process paired A/B:

| ctx | off tps | retention tps | **Δ%** | off−ret gap | skip_frac | retained / total |
|---:|---:|---:|---:|---:|---:|---:|
| 8 192  | 28.02 | 23.08 | **−17.6 %** | 4.94 | 79.6 % | 1590 / 7797 |
| 16 384 | 28.50 | 23.45 | **−17.7 %** | 5.05 | 89.5 % | 1626 / 15468 |
| 30 720 | 25.11 | 22.44 | **−10.6 %** | **2.67** | 94.1 % | 1715 / 28873 |

Quality `{0.10: 1.0, 0.50: 1.0}` for **both** modes at every ctx.

**Read of the shape:**
- **`off` is flat to 16k, then slopes down** (28.5 → 25.1). Below ~16k, decode is
  weight-bound (14 GB of weights dominate); the KV read only becomes a visible
  cost past ~16k — exactly where `off` starts losing tps.
- **`retention` is nearly flat** (23.45 → 22.44): the retained set is *bounded*
  (~1.6–1.7k positions) regardless of context, so its per-step cost barely moves.
- The **gap halves from 16k→30k** (5.05 → 2.67 tps). Extrapolating that segment
  (Δ% climbing +7.1 pt per 14.3k tokens) puts the **crossover at ~50k context**.
  This is the long-context play the whole phase pointed at — it simply lives
  beyond Qwen2.5's 32k native window.

## How we got from −31 % to −10.6 % at 30k (what each step bought)

| stage | ctx=30k Δ% | what changed |
|---|---:|---|
| Phase 9 / early Phase 10 | ~−30 %+ | host gather + `as_tensor(python_list)` per layer/step |
| Step 1 (kernel scoring) | — | scores computed in-kernel, not a second pass |
| Step 3 (GPU-native index) | −15.2 % | killed `as_tensor(list_of_thousands)`; index built on-device from the small block set |
| **Step 4 (block-id cache)** | **−14.1 %** | cache `torch.tensor(sorted(retained))` across steady steps; rebuild only on observe. Exact (highest block still fills as seq_len grows). |
| **+ `REFRESH=0`** (tune observe freq) | **−10.6 %** | observe only the first 8 steps, never re-score → ~half the observe overhead. Quality held (static needle). |

Step 4 is **always-on, no flag, exact** — proven equal to the list path in
`readskip_select.py` (selftest) and across **growing** steady seq_len on GPU in
`test_gather_decode_gpu.py` ("active_index == active_positions across growing
steady steps (cached): PASS").

## Why it can't win on raw tps at ≤32k (the structural floor)

94 % skip (reads 1715 of 28873) yet still −10.6 %. The reason is in the sweep:
**`off`'s int4 KV read is already cheap** at these lengths — decode is largely
weight-bound, and the contiguous int4 read is coalesced. Retention trades that
for a *gather* of ~54 scattered blocks plus per-step decision/dequant. 16× fewer
positions ≠ 16× less time when the baseline read isn't the bottleneck. The
benefit only dominates once `off`'s KV read grows large enough to bite — i.e.
past ~50k, where the *bounded* retained set finally beats `off`'s *linear* growth.

## The density framing (the realized win)

- **Storage:** int4 KV = **4× the density** of bf16 (4-bit vs 16-bit elements).
  The same KV-cache VRAM budget holds ~4× the context length. (At 30k, `off`
  itself is already int4 here — the 4× is vs a bf16 baseline.)
- **Read:** READ-SKIP drops the *per-step* KV read to the bounded retained set
  (~6 % of positions at 30k, 94 % skipped). The point of that bound is not raw
  tps at 30k — it is that decode stays **~flat as context scales** (23.45 tps at
  16k → 22.44 at 30k), instead of `off`'s linear slide (28.5 → 25.1 and falling).
- **Combined value prop:** *store* 4× more context per GB (int4), and *use* it
  without decode degrading linearly (READ-SKIP). The speed crossover past ~50k is
  then a bonus on top of the capacity win — not the headline.

## Knobs (all env, in `int4_cache_kv_route_a.py`)

| env | default | effect |
|---|---:|---|
| `INT4_READSKIP_KERNEL_SCORES` | 0 | 1 = compute block scores in the attention kernel (Step 1). |
| `INT4_READSKIP_SINK` | 64 | always-keep prefix tokens. |
| `INT4_READSKIP_RECENT` | 512 | always-keep recent window. |
| `INT4_READSKIP_BUDGET` | 512 | retained-block budget (the bound that flattens decode). |
| `INT4_READSKIP_OBSERVE` | 8 | initial read-all/observe steps (build EMA). |
| `INT4_READSKIP_REFRESH` | 16 | periodic re-score cadence. **Quality/speed knob** — raise (or 0) to cut observe overhead. |
| `INT4_READSKIP_INKERNEL` | 0 | leave **off** — host compaction (coalesced) beats the in-kernel uncoalesced gather (Phase 10 Step 2). |

**`REFRESH=0` caveat:** it never re-selects, so it's favorable to a *static*
needle. For shifting-attention workloads keep `REFRESH` moderate (default 16);
treat it as a quality/speed dial, not a free win. The shipped code default stays 16.

## When to use / not use

- **Use:** very long context (≳50k for raw speed; any length for the 4× capacity)
  where holding the KV in VRAM is the constraint and per-token decode must not
  slide linearly with length.
- **Don't expect:** a decode-tps win below ~32k on this model — `off` is too cheap
  there. Ceiling remains ~0.5× bf16 throughput; this is density + flat-scaling,
  not faster-than-bf16.

## Reproduce

```bash
cd /workspace/symbolu && git pull origin claude/bold-johnson-rXAd4 && cd CTM_plus
python Bench/scripts/test_gather_decode_gpu.py     # correctness gates (incl. Step-4 cache)

for CTX in 8192 16384 30720; do
INT4_READSKIP_KERNEL_SCORES=1 INT4_READSKIP_SINK=64 INT4_READSKIP_RECENT=512 \
INT4_READSKIP_BUDGET=512 INT4_READSKIP_REFRESH=0 \
python Bench/scripts/phase9_p3_fused_needle.py --ab --ab-modes off,retention \
  --context-tokens $CTX --max-model-len 32768 --ab-gen 128 \
  --seeds 1,2,3 --depths 0.1,0.5 --repeats 3 --warmup 2 \
  --out Bench/bench_out/PHASE10_AB/ab_sweep_ctx${CTX}.json
done
```

## If resumed later (not pursued now)

- **Prove the crossover:** YaRN rope-scaling (factor ~2) to run 48–64k and show
  `retention` cross **positive**; validate YaRN doesn't erode needle quality at
  extended context first.
- **Pull the crossover earlier:** move the controller fully on-GPU to kill the
  per-step decision sync (`readskip_decision`); structural, risky, bounded by
  gather efficiency at ≤32k — diminishing returns vs the YaRN proof.
