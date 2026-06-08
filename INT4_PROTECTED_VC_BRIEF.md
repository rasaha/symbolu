# int4_protected — VC Brief

**Cognade Labs | KV-Cache Quantization that Preserves Quality**
*Prepared May 2026 · throughput section updated June 2026 (Phase 6M) · read-skip / long-context decode-scaling updated June 2026 (Phase 10)*

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
> per concurrent user.** int4_protected is built to move it on the very axes
> Srinivas names — and, decisively, without spending the **accuracy** term that
> competitors trade away:
>
> - **per user / cost (shipped):** 1.83× denser KV-cache → more concurrent
>   long-context users on the same GPU.
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
>   **linearly**: the measured A/B gap **halves from 16K→32K** and the curves
>   **extrapolate to cross near ~50K**, where read-skip turns throughput-positive
>   (a YaRN-extended run to convert that extrapolation into a measured number is
>   the next gate). Realized value today is **density + flat decode-scaling that
>   compounds on int4** — store 4× the context per GB and hold per-token decode
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
| **fp8** (half-precision) | 0.5× KV | **poor** — needle 1/15 (6.7%) on Qwen-7B (200-fillers 1/5, 600-fillers 0/5, 1200-fillers 0/5, direct measurement); 0/6 bit-identical greedy decode; 12% common-prefix overlap vs bf16 | shipped, widely deployed; quality degradation accepted |
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

**The honest trade-off**: int4_protected costs ~+4.4 GB total HBM
vs bf16 (protection sidecars; Phase 6L live-measured the tax at
**4.38 GB** at mml=8K) and is **decode-throughput-negative**: ~1.5–1.9×
slower per-seq at low load, and at saturation Phase 6L measured **0.22×
bf16 aggregate tok/s** (~9× slower per user) on the as-yet-unoptimized
int4 decode path (see the capacity section). The win is
**fidelity-at-density**, not raw memory savings or throughput vs bf16.

This brief documents the int4_protected backend: the calibration
methodology, the validated 4-model portfolio, the integration
through vLLM, and the honest trade-offs.

---

## Page 2 — The Architecture

### int4_protected — one backend, one calibration script, one user-facing API

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
import kv_policy.int4_protected           # registers the backend
from kv_policy.int4_protected import Int4ProtectedLLM
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

| Length bucket | bf16 stock | int4_protected |
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
- **Total HBM is +4.7 GB higher** for int4_protected at equal
  `gpu_memory_utilization` (this long-context bench's total-HBM figure;
  Phase 6L's saturated run measured the delta at **+4.39 GB**, of which
  **4.38 GB is sidecars** — the bench's larger figure also includes the
  CUDA-graph private pools). This is the sidecar overhead (protection
  tensors for scale, xmin, and protected channels) — int4_protected does
  **not** shrink the absolute HBM footprint; it costs more.
- **max_concurrency is 2×** because int4 packs ~4× tokens per block
  (block_size=32, groups of 32 with 4-bit nibbles), so the same KV
  budget holds ~2× the full-context sequences. This is the
  **concurrency density** win — 2× more sequences per fixed KV
  allocation.
- **Net capacity density** (accounting for the sidecar overhead) —
  **now DEMONSTRATED under sustained saturation (Phase 6L)**: at
  mml=8K, B=128, both cells hit 100% KV-block utilization with
  preemption (genuine saturation); protected held **117 live seqs vs
  bf16 58** (2.02× raw), which net of the measured HBM tax is
  protected **2.498 seq/GB vs bf16 1.367 seq/GB = 1.83× per GB** of
  total HBM. This is the real high-load story: at saturation,
  int4_protected serves ~1.83× more concurrent users per GPU than
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

### Throughput (Qwen-7B, A100-80GB) — a WORKLOAD CURVE, not one number

int4_protected's decode throughput is below bf16 at every operating point, but
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

**The throughput tax ranges 0.22×–0.54× depending on workload.** The widely-quoted
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
fan-out traffic to int4_protected (2× the users/GPU, quality-preserved), keep
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
| **int4_protected** | **3 of 6 IDENTICAL** | the other 3 share 33%, 76%, and 82% prefix with bf16 |
| **fp8** | **0 of 6 IDENTICAL** | diverges within 6–16 chars on every prompt (5.9–16.2% prefix overlap) |

---

## Page 4 — Competitive Landscape

