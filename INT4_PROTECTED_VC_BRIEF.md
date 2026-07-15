# KVPro — VC Brief

**Ugence Labs | Quality-Safe KV-Cache Compression for Long-Context LLM Serving**
*Prepared May 2026 · throughput section updated June 2026 (Phase 6M) · read-skip / long-context decode-scaling updated June 2026 (Phase 10) · prefix caching (APC) shipped eager-only June 2026 (Phase 6K.16) · APC payoff + live density measured June 2026 · HBM-vs-NAND logical/physical density distinction + modeled storage-tier limits added June 2026 (P0–P1, not silicon-measured) · hierarchical-KV (vLLM/LMCache) reliability-layer positioning + SAW-INT4 head-to-head (MEASURED, n=1) added June 2026 · KVPro WarmTier: byte-faithful disk snapshot/restore (Phase-0, MEASURED) + KVPro-vs-CacheGen codec fidelity (MEASURED, end-to-end open) added June 2026 · renamed to KVPro + 1-page exec summary added June 2026*

> **Product family.** KVPro is an **AI Infrastructure** product in the Ugence Labs platform, alongside the Cloud Scaling Controller. Canonical platform architecture: `UGENCE_PLATFORM_OVERVIEW.md`.
>
> **Naming key.** **KVPro** = the product / module. **int4_protected** = its first shipped codec
> implementation (the vLLM backend measured throughout this brief; the registered `kv_cache_dtype`
> string stays `int4_protected`). **Protected channels** = the core mechanism (keep the ~4%
> highest-attention K channels at bf16, quantize the rest to int4). **KVPro WarmTier** = the
> storage/reuse product direction (snapshot KV to CPU/NVMe and reuse it across sessions).

---

## Executive Summary (one page)

**The problem.** At long context (32K+), the **KV-cache — not model weights — dominates LLM serving
cost and caps concurrency.** The obvious fix, 4-bit KV, hasn't shipped *at quality*: fp8 and naive int4
buy density by spending accuracy (fp8: needle 1/15; naive int4: token-agreement vs bf16 collapses to
0.53). The gap between "4-bit density" and "maintained quality" is the market.

**The product.** **KVPro** is a quality-safe KV-cache compressor. Its first codec, **int4_protected**,
uses the **protected-channels** mechanism — keep the ~4% highest-attention K channels at bf16, quantize
the rest to int4 — to restore **near-bf16 fidelity at ~2× KV density**. It ships through vLLM as a
one-line backend: no retraining, no quantization-aware fine-tuning.

**What's measured (this quarter, real H100/A100):**
- **Quality:** 4 models (Qwen / Mistral / Llama, 7–14B) hit **15/15 needle == bf16** (2-of-2 seeds);
  MMLU / ARC / TruthfulQA **0.0-pt delta + 100% per-question agreement**; **+20.4 pt** token-agreement
  over naive int4; hard-needle 0.964 vs naive 0.915.
- **Density:** **2.0× raw KV slots, ~1.8× net** of the sidecar tax (1.83× Qwen util 0.5 / 1.75× Llama
  util 0.85), demonstrated under sustained saturation.
- **Honest cost:** decode is **throughput-negative — 0.13–0.67× bf16** (0.22× worst case; 0.54× at
  short generation). KVPro is a **capacity + quality** tool, not a bf16 *speed* replacement: route
  memory-bound, long-context, high-concurrency, and shared-prefix traffic to it; keep latency-critical
  single-stream on bf16.

**The competitive edge (measured).** Against every *denser* competitor, KVPro's protected channels
**hold the hard tail where they collapse**: **SAW-INT4** → 0% needle on Qwen2.5-7B (KVPro/bf16 100%);
**KVarN** → hard-needle 0.25→0.06; and vs LMCache's **CacheGen** codec, KVPro has **zero error on the
high-attention K channels vs CacheGen's 0.0145** (measured on real KV). The trade is honest: KVPro is
**less dense, quality-safe.**

**KVPro WarmTier (the direction).** As serving moves to **GPU→CPU→NVMe KV hierarchies**, the bottleneck
becomes quality-safe KV *movement*. KVPro's snapshot/restore is **byte-faithful** (Phase-0 proven on
Qwen2.5-7B, both protect formats) — so reused KV loses **zero** quality, a guarantee lossy codecs can't
make. This positions KVPro as the **reliability layer** on top of LMCache's offload plumbing. *(Serving
integration and the end-to-end CacheGen needle comparison are scoped-but-open.)*

**The ask.** A production partner (~10–100 GPUs of long-context traffic) to convert "shipped through
vLLM at near-bf16 fidelity" into "deployed with measured $/quality/latency," and to fund v2 Tier-1
(decode-kernel throughput recovery, tensor parallelism, KVPro WarmTier serving).

---

> ## North star: "the most token value per watt per user"
>
> > *"Whoever is able to maximize this particular objective really will — by
> > balancing accuracy, latency, cost, privacy and intelligence all together —
> > they're going to win; that's what's going to win long term."*
> > — **Aravind Srinivas, CEO, Perplexity**, on the company that delivers the
> > "most token value per watt per user" (CNBC, interview with Elaine Yu, June 2026)
>
> Inference economics reduce to that ratio: **useful tokens delivered per joule,
> per concurrent user.** KVPro is built to move it on the very axes
> Srinivas names — and, decisively, without spending the **accuracy** term that
> competitors trade away:
>
> - **per user / cost (shipped):** **~1.8× denser KV-cache (net)** → more concurrent
>   long-context users on the same GPU. *Canonical density figure used throughout:*
>   **2.0× raw KV slots, ~1.8× net of the sidecar tax** — measured 1.83× on Qwen
>   (util 0.5, mml 8K, Phase 6L) and 1.75× on Llama-3.1-8B (util 0.85, mml 32K); both
>   appear below tagged to their config.
> - **token *value* / accuracy (shipped):** quality held at bf16 parity (MMLU/ARC
>   0.0 pt; needle preserved). A cheap *wrong* token has no value — this is the
>   wedge: fp8 and naive int4 buy density by spending accuracy; we don't.
> - **per watt / long-context (in build, Phase 10):** layered on the int4 cache,
>   attention-guided **read-skip** cuts per-token KV-read traffic — the
>   energy-per-token lever — by **94% at 32K with needle quality fully preserved**
>   (1.0/1.0 at both depths; the retained-index path is GPU-verified
>   output-identical to full-read, `gather == full-read`). Honest on timing:
>   below ~32K decode is weight-bound and full-int4 KV reads are already cheap, so
>   read-skip measures **−10.6% vs full-int4 at 32K** (recovered from ~−30% as the
>   controller moved on-GPU — tensor index + cached block-ids + tuned observe
>   cadence). But the retained set is **bounded** while full attention grows
>   **linearly**: read-skip now MEASURES throughput-positive **vs full-int4**
>   from ≤32K on 8-KV-head models (+8%→+36% across 32→60K at 77–88% skip,
>   June 2026; +25%→+72% at the ~95%-skip config — keep-set dependent),
>   quality 1.0/1.0 throughout. Absolute disclosure (bf16-ref, same harness):
>   even with read-skip, decode is **~0.21–0.24× bf16, flat across 32–100K**
>   — it does NOT cross bf16 at these lengths (quality 1.0/1.0 to 100K). Realized value today is **density + flat decode-scaling that
>   compounds on int4** — store ~2× the context per GB (1.83× net of the sidecar tax) and hold per-token decode
>   ~flat as context grows, not a sub-32K speed win. Software-capturable, not a
>   hardware mandate.
>
> The bet: when accuracy is non-negotiable, the efficiency frontier is won by the
> approach that compounds density + energy savings *on top of* preserved quality —
> not by trading quality for either.

---

## Page 1 — The Problem

### LLM inference is becoming memory-bound, and 4-bit KV is the obvious answer that nobody has gotten to work

Production LLM serving is dominated by one cost: the **KV-cache**.
At long context (32K+), KV-cache memory exceeds model weight memory
on most popular open models. A single Mistral-7B request at 32K
context can consume ~2 GB of KV-cache in bf16. An H100-80GB
running concurrent traffic spends the majority of its HBM holding
KV state.

The industry has tried four mitigations:

| Approach | Memory savings | Quality | Status |
|---|---:|---|---|
| **bf16** (baseline) | 1.0× | perfect | the reference |
| **fp8** (half-precision) | 0.5× KV | **poor-to-mixed, MODEL-DEPENDENT** — Qwen-7B: needle 1/15 (6.7%), 0/6 bit-identical greedy, 12% prefix overlap (direct measurement). Llama-3.1-8B gate (June 2026): lite needles PASS (3/3@8K, 5/5@32K) but greedy divergence persists — e5m2 1/6 identical / 41% overlap, e4m3+calculated-scales 2/6 / 84% — and **both measured SLOWER than bf16 on vLLM 0.7.3** (0.76× / 0.33× @32K B=1): no speed win to offset the quality risk | shipped, widely deployed; quality degradation accepted |
| **naive int4** (unprotected 4-bit) | 0.5× KV | degraded — token-agreement vs bf16 collapses to 0.533 (53%); easy needle deceptively OK (≈0.96–1.0) but general generation fidelity is substantially degraded; hard multi-needle retrieval 0.915 (vs bf16 1.000) | research-grade only; not shippable for quality-sensitive workloads |
| **int4 with protected channels** *(our approach)* | **0.5× KV** | **near-bf16 fidelity: token-agreement 0.737 (+20.4 pt over naive); easy needle ≈ bf16 (saturated); hard-needle retrieval 0.964 (vs naive 0.915, bf16 1.000); 4-model portfolio 15/15 needle replicated 2-of-2 seeds on Mistral-7B, Llama-3.1-8B, Qwen-14B** | **shipped via vLLM, 4 models measured this quarter** |

The dominant production answer (fp8) sacrifices quality. Naive
int4 improves density but degrades general generation fidelity.
Neither is satisfactory for quality-sensitive deployments. The gap
between them is the market — anyone serving LLM workloads where
output accuracy matters wants 4-bit density AND maintained fidelity.

### Why the standard 4-bit approach fails

KV-cache K-vectors have **highly heterogeneous channel
importance**: a small fraction of the D channels carry most of the
attention signal, and the rest carry diffuse noise. Quantizing all
channels uniformly to int4 destroys the high-magnitude channels
that matter most for the attention inner product.

**Easy needle tasks are a deceptive benchmark.** Naive int4 achieves
0.96–1.0 recall on short-context needle retrieval — superficially
matching bf16. But the real quality signal is general generation
fidelity: token-for-token agreement vs bf16 collapses to 0.533.
Over half of all generated tokens diverge, even when a factual key
is retrieved correctly. Under harder retrieval stress (multi-needle,
look-alike distractors, conflicting facts), naive int4 accumulates
5 genuine misses vs bf16's 0, with both K-bound and V-bound errors.

### The breakthrough

**Protect 4% of K channels per (layer, head) at bf16; quantize the
rest aggressively to int4.** Pick the channels per-model by a 30-
second calibration pass that profiles which K-channels carry the
most magnitude. The result is a 4-bit KV scheme that restores
near-bf16 fidelity over naive int4 — **+20.4 points token-agreement,
hard-needle retrieval 0.964 vs naive 0.915** — at the same 4-bit KV
density.

**The honest trade-off**: KVPro costs ~+4.4 GB total HBM
vs bf16 (protection sidecars; Phase 6L live-measured the tax at
**4.38 GB** at mml=8K) and is **decode-throughput-negative**: ~1.5–1.9×
slower per-seq at low load, and at saturation Phase 6L measured **0.22×
bf16 aggregate tok/s** (~9× slower per user) on the as-yet-unoptimized
int4 decode path — *this 0.22× is the **worst case** (deep saturation +
long generation); the workload curve is 0.13×–0.54×, and short-output
serving pays only ~0.54× (see the throughput section)*. The win is
**fidelity-at-density**, not raw memory savings or throughput vs bf16.

This brief documents the KVPro backend: the calibration
methodology, the validated 4-model portfolio, the integration
through vLLM, and the honest trade-offs.

---

## Page 2 — The Architecture

### KVPro — one backend, one calibration script, one user-facing API

```
┌───────────────────────────────────────────────────────────────┐
│  User: Int4ProtectedLLM(model="...")                         │
└──────────────────┬────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│   Int4ProtectedAttentionImpl (vLLM backend subclass)         │
│   ──────────────────────────────────────────                 │
│   Write path:   bf16 K/V → int4 nibbles + per-block scale    │
│                 + xmin + 4% protected channels at bf16        │
│   Read path:    paged gather + tail splice + dispatch to     │
│                 forked FA kernel                              │
└──────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│   vllm-flash-attn fork (SHA 720c948 + int4 path)             │
│   ──────────────────────────────────────────                 │
│   In-kernel int4 dequant against vLLM block_table            │
│   Splices protected channels at correct slot indices         │
│   Outputs bit-comparable to bf16 FA at per-(layer,head) level│
└──────────────────────────────────────────────────────────────┘
```

