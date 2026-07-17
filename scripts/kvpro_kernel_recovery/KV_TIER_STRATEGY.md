# KV-cache tier strategy — capacity (int4) vs speed (8-bit), post-K2-M1

> **Decision (2026-07-17, user-directed after the K2-M1 measured NO-GO):** keep INT4-protected as
> the **capacity tier**; **evaluate 8-bit (fp8/int8) KV as the speed tier** before funding any more
> INT4 kernel work. **Defer 6F** (the measured ~1.4× decode gather-fusion) unless a specific
> low-concurrency/long-context customer needs it. **Do not start M2** (the occupancy-first kernel
> rewrite) now.

## Why (the measured chain that got us here)

| finding | evidence |
|---|---|
| int4 decode is ~7–12× slower than bf16 at long ctx | `K2_AGGREGATE_LOCK_MEASURED.md` (whole-step profile) |
| the int4 attention kernel is 12× bf16, latency-bound at 2% HBM BW | `K2_KERNEL_DIAGNOSIS.md` (roofline) |
| that is **12% occupancy set by the BASE kernel's 255 regs** (stock bf16 is 255 too) | `K2_M1_BASELINE_MEASURED.md` (cuobjdump) |
| **cutting the int4 register spill does NOT reduce decode latency** (−0.2…−0.7% across U1/U2/U4) | `K2_M1_VERDICT.md` (op microbench) |

⇒ No *cheap* kernel change makes int4 fast; the only kernel lever left (M2) fights the base-kernel
occupancy ceiling for weeks with uncertain payoff. **int4's value is capacity, not speed.** So the
speed problem is better solved by a *different, cheaper* compression — 8-bit — not more int4 kernels.

## The two-tier design

| tier | dtype | compression vs bf16 | decode speed | when to use |
|---|---|---|---|---|
| **capacity** | INT4-protected | ~4–8× | ~7–12× slower (measured) | max context / concurrency per GPU; latency-tolerant |
| **speed (candidate)** | **fp8** (`kv_cache_dtype="fp8"`) | 2× | **≈ bf16 (to measure)** | latency-sensitive serving; needs the eval below |
| (baseline) | bf16 | 1× | 1× | when neither capacity nor a proven 8-bit tier is needed |

**Why fp8 is the concrete "8-bit KV" candidate:** vLLM 0.7.3 + the flash-attn fork support
`kv_cache_dtype="fp8"` (e4m3/e5m2) **natively** — the dequant is a single scale multiply, no nibble
unpack, no per-group scale/xmin, no protected-channel sidecar. So it should be near-bf16 speed with
**zero custom kernel** (the opposite of int4's problem). Integer int8 KV is *not* native in this
stack (would need a quant method + custom kernel — which defeats the "cheap speed tier" goal), so the
evaluation leads with fp8 and only falls back to int8-integer if fp8's quality is inadequate.

## The evaluation (before funding more int4 or committing the speed tier)

Run `bench_kv_tier_eval.py` on the A100 to measure, at matched operating points, `kv_cache_dtype ∈
{auto(bf16), fp8}` (+ the int4 number from `K2_M1_VERDICT.md` for context):

1. **decode latency** (prefill-subtracted ms/tok, eager) — is fp8 within ~10–20% of bf16?
2. **quality** — token divergence vs bf16 (greedy): first-divergence position + fraction-matching
   over a fixed generation. (fp8-e4m3 KV typically loses little; measure it, don't assume.)
3. **capacity** — KV blocks / max concurrency at fixed GPU-mem (fp8 ≈ 2× bf16; int4 ≈ 4–8×).

### Pre-registered decision

- **fp8 GO as speed tier** if decode ≈ bf16 (≤ ~1.2×) **and** quality loss is acceptable for the
  target workload (fraction-matching high / small perplexity delta). → ship two tiers: int4=capacity,
  fp8=speed; bf16 only where fp8 quality is insufficient.
- **fp8 quality insufficient** → evaluate int8-integer (calibrated) as a follow-up, accepting it needs
  custom work; or keep bf16 for speed-critical paths.
- **fp8 not meaningfully faster than int4** (unlikely) → re-open the int4 speed question.

## Standing items (not now)

- **6F gather-fusion** — measured ~1.4× decode (`K1_HEADROOM_MEASURED.md`); **deferred**, build only
  if a specific low-concurrency/long-context customer needs it. Does not change the capacity-vs-speed split.
- **M2 occupancy rewrite** — **not started**; only if int4 *speed* becomes a hard requirement and the
  8-bit tier is ruled out.
- Production INT4 kernel: unchanged, known-good, preserved.