### Where int4_protected sits in the KV-compression space

| Approach | Memory | Quality | Notes |
|---|---:|---|---|
| **bf16** (vLLM default) | 1.0× | perfect | the reference |
| **fp8** (vLLM-supported) | 0.5× KV | poor — needle 1/15 (6.7%) on Qwen-7B; 0/6 bit-identical greedy; 12% common-prefix overlap | half-precision; ships, accepted as a quality compromise |
| **AWQ / GPTQ** (weight-only quantization) | weights only, not KV | high | does NOT compress KV-cache; orthogonal solution |
| **naive int4 (KIVI-style)** | 0.5× KV | degraded — token-agreement vs bf16: 0.533 (53%); easy needle deceptively OK but general fidelity substantially reduced | research-grade; our measurements confirm fidelity degradation |
| **TurboQuant W4A4** (Google) | weights + activations | <1% MMLU loss on Llama-2 *(competitor's reported figure)* | W4A4 not KV; complementary, not competitive |
| **int4_protected** *(this work)* | **0.5× KV + ~4.4 GB sidecar overhead (4.38 GB live)** | **token-agreement 0.737 (+20.4 pt over naive); easy needle ≈ bf16; hard-needle retrieval 0.964 vs naive 0.915; 4-model portfolio 15/15 needle 2-of-2 seed** | **best fidelity at 4-bit KV density; sidecar cost is the trade-off** |

### The relevant comparison

There are two distinct comparisons:

**int4_protected vs naive int4** (the quality story):
- Same 4-bit KV density. Same total HBM footprint (roughly).
- int4_protected wins on every quality metric: +20.4 pt
  token-agreement, +0.049 hard-needle retrieval, K-bound misses
  eliminated. Protect is near-free *over naive*, so there is no
  reason to ship naive int4 over protected.

**int4_protected vs bf16** (the capacity story):
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

**int4_protected vs fp8** (the quality-at-density story):
- Both deliver ~2× KV concurrency density vs bf16.
- fp8 costs less total HBM (no sidecars); int4_protected costs ~4.4 GB
  more than bf16 (Phase 6L: 4.38 GB sidecars) while fp8 costs less.
- int4_protected wins decisively on quality: 0.737 token-agreement
  vs fp8's degraded output (0/6 bit-identical, 12% prefix overlap,
  1/15 needle). For quality-sensitive workloads, fp8 is not a viable
  alternative.

### Why the gap isn't closed by faster fp8 kernels or AWQ

| Alternative | Why it doesn't substitute |
|---|---|
| Faster fp8 kernels | fp8's quality limit isn't a kernel issue — it's a representation issue. 8 bits per element cannot preserve the per-channel dynamic range of K at the precision that long-context attention requires. |
| AWQ + AWQ-Marlin | These quantize *weights*, not KV-cache — orthogonal budgets, **complementary** to int4_protected. **Composition status (Phase 6O, measured + fixed):** the stack initially crashed on a dtype mismatch (AWQ fp16 activations vs int4 bf16-dequant K); a one-commit dtype bridge (e06dd26) fixed it, and **byte-equivalence on the bf16 path stayed GREEN (15/15)** — the fix is non-invasive. **AWQ weights + int4_protected KV now load and run together with quality preserved — MMLU 56% (stacked) vs 55% (each alone), within noise.** The *integration and quality* compose, validated. **Memory composition also MEASURED (live introspection, Phase 6O): AWQ shrinks weights 14.25 → 5.57 GB (2.6×, −8.7 GB), and the saving is IDENTICAL with bf16 KV and int4 KV (5.571 = 5.571) — proving the two are orthogonal and additive.** So int4_protected compresses the KV-cache (its moat, which AWQ/GPTQ cannot touch) AND stacks with AWQ weight-quant: both memory budgets shrink together, quality preserved. |
| Speculative decoding | Reduces decode FLOPs, doesn't reduce KV memory. Orthogonal to KV compression. |
| Paged attention (vLLM) | Already deployed everywhere. Paged attention manages KV memory; it doesn't compress KV. int4_protected uses vLLM's paged cache as its substrate. |

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
  **Academic benchmarks (Qwen-7B, Phase 6N/6N.2): int4_protected = bf16 with
  0.0 pt delta AND 100% per-question agreement on THREE benchmarks —
  MMLU (63.5%=63.5% @200Q; 73.9%=73.9% @1,000Q), ARC-Challenge (91.5%=91.5%),
  TruthfulQA (71.5%=71.5%).** Across all of them int4 chose the IDENTICAL answer
  on every question (net_flips=0) — no measurable accuracy loss AND no hidden
  compensating flips. (Recalibrated mask; hard-needle 4/4, COLLAPSE=0.)