### Three components

**1. The calibration script** (`calibrate_phase5b_protect_mask.py`)

Runs a 55-prompt corpus through the model once. Hooks every
attention layer's prefill K. For each `(layer, h_kv, channel)`
accumulates max-abs of K activations. Per `(layer, h_kv)` picks
the top-N channels (N = round(D * protect_fraction), N=5 at 4% for
D=128) as protected. Saves the mask as a small `(num_layers, H_kv,
D) int8` artifact (~17-50 KB per model).

Cost: ~30 seconds on H100 after the model loads. Model-agnostic
(works for any D=128 architecture without code changes).

**2. The vLLM backend** (`Int4ProtectedAttentionImpl`)

Subclasses vLLM's `FlashAttentionImpl`, installed via post-init
class swap on each Attention layer. The write path quantizes K/V
on cache-store. The read path gathers the int4 blocks +
reconstruction sidecars + protected channels and dispatches to the
forked FA kernel.

**3. The forked FA kernel** (vendored from `vllm-flash-attn` at
SHA `720c948`)

A new `_int4kv` variant of the FA decode kernel: reads int4
nibbles, dequantizes on the fly using per-block `(scale, xmin)`,
splices the protected channels back at the right positions, runs
the standard attention inner-product. Output is bit-comparable to
bf16 attention at the per-(layer, head) level.

### One-line user API

```python
import kv_policy.KVPro           # registers the backend
from kv_policy.KVPro import Int4ProtectedLLM
from vllm import SamplingParams

llm = Int4ProtectedLLM(model="Qwen/Qwen2.5-7B-Instruct")
out = llm.generate(["Tell me about..."],
                   SamplingParams(temperature=0.0, max_tokens=64))
```

That is the entire integration surface for an existing vLLM
deployment. No model code changes. No model retraining. No
quantization-aware fine-tuning. Pure post-hoc cache compression.

---

## Page 3 — Validated Portfolio

### Four models, three families, two scales — all measured GREEN

| Model | Family | Architecture | Calibration | Needle (Tier A 2-seed) | Replicated? |
|---|---|---|:-:|:-:|:-:|
| Qwen2.5-7B-Instruct | Qwen | 28L × H_kv=4 × D=128 | ✓ | 13/15 (seed=43) + 15/15 (seed=44) | **at-the-margin** |
| Mistral-7B-Instruct-v0.3 | Mistral | 32L × H_kv=8 × D=128 | ✓ | **15/15 + 15/15** | **yes** |
| Llama-3.1-8B-Instruct *(NousResearch ungated mirror)* | Llama | 32L × H_kv=8 × D=128 | ✓ | **15/15 + 15/15** | **yes** |
| Qwen2.5-14B-Instruct | Qwen | 48L × H_kv=8 × D=128 | ✓ | **15/15 + 15/15** | **yes** |

Three of four models hit **100% needle retrieval at 4%
protect_fraction**, matching stock bf16 vLLM exactly, with
2-of-2 independent-seed replication (Tier A). **Qwen-7B shows
seed-level variance at the longest L1200 bucket under 4%
protect_fraction** (typical 15/15; seed=43 dropped to 13/15, all
two misses at L1200; seed=44 recovered to 15/15). 6%/8%
protect_fraction is the obvious safety knob if a partner
requires a zero-margin guarantee on this specific model; the
calibration script supports it without code changes.

Zero kernel fallbacks across the measured cells — for example,
the Qwen-7B R7-latency run alone logged 9,240 packed decode
calls + 9,408 write-path calls with 0 fallbacks.

### What "needle 15/15" means

The needle-in-haystack benchmark plants a unique unmistakable code
("XAJ-I0Y-6DP") inside a filler-text context of varying length and
asks the model to recall it. 15 trials = 5 unique codes × 3
context-length buckets (~200, ~600, ~1200 filler tokens, needle
always in the middle).

| Length bucket | bf16 stock | KVPro |
|---|:-:|:-:|
| 200 filler tokens | 5/5 | 5/5 |
| 600 filler tokens | 5/5 | 5/5 |
| 1200 filler tokens | 5/5 | 5/5 |
| **Total** | **15/15 (100%)** | **15/15 (100%)** |

(Same matrix for all four models in the portfolio.)

This establishes that the calibrated 4% mask preserves the model's
ability to retrieve information from mid-context. Easy needle is a
necessary bar but **not a sufficient quality signal**: naive int4
also passes it. The stronger signal is **general generation
fidelity** (token-agreement) and **hard-needle retrieval**
(multi-needle, distractors, conflicting facts) — see Page 6.

### Memory, concurrency, and throughput (A100-80GB, gpu_util=0.5, post-fix)

The long-context bench (Qwen2.5-7B, mml ∈ {8K, 16K, 32K}) is the
authoritative capacity + throughput measurement. All numbers below
are from **clean post-correctness-fix runs** (Phase 6K.7/6K.9/6K.10
— see Page 6); pre-fix benchmarks measured on broken decode are
superseded.

| mml | bf16 HBM | int4 HBM | **Δ HBM** | bf16 max-conc | int4 max-conc | conc ratio |
|---|---|---|---|---|---|---|
| 8,192 | 39.1 GB | 43.8 GB | **+4.7 GB** | 55.3 | 110.6 | **2.00×** |
| 16,384 | 38.0 GB | 42.7 GB | **+4.7 GB** | 26.4 | 52.8 | **2.00×** |
| 32,768 | 35.9 GB | 40.5 GB | **+4.7 GB** | 12.0 | 23.9 | **1.99×** |

**What these numbers mean:**
- **Total HBM is +4.7 GB higher** for KVPro at equal
  `gpu_memory_utilization` (this long-context bench's total-HBM figure;
  Phase 6L's saturated run measured the delta at **+4.39 GB**, of which
  **4.38 GB is sidecars** — the bench's larger figure also includes the
  CUDA-graph private pools). This is the sidecar overhead (protection
  tensors for scale, xmin, and protected channels) — KVPro does
  **not** shrink the absolute HBM footprint; it costs more.
