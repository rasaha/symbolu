# Experiment 6 — throughput: does protected-K actually run fast enough to beat FP8

Status: **6b (analytic ceiling) done — this commit.** 6a runnable, gated on
route-A GPU-verification. 6c (the fused kernel) is the long pole.

## Why this is the decisive experiment

§20.4.2 made the quality case: protected-K (top 4% of K channels FP16, rest
INT4, V-INT4) → 100% needle at 16k, ~3.1× compression. But **compression +
quality only beats FP8 on paper.** FP8 is 2×, has hardware tensor-core
support, and ships in vLLM today with mature kernels. Protected-K's ~3.1×
memory becomes a *product* win only if it also **decodes fast enough**.
Experiment 6 measures that. Until it is done, "beats FP8" is a
compression-and-quality claim, not an end-to-end one — and throughput is
the dominant remaining risk for the whole INT4 line.

## Exp 6 is engineering + measurement — not a harness run

Experiments 1–5 are "run the harness, read needle %". Exp 6 has a **build
step**. It splits into three parts.

### 6a — Measure the no-kernel floor (runnable now)

Route-A (the vLLM monkey-patch, `int4_cache_kv_route_a.py`) ships a PyTorch
dequant fallback: every attention call dequantizes INT4→FP16 in a torch op,
then runs FlashAttention on FP16. That is the **floor** — it works today,
no kernel — but it *adds* dequant cost, so it is expected to be slower than
FP16. Measuring it quantifies the gap a kernel must close.

- Environment: **venv-vllm** (vLLM 0.7.3, transformers 4.48.3) — not the
  venv-hf used for the quality runs.
- First: **GPU-verify route-A** — §20.5 lists it as CPU-validated only,
  Days 4-5 (GPU verification) pending. See `ROUTE_A_VLLM_CACHE_KV_PLAN.md`.
- Then: the §20.1 four-cell throughput harness — `vllm_throughput_cell.py`
  and `track_e_throughput.py` — measure vLLM FP16, vLLM FP8, and route-A
  INT4 tokens/sec. See `FP8_INT4_THROUGHPUT_RUNBOOK.md` for the cell
  definitions.
- Expected: naive route-A is **slower** than FP16 (the sketch estimates
  ~5–15% dequant overhead). That number is the gap.

Note: route-A currently implements **uniform INT4**, not protected-K. Step
6a measures uniform-INT4 route-A; extending route-A to protected-K is part
of the 6c kernel phase (the mixed layout and the kernel are co-designed).

### 6b — The analytic ceiling (done — this commit)

Decode attention is bandwidth-bound. A fused kernel that streams INT4 from
HBM and dequantizes in registers — no FP16 round-trip — has a HBM-traffic
ceiling, computed in `int4_fused_attention_sketch.py`:

| Layout | HBM-traffic ceiling vs FP16 |
|---|---|
| uniform INT4 (asymmetric, group 32) | ~3.20× |
| **protected-K 4% — the §20.4.2 winner** | **~3.07×** |
| symmetric-only (reference) | ~3.56× |

Run: `python -m kv_policy.int4_fused_attention_sketch`.

**Finding:** protecting 4% of K channels at FP16 costs only ~0.13× of the
ceiling. The mixed FP16+INT4 K layout does **not** kill the kernel's
bandwidth advantage — a fused kernel for protected-K is worth building,
~as much as for uniform INT4. This is the Exp-6 go-ahead input.

### 6c — The fused kernel (the long pole — specialist work)

The kernel that closes the 6a→6b gap: reads INT4 packed values (plus the
FP16 outlier channels) from HBM, dequantizes inline in registers, feeds
`softmax(QK^T)V` directly — no FP16 intermediate.

- **~1–2 weeks of Triton/CUDA specialist work** — sized in
  `int4_fused_attention_sketch.py` ("Sizing notes"). It cannot be written
  or validated in a non-GPU agent session; it needs a GPU-kernel engineer.
- Contract: `fused_int4_attention_reference` is the numerical spec — but it
  must be **extended for protected-K**: after the INT4 dequant, merge the
  FP16 outlier channels back in (mirrors `_restore_outlier_channels` in
  `int4_per_channel_hf_cache.py`). The exact param layout — how the FP16
  outliers and the channel mask are passed and tiled — should be
  co-designed with the kernel's memory layout, so it is the **first
  kernel-phase task**, not pre-written here.
- Recommendation: Triton-prototype first (validates the algorithm + the
  HBM access pattern, ~70% of CUDA perf), CUDA-promote only if the Triton
  overhead vs the FP16 FlashAttention baseline is > 5%.

## Decision gate

**After 6a:**
- Naive route-A within ~10% of FP16 → route-A could ship without a kernel;
  the kernel becomes pure upside. (Unlikely, but it bounds the work.)
- Naive route-A materially slower than FP16 → the kernel is **required** to
  be throughput-competitive. 6b shows the ceiling is ~3× — real headroom —
  so committing to 6c is justified.

**After 6c:**
- Kernel within ~5–10% of FP16 decode latency → protected-K's ~3.1× memory
  + ~100% quality is a genuine **end-to-end** win over FP8 — and note §20.1
  measured FP8 at only ~1.18× FP16 on A100, so FP8's throughput edge is
  modest without H100 hardware.
- Kernel can't get close to FP16 → protected-K stays a memory/quality win
  with no throughput win; FP8 remains competitive on speed, and the honest
  position is "protected-K for memory-bound deployments, FP8 for
  latency-bound."

## Honest status

- **6b: done** (analytic, this commit) — the kernel is worth building.
- **6a: runnable**, gated on route-A GPU-verification (§20.5 Days 4-5).
- **6c: not started — and out of scope for an agent session.** It is real
  GPU-kernel engineering (~1–2 weeks, a specialist). This is the genuine
  long pole. Everything upstream (quality, the analytic case) now says it
  is worth doing; doing it is a staffing decision, not a script run.