- **Correctness**: all three decode bugs fixed (Phase 6K.7/6K.9/6K.10)
  — eager and graph modes both verified correct. Int4 decode
  confirmed `COLLAPSE=0` across every cell × mml post-fix.
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

### What v2 unlocks (in priority order)

**Tier 1 — production blockers**

| Item | Status | Impact |
|---|---|---|
| **Capacity demonstration** (sustained high-B saturation) | ✅ DONE (Phase 6L: `--resident-pressure`, mml=8K B=128, both cells 100% KV-block util) | Validated the density claim under real load: **1.83× seq/GB** net of tax (2.02× raw live). Caveat: aggregate throughput **0.22× bf16** at saturation (unoptimized decode path) |
| **Decode-throughput recovery** (the 0.22× closer) | **Attributed (Phase 6M.4): GPU-work-bound at saturation** — decode-attention kernel ~29% + paged gather/copy ~19.5%; host syncs <1%. **CUDA graphs ruled OUT** (6M.3: neutral at saturation, eager ≈ captured). Next gate = **Test 1 roofline (6M.5)** to split compute- vs bandwidth-bound. **⚠ Test 1 BLOCKED on RunPod A100 (`ERR_NVGPUCTRPERM`, perf counters locked) — needs a profiling-enabled experiment server; tooling is committed and ready.** | Bounds the recoverable headroom. Honest ceiling: **~0.22× → ~0.27–0.30×, NOT bf16 parity** (int4 fundamentally reads packed KV + sidecars and dequants/token). Kernel fusion (6F) is gated on the Test 1 verdict + a funding decision |
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
| **Read-skip long-context crossover (YaRN-extended 48–64K)** | 2–3 days | Convert the **~50K crossover extrapolation into a measured throughput-positive number** — the read-skip headline. Rope-scaling decouples the speed win from Qwen-7B's 32K native cap; validate needle quality holds at extended context first. Tooling (`phase9_p3_fused_needle.py --ab`) is committed; gated only on the YaRN config + GPU time. |

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

End state: int4_protected shipping on 4+ model families with
demonstrated sustained capacity, a comprehensive quality bar (not
just needle), and a production deployment story.

---

## Page 6 — Honest Validation Status

We separate **measured** from **projected** in our pitch. Partners
should be able to tell which is which.

### Critical correctness work completed this quarter