- **max_concurrency is 2×** because int4's 4-bit nibbles are 4× denser
  than bf16 *at the element level*, but the per-block scale/xmin sidecars
  + 4% bf16 protect channels consume ~half of that — so the same KV budget
  **nets ~2×** the full-context sequences (block_size=32 vs bf16's 16). This
  is the **concurrency density** win — 2× more sequences per fixed KV
  allocation; the raw 4× is the nibble ratio before the sidecar tax.
- **Net capacity density** (accounting for the sidecar overhead) —
  **now DEMONSTRATED under sustained saturation (Phase 6L)**: at
  mml=8K, B=128, both cells hit 100% KV-block utilization with
  preemption (genuine saturation); protected held **117 live seqs vs
  bf16 58** (2.02× raw), which net of the measured HBM tax is
  protected **2.498 seq/GB vs bf16 1.367 seq/GB = 1.83× per GB** of
  total HBM. This is the real high-load story: at saturation,
  KVPro serves ~1.83× more concurrent users per GPU than
  bf16, even after paying the 4.38 GB sidecar tax.

> ✅ **DEMONSTRATED (Phase 6L, mml=8K, B=128):** the 2× concurrency is
> no longer a block-budget estimate — under sustained `--resident-pressure`
> load both cells reached the KV block limit and protected sustained
> 1.83× live seqs/GB net of the sidecar tax. One caveat surfaced at the
> same operating point: **aggregate decode throughput collapses to 0.22×
> bf16 at saturation** (the unoptimized int4 decode path) — density-
> positive, throughput-negative; see the Throughput section + Page 6.

**Sidecar memory breakdown** (mml=8K, B=128, Phase 6L live-measured):

| Tensor | Role | Overhead |
|---|---|---|
| `k_protect_ext` | protected channels at bf16 | 1.015 GB |
| `v_scale_ext` / `v_xmin_ext` | V reconstruction | 0.812 GB each |
| `k_scale_ext` / `k_xmin_ext` | K reconstruction | 0.812 GB each |
| `_k_stage_pool` | decode staging (scales with B) | 0.117 GB |
| **measured sidecar tax (sum)** | — | **4.38 GB** |
| CUDA graph private pools *(non-PyTorch, separate)* | graph capture | ~0.62 GB |

No single tensor dominates; the overhead is structural (scales with the
KV block count). The +4.39 GB HBM delta vs bf16 at saturation is **~99.8%
sidecars** (CUDA-graph pools sit outside `max_memory_allocated`). NB: the
earlier 0.82 / 0.65 GB figures were the Phase 6G audit at **mml=32K in
binary GiB** — a different config, not the live 8K numbers above.

**Critically, the sidecar tax is FLAT with context length** — measured
constant at +4.4–4.7 GB across mml = 8K / 16K / 32K (the capacity table
above). All five reconstruction sidecars are indexed by the *KV block pool*
(`NB`, fixed at init by `gpu_memory_utilization`), not by any request's
length, so a longer context consumes more of the same pre-allocated pool
and allocates **zero** new sidecar. The density advantage therefore does
**not** decay as context grows. The two knobs that *do* move the tax are
`gpu_memory_utilization` (proportional) and `max_num_seqs` staging
(~24 MB/slot, ~6 GB at 256). Full scaling analysis: **Page 8 — Technical
Understanding §3.**

### Throughput (Qwen-7B, A100-80GB) — a WORKLOAD CURVE, not one number

KVPro's decode throughput is below bf16 at every operating point, but
**the size of the gap is workload-dependent — and that is the actionable finding.**
The int4 tax is dominated by a per-decode-step paged-gather; it amortizes over
**fewer steps at short generation**, so short-output workloads pay far less.

**Saturated operating curve (mml=8K, ~0.95×mml prompt, b-list 48–128, Phase 6M.6;
A100, reproduced on independent hardware):**

| Generation length | bf16 agg_tps | int4 agg_tps | **agg ratio** | per-user | density |
|---|---:|---:|---:|---:|---:|
| **gen=128 (short output)** | 211.3 | 113.4 | **0.54×** | 0.27× (~3.7× slower) | 1.81× |
| gen=512 | 576.3 | 184.4 | 0.32× | 0.16× (~6.3× slower) | 1.83× |
| gen=512, deep saturation (locked 6L) | 597.3 | 130.4 | **0.22×** | 0.11× (~9× slower) | 1.83× |

**The throughput tax ranges 0.13×–0.54× depending on workload** (floor 0.13×: B=1 eager 100K-ctx Llama, June 2026). The widely-quoted
"0.22× / ~9× slower" is the **worst case** (deep saturation + long generation), NOT
the typical case. **Density is invariant at ~1.81–1.83× across the entire curve** —
the compression win does not depend on the operating point.

**What this means commercially (honest segmentation):**
- **Short-output, high-concurrency workloads** — embeddings, classification,
  reranking/scoring, extraction, agentic tool-routing, eval/labeling, RAG retrieval
  — get the **full ~1.81× density at only ~2× aggregate slowdown (0.54×).** This is
  the **target segment**, and it is one of the fastest-growing parts of inference
  spend (agentic + RAG traffic is short-output, high-fan-out by nature).
- **Long-generation workloads** — interactive chat, long summarization — remain a
  **batch/offline density play** (0.22–0.32×).
- **Still NOT interactive-chat-viable** by the ≥0.70×/user bar anywhere. The honest
  thesis is "win the high-concurrency short-output segment on density economics,"
  not "replace bf16 everywhere."

**Deployment is a routing decision customers already make:** send short-output
fan-out traffic to KVPro (2× the users/GPU, quality-preserved), keep
long-form chat on bf16. The density savings beat the latency cost on $/request for
KV-bound short-output traffic. See `PHASE_6M_HEADROOM_NO_NCU.md` (deployment
guidance) for the routing rubric.

**Bounded recovery (not parity):** attribution (Phase 6M.4) localized the tax to
genuine int4 reconstruction (paged gather ~25% + decode attention ~21%; host syncs
<1%). A read-path kernel-fusion effort (6F) could lift the *worst-case* long-gen
point from ~0.22× toward a **bounded ~0.27–0.30× ceiling — never bf16 parity**
(int4 fundamentally reads packed KV + sidecars and dequants per token). That work
is gated on a roofline measurement (Test 1, currently blocked on counter-locked
pods) and is **lower priority than just deploying at short generation**, where the
tax is already smallest for free.

### Bit-identical and prefix-overlap detail (Qwen-7B, 6 prompts, max_model_len=4096)

| Backend | Bit-identical | Non-identical prompts share |
|---|---|---|
| **KVPro** | **3 of 6 IDENTICAL** | the other 3 share 33%, 76%, and 82% prefix with bf16 |
| **fp8** | **0 of 6 IDENTICAL** | diverges within 6–16 chars on every prompt (5.9–16.2% prefix overlap) |

---

## Page 4 — Competitive Landscape

### Where KVPro sits in the KV-compression space

| Approach | Memory | Quality | Notes |
|---|---:|---|---|
| **bf16** (vLLM default) | 1.0× | perfect | the reference |
| **fp8** (vLLM-supported) | 0.5× KV | poor-to-mixed, model-dependent — Qwen-7B needle 1/15; Llama-3.1-8B (June 2026): lite needles pass, greedy still diverges (e5m2 1/6 / 41%; e4m3+scales 2/6 / 84%), and both decode SLOWER than bf16 on vLLM 0.7.3 (0.76× / 0.33×) | half-precision; ships, accepted as a quality compromise |
| **AWQ / GPTQ** (weight-only quantization) | weights only, not KV | high | does NOT compress KV-cache; orthogonal solution |
| **naive int4 (KIVI-style)** | 0.5× KV | degraded — token-agreement vs bf16: 0.533 (53%); easy needle deceptively OK but general fidelity substantially reduced | research-grade; our measurements confirm fidelity degradation |
| **TurboQuant W4A4** (Google) | weights + activations | <1% MMLU loss on Llama-2 *(competitor's reported figure)* | W4A4 not KV; complementary, not competitive |
| **KVarN k4v2** (Huawei, vLLM-0.22) | 2.67× KV (−9.5 GB tail pool); Llama-family only | easy free-gen 0.982 vs bf16; **hard-needle COLLAPSE: 0.25 (8K) → 0.06 (32K), K-bound**; crashes on Qwen2.5-7B (GQA-7) | only competitor run **head-to-head on our hardware** — wins easy metric + throughput, loses the hard tail |
| **SAW-INT4 (BDR)** (Together, 2026) | ~3.56× KV (token-wise int4 + parameter-free Hadamard rotation → ~0 metadata) | near-lossless on **Qwen3** (their eval) BUT **MEASURED 0% needle AND 0% hard-needle on Qwen2.5-7B-Instruct** (our A100; BF16=100% on identical prompts; rotation confirmed active) — **model-transfer fragility, n=1** | SGLang-native; head-to-head June 2026 — densest competitor on paper, collapses on a mainstream model KVPro handles. `docs/SAW_INT4_QWEN_HEADTOHEAD_RESULTS.md` |
| **CacheGen** (LMCache; warm-tier offload codec) | per-layer bins-quant (~4–5 bit) + arithmetic coding; denser, no sidecar | **MEASURED codec fidelity** (real Qwen2.5-7B KV): better *average* fidelity than KVPro, but **0.0145 error on top-attention K channels vs KVPro's 0.0000**; lossy (no lossless reuse) | the real warm-tier incumbent; KVPro edge = top-channel fidelity + lossless reuse; **end-to-end needle at iso-bytes still open**. `docs/KVPRO_VS_CACHEGEN_VERDICT.md` |
| **KVPro** *(this work)* | **0.5× KV + ~4.4 GB sidecar overhead (4.38 GB live)** | **token-agreement 0.737 (+20.4 pt over naive); easy needle ≈ bf16; hard-needle retrieval 0.964 vs naive 0.915; 4-model portfolio 15/15 needle 2-of-2 seed; warm-tier snapshot/restore byte-faithful (Phase-0)** | **best fidelity at 4-bit KV density; sidecar cost is the trade-off** |

### The relevant comparison

There are two distinct comparisons:

**KVPro vs naive int4** (the quality story):
- Same 4-bit KV density. Same total HBM footprint (roughly).
- KVPro wins on every quality metric: +20.4 pt
  token-agreement, +0.049 hard-needle retrieval, K-bound misses
  eliminated. Protect is near-free *over naive*, so there is no
  reason to ship naive int4 over protected.

**KVPro vs bf16** (the capacity story):
- int4 packs 2× the sequences in the same KV block budget (Phase 6L:
  117 vs 58 live at saturation = 2.02× raw).
- int4 costs **4.38 GB** sidecar tax (Phase 6L live-measured; ~+4.4 GB HBM).
- **Net (DEMONSTRATED, Phase 6L)**: **1.83× concurrent max-len seqs per
  GB** — density-positive but not footprint-positive, and
  **throughput-negative at saturation (0.22× bf16 agg tok/s)**. For
  workloads that hit the KV block limit (many concurrent long-context
  users) and are throughput-insensitive, int4 serves ~1.83× more users
  per GPU at near-bf16 quality. For workloads with slack KV headroom or
  latency sensitivity, bf16 is simpler and faster per-seq.

**KVPro vs KVarN** (the head-to-head we actually ran — same model, same needles):
- KVarN (Huawei, vLLM-0.22 fork; Hadamard + iterative variance-normalization; 4-bit K / 2-bit V;
  **no protect**) is the strongest external KV method we tested: near-lossless easy free-gen
  (0.982 token-agreement vs bf16), 2.67× density, throughput ≥ bf16 on a modern (V1) engine.
- Run head-to-head on **identical** Llama-3.1-8B hard needles (same builder / classifier / seed
  as our own validation), KVPro matches **full precision** exactly where KVarN
  **collapses K-bound**:

  | hard-needle retrieval | bf16 | KVPro | KVarN |
  |---|---:|---:|---:|
  | 8K | 0.955 | **0.955** | 0.250 |
  | 32K | 1.000 | **1.000** | 0.062 |

- The failure is precisely what protect defends: KVarN drops the protected channels, so its 4-bit
  K loses long-range retrieval (`MISS_K`-heavy, **worsening with context length**). KVPro
  was confirmed genuinely active (2.0× token capacity, `kv_cache_dtype=int4_protected` — not a
  bf16 fallback). **A credible competitor — near-lossless on the easy metrics — was beaten on the
  regime the product targets (selective long-context retrieval), while KVPro held
  full-precision quality at 2× density.**
- **Fair to KVarN (the honest moat boundary):** KVarN wins density (2.67× vs 2.0×), throughput
  (≥bf16 vs 0.3–0.5×), and easy/short-context quality, on a newer engine. For short-context or
  throughput-bound serving it is the better choice. KVPro's defensible moat is the
  **hard tail** (long-context selective retrieval) **and Qwen2.5-7B / GQA-7 models where KVarN
  crashes** — not throughput. (Full data: `CTM_plus/Bench/scripts/KVARN_EVAL_FINDINGS.md`.)

**KVPro vs fp8** (the quality-at-density story):
- Both deliver ~2× KV concurrency density vs bf16.
- fp8 costs less total HBM (no sidecars); KVPro costs ~4.4 GB
  more than bf16 (Phase 6L: 4.38 GB sidecars) while fp8 costs less.
- KVPro wins decisively on quality: 0.737 token-agreement
  vs fp8's degraded output (0/6 bit-identical, 12% prefix overlap,
  1/15 needle). For quality-sensitive workloads, fp8 is not a viable
  alternative.

### Why the gap isn't closed by faster fp8 kernels or AWQ

| Alternative | Why it doesn't substitute |
|---|---|
| Faster fp8 kernels | fp8's quality limit isn't a kernel issue — it's a representation issue. 8 bits per element cannot preserve the per-channel dynamic range of K at the precision that long-context attention requires. |
| AWQ + AWQ-Marlin | These quantize *weights*, not KV-cache — orthogonal budgets, **complementary** to KVPro. **Composition status (Phase 6O, measured + fixed):** the stack initially crashed on a dtype mismatch (AWQ fp16 activations vs int4 bf16-dequant K); a one-commit dtype bridge (e06dd26) fixed it, and **byte-equivalence on the bf16 path stayed GREEN (15/15)** — the fix is non-invasive. **AWQ weights + KVPro KV now load and run together with quality preserved — MMLU 56% (stacked) vs 55% (each alone), within noise.** The *integration and quality* compose, validated. **Memory composition also MEASURED (live introspection, Phase 6O): AWQ shrinks weights 14.25 → 5.57 GB (2.6×, −8.7 GB), and the saving is IDENTICAL with bf16 KV and int4 KV (5.571 = 5.571) — proving the two are orthogonal and additive.** So KVPro compresses the KV-cache (its moat, which AWQ/GPTQ cannot touch) AND stacks with AWQ weight-quant: both memory budgets shrink together, quality preserved. |
| Speculative decoding | Reduces decode FLOPs, doesn't reduce KV memory. Orthogonal to KV compression. |
| Paged attention (vLLM) | Already deployed everywhere. Paged attention manages KV memory; it doesn't compress KV. KVPro uses vLLM's paged cache as its substrate. |

### Why the methodology generalizes

Three independent observations from this quarter's work:

1. **Cross-family transfer**: the same calibration script + 4%
   protect_fraction works on Qwen, Mistral, and Llama families
   with no per-family tuning. This is unusual — quantization
   methods typically need per-architecture tuning.
2. **Cross-scale transfer**: validated at 7B + 8B + 14B. Larger
   models actually exhibit *more* per-layer channel specialization
   (Qwen-7B Layer-0 vs Layer-1 channel-overlap: 11.1%; Qwen-14B:
   2.6% — computed by `calibrate_phase5b_protect_mask.py` at
   calibration time, single calibration run per model) —
   consistent with deeper feature specialization at scale.
3. **Static masks are sufficient**: the protected channels are
   frozen per model at calibration time. No per-step or per-prompt
   adaptation needed. This is what makes the runtime cheap.

Any D=128 architecture with GQA or MHA should work (Llama family,
Mistral family, Qwen family, etc.). Models with different head dims
(D=64, D=96 — Phi, some smaller models) need a one-time kernel
recompile, not a methodology change.

---

## Page 5 — Roadmap

### What's locked

- **Quality**: 4 models, 3 families, 2 scales, all 15/15 needle
  replicated 2-of-2 seeds on Mistral / Llama-3.1-8B / Qwen-14B;
  token-agreement +20.4 pt over naive (0.737 vs 0.533, post-fix).
  **Academic benchmarks (Qwen-7B, Phase 6N/6N.2): KVPro = bf16 with
  0.0 pt delta AND 100% per-question agreement on THREE benchmarks —
  MMLU (63.5%=63.5% @200Q; 73.9%=73.9% @1,000Q), ARC-Challenge (91.5%=91.5%),
  TruthfulQA (71.5%=71.5%).** Across all of them int4 chose the IDENTICAL answer
  on every question (net_flips=0) — no measurable accuracy loss AND no hidden
  compensating flips. (Recalibrated mask; hard-needle 4/4, COLLAPSE=0.)
- **Correctness**: all three decode bugs fixed (Phase 6K.7/6K.9/6K.10)
  — eager and **non-APC** graph modes verified correct. Int4 decode
  confirmed `COLLAPSE=0` across every cell × mml post-fix. (graphs+APC
  is a separate, kernel-level open item — Page 6.)
- **Methodology**: calibration script + backend impl + kernel
  fork. Model-agnostic.
- **Integration**: one-line `Int4ProtectedLLM(model="...")`. No
  retraining, no quantization-aware fine-tuning.
- **vLLM compatibility**: works with vLLM 0.7.3 V0 paged attention
  + multi-batch decode.
- **Slot lifecycle** (Phase 6K.14): auto-bump + evict-on-completion
  wired — slot pool scales to `max_num_seqs` automatically; slots
  freed on sequence completion. Validated B=128 with zero
  slot-exhaustion on GPU.
- **Prefix caching (APC), eager-only** (Phase 6K.16): shipped +
  validated bit-exact (S1 byte-gate 13/13 cached blocks byte-identical
  to a fresh prefill; hard-needle with APC 0.955 = bf16; zero degenerate
  outputs). The first throughput-tax reducer — measured (Llama-3.1-8B,
  A100-80G, June 2026): **TTFT −53/56/78/86% per cache hit** at
  1K/2K/4K/8K shared prefixes, **1.85× batch throughput** at 94% hit
  rate (1.54× at 75%), quality 1.00 == APC-off in every cell — net of
  the eager tax. graphs+APC gated off (int4 kernel not
  graph-safe at B>1 — see Page 6).

### What v2 unlocks (in priority order)

**Tier 1 — production blockers**

| Item | Status | Impact |
|---|---|---|
| **Capacity demonstration** (sustained high-B saturation) | ✅ DONE (Phase 6L: `--resident-pressure`, mml=8K B=128, both cells 100% KV-block util) | Validated the density claim under real load: **1.83× seq/GB** net of tax (2.02× raw live). Caveat: aggregate throughput **0.22× bf16** at saturation (unoptimized decode path) |
| **Decode-throughput recovery** (the 0.22× closer) | **Attributed (Phase 6M.4): GPU-work-bound at saturation** — decode-attention kernel ~29% + paged gather/copy ~19.5%; host syncs <1%. **CUDA graphs ruled OUT** (6M.3: neutral at saturation, eager ≈ captured). Next gate = **Test 1 roofline (6M.5)** to split compute- vs bandwidth-bound. **⚠ Test 1 BLOCKED on RunPod A100 (`ERR_NVGPUCTRPERM`, perf counters locked) — needs a profiling-enabled experiment server; tooling is committed and ready.** | Bounds the recoverable headroom. Honest ceiling: **~0.22× → ~0.27–0.30×, NOT bf16 parity** (int4 fundamentally reads packed KV + sidecars and dequants/token). Kernel fusion (6F): **headroom now measured directly** (June 2026, CUDA-event GPU split at B=1 — no perf counters needed): fuseable pre-kernel gather+splice+prep = **60% of the int4 read path at 8K ctx, 42% at 32K** → **GO**, realized < headroom (in-register gather remains). Test 1 roofline still wanted for the saturation regime; the funding decision now has a measured upside bound |
| **Tensor parallelism** (TP) for 70B-class models | Not yet validated | Unlocks 70B Llama / Qwen-72B where memory savings move the dollar economics |
| **Broader quality bench** (MMLU, HumanEval, LongBench) beyond needle | **MMLU DONE (Phase 6N.2): 0.0 pt + 100% per-question agreement at 1,000 Q.** HumanEval/LongBench tooling committed (generate-only; sandbox to score pass@1) | De-risks customer adoption — MMLU closed at scale with fidelity diagnostic; remaining benches are runner-ready |

**Tier 2 — reach + maintainability**

| Item | Effort | Impact |
|---|---|---|
| Kernel support for D=64 / D=96 head dims | 1-2 days per | Unlocks Phi family + smaller models |
| Port to vLLM V1 engine | 1-2 weeks | Forward-compat; V0 is being deprecated |
| Long-context hard needle (>8K, more items) | 1-2 days | Confirm Phase 6K.12 hard-needle advantage at 16K/32K with more items |
| Sidecar diet (fp8 sidecars, option C) | ~3 days kernel work | Reduces sidecar overhead by ~1.7 GB (partial toward HBM parity) |
| Pre-calibrated mask zoo | 1 day | Ship 10-20 popular models pre-calibrated; remove user-side calibration step |
| Cold-tier (per-session safetensors snapshot/restore) | 4-6 weeks | Optional 3-tier KV storage (hot GPU / warm CPU swap / cold disk). Warm-tier foundation verified bit-clean (TIER5A measured GREEN — see Page 6). |
| **Read-skip vs bf16 long-context crossover — ANSWERED (June 2026): NO** | done | Measured on 128K-native Llama-3.1-8B, no YaRN (B=1, gen=128, eager, 32–100K): int4+read-skip = **0.21–0.24× bf16, flat** (16.1→10.3 tok/s vs bf16 66.2→49.3); quant-alone slopes 0.23→0.13×; read-skip claws back +8%→+65% at skip 77→93%, quality 1.00/1.00/1.00 in every cell **including 100K at 93.3% skip**. **No bf16 crossover ≤100K** — the parity thesis is unsupported at these lengths; the headline stays density + quality + APC, with read-skip as the long-context decode-tax mitigator (vs full-int4), not a bf16-beater. `phase10_crossover_sweep.py`, /tmp/x10. |

**Tier 3 — research extensions**

| Item | Notes |
|---|---|
| Dynamic per-step protect masks | Adaptive quality at the same memory budget. Research-grade. |
| Pre-RoPE quantization | Better distributional properties; may need fewer protected channels. |
| FP4 / NVFP4 storage on Hopper / Blackwell | Newer hardware opportunity. |
| ROCm port (AMD) | Open hardware story. Kernel fork is currently CUDA-only. |

### Realistic v2 timeline

A focused 6-8 week effort can land Tier 1 cleanly:
- Weeks 1-2: Decode-throughput recovery — Test 1 roofline (6M.5) on a profiling-enabled pod, then gated read-path kernel fusion (6F) toward the ~0.27–0.30× ceiling (NOT graph capture — Phase 6M.3 ruled it neutral at saturation)
- Weeks 2-3: Tensor parallelism (multi-rank pool sharding; smoke verify on 2-rank pod)
- Weeks 3-4: Quality bench suite (lm-eval-harness integration; run all 4 models)
- Weeks 5-6: Hard-needle at 16K/32K + sidecar diet option C
- Weeks 6-8: Broader hardening + pre-calibrated mask zoo + buffer for findings

End state: KVPro shipping on 4+ model families with
demonstrated sustained capacity, a comprehensive quality bar (not
just needle), and a production deployment story.

---

## Page 6 — Honest Validation Status

We separate **measured** from **projected** in our pitch. Partners
should be able to tell which is which.

### Critical correctness work completed this quarter

Three independent decode bugs were found and fixed after the initial
Phase 5 ship. All prior quality and throughput benchmarks on
KVPro were measured on broken code; the corrected results
below supersede them.

| Bug | Symptom | Fix |
|---|---|---|
| **6K.7 dispatch** (`flash_api.cpp`): int4 decode fell into the non-split branch (no int4 loaders) | All-zero attention output on every layer/step | Excluded int4 modes from non-split branch so they always reach the wired split-KV kernel |
| **6K.9 eager stale-state** (`phase5b_backend_install.py`): `evict_sequence()` never called on sequence completion | Recycled `seq_id` reused stale `SeqState`; `seq_pos` accumulated → `pérdida` collapse | Wire `evict_sequence(seq_id)` at the prefill boundary; calibrated A/B: `A_collapse=0.0` fix-on vs `0.4` fix-off |
| **6K.10 graph precapture hook** (`int4_protected.py`): public `Int4ProtectedLLM` factory never installed the Phase 6B.2 precapture hook | First-request CUDA-graph collapse; device pools never synced | Auto-install the precapture hook in the factory for graph mode |

**Post-fix confirmation**: `phase6k9` matrix — all `A_rate=0.0` across
`{protected, naive} × {FUSED 0,1} × {eager, graph}`. Int4 decode
is correct in both modes. `phase6k11` reports `COLLAPSE=0` across
every cell × mml.

### Measured on real GPUs this quarter (Qwen / Mistral / Llama on H100 / A100)

| Claim | Evidence |
|---|---|
| 3 of 4 models hit 15/15 needle retrieval == stock bf16 with 2-of-2 seed replication at 4% protect_fraction (Mistral-7B, Llama-3.1-8B, Qwen-14B) | Tier A replication: `Bench/scripts/verify_phase5b_5_needle.py` × 2 seeds (43, 44) per model |
| Qwen-7B at-the-margin under 4% protect_fraction: 15/15 at seed=44, 13/15 at seed=43 (both misses at L1200); 6%/8% recalibration is the safety knob | Tier A replication; `Bench/bench_out/VC_BRIEF_TIER_A/` |
| fp8 needle on Qwen-7B: 1/15 (6.7%) — direct measurement | Tier A R1: `Bench/scripts/verify_phase5b_5_needle_fp8.py` |
| **Token-agreement vs bf16 (post-fix, Qwen-7B, 8K-32K mml):** naive int4 = 0.533, protected int4 = **0.737 (+20.4 pt)** | `phase6j_quality_comparison.py` on clean post-fix data (6K.7/6K.9/6K.10); 295/553 naive vs 420/570 protected |
| **Easy needle saturated (post-fix):** naive int4 ≈ bf16 (0.96–1.00 at 8K–32K mml) — this gate no longer discriminates protect | `phase6k11_needle_failuremode.py`; COLLAPSE=0 confirmed |
| **Hard-needle retrieval (post-fix, mml=8192, 60 items):** bf16 1.000, protected **0.964**, naive 0.915 (+0.049); genuine misses 5→2 (K-bound miss eliminated by protect, V-bound halved) | `phase6k12_hard_needle.py`; adjudicated FORMAT items; `retrieved_or_present` metric |
| **Memory (A100-80GB, gpu_util=0.5):** KVPro uses ~+4.4 GB HBM vs bf16; Phase 6L live-measured the sidecar tax at **4.38 GB** (mml=8K, B=128) = ~99.8% of the +4.39 GB delta | `bench_phase6_long_context_gpu.py`; Phase 6L `report.json`; `MEMORY_STORY.md` Table 1 |
| **vLLM max_concurrency 2× bf16** at all tested mml; **DEMONSTRATED under load (Phase 6L):** 117 vs 58 live at saturation = 2.02× raw | Long-context bench + Phase 6L `--resident-pressure` |
| **Concurrency density (DEMONSTRATED, Phase 6L):** protected **2.498 seq/GB** vs bf16 **1.367 seq/GB** = **1.83× net** of the 4.38 GB sidecar tax | Phase 6L live: peak_live / hbm_gb at saturation; `PHASE_6L_CAPACITY_DEMO_RESULT.md` |
| **Throughput (post-fix), mml=8K B=8 short-gen:** int4 0.56× bf16 agg_tps; mml=16K 0.65×; mml=32K 0.67× | `bench_phase6_long_context_gpu.py` post-fix; `MEMORY_STORY.md` Table 2 |
| **Throughput at saturation (DEMONSTRATED, Phase 6L):** int4 **0.22× bf16** agg tok/s (130.4 vs 597.3) at mml=8K B=128 gen=512 — ~9× slower per user; unoptimized decode path | Phase 6L `report.json`; `PHASE_6L_CAPACITY_DEMO_RESULT.md` §3 |
| **Slot lifecycle fix (6K.14):** auto-bump to `max_num_seqs` + evict-on-completion; protected ran B=48–128 with `slots=B`, zero slot-exhaustion / OOM / preempt | GPU Run 1; `PHASE_6K14_SLOT_LIFECYCLE_FINDINGS.md` |
| 2.01× total-slot ratio at same memory budget (Qwen-7B, gpu_util=0.5, max_model_len=4096): bf16 27,934 / KVPro 28,060 cuda blocks at block_size=16 and block_size=32 respectively | Tier A `bench_phase5c_v1.py` three-way bench; `PHASE5C_USAGE.md` |
| 219× max concurrency vs stock 109× (Qwen-7B at max_model_len=4096) | Tier A three-way bench; vLLM engine-init log |
| 0 fallbacks across packed decode + write paths on Qwen-7B Tier A R7-latency run (9,240 decode + 9,408 write = 18,648 calls) | `Int4ProtectedAttentionImpl.get_call_stats()` snapshot |
| 3/6 diverse prompts produce bit-identical greedy output vs stock; remaining 3 share 33% / 76% / 82% prefix; fp8 diverges within 6-16 chars on every prompt | `bench_phase5c_v1.py` (Qwen-7B, max_model_len=4096, Tier A) |
| Multi-batch determinism (run1 == run2 byte-identical at B=2..8) | `verify_phase5b_6_batch.py` ALL 7 gates GREEN |
| Warm-tier swap-restore is byte-clean for KVPro on vLLM 0.7.3 (Qwen-7B + A100 + `preemption_mode='swap'`): under matched concurrent pressure, swap-mode and recompute-mode baselines produced bit-identical 64-token output. All six TIER5A acceptance gates GREEN. | TIER5A bench: `Bench/scripts/PHASE_TIER5A_SWAP_RESTORE_FINDINGS.md` |
| Read-path preflight for CUDA Graphs (B-pre-1..4) COMPLETE; graph mode verified correct end-to-end (6K.10) | `Bench/scripts/OPTION_B_PREFLIGHT.md`; `PHASE_6K7_INT4_DISPATCH_FIX_FINDINGS.md` |
| CPU regression: slot lifecycle (5/5 PASS, including wave-leak repro + fix) | `Bench/tests/test_phase6k14_slot_gc.py` |
| **Read-skip (Phase 10, Qwen-7B, A100):** at 32K context **94% of per-token KV positions skipped** with **needle 1.0/1.0** (depths 0.1/0.5); the retained-index path is GPU-gated **output-identical to full-read** (`gather == compacted == full`). Decode **−10.6% vs full-int4 at 32K** (weight-bound regime; recovered from ~−30% via on-GPU tensor index + block-id cache + tuned observe cadence). A/B gap **halves 16K→32K** (5.05→2.67 tok/s), extrapolating to a ~50K crossover | `phase9_p3_fused_needle.py --ab` (sweep 8K/16K/32K); `test_gather_decode_gpu.py`; `Bench/scripts/PHASE10_FINAL_VERDICT.md` |

### Tested-and-found (the negative results — partner-shareable)

| Item | Result |
|---|---|
| **KVPro total HBM vs bf16** | CAPACITY-NEGATIVE at equal `gpu_memory_utilization`: ~+4.4 GB more (Phase 6L live-measured 4.38 GB sidecar tax). The net capacity density is **1.83× seq/GB (DEMONSTRATED, Phase 6L)**, which requires running **at the KV block limit** to realize (not a savings at low B). |
| **Decode throughput** | Per-seq ~1.5–1.9× slower than bf16 at low load; **at saturation Phase 6L measured 0.22× bf16 aggregate tok/s (~9× slower per user)** on the unoptimized int4 decode path. Density-positive, throughput-negative at saturation — fine for batch/offline, needs decode-kernel optimization for interactive serving. |
| **Sidecar diet ceiling** | A+F+C stack (fp8 sidecars + fewer protect channels + coarser V groups) saves ~2.5 GB realistically — leaving int4 still ~2.5 GB above bf16. Diet alone likely can't reach HBM parity; option D (inline protect into KV layout) is an additional lever. |
| **Deleting the tax via rotation (KurTail / SpinQuant-style)** | The ~3.4 GB per-channel-scale + protect tax is **structural, not removable by rotation** — measured on **2 models**. A learned (kurtosis-optimized) rotation that should let *per-tensor* int4 replace per-channel scales **FAILS the hard-tail free-gen gate on both**: learned-rotation+per-tensor agreement vs bf16 = **Qwen 0.040 / Llama 0.385**, below per-channel+protect (**0.266 / 0.510**) and below even **naive per-channel int4** (0.236 / 0.471) — i.e. rotating to drop the scales makes K *worse* than keeping them. Llama is the more rotatable model and still loses. Negative across **6 independent lines** (light KV-QAT FT, Hadamard & learned rotation, scale-drop 7.1×, head-wise allocation, TurboQuant package `sym4`=0.037 with `sym8`=0.70 proving a genuine low-bit-K wall, and KVLinC's published design keeping per-channel K). **Conclusion: per-channel + protect is *necessary*, not a tunable — the tax is the price of K quality, and the hybrid scheduler (never worse than bf16) is the operational answer.** |
| **Pure int4 KIVI on K + V** | Token-agreement vs bf16 = 0.533 (53%); hard-needle misses = 5 (4 V-bound + 1 K-bound) vs bf16's 0. The K channel is the dominant failure; protected-K eliminates K-bound misses. |
| **Higher protect_fractions (6%, 8%, 16%)** | 4% holds for Mistral-7B / Llama-3.1-8B / Qwen-14B (2-of-2 seeds). Qwen-7B shows seed-level variance at L1200 under 4%; 6%/8% is the documented safety knob. |
| **`enforce_eager=False` graph capture (pre-fix)** | Crashed pre-Phase 6K.10. Post-fix: non-APC graph mode correct (A_rate=0.0 all cells; no COLLAPSE in 6K.10/6M graph runs). Write-path capture (for full CUDA-graph throughput benefit) is the remaining engineering item. *Flagged (6K.16):* the B>1 kernel finding below shares this kernel — non-APC graphs at B>1 is a revalidation item (prior runs showed no COLLAPSE, so likely an APC-read-path trigger, but unconfirmed against this specific ~1.8× failure mode). |
| **graphs + APC (CUDA graphs + prefix caching) at B>1** | Corrupts under graph capture — **root-caused to the int4 FA kernel, not graph-safe at B>1** (Phase 6K.16). A per-row mirror proved the kernel's **K/V inputs are bit-identical eager-vs-graphs (k_int4 byte-exact, v ~0.03%) yet the attention output is ~1.8× inflated**, constant across rows → degenerate tokens on near-tie prompts (needle MISS at B=6; B=1 is byte-exact). This **cleared the entire Python state machine** — identity, GC, masking, protect (ablated), partial-tail splice, dequant inputs all measured equal across eager/graphs. APC ships **eager-only**; graphs+APC gated off. Low-ROI to fix (int4 is kernel-bound, graphs neutral at saturation — 6M.3) and needs the FA-fork source. Full input-vs-output proof + the eliminated-hypothesis chain: `PHASE6K16_APC_CONTRACT.md` ("ROOT FOUND"). |
| **Read-skip decode below ~32K** | Throughput-NEGATIVE: −17.6% (8K), −17.7% (16K), −10.6% (32K) vs full-int4. Below ~32K decode is weight-bound and full-int4 KV reads are already cheap/coalesced, so skipping 94% of a *scattered* gather doesn't beat the *contiguous* full read. Attribution: the residual is the **gather/compaction copy**, NOT the controller (the per-step GPU→CPU sync was already removed on-GPU in Phase 10). The win is gated to long context (≳50K, extrapolated) — not a sub-32K speed play. |

### Honest cost / risk

| Item | Status |
|---|---|
| **Decode throughput negative — WORKLOAD-DEPENDENT, range 0.13×–0.54×** | Real cost, but a curve not a number (Phase 6M.6, reproduced on fresh A100): **0.54× at short gen (gen=128), 0.32× at gen=512, 0.22× worst-case (deep sat + long gen)**; **quant-alone declines with context at B=1 eager: 0.23×@32K → 0.17×@60K → 0.13×@100K (Llama, June 2026); read-skip holds ~0.21× at 80–100K** — density invariant ~1.83× throughout. The "0.22× / 9× slower" is the worst case; short-output workloads pay only ~2×. Attribution (6M.4): GPU-work-bound (paged gather ~25% + attention ~21%, host syncs <1%) → recoverable headroom **bounded ~0.27–0.30×, not parity**; the closing lever (read-path fusion, 6F) now has a **measured GO at B=1** (gather-headroom profile, June 2026: fuseable 60% of the read path @8K ctx / 42% @32K; the gather is GPU-time-bound, cpu/gpu 0.2–0.7×, so CUDA fusion — not Python vectorization — is the fix). Realized < headroom; ceiling unchanged ~0.27–0.30×; still **lower priority than deploying at short generation.** |
| **~+4.4 GB total HBM vs bf16 (4.38 GB sidecars)** | Structural (sidecar overhead); diet options can reduce by ~2.5 GB but cannot reach HBM parity without option D or a different KV layout |
| **Capacity now DEMONSTRATED (Phase 6L) — residual: single-mml** | Was a block-budget estimate; Phase 6L confirmed it under sustained `--resident-pressure` load at mml=8K B=128 (1.83× seq/GB net, 2.02× raw live). Residual: only mml=8K tested; 16K/32K robustness pending |
| **Tensor parallelism not validated** | Code expected to generalize; unverified — requires multi-GPU pod (Tier 1 v2) |
| **Swap-to-CPU preemption unsupported — now GUARDED (Phase 6K.15)** | The quantization sidecars (scales/xmin/protect/staging) live outside vLLM's paged KV tensor and are **not migrated** by `swap_out/swap_in`; a swapped sequence would resume with silently corrupted KV. vLLM V0's *default* policy picks SWAP for multi-seq groups (parallel sampling / beam), so this was a correctness landmine behind a config default. Fixed: the factory now forces `preemption_mode="recompute"` and refuses `"swap"` at init (loud error; `INT4_PROTECTED_ALLOW_SWAP=1` dev escape hatch). Residual: recompute + parallel sampling under preemption pressure hits vLLM's single-seq recompute assert — a loud failure, not corruption. True sidecar migration = future work, only needed if swap-preemption serving is a requirement. |
| **Slot-pool staging memory scales with `max_num_seqs`** | Multi-batch decode is implemented + proven (slot pool, Phase 6K.14 auto-bump/GC; measured at B=128 / 117 live seqs in Phase 6L), but each slot carries ~24 MB staging state — `max_num_seqs=256` adds ~6 GB on top of the sidecar tax — which scales with the KV pool (~16–17%): 4.38 GB at a mid-size pool, **8.3 GiB measured at a max-util 48.8 GiB pool** (June 2026). The auto-bump makes this implicit; deployments should pin `PHASE6_MAX_ACTIVE_SLOTS` to actual concurrency. **Prefix caching (APC) now SHIPS eager-only** (Phase 6K.16) — validated bit-exact: S1 byte-gate **13/13 cached prefix blocks byte-identical** to a fresh no-APC prefill (packed K + packed V + all five sidecars), hard-needle with APC **0.955 = bf16**, zero degenerate outputs. The storage layer was APC-compatible *by construction* (block-local quant groups = block size; sidecars keyed by block_id travel with shared blocks), so the eager ship was the Tier-1 (days) item it was scoped as. This is **the first lever that reduces the throughput tax — now measured** (Llama-3.1-8B, A100-80G, June 2026): TTFT −53→−86% per cache hit as shared prefixes grow 1K→8K, batch throughput 1.19–1.85× at 94% hit rate (1.28–1.54× at 75%), quality 1.00 == APC-off in every cell, net of the eager tax; density compounds it (2× blocks ⇒ ~2× cacheable prefix), so high-fan-out shared-prefix workloads (agentic / RAG — the target segment) pay the int4 tax on fewer tokens. **graphs+APC is gated off** (factory forces `enforce_eager=True` under APC): root-caused this quarter to the **int4 FA kernel not being CUDA-graph-safe at B>1** (see the negative-results table) — low-ROI to chase since int4 is kernel-bound (graphs neutral at saturation, 6M.3). Chunked prefill remains off. |
| **vLLM 0.7.3 V0 fork vendored at SHA `720c948`** | Upstream vLLM has moved to V1; forward-port is 1-2 weeks of maintenance (Tier 2 v2) |
| **Only D=128 head dim supported** | Kernel constraint; Phi-3.5 (D=96) and similar need a kernel recompile (Tier 2 v2) |
| **Quality bench: needle + token-agreement + hard-needle + MMLU (1K)** | **MMLU 0.0 pt + 100% per-question agreement at 1,000 Q (Phase 6N.2)** — the agreement diagnostic rules out compensating flips that aggregate parity could hide. Residual: 100% agreement on 4-way MC proves argmax unchanged, not bitwise-identical logits; HumanEval pass@1 (sandboxed) + LongBench F1 are runner-ready but not yet executed |

### Projected (not yet measured)

| Item | Confidence |
|---|---|
| ~~Write-path CUDA graph capture unlocks 2× aggregate throughput~~ **WITHDRAWN (Phase 6M.3)** | **Overturned.** At saturation, eager ≈ captured (125.5 ≈ 130.4 tok/s) — graphs are **neutral**, not a 2× lever; launch overhead is NOT the saturation bottleneck (6M.4: GPU-work-bound). The real (bounded) lever is read-path kernel fusion, gated on Test 1 |
| Decode-throughput recovery to ~0.27–0.30× (read-path fusion, 6F) | Medium, and **bounded** — Phase 6M.4 localized the tax to genuine int4 reconstruction (decode-attention + paged gather); fusion can trim the gather pass (~19.5% at saturation, 6M.4; **measured 42–60% of the B=1 read path** incl. splice/prep, June 2026 → GO) but int4 cannot reach bf16 parity. Test 1 roofline (saturation regime) remains blocked on counter-locked pods; the B=1 headroom is CUDA-event-measured and needs no counters |
| ~2× net capacity under sustained high-concurrency load | ✅ **CONFIRMED (Phase 6L)** — the block-budget estimate (~1.8× seq/GB) was confirmed by direct `--resident-pressure` observation: 1.83× net seq/GB, 2.02× raw live at saturation |
| TP enables 70B-class serving | Medium — code structure looks TP-compatible; risk is in vLLM-side plumbing |
| Sidecar diet option C (~1.7 GB savings) + option F preserves token-agreement gain | Medium — no quality re-bench yet after diet |
| Methodology extends to Phi (D=96) | Medium — calibration math is architecture-agnostic; kernel constraint is the only barrier |
| Methodology extends to mixture-of-experts (Mixtral, DeepSeek) | Untested — MoE adds routing complexity orthogonal to attention |
| **Read-skip decode throughput-positive at long context — GRADUATED: projected → MEASURED** | ✅ **MEASURED** (`Llama-3.1-8B-Instruct`, 128K-native, int4 read-skip, no rope hacking): retention vs full-int4 decode = **+25.0 % @32K, +46.4 % @44K, +58.8 % @52K, +72.2 % @60K**, needle **1.0/1.0** at every ctx (monotonic — grows with length). `off` slopes down (linear KV read), retention stays flat (bounded ~1.9K retained, ~95 % skip) → gap **grows** with length. **Replicated on a second standard-rope model:** Mistral-7B-v0.3 crosses **+25.6 % @30K** (8 KV heads) — within noise of Llama's +25.0 %, confirming the crossover tracks **KV-head count**, not a single model. Crossover lands **≤32K on KV-heavy GQA** (8-KV-head Llama/Mistral); ~42K on 4-KV-head Qwen. **Caveat 1 (int4-KV quality):** int4-KV long-context *quality* is **model-dependent** — held 1.0/1.0 on Llama & Mistral (standard rope) out to 30–60K — and on Llama now measured to **100K** (June 2026, incl. retention at 93.3% skip), broke on Qwen2.5-7B-1M (extreme `rope_theta`: passes at 8K, `off` itself collapses to 0.667/0.0 by 32K). **Caveat 2 (retention quality):** the read-skip *retention policy* is also model-dependent at a fixed keep-set — Llama held needle 1.0/1.0, but Mistral dropped depth-0.5 to **0.667** (1 of 3 mid-context needles lost); the keep-set must be validated/widened per model. The **throughput** win reproduces cleanly; the **quality** of skipping does not, automatically. **Caveat 3 (absolute scale — June 2026 bf16-ref, same harness):** the relative win does NOT cross bf16 — int4+read-skip is **~0.21–0.24× bf16, flat across 32–100K** (B=1, gen=128, eager), and the relative delta grows with length (+8%@32K → +65%@100K at 77→93% skip). Read-skip mitigates the long-context decode tax; it does not buy bf16 parity. |
| **Read-skip general fidelity under skip** — token-agreement beyond needle, + the observe-refresh quality/speed knob | Untested — needle 1.0/1.0 validated at 94% skip, but broader generation fidelity and the refresh-cadence trade-off on *shifting*-attention workloads (the static needle is favorable) are not yet benched |

---

## Page 7 — Competitive Moat + Business Case

### What's defensible

**Methodology**: the cross-family calibration result (Qwen +
Mistral + Llama, 15/15 each with 2-of-2 seed replication) is
non-obvious and was the result of the protected-channel design +
the calibration corpus + the kernel-integrated dequant. None of
these are individually novel; the combination as a shipping vLLM
backend with near-bf16 fidelity (+20.4 pt token-agreement over
naive int4) is.

**Implementation surface**: the vLLM-FA kernel fork + the
`Int4ProtectedAttentionImpl` swap + the paged-writer storage
architecture + the slot lifecycle management (6K.14) is ~3000
lines of carefully-tuned code plus a forked CUDA kernel.
Replication effort: ~6-8 engineer weeks for a competent team,
plus calibration time per target model.

**Operational know-how**: the protect_fraction=4% lock, the
calibration corpus design, the static-vs-dynamic mask trade-off,
the per-layer specialization observation (Qwen-14B 2.6% IoU vs
Qwen-7B 11.1% IoU), the sidecar memory ceiling analysis, the
correctness bug characterization and fixes — these are operational
decisions earned through this quarter's measurement work.

### Where the business value sits

The serving economics for long-context workloads are governed by
**concurrent users per GPU**. KVPro delivers:

- **1.83× concurrent max-len sequences per GB of HBM** (DEMONSTRATED,
  Phase 6L) at near-bf16 quality (0.737 token-agreement vs naive's
  0.533, both at 4-bit density). The density advantage is real and net
  of the 4.38 GB sidecar tax.
- **But throughput-negative at saturation**: the same Phase 6L run
  measured int4 at **0.22× bf16 aggregate tok/s (~9× slower per user)**
  on the unoptimized decode path — the **worst case** (deep saturation +
  long generation); short-output serving pays only ~0.54× (curve:
  0.13×–0.54×, throughput section). The density win is real; it currently
  costs per-user latency at the saturated operating point.

Translated to operator economics: a serving deployment at the KV
block limit (the common case for production serving at peak load)
can serve **~1.83× more concurrent long-context users per GPU** at
near-bf16 output quality — but at ~0.22×–0.54× the aggregate token rate
(workload-dependent) until the int4 decode kernel is optimized. That makes the current demonstrated
fit **throughput-insensitive, density-bound workloads** (offline eval,
bulk summarization, agentic batch); interactive serving is gated on
decode-kernel optimization.

**The quality story is the differentiator.** KVPro is the
only 4-bit KV scheme with a published validated quality story: +20.4
pt token-agreement over naive int4, replicated across 4 model
families, at a cost structure fully disclosed above. fp8 achieves
similar density with dramatically lower quality (0/6 bit-identical).
Naive int4 achieves the same density with degraded fidelity.
KVPro closes the quality gap while maintaining the density
advantage.

### Forward thesis — the bottleneck is shifting from memory capacity to data movement

The infrastructure conversation is moving from "can it fit in HBM?" (capacity) to
"what does it cost to **move** the bytes?" — HBM↔compute bandwidth, GPU↔GPU
interconnect, and the cross-node KV transport that disaggregated prefill/decode,
prefix caching, and KV offload now depend on. This shift is a **tailwind, not a
pivot**, because the portfolio's single strongest *measured* result is itself a
data-movement result — but the framing stays honest about which legs are proven.

**read-skip is a data-movement win, already MEASURED.** Decode is memory-**bandwidth**-
bound: the per-token cost is *moving* weights + KV out of HBM, not merely storing them.
read-skip cuts the KV bytes moved per step by **~95%** (bounded retained set vs linear
growth), which is why it decodes **+25% at 32K growing to +72% at 60K** on
Llama-3.1-8B at needle **1.0/1.0** (replicated **+25.6%** on Mistral-7B). That is a
direct reduction in the dominant data-movement term of decode, **captured in software
on today's GPUs** — no new hardware mandate. As the narrative moves capacity→movement,
this is the asset that moves to center stage.

**KVPro (the quant) is a quality-preserving KV shrink — most valuable exactly
where KV becomes *transported* data.** The emerging movement-bound architectures —
disaggregated prefill/decode, cross-request prefix caches, HBM→CPU/NVMe KV offload —
all ship and store the KV cache as their primary payload. A 4-bit KV that *holds
quality* is the right thing to move and cache: **~1.8× less KV transported than bf16
without the fidelity loss fp8 takes** (fp8: needle 1/15). Byte-clean CPU swap-restore
is already validated (TIER5A). **PROJECTED, not built:** the high-value transport legs
— tensor/context-parallel KV exchange and disaggregated/cross-node KV — are
unimplemented, and TP is explicitly unvalidated. We claim the *mechanism* on these,
not a measurement.

**The composed view — the stack attacks all three data-movement terms of decode**, two
of three already measured:

| decode HBM-traffic term | lever | status |
|---|---|---|
| weight movement (short-ctx bottleneck) | AWQ weight-quant — **composes**, orthogonal budget (weights 14.25→5.57 GB, identical under bf16 and int4 KV) | MEASURED stack |
| KV bytes per position | KVPro — ~1.8× net (sidecar-inclusive) | density MEASURED; bandwidth unrealized as wall-clock |
| KV positions read per step | read-skip — ~95% fewer | MEASURED (+72% @60K, quality 1.0/1.0) |

**The honest drag carries to this axis too.** The ~3.4 GB sidecar tax isn't only a
capacity cost — in a movement-bound world the sidecars are *extra bytes to move, and
scattered* (poorer coalescing than the contiguous int4 read), so the net transport
reduction is the **~1.8×** density figure, not 4×. The same tax, on a new axis. And on
the single-GPU decode path the int4 quant remains throughput-negative today
(**0.13–0.67× bf16**) — the per-position byte saving is real but unrealized as
wall-clock until read-path kernel fusion.

**Net positioning:** the move to data movement *promotes* read-skip (measured, on the
dominant bottleneck) and gives the quality-preserving KV shrink a second use
(transported/cached KV) — provided the multi-GPU and disaggregated legs stay labeled
**projected** until built.

### Where KVPro sits in the memory stack

The serving bottleneck *is* the memory hierarchy — **"AI is only as fast as the
memory feeding it."** KVPro has a clear primary home in that stack, a
strong secondary lever, and honest zones of no influence. Mapped to the five
layers (it doesn't make any layer intrinsically *faster* — it **reduces the
demand** on the ones that bind):

| Layer | Influence | How |
|---|---|---|
| **① SRAM** — on-chip cache | **None — and a small cost** | The 4-bit→bf16 dequant runs in registers/compute; this is the *source* of the throughput tax, not a saving. |
| **② HBM / DRAM** — the fuel line | **PRIMARY — maximum influence** | The KV-cache lives here and **exceeds weight memory past ~32K**. **Capacity:** 2× KV density (1.83× net) → ~2× more concurrent users / longer context in the same HBM. **Bandwidth:** decode is HBM-bound — 4-bit KV moves **~1.8× fewer bytes/token** to compute (the literal "lighter feed"). |
| **③④ NAND/SSD + HDD** — active + archive | **Indirect — cheaper at every tier below HBM** | A 4-bit, quality-preserving KV is ~1.8× smaller to spill or archive; warm-tier CPU swap-restore is **byte-clean** (TIER5A). When the hot tier overflows, the offload payload shrinks and restore is faster — the right payload to *move and cache* as KV becomes transported data. |
| **⑤ Controllers** — traffic system | **Strong secondary — via read-skip** | read-skip *is* a memory-traffic controller: it moves only the KV positions worth reading (**95% fewer at 32K, needle 1.0/1.0**) — "optimizes flow, prevents bottlenecks," layered *on* the Layer-2 compression. Deployment routing (short-output→int4, long-form→bf16) is controller logic too. |
| **Model weights** | **Not its lever** | Weight footprint is AWQ's domain; KVPro composes with it but owns only the *KV* term. |

**One line:** KVPro's say is at **Layer 2** — it makes the KV-cache (the
dominant thing the fuel line carries at long context) **~2× denser and ~1.8×
lighter to move**, with read-skip (Layer 5) cutting *positions* moved by ~95%.
It's a **capacity-and-bandwidth play, not a raw-speed one** (it spends some
Layer-1 compute on dequant — the disclosed tax). In the stack's own terms: *it
doesn't make the fuel line faster — it makes the engine sip instead of guzzle,
and packs 2× the fuel in the tank, without losing octane (quality).*

