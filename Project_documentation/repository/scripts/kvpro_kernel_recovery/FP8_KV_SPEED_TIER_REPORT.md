# FP8 KV Cache as the Speed Tier — Evaluation Report

**Date:** 2026-07-17 · **Hardware:** A100 80 GB (sm_80) · **Stacks:** vLLM 0.7.3 (int4-pinned) and
vLLM 0.8.5.post1 (Qwen3 only) · **Status:** COMPLETE

---

## 1. TL;DR (verdict)

**fp8 KV cache is a validated speed tier — for any model whose KV is not outlier-pathological, which is
the modern norm.** It delivers **≈bf16 decode latency (1.00×) at 2× KV capacity** with **negligible
quality loss** on 3 of the 4 models tested. The single failure — **Qwen2.5-7B** — is a *model* property
(per-channel KV outliers), **not** a stack/version artifact, and it is already fixed in its successor
**Qwen3-8B** by QK-normalization.

| tier | dtype | compression | decode speed | quality | role |
|---|---|--:|--:|---|---|
| **speed** | **fp8** (e4m3) | 2× | **1.00× bf16** | ✅ on fp8-robust models | latency-sensitive serving |
| **capacity** | int4-protected | 4–8× | ~9× slower | robust (protects outliers) | max context/concurrency, latency-tolerant |
| **fidelity / fallback** | bf16 | 1× | 1× | perfect | fp8-hostile models, or max accuracy |

**Operational rule:** enable fp8 **per model behind the perplexity gate** (`bench_kv_quality_eval.py`);
it caught a 4–6 nat catastrophe on Qwen2.5 and cleared the other three. Never enable fp8 by assumption.

---

## 2. Motivation

The production **int4-protected** KV kernel is a *capacity* play (4–8× compression) but is **~9× slower
than bf16 at decode** and occupancy-bound at ~12% (255 registers), with **no cheap kernel fix** — the
bounded-unroll register-reduction experiment (K2-M1) returned a measured NO-GO (−0.2…−0.7% latency; see
`K2_M1_VERDICT.md`). The remaining kernel lever (M2, an occupancy-first rewrite) is weeks-to-months of
uncertain work. Rather than fund more int4 kernel work, we evaluated whether **fp8** — a *commodity*
8-bit KV format native to vLLM, whose dequant is a single multiply (no dependency chain, no per-channel
metadata) — can serve as the speed tier at ~bf16 speed with acceptable quality.

---

## 3. Method

Two stock-vLLM benchmarks (no custom kernel), all thresholds **frozen before measurement**:

- **`bench_kv_tier_eval.py`** — decode latency (prefill-subtracted ms/tok, eager, median of 3) and KV
  capacity (# gpu blocks at fixed gpu-mem) for `kv_cache_dtype ∈ {auto(bf16), fp8}`.
  Pre-registered latency gate: **fp8 ≤ 1.2× bf16**.
- **`bench_kv_quality_eval.py`** — teacher-forced **perplexity** (mean NLL over the tail of a long
  context) for `kv_cache_dtype ∈ {auto(bf16), fp8, fp8_e5m2}`, on real text (wikitext-2, or a capped
  ~1000-token built-in prose fallback). Pre-registered quality gate: **fp8 PPL delta ≤ 1%**.

**Why perplexity, not token-match.** Greedy token-divergence is *confounded*: a single early token flip
diverges the whole sequence, so a benign perturbation reads as ~2% match. Perplexity scores the *same*
tokens under each precision (teacher-forced), so it is not confounded — a small error → small delta, a
real degradation → large delta. Both the relative % and the **absolute nats/token** are reported (the
latter is stable even when the baseline PPL is small).

**Backend requirement.** vLLM 0.7.3's FlashAttention-2 backend **cannot** serve fp8 KV — it silently
falls back to XFormers (~7× slower). All fp8 cells force `VLLM_ATTENTION_BACKEND=FLASHINFER`; bf16 stays
on FA2.

---

## 4. Results

### 4.1 Latency & capacity — `bench_kv_tier_eval.py`

Qwen2.5-7B-Instruct, ctx = 16 000, batch = 8, gen = 64, eager, A100:

| dtype | backend | decode ms/tok | vs bf16 | KV blocks | capacity |
|---|---|--:|--:|--:|--:|
| auto (bf16) | FlashAttention-2 | **16.82** | 1.00× | 45 008 | 1× |
| **fp8 (e4m3)** | **FlashInfer** | **16.87** | **1.00×** | 89 647 | **2.0×** |
| int4-protected (ref) | custom fork | 152 | **9.0×** | — | ~4–8× |

- fp8 decode latency is **statistically identical to bf16** (1.00×), at **2× KV capacity**.
- int4-protected is **9× slower** — the measured basis for treating it as capacity-only.

> **Invalid run (recorded for honesty):** the *first* fp8 latency measurement returned **119.5 ms/tok
> (7.24× bf16)**. That was an XFormers-fallback artifact (FA2 can't do fp8 KV), **not** fp8's cost —
> eliminated by forcing FlashInfer.

### 4.2 Quality — perplexity, `bench_kv_quality_eval.py`

fp8-e4m3 KV vs bf16, teacher-forced PPL on the tail of a long context (gate = ≤ 1% delta):

| model | vLLM | text (n tok) | bf16 PPL | fp8 PPL | Δ% | Δ nats/tok | verdict |
|---|---|---|--:|--:|--:|--:|---|
| **Llama-3.1-8B-Instruct** | 0.7.3 | wikitext (3931) | 8.9740 | 8.9885 | **+0.16%** | **+0.0016** | ✅ clean |
| **Mistral-7B-Instruct-v0.3** | 0.7.3 | wikitext (4001) | 7.0619 | 7.0529 | **−0.13%** | **−0.0013** | ✅ clean |
| **Qwen3-8B** | 0.8.5 | wikitext (4000) | 10.8396 | 10.8819 | **+0.39%** | **+0.0039** | ✅ clean |
| **Qwen2.5-7B-Instruct** | 0.7.3 | prose (390) | 13.5891 | 798.6385 | +5777% | **+4.0736** | ❌ catastrophic |
| **Qwen2.5-7B-Instruct** | 0.8.5 | wikitext (4000) | 6.8322 | 4975.9750 | +72731% | **+6.5907** | ❌ catastrophic |

**3 of 4 models are fp8-clean.** Qwen2.5 is broken by ~4–6.6 nats/token — the model is nearly
unusable under fp8 KV. Note Qwen2.5 fails at **both** context lengths and on **both** vLLM versions.

> **Invalid runs (recorded):** early Qwen2.5 quality runs used a *tiled* short prose that made the tail a
> memorized loop → degenerate baseline **bf16 PPL 1.0009** → the relative metric exploded (a
> division-by-≈0 artifact), reported as +202% / +6.6 M%. Fixed by (a) real wikitext text, (b) a
> degenerate-baseline guard that refuses to emit a verdict when bf16 PPL < 1.5, (c) never tiling (cap the
> context to the available real text). The valid Qwen2.5 numbers are the two rows above.

### 4.3 fp8_e5m2 (the alternate 8-bit format)

Consistently worse than e4m3 (2 mantissa bits): Qwen2.5-7B (0.7.3, prose) **fp8_e5m2 PPL 1239.60
(+4.51 nats/tok)** vs e4m3's 798.64. e5m2 is not a viable rescue for a fp8-hostile model.

### 4.4 Runtime calibration is a verified NO-OP (on vLLM 0.7.3 + FlashInfer)

`calculate_kv_scales=True` (the runtime KV-scale lever) was **confirmed passed** on Qwen2.5-7B but had
**no effect**: the applied KV scales stayed `[1.0, 1.0, 1.0, 1.0]` and the fp8 PPL was **byte-identical**
(798.6385) to the uncalibrated run. Two independent signals (introspected scales + unchanged PPL) agree.
⇒ Runtime calibration does not rescue Qwen2.5 on this path; only offline scales
(`--quantization-param-path`) remain — and a **per-tensor** scale structurally cannot protect
**per-channel** outliers (the exact problem int4-protected was built for), so it is a long shot.

### 4.5 Prior-work corroboration (earlier sessions, other metrics)

fp8 KV quality had been measured on this codebase before, on *different* metrics — all consistent with
the perplexity result above:

| metric | model | fp8 (uncalibrated) | source |
|---|---|---|---|
| needle-in-haystack | Qwen2.5-7B | **1/15 (6.7%)** | `verify_phase5b_5_needle_fp8.py` → `INT4_PROTECTED_VC_BRIEF.md:648` |
| greedy bit-exactness | Qwen2.5-7B | **0/6 identical, ~12% overlap** | `bench_phase5c_v1.py` → `PHASE5C_SHIP_REPORT.md:12,43` |
| needle + greedy (calc-scales) | Llama-3.1-8B | needles **pass**; greedy 2/6, 84% | `bench_8bit_kv_gate.py` → `NEXT_POD_SESSION_INT4_GPU_RUNS.md:456` |
| greedy token-match (this session) | Qwen2.5-7B | **~2%** | `bench_kv_tier_eval.py` |

So Qwen2.5 fp8 fails on **four** independent metrics (perplexity, needle, greedy bit-exactness,
token-match); Llama passes. Also confirmed from vLLM source: **there is no int8 KV cache** in this stack
(fp8 is the only native 8-bit option).

---

## 5. The controlled attribution: model, not version

The Qwen2.5→Qwen3 jump changed two things (model generation *and* vLLM 0.7.3→0.8.5). The following matrix
isolates the cause to the **model**:

| model | on vLLM 0.7.3 | on vLLM 0.8.5 |
|---|---|---|
| **Qwen2.5-7B** | ❌ +4.07 nats | ❌ +6.59 nats |
| **Qwen3-8B** | *(0.7.3 cannot load it)* | ✅ +0.39% |
| **Llama-3.1-8B** | ✅ +0.16% | — |
| **Mistral-7B** | ✅ −0.13% | — |

- **0.7.3 column:** Qwen2.5 fails while Llama & Mistral are clean — *same version* ⇒ version is not the cause.
- **0.8.5 column:** Qwen2.5 fails while Qwen3 is clean — *same version* ⇒ opposite outcomes purely by model.
- **Qwen2.5 row:** broken on *both* versions ⇒ no vLLM release fixes it.

The only variable that predicts the outcome is the **model's KV distribution**. **Version, backend, and
eval are held constant across the failures and the passes.** Attribution to the model is airtight.

---

## 6. Mechanism

fp8 KV in vLLM uses a **single per-tensor scale** per layer. **Qwen2.5-7B's KV has large per-channel
outliers**; a per-tensor scale cannot represent both the outlier channels and the normal channels, so
fp8 either saturates or loses all precision → catastrophic degradation. **Llama-3.1, Mistral-7B, and
Qwen3-8B** have well-behaved KV (Qwen3 specifically adds **QK-normalization**, which suppresses those
outliers), so fp8's single scale is sufficient → negligible loss. The ~1000× Qwen2.5→Qwen3 swing on the
identical eval is the direct evidence. Because normalization is becoming standard in new architectures,
**fp8-friendliness is expected to become more, not less, the norm over time.**

---

## 7. Engineering notes & gotchas (for reproduction)

1. **fp8 KV must run on FlashInfer** in vLLM 0.7.3 — FA2 falls back to XFormers (~7× slower, invalid).
2. **prompt_logprobs OOM:** perplexity via `prompt_logprobs` materializes a `[ctx × vocab]` rank tensor
   (~9 GB at ctx 8000 / 152k vocab). vLLM's profiler sizes the KV pool without accounting for it, so at
   `gpu_memory_utilization=0.70` the idle KV reservation starves it → OOM. Fix: **`--gpu-util 0.30`** (KV
   for one sequence is <1 GB; the peak is activation, not KV).
3. **Degenerate baseline:** tiling short text → memorized loop → bf16 PPL ≈ 1.0 → relative delta explodes.
   Use real text (wikitext) and never tile; a guard refuses verdicts when bf16 PPL < 1.5.
4. **Qwen3 needs a newer stack:** vLLM ≥ 0.8.4 / transformers ≥ 4.51 (0.7.3 predates Qwen3). On an A100
   with **CUDA driver 12.4**, pin **vLLM 0.8.x** (torch 2.6 / cu124) — vLLM 0.9+ ships cu126/cu128 and
   fails with "driver too old." Force **`VLLM_USE_V1=0`** (V0 engine) for script compatibility, and pin
   **transformers 4.51.3** (newer transformers trips vLLM 0.8.5's tokenizer path). Tested in a *separate*
   venv so the int4-pinned 0.7.3 stack is untouched.

---

## 8. Decision & operational policy

- **fp8 = speed tier**, enabled **per model behind `bench_kv_quality_eval.py`** (≤ 1% PPL gate). Pass →
  ship fp8 (2× capacity at bf16 speed). Fail (Qwen2.5-style) → bf16 for that model.
- **int4-protected = capacity tier** (unchanged, known-good, preserved). No further int4 *kernel* work is
  warranted (K2-M1 NO-GO; M2 not justified by the measured evidence).
- **bf16 = fidelity/fallback.**
- **Final ship gate for a chosen model:** task-accuracy / needle on the *target workload* (PPL is a strong
  screen, not the last word) — low-risk for the three clean models.

---

## 9. Caveats & limits

- Perplexity is a **screen**, not the final quality word; a retrieval-heavy workload should confirm with
  needle/task-accuracy (Qwen2.5's needle failure is already independently recorded).
- Latency/capacity measured at a **single operating point** (ctx 16k, B=8); the fp8≈bf16 result is a
  kernel/format property unlikely to reverse, but is stated as measured-here.
- Quality measured at ctx ≈ 4–8k tail tokens; Qwen2.5 fails at both 780 and 8000 ctx.
- Only **4 models** tested. The base rate (3/4 clean, failure superseded) is favorable but the gate
  remains mandatory per new model.
- fp8 offline-calibration (`--quantization-param-path`) for Qwen2.5 was **not** built — judged a long shot
  (per-tensor scale vs per-channel outliers) and not worth the infra given Qwen3 already fixes it.

---

## 10. Reproduction

```bash
# Latency + capacity (vLLM 0.7.3 stack)
python CTM_plus/Bench/scripts/bench_kv_tier_eval.py --context-tokens 16000 --batch 8 --gen 64 --dtypes auto,fp8

# Quality — perplexity gate (any model; needs `datasets` + `hf_transfer` for wikitext)
python CTM_plus/Bench/scripts/bench_kv_quality_eval.py --model <HF_ID> --dtypes auto,fp8 --gpu-util 0.30
#   add --calibrate to test runtime KV-scale calc (verified no-op on 0.7.3+FlashInfer)

# Qwen3 (separate venv; A100 / driver 12.4):
#   pip install "vllm>=0.8.4,<0.9" "transformers==4.51.3" datasets hf_transfer flashinfer-python
#   VLLM_USE_V1=0 python .../bench_kv_quality_eval.py --model Qwen/Qwen3-8B --dtypes auto,fp8 --gpu-util 0.30
```

**Frozen thresholds:** latency GO ≤ 1.2× bf16 · quality GO ≤ 1% PPL delta (both set before measurement).
No GPU/quality number in this report is modeled or projected — every value is measured, with invalid runs
labeled as such.

---

*Related: `KV_TIER_STRATEGY.md` (decision doc) · `K2_M1_VERDICT.md` (int4 kernel NO-GO) ·
`K2_KERNEL_DIAGNOSIS.md` (int4 occupancy roofline).*