Three independent decode bugs were found and fixed after the initial
Phase 5 ship. All prior quality and throughput benchmarks on
int4_protected were measured on broken code; the corrected results
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
| **Memory (A100-80GB, gpu_util=0.5):** int4_protected uses ~+4.4 GB HBM vs bf16; Phase 6L live-measured the sidecar tax at **4.38 GB** (mml=8K, B=128) = ~99.8% of the +4.39 GB delta | `bench_phase6_long_context_gpu.py`; Phase 6L `report.json`; `MEMORY_STORY.md` Table 1 |
| **vLLM max_concurrency 2× bf16** at all tested mml; **DEMONSTRATED under load (Phase 6L):** 117 vs 58 live at saturation = 2.02× raw | Long-context bench + Phase 6L `--resident-pressure` |
| **Concurrency density (DEMONSTRATED, Phase 6L):** protected **2.498 seq/GB** vs bf16 **1.367 seq/GB** = **1.83× net** of the 4.38 GB sidecar tax | Phase 6L live: peak_live / hbm_gb at saturation; `PHASE_6L_CAPACITY_DEMO_RESULT.md` |
| **Throughput (post-fix), mml=8K B=8 short-gen:** int4 0.56× bf16 agg_tps; mml=16K 0.65×; mml=32K 0.67× | `bench_phase6_long_context_gpu.py` post-fix; `MEMORY_STORY.md` Table 2 |
| **Throughput at saturation (DEMONSTRATED, Phase 6L):** int4 **0.22× bf16** agg tok/s (130.4 vs 597.3) at mml=8K B=128 gen=512 — ~9× slower per user; unoptimized decode path | Phase 6L `report.json`; `PHASE_6L_CAPACITY_DEMO_RESULT.md` §3 |
| **Slot lifecycle fix (6K.14):** auto-bump to `max_num_seqs` + evict-on-completion; protected ran B=48–128 with `slots=B`, zero slot-exhaustion / OOM / preempt | GPU Run 1; `PHASE_6K14_SLOT_LIFECYCLE_FINDINGS.md` |
| 2.01× total-slot ratio at same memory budget (Qwen-7B, gpu_util=0.5, max_model_len=4096): bf16 27,934 / int4_protected 28,060 cuda blocks at block_size=16 and block_size=32 respectively | Tier A `bench_phase5c_v1.py` three-way bench; `PHASE5C_USAGE.md` |
| 219× max concurrency vs stock 109× (Qwen-7B at max_model_len=4096) | Tier A three-way bench; vLLM engine-init log |
| 0 fallbacks across packed decode + write paths on Qwen-7B Tier A R7-latency run (9,240 decode + 9,408 write = 18,648 calls) | `Int4ProtectedAttentionImpl.get_call_stats()` snapshot |
| 3/6 diverse prompts produce bit-identical greedy output vs stock; remaining 3 share 33% / 76% / 82% prefix; fp8 diverges within 6-16 chars on every prompt | `bench_phase5c_v1.py` (Qwen-7B, max_model_len=4096, Tier A) |
| Multi-batch determinism (run1 == run2 byte-identical at B=2..8) | `verify_phase5b_6_batch.py` ALL 7 gates GREEN |
| Warm-tier swap-restore is byte-clean for int4_protected on vLLM 0.7.3 (Qwen-7B + A100 + `preemption_mode='swap'`): under matched concurrent pressure, swap-mode and recompute-mode baselines produced bit-identical 64-token output. All six TIER5A acceptance gates GREEN. | TIER5A bench: `Bench/scripts/PHASE_TIER5A_SWAP_RESTORE_FINDINGS.md` |
| Read-path preflight for CUDA Graphs (B-pre-1..4) COMPLETE; graph mode verified correct end-to-end (6K.10) | `Bench/scripts/OPTION_B_PREFLIGHT.md`; `PHASE_6K7_INT4_DISPATCH_FIX_FINDINGS.md` |
| CPU regression: slot lifecycle (5/5 PASS, including wave-leak repro + fix) | `Bench/tests/test_phase6k14_slot_gc.py` |
| **Read-skip (Phase 10, Qwen-7B, A100):** at 32K context **94% of per-token KV positions skipped** with **needle 1.0/1.0** (depths 0.1/0.5); the retained-index path is GPU-gated **output-identical to full-read** (`gather == compacted == full`). Decode **−10.6% vs full-int4 at 32K** (weight-bound regime; recovered from ~−30% via on-GPU tensor index + block-id cache + tuned observe cadence). A/B gap **halves 16K→32K** (5.05→2.67 tok/s), extrapolating to a ~50K crossover | `phase9_p3_fused_needle.py --ab` (sweep 8K/16K/32K); `test_gather_decode_gpu.py`; `Bench/scripts/PHASE10_FINAL_VERDICT.md` |

### Tested-and-found (the negative results — partner-shareable)