### KVPro WarmTier — where compression unlocks cheaper KV reuse (LMCache *and* NAND)

> *Strategic framing (June 2026). The market shift is **EXTERNAL and real** (vLLM/LMCache ship
> hierarchical KV today). KVPro's fit is anchored on **MEASURED** results (quality on 4 models; the
> SAW-INT4 head-to-head n=1; KVPro-vs-CacheGen codec fidelity; byte-faithful snapshot). KVPro-inside-
> LMCache **serving** and the **NAND** economics are **PROJECTED / modeled** — labeled below. The NAND
> figures are **analytical-model / SSD-simulator (NDOL + MQSim, P0–P1), NOT silicon-measured.***

**The shift: long-context serving is becoming a KV-cache *lifecycle* problem, not a GPU-memory
problem.** Production stacks (vLLM + LMCache) now treat the KV cache as a managed object that moves
across tiers — **GPU HBM (hot) → CPU DRAM (warm) → NVMe / local / remote (cold/reused)** — to reuse
expensive prefill, keep long sessions alive, and serve repeated document/agent contexts without
recomputing the prefix. A **physical NAND/flash tier** is just the same idea one shelf lower. Both are
instances of one thesis: *compression that stays quality-safe makes keeping KV far from compute cheap
enough to be worth it.* This is becoming **infrastructure**; we do **not** claim to have invented KV
offload — the differentiator is the **quality-safe payload**, not the plumbing.

