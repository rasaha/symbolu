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

## ⚠ Backend requirement (measured gotcha — read before trusting any fp8 number)

**vLLM 0.7.3's FlashAttention-2 backend CANNOT serve fp8 KV.** When `kv_cache_dtype="fp8"` it logs
`Cannot use FlashAttention-2 backend for FP8 KV cache … Using XFormers backend` and **silently falls
back to XFormers**, which is ~7× slower. That fallback latency is a *backend artifact, not fp8's cost.*

- **First run (INVALID):** ctx16k B=8 — bf16 **16.50 ms/tok** (FA2, 45010 blocks) vs fp8 **119.50 ms/tok
  = 7.24× bf16** (XFormers, 90272 blocks, token-match 1.6%). The 7.24× and the 1.6% are both XFormers
  artifacts — bf16 ran on the fast FA2 path while fp8 ran on the slow XFormers path, so the comparison
  is apples-to-oranges and **does not measure fp8**.
- **Fix (in `bench_kv_tier_eval.py`):** for any `fp8*` dtype the bench now sets
  `VLLM_ATTENTION_BACKEND=FLASHINFER` (and warns + flags the result INVALID if flashinfer is not
  installed); bf16 stays on its FA2 default. fp8 KV is only fairly measured on **FlashInfer**.
- The 1.6% token-match is *also* suspect under XFormers (different backend, not just different KV
  precision). Re-measure quality on FlashInfer, and remember uncalibrated fp8-e4m3 uses a default scale
  — a real quality gate needs **calibrated scales**, not this proxy.

**Re-run (valid) once FlashInfer is present:**
```bash
python -c "import flashinfer" 2>/dev/null || pip install flashinfer-python   # match torch2.5.1+cu12x
python CTM_plus/Bench/scripts/bench_kv_tier_eval.py --context-tokens 16000 --batch 8 --gen 64 --dtypes auto,fp8
```

## ✅ Measured (2026-07-17, VALID — fp8 on FlashInfer)

Re-run with fp8 forced onto FlashInfer (flashinfer **0.6.15** worked with vLLM 0.7.3 — no fallback),
Qwen2.5-7B, ctx 16000, B=8, gen 64, eager:

| dtype | decode ms/tok | vs bf16 | KV blocks | token-match |
|---|--:|--:|--:|--:|
| auto (bf16, FA2) | 16.82 | 1.00× | 45,008 | — |
| **fp8 (FlashInfer)** | **16.87** | **1.00×** | 89,647 (**2.0×**) | 2% (confounded — see below) |
| int4-protected (ref) | 152 | 9.0× | ~4–8× cap | — |

- **Latency: GO.** fp8 KV is bf16 speed (1.00×). The earlier 119.5 ms/tok "7.24×" was a pure XFormers
  fallback artifact, now eliminated by forcing FlashInfer.
- **Capacity: 2.0×** KV blocks at fixed GPU-mem (half the KV bytes), vs int4's 4–8×.
- **Quality: the 2% token-match is NOT a quality signal.** Greedy decoding diverges completely after one
  early token flip, so a benign sub-percent fp8 rounding reads as ~2% match; it came out ~the same
  (1.6–2%) on BOTH backends, confirming it tracks precision *drift*, not damage. The real gate is
  **perplexity** — `bench_kv_quality_eval.py`, teacher-forced NLL over fixed text (not confounded by
  drift), **PPL delta ≤ 1% frozen before measurement**. **Run that next; it is the last open leg.**

Environment: fp8 KV needs FlashInfer in this stack; flashinfer 0.6.15 installed against torch 2.5.1+cu121
and served fp8 at bf16 speed (protobuf downgraded 7.35.1→6.33.6, harmless; int4 op unaffected).

## The evaluation (before funding more int4 or committing the speed tier)

Run `bench_kv_tier_eval.py` on the A100 to measure, at matched operating points, `kv_cache_dtype ∈
{auto(bf16), fp8}` (+ the int4 number from `K2_M1_VERDICT.md` for context). **fp8 must run on
FlashInfer (above) or the latency is invalid:**

1. **decode latency** (prefill-subtracted ms/tok, eager) — is fp8 within ~10–20% of bf16?
2. **quality** — token divergence vs bf16 (greedy): first-divergence position + fraction-matching
   over a fixed generation. (fp8-e4m3 KV typically loses little; measure it, don't assume.)
3. **capacity** — KV blocks / max concurrency at fixed GPU-mem (fp8 ≈ 2× bf16; int4 ≈ 4–8×).

### Pre-registered decision

**Status (2026-07-17): latency ✅ (1.00×) · capacity ✅ (2.0×) · quality ❌ UNCALIBRATED fp8 is
CATASTROPHIC on Qwen2.5-7B — calibration is the untested make-or-break lever.** fp8 is fast and dense
but NOT a clean speed tier as-shipped (default scale=1.0). Speed-tier viability now hinges entirely on
whether runtime KV-scale calibration (`--calibrate` / `calculate_kv_scales=True`) rescues quality.

#### Quality — MEASURED (uncalibrated fp8, Qwen2.5-7B), 4 independent metrics agree

| metric | source | fp8 (uncalibrated) vs bf16 | note |
|---|---|---|---|
| perplexity (teacher-forced, real text) | `bench_kv_quality_eval.py` 2026-07-17 | PPL **13.6 → 799** (**+4.07 nats/tok**) | not confounded; healthy baseline |
| greedy token-match | `bench_kv_tier_eval.py` this session | **~2%** | (was mis-read as "benign drift" — it wasn't) |
| needle-in-haystack | `verify_phase5b_5_needle_fp8.py` → `INT4_PROTECTED_VC_BRIEF.md:648` | **1/15** | retrieval catastrophe |
| greedy bit-exactness | `bench_phase5c_v1.py` → `PHASE5C_SHIP_REPORT.md:12,43` | **0/6, ~12% overlap** | 2026-05-25 |

Cross-**backend** (XFormers + FlashInfer) and cross-**session** — so it is fp8, not a harness artifact.
**Likely cause:** default scale=1.0 saturates Qwen's KV outliers. **Rescued on Llama-3.1-8B** with
calculated scales (needles pass — `NEXT_POD_SESSION_INT4_GPU_RUNS.md:456`), so calibration is the
candidate fix, UNTESTED on Qwen. fp8 **MMLU/task-accuracy** was never measured (int4-only).

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