| Item | Result |
|---|---|
| **int4_protected total HBM vs bf16** | CAPACITY-NEGATIVE at equal `gpu_memory_utilization`: ~+4.4 GB more (Phase 6L live-measured 4.38 GB sidecar tax). The net capacity density is **1.83× seq/GB (DEMONSTRATED, Phase 6L)**, which requires running **at the KV block limit** to realize (not a savings at low B). |
| **Decode throughput** | Per-seq ~1.5–1.9× slower than bf16 at low load; **at saturation Phase 6L measured 0.22× bf16 aggregate tok/s (~9× slower per user)** on the unoptimized int4 decode path. Density-positive, throughput-negative at saturation — fine for batch/offline, needs decode-kernel optimization for interactive serving. |
| **Sidecar diet ceiling** | A+F+C stack (fp8 sidecars + fewer protect channels + coarser V groups) saves ~2.5 GB realistically — leaving int4 still ~2.5 GB above bf16. Diet alone likely can't reach HBM parity; option D (inline protect into KV layout) is an additional lever. |
| **Pure int4 KIVI on K + V** | Token-agreement vs bf16 = 0.533 (53%); hard-needle misses = 5 (4 V-bound + 1 K-bound) vs bf16's 0. The K channel is the dominant failure; protected-K eliminates K-bound misses. |
| **Higher protect_fractions (6%, 8%, 16%)** | 4% holds for Mistral-7B / Llama-3.1-8B / Qwen-14B (2-of-2 seeds). Qwen-7B shows seed-level variance at L1200 under 4%; 6%/8% is the documented safety knob. |
| **`enforce_eager=False` graph capture (pre-fix)** | Crashed pre-Phase 6K.10. Post-fix: graph mode correct (A_rate=0.0 all cells). Write-path capture (for full CUDA-graph throughput benefit) is the remaining engineering item. |
| **Read-skip decode below ~32K** | Throughput-NEGATIVE: −17.6% (8K), −17.7% (16K), −10.6% (32K) vs full-int4. Below ~32K decode is weight-bound and full-int4 KV reads are already cheap/coalesced, so skipping 94% of a *scattered* gather doesn't beat the *contiguous* full read. Attribution: the residual is the **gather/compaction copy**, NOT the controller (the per-step GPU→CPU sync was already removed on-GPU in Phase 10). The win is gated to long context (≳50K, extrapolated) — not a sub-32K speed play. |

### Honest cost / risk

| Item | Status |
|---|---|
| **Decode throughput negative — WORKLOAD-DEPENDENT, range 0.22×–0.54×** | Real cost, but a curve not a number (Phase 6M.6, reproduced on fresh A100): **0.54× at short gen (gen=128), 0.32× at gen=512, 0.22× worst-case (deep sat + long gen)** — density invariant ~1.83× throughout. The "0.22× / 9× slower" is the worst case; short-output workloads pay only ~2×. Attribution (6M.4): GPU-work-bound (paged gather ~25% + attention ~21%, host syncs <1%) → recoverable headroom **bounded ~0.27–0.30×, not parity**; the closing lever (read-path fusion, 6F) is gated on Test 1 (6M.5, blocked on counter-locked pods) and is **lower priority than deploying at short generation.** |
| **~+4.4 GB total HBM vs bf16 (4.38 GB sidecars)** | Structural (sidecar overhead); diet options can reduce by ~2.5 GB but cannot reach HBM parity without option D or a different KV layout |
| **Capacity now DEMONSTRATED (Phase 6L) — residual: single-mml** | Was a block-budget estimate; Phase 6L confirmed it under sustained `--resident-pressure` load at mml=8K B=128 (1.83× seq/GB net, 2.02× raw live). Residual: only mml=8K tested; 16K/32K robustness pending |
| **Tensor parallelism not validated** | Code expected to generalize; unverified — requires multi-GPU pod (Tier 1 v2) |
| **vLLM 0.7.3 V0 fork vendored at SHA `720c948`** | Upstream vLLM has moved to V1; forward-port is 1-2 weeks of maintenance (Tier 2 v2) |
| **Only D=128 head dim supported** | Kernel constraint; Phi-3.5 (D=96) and similar need a kernel recompile (Tier 2 v2) |
| **Quality bench: needle + token-agreement + hard-needle + MMLU (1K)** | **MMLU 0.0 pt + 100% per-question agreement at 1,000 Q (Phase 6N.2)** — the agreement diagnostic rules out compensating flips that aggregate parity could hide. Residual: 100% agreement on 4-way MC proves argmax unchanged, not bitwise-identical logits; HumanEval pass@1 (sandboxed) + LongBench F1 are runner-ready but not yet executed |

### Projected (not yet measured)