```
   User / Agent / RAG workload
            │  large prompt / document / session prefix
            ▼  prefill ONCE
     KV cache generated
            ▼
   KVPro compressed + protected KV  (quality-safe, ~1.8× smaller)
            ▼
 ┌───────────────┬───────────────┬───────────────────┐
 │ GPU HBM       │ CPU DRAM      │ NVMe / disk / remote│
 │ hot KV        │ warm KV       │ cold / reused KV    │
 └───────────────┴───────────────┴───────────────────┘
            ▼  reload / reuse
   lower TTFT  +  fewer bytes moved  +  hard retrieval preserved
   (LMCache = the plumbing · KVPro = the quality-safe payload)
```

**The new bottleneck the shift creates: quality-safe bytes moved per reused context.** Once KV
leaves HBM, bytes are the enemy — every reused prefix must be read, transferred, decoded, and
reattached before generation, so at long context **TTFT and p99 become transfer-bound, not
compute-bound**. Fewer KV bytes ⇒ less CPU/NVMe footprint, less PCIe/NVMe traffic, faster
warm-prefix reload, lower cost per repeated query. (Honest: this is *"≈proportional when
transfer-bound,"* not a guaranteed 1.8× TTFT in every workload.)

**KVPro is the reliability layer for that hierarchy.** Generic KV compression optimizes nominal
bits/element; KVPro optimizes the production objective — **fewer bytes moved across tiers while
preserving hard long-context retrieval**. In a hierarchy the winning codec is not the smallest; it
must be small enough to store/transport, fast enough to reload/decode, and **safe enough that the
hard retrieval tail survives** compression *and* reuse.

**Why "quality-safe" is the moat — measured: maximum-density codecs collapse on the hard tail.**
Two head-to-heads on our own hardware:
- **SAW-INT4 (BDR)** — ~3.56× nominal density (vs KVPro's 1.8×), SGLang-native, parameter-free
  rotation. **MEASURED (June 2026, A100-80GB):** works on the Qwen3 model it was tuned on (needle
  1.000) but **collapses to 0% needle/hard-needle on Qwen2.5-7B-Instruct** under SAW's documented
  recipe, where BF16 is perfect on identical prompts (rotation confirmed active — distinct failure
  signature from naive int4). Proves **model-transfer fragility**, scoped to **n=1** (breadth on
  Mistral/Llama not yet tested). `docs/SAW_INT4_QWEN_HEADTOHEAD_RESULTS.md`.
- **KVarN** — 2.67× density, near-lossless easy free-gen, throughput ≥ bf16, yet **hard-needle
  collapses 0.25→0.06 (8K→32K)** where KVPro holds full precision (Page 4).

In both, higher nominal density bought a hard-tail cliff. KVPro spends bits to protect high-leverage
K structure and **holds the tail** — exactly the property a hierarchy that *reuses* compressed KV
depends on.

**The real warm-tier incumbent is CacheGen, not SAW.** LMCache ships **CacheGen** — per-layer
bins-quantization (~4–5 bit) + arithmetic coding, purpose-built for offload/reuse. We read its shipped
config and ran a **MEASURED KV-codec fidelity test on real Qwen2.5-7B KV** (28 layers,
`scripts/compare_kvpro_vs_cachegen_fidelity.py`, June 2026):

| codec | K bits/elem | K rel-err | **K rel-err @ top-attention channels** | V rel-err |
|---|---|---|---|---|
| CacheGen (bins=16) | 3.68 | 0.056 | 0.030 | 0.102 |
| CacheGen (bins=32) | 4.72 | 0.027 | **0.0145** | 0.049 |
| KVPro (int4+protect) | 4.48 | 0.052 | **0.0000** | 0.102 |

**The honest read:** KVPro uniquely delivers **zero error on the high-attention K channels** (its
protected-channel design, confirmed on real KV) at competitive bits — the exact failure mode that
collapsed naive int4 / SAW / KVarN end-to-end. **But CacheGen is a capable codec, not a pushover:** at
bins=32 it has *better average* fidelity than KVPro (it spends bits evenly) and only ~half the
critical-channel error of naive int4. So KVPro's edge is **real but narrow** (the protected channels +,
separately, lossless reuse), and a *measured end-to-end* win over CacheGen is **not yet proven** — the
remaining open item is whether CacheGen's small (0.0145) critical-channel error breaks hard-tail
retrieval in a live needle run (needs the LMCache server; see `docs/KVPRO_VS_CACHEGEN_VERDICT.md`).

**Integration posture (stated carefully).** KVPro *is* a vLLM backend — its entire implementation is
a vLLM-FA fork + impl swap — so it sits in the **same ecosystem as LMCache** (vLLM-native). SAW is
**SGLang-oriented**; its LMCache/vLLM warm-tier compatibility is **unproven for it**. We do **not**
claim "SAW can't enter" (almost anything is adaptable with engineering) — only that the burden is on
it, and KVPro starts in-stack. This is a practical edge, not a codec claim.

**On the NAND/flash tier specifically (modeled, NDOL+MQSim P0–P1 — not silicon).** The same warm-tier
logic extends one shelf lower, with two honest caveats:
- **It's logical density, medium-agnostic — not a NAND innovation.** The ~1.8× byte reduction applies
  identically in HBM/DRAM/NAND; a flash tier just inherits it on a cheaper shelf. The *physical* cell
  lever (SLC→TLC→QLC, protect-mask placement) adds only **~1.14× over a fair iso-reliability baseline**
  (≈2.0× vs bf16 compounded) — a hardware ceiling (ECC parity eats the gain), a **known technique**, not
  patent-worthy. We claim cost-tiering, not a flash density mechanism.
- **Flash is warm-only.** It does nothing for NAND array-read latency (`t_R` ~50–100 µs vs HBM ns), and
  QLC endurance (~1k P/E ≈ months at ~10 DWPD) gates per-request hot churn off it. The payoff: 1.8× fewer
  bytes × read-skip's ~95%-fewer positions ⇒ **~20–35× less HBM↔NAND transfer per token (modeled)**,
  which is what turns flash from "cold archive" into a viable warm/reused tier — boundaries move, tiers
  don't.

**Honest scope — what is and isn't built:**

| Element | Status |
|---|---|
| Hierarchical KV market (vLLM/LMCache offload across HBM/DRAM/NVMe) | **EXTERNAL, real, shipping** |
| KVPro near-bf16 quality at ~1.8× density | **MEASURED** (this brief, 4 models) |
| SAW-INT4 collapse on Qwen2.5-7B (the quality-edge proof) | **MEASURED, n=1** |
| Byte-clean warm-tier CPU swap-restore | **MEASURED** (TIER5A) |
| KVPro disk snapshot/restore byte-faithful (NVMe warm tier) | **MEASURED** (Phase-0, Qwen2.5-7B, 8 prefixes, both protect formats — `KVPRO_SNAPSHOT_ROUNDTRIP_POD_RUNBOOK.md`) |
| KVPro vs CacheGen — **codec fidelity** (zero error on top-K channels vs CacheGen 0.0145) | **MEASURED** (real KV, June 2026) |
| KVPro vs CacheGen — **end-to-end needle / TTFT at iso-bytes** | **OPEN — needs LMCache server (newer-driver pod)** |
| KVPro inside the LMCache offload serving path | **PROJECTED — not built** (needs the int4 decode FA fork + scheduler injection) |

> *Note on the warm-tier test design:* for a **fixed** codec, store→NVMe→reload is byte
> round-tripping — quality after reload ≈ quality without it, and is already covered by the needle
> results (the needle lives in the reused prefix). So the warm-tier open work is a **systems /
> economics** benchmark (bytes, transfer, TTFT, p99, cost), with quality only as a sanity check
> against dtype/chunking/partial-load bugs in the storage path — not a quality re-test.

**What NOT to claim** ✗ "we invented hierarchical KV / cold storage" ✗ "KVPro extends the true
context window" ✗ "KVPro is the densest codec" ✗ "KVPro owns full lifecycle management" ✗ "SAW
can't enter vLLM/LMCache" ✗ "KVPro beats CacheGen end-to-end" (codec-fidelity favors KVPro on the tail,
but the end-to-end needle win is **not yet measured** — CacheGen is denser and better on average).
**Claim instead:** *hierarchical KV memory is emerging as the long-context serving architecture; KVPro
is a quality-safe compressed KV layer for it, with two measured guarantees the incumbent lossy codecs
lack — **(1) zero error on the high-attention K channels** (vs CacheGen's 0.0145, naive/SAW's collapse)
and **(2) byte-faithful snapshot/restore for warm-tier reuse** (Phase-0, both protect formats). It
trades raw density for those guarantees.*