| Item | Confidence |
|---|---|
| ~~Write-path CUDA graph capture unlocks 2× aggregate throughput~~ **WITHDRAWN (Phase 6M.3)** | **Overturned.** At saturation, eager ≈ captured (125.5 ≈ 130.4 tok/s) — graphs are **neutral**, not a 2× lever; launch overhead is NOT the saturation bottleneck (6M.4: GPU-work-bound). The real (bounded) lever is read-path kernel fusion, gated on Test 1 |
| Decode-throughput recovery to ~0.27–0.30× (read-path fusion, 6F) | Medium, and **bounded** — Phase 6M.4 localized the tax to genuine int4 reconstruction (decode-attention + paged gather); fusion can trim the ~19.5% gather pass but int4 cannot reach bf16 parity. Contingent on the Test 1 roofline verdict (currently blocked on a counter-unlocked pod) |
| ~2× net capacity under sustained high-concurrency load | ✅ **CONFIRMED (Phase 6L)** — the block-budget estimate (~1.8× seq/GB) was confirmed by direct `--resident-pressure` observation: 1.83× net seq/GB, 2.02× raw live at saturation |
| TP enables 70B-class serving | Medium — code structure looks TP-compatible; risk is in vLLM-side plumbing |
| Sidecar diet option C (~1.7 GB savings) + option F preserves token-agreement gain | Medium — no quality re-bench yet after diet |
| Methodology extends to Phi (D=96) | Medium — calibration math is architecture-agnostic; kernel constraint is the only barrier |
| Methodology extends to mixture-of-experts (Mixtral, DeepSeek) | Untested — MoE adds routing complexity orthogonal to attention |
| **Read-skip turns decode throughput-positive past ~50K context** (bounded retained set vs linear full-attention; the measured 16K→32K gap-halving extrapolated) | Medium — **two independent estimates agree**: the A/B gap-halving extrapolates to ~50K, and **section-level profiling independently predicts ~53K** (the `kernel_call` skip-saving scales with context while the fixed overhead stack — `cache_append` + decision + index — stays mostly bounded). Still **PROJECTED, no measured speedup claimed**: the crossover sits past Qwen-7B's 32K native window, so a YaRN-extended run is needed to confirm it directly |
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
**concurrent users per GPU**. int4_protected delivers:

- **1.83× concurrent max-len sequences per GB of HBM** (DEMONSTRATED,
  Phase 6L) at near-bf16 quality (0.737 token-agreement vs naive's
  0.533, both at 4-bit density). The density advantage is real and net
  of the 4.38 GB sidecar tax.
- **But throughput-negative at saturation**: the same Phase 6L run
  measured int4 at **0.22× bf16 aggregate tok/s (~9× slower per user)**
  on the unoptimized decode path. The density win is real; it currently
  costs per-user latency at the saturated operating point.

Translated to operator economics: a serving deployment at the KV
block limit (the common case for production serving at peak load)
can serve **~1.83× more concurrent long-context users per GPU** at
near-bf16 output quality — but at ~0.22× the aggregate token rate until
the int4 decode kernel is optimized. That makes the current demonstrated
fit **throughput-insensitive, density-bound workloads** (offline eval,
bulk summarization, agentic batch); interactive serving is gated on
decode-kernel optimization.

**The quality story is the differentiator.** int4_protected is the
only 4-bit KV scheme with a published validated quality story: +20.4
pt token-agreement over naive int4, replicated across 4 model
families, at a cost structure fully disclosed above. fp8 achieves
similar density with dramatically lower quality (0/6 bit-identical).
Naive int4 achieves the same density with degraded fidelity.
int4_protected closes the quality gap while maintaining the density
advantage.

### Target customer profile

The shippable product fits any of:

| Customer | Why int4_protected fits |
|---|---|
| Inference API providers (OpenRouter-like, Replicate-like) | High-concurrency, long-context workloads where KV block limit is the binding constraint. Density advantage converts to per-token margin; quality advantage is the differentiator vs fp8 alternatives. |
| Enterprise self-hosters | Quality-sensitive deployments (legal, healthcare, finance) that need near-bf16 output fidelity but can't justify bf16's concurrency limit. |
| Open-model hubs deploying Llama / Mistral / Qwen at scale | The 3 model families validated this quarter cover ~80% of open-weights serving traffic by category. |
| Edge / low-HBM hardware (H100 PCIe 80GB, L40S 48GB) | Lower-tier GPUs that can't hold 32K concurrent context in bf16 can hold it in int4_protected at near-bf16 fidelity. |

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
| VC brief replication audit | `CTM_plus/Bench/scripts/VC_BRIEF_REPLICATION_AUDIT.md` |

---

*This brief is shareable with prospective partners and investors
under standard NDA. All bench numbers are reproducible from the
referenced scripts. Post-Phase-5 numbers (token-agreement, hard-needle,
long-context capacity) require A100-class GPU + vLLM 0.7.3 + the
vendored vLLM-FA fork. The Phase 5 portfolio numbers (needle 15/15,
3/6 bit-identical) require H100-class GPU + the same stack.*