**One line for the deck:** *As long-context serving moves to GPU/CPU/NVMe KV hierarchies, the
bottleneck becomes quality-safe KV movement. KVPro reduces the bytes moved per reused context while
protecting the high-leverage structure hard retrieval needs — the reliability layer on top of the
offload plumbing LMCache already provides.*

### Target customer profile

The shippable product fits any of:

| Customer | Why KVPro fits |
|---|---|
| Inference API providers (OpenRouter-like, Replicate-like) | High-concurrency, long-context workloads where KV block limit is the binding constraint. Density advantage converts to per-token margin; quality advantage is the differentiator vs fp8 alternatives. |
| Enterprise self-hosters | Quality-sensitive deployments (legal, healthcare, finance) that need near-bf16 output fidelity but can't justify bf16's concurrency limit. |
| Open-model hubs deploying Llama / Mistral / Qwen at scale | The 3 model families validated this quarter cover ~80% of open-weights serving traffic by category. |
| Edge / low-HBM hardware (H100 PCIe 80GB, L40S 48GB) | Lower-tier GPUs that can't hold 32K concurrent context in bf16 can hold it in KVPro at near-bf16 fidelity. |

### Real-world economics — the bf16 + KVPro playbook (measured numbers)

KVPro is **not a bf16 replacement** —
the crossover sweep settled that (decode 0.17–0.67× bf16, no parity ≤60K).
It is a **memory-density tool**: bf16 buys speed, KVPro buys capacity, and a
deployment that routes between them beats either alone.

**The core principle: if memory is the constraint, KVPro; if speed is the
constraint and the KV fits, bf16. They complement, not compete.**

| Workload | Route to | Why (measured) |
|---|---|---|
| Short chat (<4K), low concurrency | bf16 | speed matters; the KV fits anyway |
| Short/mid chat, high concurrency | **KVPro** | the KV pool is the binding constraint → 2.00× slots |
| Long context (16K+) | **KVPro** | 2× context per GPU at near-bf16 quality (needle 1.0 to 60K) |
| Agentic, many turns | **KVPro** | sessions grow; APC cuts re-prefill **−53→−86% per hit** |
| RAG over shared documents | **KVPro** | document prefix cached once (APC): **1.19–1.85×** batch throughput at 94% hit rate |
| Latency-critical single-stream long-gen | bf16 | KVPro's disclosed worst regime (0.13× at 100K, B=1) |

**What about an 8-bit middle tier?** Gated on this stack (June 2026,
`bench_8bit_kv_gate.py`): vLLM has **no int8 KV** (fp8 only, verified from
source), and **neither fp8 variant is a speed tier** — e5m2 decodes at 0.76×
bf16 with corrupted greedy output (1/6 identical, 41% overlap), e4m3 with
calculated scales at **0.33× bf16** with lite-gate quality only (needles pass
on Llama, 2/6 identical / 84% overlap; the hard gates KVPro passed — depth-
stressed hard-needle, 60K retention, byte-exact APC — have not been run on
it). fp8-e4m3 is the honest **max-density** option (2.00× in-pool, no sidecar
tax, vs KVPro's 1.75× net) for quality-tolerant traffic; it does not replace
bf16 for speed or KVPro for hard-gated quality. The bf16/KVPro split stands.

**The economics on one A100-80G (measured, Llama-3.1-8B, util 0.85, mml 32K):**
*(Net density here is **1.75×** for this specific config — Llama, util 0.85, mml 32K;
the canonical headline is ~1.8× net / 2.0× raw, which lands at 1.83× for the Qwen util-0.5
config. Both are measured; the spread is the sidecar tax's share of different pool sizes.)*

| Metric | bf16 | KVPro | Ratio |
|---|---|---|---|
| KV tokens per GiB of pool | ~8,200 | ~16,400 raw / ~14,000 net of sidecars | **2.00× / 1.75×** |
| Resident 32K sequences | 12 | 24 | **2.00×** (vLLM's own max-concurrency line) |
| Per-sequence decode @32K, B=1 | 66 tok/s | 15–16 tok/s | 0.23× |
| Total throughput at saturation | — | — | **0.22–0.54×, workload-dependent** (6M.6; B=1 × N extrapolation is invalid) |

**GPU-count example (measured density):** 100 concurrent 32K agent sessions
need ~9 bf16 GPUs (12 resident sequences each) vs **~5 KVPro GPUs** (24 each)
— **~44% fewer GPUs** for memory-resident concurrency, paid for with slower
per-session decode. Right for latency-tolerant agentic / batch / async traffic;
wrong for interactive single-stream.

**Hybrid deployment = ROUTING, not swapping.** Run two engine pools (bf16 for
speed-critical, KVPro for memory-bound / shared-prefix) and route per request —
the controller logic already named in the memory-stack table. Do **not** plan
on migrating live sequences between pools: cache dtype is per-engine, and swap
preemption is hard-refused inside KVPro (6K.15 — the sidecars are not migrated;
the guard exists because the failure mode is silent KV corruption).

**One sentence for the budget owner:** *KVPro gives 2.00× the KV slots per GPU
(1.75× net of sidecars, measured live) at 0.17–0.67× decode speed — route
memory-bound, long-context, shared-prefix, and high-concurrency traffic to it,
keep latency-critical traffic on bf16, and the measured 32K-concurrency example
runs on ~44% fewer GPUs at near-bf16 quality.*

### The ask

Validate the production deployment story with a partner
serving real workloads. The methodology is locked; the v2
roadmap is scoped; what's missing is the operator feedback that
converts "shipped through vLLM at near-bf16 fidelity" into
"deployed in your serving stack with measured cost savings."

A partnership of the form:
- Partner: production-scale serving deployment (~10-100 GPUs of
  long-context workload)
- Us: integration support + v2 Tier 1 delivery (capacity demo +
  CUDA graph capture + TP + quality bench) within 6-8 weeks
- Joint: measured cost / quality / latency report against
  partner's existing bf16 or fp8 baseline

closes the gap from "shippable backend" to "production-validated
serving solution."

---

## Page 8 — Technical Understanding (the mechanisms behind the moat)

Every exclusivity claim in this brief rests on a mechanism a technical
reviewer can verify *independently of our benchmarks*. This page states the
"why" behind each — so the moat is auditable, not asserted, and the honest
limits are stated alongside the wins.

### 1. The core IP — why protecting 4% of K channels restores near-bf16 fidelity

KV-cache **K-vectors have highly heterogeneous channel importance**: the
attention score `Q·K` is dominated by a small set of high-magnitude K
channels per `(layer, head)`; the rest carry diffuse, low-magnitude signal.
Uniform int4 quantizes all `D` channels onto one 4-bit grid under a single
per-block scale, so the few high-dynamic-range channels — the ones the inner
product actually depends on — are the first to be crushed. KVPro
keeps the **top `N = round(D × 4%)` (= 5 at D=128) highest-magnitude channels
per `(layer, h_kv)` at bf16** and quantizes the rest to int4: the protected
channels carry the inner-product signal at full precision, the int4 bulk
carries the cheap remainder.

- **Per-`(layer, head)`, not global** — the important channels differ by
  layer and head (measured channel-overlap IoU: Qwen-7B L0-vs-L1 = 11.1%,
  Qwen-14B = 2.6% — *more* specialization at scale). One global mask would
  protect the wrong channels in most heads.
- **Static, frozen at calibration** — importance is a property of the trained
  weights, not the prompt, so a one-time 30-second profiling pass suffices and
  the runtime stays cheap (no per-step adaptation).
- **Why this *is* the moat** — the failure it defends against is **K-bound**:
  long-range retrieval depends on precise K, so any scheme that drops protected
  K collapses on the hard tail. That is exactly where every competitor without
  protect fails — naive int4 (5 misses, K- and V-bound), fp8 (1/15 needle),
  KVarN (0.062 at 32K, K-bound, *worsening with context*). Protect removes the
  K-bound miss (hard-needle 5→2; 0.964 vs naive 0.915; == bf16 head-to-head vs
  KVarN). **Exclusivity defended: the entire quality story.**

### 2. Density ≠ compression — why the honest number is 2× (1.83× net)

Two distinct quantities, routinely conflated:
- **Compression** = bytes to store *the same* KV (`bf16 / int4`, per token).
- **Density** = sequences per **GB of total HBM** (the operator's number).

They relate by `density ≈ compression × (KV's share of the memory being
compressed)`, because total HBM = weights (fixed) + KV + sidecars and
compression shrinks only the KV term. **They converge only when KV dominates
memory** — precisely KVPro's regime (long context 32K+, where KV
exceeds weight memory).

For KVPro both land near 2× for two *stacked* reasons: (1) the 4-bit
nibbles are **4× denser at the element level, but the protect/scale/xmin
sidecars are themselves stored bytes**, so the realized KV *compression* is
~2×, not 4×; (2) that ~2× compression carries through to **~2× concurrency**
because KV dominates long-context memory. They are **not** identical — the
brief reports both on purpose: **2.0× = KV-block density** (sidecar-excluded)
vs **1.83× = net seq/GB** (sidecar-included). **That 2.0 → 1.83 (~8%) gap *is*
"compression minus density"** — the 4.38 GB sidecar tax is fixed overhead that
does not scale with concurrency. At short context (weights-dominant) the gap
blows open; KVPro is deployed long-context specifically so the
compression carries through. **The defensible headline is 2× density (1.83×
net) — never 4×.**

### 3. The sidecar tax is structural — and FLAT with context length

All five reconstruction sidecars are indexed by `NB` = the **paged KV block
pool** (sized once at engine init by `gpu_memory_utilization`), not by any
request's length:

```
k_scale_ext   (NB, H, D)            k_protect_ext (NB, BS, H, n_protect)
k_xmin_ext    (NB, H, D)            v_scale_ext   (NB, BS, H, v_n_groups)
                                    v_xmin_ext    (NB, BS, H, v_n_groups)
```

A longer-context request therefore consumes more of the **same pre-allocated**
pool (fewer concurrent sequences) and allocates **zero** new sidecar —
**measured flat at +4.4–4.7 GB across mml = 8K / 16K / 32K.** The density
advantage does **not** decay as context grows (a selling point, not just a
cost). What the tax *does* scale with:

| Condition | Effect | Tensors |
|---|---|---|
| **KV pool size (`gpu_memory_utilization`)** — primary | proportional (~fixed fraction of the KV blocks) | all 5 (∝ `NB`) |
| **Model size** (`n_layers` × `H_kv` × `D`) | per-layer sidecar set; per-block bytes ∝ `H_kv·D` | all 5 |
| **`max_num_seqs`** (concurrency) | **staging pool only** — `_k_stage_pool ∝ B`, ~24 MB/slot (~6 GB at B=256, *on top of* the ~4.4 GB) | `_k_stage_pool` |
| **`protect_fraction`** | `k_protect_ext ∝ n_protect` (4% → 8% ~doubles the 1.0 GB piece) | `k_protect_ext` |
| **V group size (`v_n_groups`)** | the "sidecar diet" lever (option C) | `v_scale/xmin_ext` |

The two knobs that surprise deployers: **`gpu_util`** (proportional, expected)
and **`max_num_seqs` staging** (~6 GB at 256) — pin `PHASE6_MAX_ACTIVE_SLOTS`
to actual concurrency. **Exclusivity implication: the density win is invariant
to context length, the axis competitors degrade on.**

### 4. APC-compatible by construction — and the graph-safety boundary

vLLM's prefix caching shares full immutable KV blocks across requests by
content hash. KVPro is APC-compatible **by construction**: (a) quant
groups are **block-local** (`group_size = block_size = 32`), so a block's
nibbles + per-block scale/xmin depend only on that block's tokens — *identical*
regardless of which request produced it; (b) the sidecars are **keyed by global
`block_id`**, so a shared block's sidecars travel with it automatically.
**Validated bit-exact**: S1 byte-gate — 13/13 cached blocks byte-identical to a
fresh no-APC prefill.

- **Payoff — measured** (Llama-3.1-8B, A100-80G, N=16, gen=32, June 2026):
  a cache hit skips the prefix's prefill — **TTFT −53/−56/−78/−86%** at
  1K/2K/4K/8K shared prefixes (miss-TTFT grows linearly 142→704 ms while
  hit-TTFT stays ~66–98 ms: the mechanism is visible in the raw data), and
  **1.19–1.85× batch throughput** at 94% hit rate (1.28–1.54× at 75%),
  quality 1.00 == APC-off in every cell, net of the eager tax. Density
  compounds it (2× blocks ⇒ ~2× cacheable prefix). Most valuable on the
  **target segment** (high-fan-out shared-prefix agentic/RAG traffic).
- **Shipped eager-only** (Phase 6K.16). **graphs+APC is gated off**: this
  quarter root-caused the corruption to the **int4 attention kernel not being
  CUDA-graph-safe at B>1** — identical K/V inputs produce ~1.8× divergent
  output under graph replay, while the entire Python state machine (identity,
  GC, masking, protect, splice, dequant) was *measured equal* eager-vs-graphs.
  Low-ROI to chase because int4 is **kernel-bound** — graphs cut launch
  overhead, which is not the bottleneck (6M.3: graphs neutral at saturation).
  *(Honest flag: the kernel is shared with non-APC graphs; non-APC graphs at
  B>1 is a revalidation item — prior runs showed no COLLAPSE, so likely an
  APC-read-path trigger, but unconfirmed against this failure mode.)*

### 5. Why the calibration transfers across families and scales

The protected-channel mask is computed by max-abs profiling of prefill K over a
55-prompt corpus — a *measurement of the trained weights' channel structure*,
not a fit to a benchmark. Because channel importance is a weight property, **one
4% mask transfers across Qwen / Mistral / Llama with no per-family tuning**
(15/15 needle each, 2-of-2 seeds) and across 7B / 8B / 14B. Larger models show
*more* per-layer specialization (lower cross-layer IoU) — consistent with the
mechanism (deeper feature specialization ⇒ the mask does *more* work, not less).
Any `D=128` GQA/MHA architecture works unchanged; other head dims need only a
kernel recompile, not a methodology change. **Exclusivity: a single shipping
backend covers ~80% of open-weights serving traffic by category.**

### 6. Orthogonality — why it composes with weight-quant and read-skip

KVPro attacks one of the three HBM-traffic terms of decode and
**composes additively** with levers on the other two (two of three already
measured):

| Decode HBM-traffic term | Lever | Why orthogonal |
|---|---|---|
| weight movement | AWQ weight-quant | disjoint budget — weights, not KV (measured: AWQ 14.25 → 5.57 GB *identical* under bf16 and int4 KV) |
| KV bytes per position | **KVPro** | the KV-cache itself — AWQ / GPTQ cannot touch this |
| KV positions read per step | read-skip | bounded retained set vs linear-growing attention → throughput-positive at long context (measured +25% @32K → +72% @60K, needle 1.0/1.0) |

Because the three target disjoint terms, the savings **add** — AWQ shrinks
weights *and* KVPro shrinks KV in the same run with quality preserved
(MMLU 56% stacked vs 55% each alone). **Exclusivity: KVPro owns the KV
term — the one budget weight-quant and spec-decode cannot address — and stacks
cleanly on top of them.**

### Honest technical limits (stated alongside the moat)

| Limit | Mechanism |
|---|---|
| **Throughput-negative (0.22–0.54× bf16)** | int4 is *kernel-bound* — per-token paged gather + on-the-fly dequant of packed KV + sidecars. Recoverable headroom is **bounded ~0.27–0.30×, not parity** (int4 fundamentally reads more tensors per token). This is also why CUDA graphs (launch-overhead reduction) buy little. |
| **+4.4 GB total HBM vs bf16** | structural sidecar tax (§3); diet levers (fp8 sidecars, coarser V groups) save ~2.5 GB but can't reach HBM parity without a different KV layout. |
| **graphs+APC gated; only D=128; V0 fork; TP unvalidated** | kernel/engineering scope items (§4 + Roadmap), not quality or methodology gaps. |

The through-line: **every win is a verifiable mechanism, and every limit is a
named, bounded cost** — the quality moat (§1) is fundamental; the throughput
drag is the disclosed price of reading 4-bit KV + sidecars per token.

---

## Appendix — Pointers

| Topic | Reference |
|---|---|
| End-user usage recipe | `CTM_plus/Bench/scripts/PHASE5C_USAGE.md` |
| Project-level README + portfolio | `CTM_plus/KVPolicy/INT4_PROTECTED_README.md` |
| Performance work history (Option A through B-pre-4) | `CTM_plus/Bench/scripts/PHASE6_PERF_REPORT.md` |
| CUDA Graphs preflight + remaining blockers | `CTM_plus/Bench/scripts/OPTION_B_PREFLIGHT.md` |
| Calibration script | `CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py` |
| Quality bench (needle) | `CTM_plus/Bench/scripts/verify_phase5b_5_needle.py` |
| Multi-batch regression gate | `CTM_plus/Bench/scripts/verify_phase5b_6_batch.py` |
| Backend impl + writer | `CTM_plus/KVPolicy/kv_policy/phase5b_backend_install.py`, `phase5b_4c_paged_writer.py` |
| Vendored vLLM-FA fork (SHA `720c948` + int4 path) | installed via forked vllm wheel; see `CTM_plus/KVPolicy/kv_policy/phase5b_backend_install.py:366` |
| TIER5A warm-tier swap-restore finding | `CTM_plus/Bench/scripts/PHASE_TIER5A_SWAP_RESTORE_FINDINGS.md` |
| Memory / capacity scorecard (post-fix) | `CTM_plus/Bench/scripts/MEMORY_STORY.md` |
| Corrected quality verdict (Phase 6J post-fix) | `CTM_plus/Bench/scripts/PHASE_6J_CORRECTED_VERDICT_FINDINGS.md` |
| Three correctness bug fixes (6K.7/6K.9/6K.10) | `CTM_plus/Bench/scripts/PHASE_6K7_INT4_DISPATCH_FIX_FINDINGS.md` |
| Slot lifecycle fix (6K.14) + capacity saturation driver | `CTM_plus/Bench/scripts/PHASE_6K14_SLOT_LIFECYCLE_FINDINGS.md`, `phase6k14_saturation.py` |
| Sidecar overhead audit + diet ceiling | `CTM_plus/Bench/scripts/PHASE_6G_SIDECAR_DIET_FINDINGS.md` |
| APC correctness contract + graphs+APC root cause (Page 8 §4) | `CTM_plus/Bench/scripts/PHASE6K16_APC_CONTRACT.md`, `PHASE6K16_PREFIX_CACHING_PLAN.md` |
| Sidecar tensor shapes (Page 8 §3) | `CTM_plus/KVPolicy/kv_policy/phase5b_4c_paged_writer.py:1530` (`*_ext` allocations) |
| VC brief replication audit | `CTM_plus/Bench/scripts/VC_BRIEF_REPLICATION_AUDIT.md` |

---

*This brief is shareable with prospective partners and investors
under standard NDA. All bench numbers are reproducible from the
referenced scripts. Post-Phase-5 numbers (token-agreement, hard-needle,
long-context capacity) require A100-class GPU + vLLM 0.7.3 + the
vendored vLLM-FA fork. The Phase 5 portfolio numbers (needle 15/15,
3/6 bit-identical) require H100-class GPU + the same stack.*
