# CTM+ / PCAM — VC Brief

**Cognade Labs | Intelligent KV-Cache Eviction for LLM Inference**
*Prepared May 2026*

---

## Page 1 — The Problem

### LLM inference is becoming memory-bound, and today's eviction heuristics are too shallow.

As context windows grow, the dominant serving bottleneck shifts from
pure matrix math toward KV-cache pressure. The **KV-cache** — the
per-request memory that stores every token's key and value tensors
so the model does not recompute them on every generation step — is
now the largest single consumer of GPU HBM in most inference
deployments.

A single Mistral-7B request at 32K context can consume on the order
of ~2 GB of KV-cache in bf16. An A100-80GB running tens of
concurrent requests can dedicate the majority of its HBM to
KV-cache. When the cache is full and a new request arrives, the
serving system must **evict** — decide which cached blocks to throw
away to make room.

In many serving stacks, the effective eviction policy remains
**LRU-like** — dominated by recency and largely blind to
transformer-specific block value. LRU is a policy invented in the
1960s that knows exactly one thing: *when was this block last
touched?*

LRU does not know:

| What LRU misses | Why it matters |
|---|---|
| Whether a block contains an **attention sink** (position 0, BOS token) that the model attends to on every step | Evicting a sink block forces a full recomputation that destroys p99 latency |
| Whether a block is from a **global-context layer** (early transformer layers handling long-range dependencies) or a **local-syntax layer** (late layers handling short-range grammar) | Global-context blocks are expensive to re-read if evicted; local-syntax blocks are cheap to recompute |
| Whether the model's **attention pattern around a block is changing** — signaling it will be re-read with full attention soon | Evicting a block right before it is needed is the most expensive possible eviction |
| Whether a block contains a **structural boundary** (sentence start, paragraph break, discourse marker) that anchors the attention pattern for multiple heads | Boundary blocks are disproportionately attended to; losing them degrades quality across the whole context |

The result: production inference operators overprovision HBM,
cap concurrent requests below what the hardware can support,
accept p99 latency spikes from bad evictions, and spend
engineering time building workarounds (prompt caching, chunked
prefill, aggressive context truncation) for a problem that should
be solved at the eviction-policy layer.

### Why this is a growing problem, not a stable one

Context windows are growing (32K → 128K → 1M+). Agent
frameworks concatenate tool results, retrieved chunks, and
conversation history, pushing real-world context lengths into the
tens of thousands of tokens on routine requests. KV-cache
pressure grows linearly with context length, but eviction-policy
quality determines whether that pressure translates into latency
spikes, quality degradation, or just a slightly smaller batch. As
context grows, the gap between "evict the right block" and
"evict the wrong block" widens — and LRU, which cannot
distinguish between the two, becomes increasingly costly.

Most provider-side mitigations address KV pressure indirectly —
through pricing (OpenAI's long-context tiers), prompt caching
(Anthropic), context management (chunked prefill), or paging
(vLLM's paged attention) — rather than through a multi-signal
eviction policy that reasons about block value directly.

---

## Page 2 — The Architecture

### CTM+ / PCAM — one specification, one runtime, seven scoring signals

CTM+ is a **canonical KV-cache eviction policy specification** —
the scoring math, the classification semantics, and the
sequence-lifecycle rules that decide which blocks deserve to stay
in HBM and which can be safely evicted. PCAM is the **runtime
backend** that implements CTM+ bit-for-bit, exposes it through a
small Python API, and plugs into real inference runtimes (vLLM,
HuggingFace) through narrow adapters.

### The scoring model

Every candidate block is scored by up to seven signals (six additive,
one multiplicative), with phase-aware weights that shift between
prefill and decode:

```
score = w_r · recency                      signal 1: when was it last read?
      + w_f · frequency                    signal 2: how often is it read?
      + w_a · attention_ema                signal 3: how much attention does it receive?
      + w_s · importance                   signal 4: is it a sink, entity, or filler?
      + w_d · boundary_score               signal 5: does it anchor a structural boundary?
      + w_u · instability_hint             signal 6: will it be re-read soon?
      + entity_bonus                       (conditional: +0.5 for high-attention non-sinks)
      × band_class                         signal 7: is it from a global or local layer?
```

Signals 1–4 are the **base model**, locked by an internal ADR
(architectural decision record) and enforced by a 20-test
bit-parity harness on every commit. These capture past behavior:
how recently and frequently a block was accessed, how much
attention it received, and whether it is structurally important
(sink blocks are pinned and never evicted).

Signals 5–7 are **FSCS-derived extensions** — three diagnostic
signals identified during our Text-FSCS research and folded into
the memory-policy layer where they naturally belong. Together they
refine **eviction-risk estimation**: boundary sensitivity captures
structural importance, band class captures expected miss cost by
layer role, and instability hints at near-future reread likelihood.
They are default-off, caller-supplied, and backward-compatible —
the base four-signal model is unchanged when they are not activated.

### Two-layer architecture

```
      Inference Runtime (vLLM, HuggingFace, custom)
                     │
                     ▼
      ┌──────────────────────────────────┐
      │            CTM+                  │   ← Canonical spec
      │   Phase-aware scoring            │      (4 base + 3 FSCS-derived)
      │   Count-Min frequency sketch     │
      │   Sink / entity / filler         │
      │   Sequence lifecycle             │
      └──────────────┬───────────────────┘
                     │  vendored + parity harness
                     ▼
      ┌──────────────────────────────────┐
      │         PCAM runtime             │   ← Consumable backend
      │   KVCachePolicy API              │
      │   PCAMEvictor (vLLM adapter)     │
      │   Tier hints (HOT/WARM/COLD)     │
      │   Trace replay + benchmarks      │
      │   Shadow + active mode bridges   │
      └──────────────────────────────────┘
```

**CTM+ is the spec. PCAM is the runtime. The parity harness is
the only sync mechanism.** There is no bridge class, no adapter
layer, no second scoring path. When CTM+ changes upstream, PCAM
re-vendors and the parity harness catches any divergence. This
discipline is what makes the system trustworthy enough for a
production SRE to turn on.

### How the FSCS-derived signals were identified

The three extension signals came from a separate research program
(Text-FSCS) that explored dynamic attention-compute reduction on
frozen Mistral-7B. That research produced a measured `r* = 6.7%`
quality-preservation frontier for attention routing, along with
three diagnostic observations about attention behavior that turned
out to be more valuable as **cache-policy inputs** than as
standalone attention modifications:

- **Boundary tokens are attention sinks** — evicting them causes
  disproportionate damage regardless of their recency
- **Layer depth predicts block importance** — global-context layers
  produce blocks that are expensive to re-read; local-syntax layers
  produce blocks that are cheap to recompute
- **Attention instability predicts future re-reads** — blocks in
  unstable regions will be re-read with full attention soon, making
  their eviction costly

These observations were implemented as CTM+/PCAM scoring signals
(not as transformer modifications) and validated end-to-end on real
Mistral-7B KV-cache data.

---

## Page 3 — Competitive Landscape

CTM+/PCAM sits at an unusual seam in the LLM serving stack — **below
the model**, **above the hardware**, and **inside the runtime** — so
"competition" is better understood as a set of adjacent categories
that each address KV-cache pressure in a different way. The table
below places us against each of them, stating for every row both
*how* we differ and *why* that difference is an advantage for a
production operator who cares about throughput, p99 latency, and TCO.

| Category | Representative players | What they ship | How CTM+/PCAM differs — and why it is better |
|---|---|---|---|
| **Production inference engines** | vLLM, TGI, TensorRT-LLM, SGLang, LMDeploy, NVIDIA Triton | High-performance serving runtimes that own batching, paged attention, continuous batching, and KV-cache allocation. Their eviction story is typically LRU-shaped or fixed-size paging. | We do not replace vLLM — we plug into it. PCAM ships as a drop-in `KVCachePolicy` / `PCAMEvictor` adapter that makes the engine's block-pool decisions **attention-aware** instead of recency-only. **Better because:** the operator keeps every other optimization the serving engine already ships (paged attention, continuous batching, CUDA graphs) and simply upgrades the one decision that determines whether a good batch is sustained under pressure or destroyed by a bad eviction. |
| **KV-cache compression research** | H2O (Heavy-Hitter Oracle), StreamingLLM, Scissorhands, SnapKV, FastGen, PyramidKV, KIVI (KV quantization) | Academic projects that drop, quantize, or compress KV entries using a single attention-derived heuristic (heavy-hitters, sink tokens, head-level pruning). | Research methods typically pick **one** signal — usually attention mass over a window — and apply it uniformly. CTM+ is a **seven-signal** scored policy (recency · frequency · attention EMA · importance · boundary · band class · instability) with phase-aware weights and a bit-parity-enforced spec. **Better because:** a single-signal heuristic overfits to its validation workload and silently fails on adjacent ones, whereas a multi-signal scored policy degrades gracefully and can be tuned per-signal against operator telemetry. Many of these methods also require a model-side change; CTM+/PCAM does not. |
| **Provider-side prompt caching** | Anthropic prompt caching, OpenAI prompt caching, Google Gemini context caching, DeepSeek context caching | API-level features that let callers mark a prompt prefix as cacheable so the provider can reuse its KV state across requests at a billing discount. | Prompt caching answers *"can I reuse this exact prefix?"* — a hit/miss question on whole prefixes. It does not answer *"which blocks inside the live cache should I evict when memory is full?"* **Better because:** we are complementary, not competitive — an operator who runs CTM+/PCAM *under* a provider's prompt cache gets both effects (free prefix reuse at the API boundary *and* intelligent block-level eviction at the runtime). For self-hosted inference where no provider cache exists, CTM+/PCAM is the only layer that reasons about block value at all. |
| **Context-management strategies** | Chunked prefill, sliding-window truncation, RAG-instead-of-long-context, context summarization, ring attention | Avoid KV-cache pressure by shortening the context the model sees or distributing it across devices. | These approaches *sidestep* the eviction problem by making the context smaller or spread thinner. That works until the workload needs the full context — agentic tool chains, long chat histories, large retrieved corpora — at which point the eviction decision comes right back. **Better because:** CTM+/PCAM lets the operator keep the full context *and* run more concurrent requests, instead of forcing a quality trade-off at the application layer. Chunked prefill in particular is complementary — a chunked-prefill scheduler on top of CTM+ gets the benefit of both optimizations. |
| **Attention-mechanism modifications** | Sliding-window attention (Mistral), StreamingLLM attention sinks, sparse/local attention, MQA/GQA, Longformer-style dilated attention | Model-architecture changes that reduce the KV footprint or attention pattern to make long context tractable at training time. | These require a **training-time or model-level change**, so they only help workloads that happen to run on a model built around them. CTM+/PCAM is a **runtime-only policy** that works on a frozen, unmodified model. **Better because:** an operator can turn CTM+ on tomorrow for any model they already serve — no retraining, no re-export, no weight rewrite — and every new model added to the fleet inherits the optimization for free. |
| **Hardware / memory-tiering approaches** | CXL memory expanders, FlexGen (CPU/SSD offload), DeepSpeed-Inference ZeRO-Inference, NVIDIA Grace-Hopper unified memory | Increase effective KV capacity by paging to tiered memory or adding physical DRAM behind the GPU. | Hardware tiering makes the cache *bigger*; it does not make it *smarter*. Evicting the wrong block is still expensive, and moving the wrong block to a slower tier is often worse than evicting it outright. **Better because:** CTM+ emits `HOT / WARM / COLD` tier hints alongside eviction decisions, so a memory-tiered system driven by CTM+ scores gets the right blocks in the right tier — and our FPGA/ASIC path means the policy can eventually move into the memory controller itself, where a pure-software LRU cannot. |
| **Classic OS / DB cache-replacement policies** | LRU, LFU, ARC, 2Q, LIRS, CLOCK-Pro, W-TinyLFU | General-purpose cache-replacement policies from the systems and database literature, often embedded in inference engines "because that's what every cache uses." | These policies treat every cache block as fungible. A transformer KV-cache block is not fungible — a sink block is irreplaceable, a late-layer local-syntax block is nearly free, and a block adjacent to an unstable attention region will be re-read with full attention within a few steps. **Better because:** CTM+ is the first eviction policy that knows the difference, and its scoring math is a strict superset of the classical ones (you recover LRU or LFU as a degenerate case by zeroing all other weights). |

### Why the overall bet is better, not just different

- **Multi-signal is a superset of single-signal.** Every incumbent in this table bets on one axis — recency for LRU, heavy-hitters for H2O, prefix equality for prompt caching, more DRAM for CXL. CTM+ is a scored composition of seven signals with phase-aware weights, so it *contains* those bets as special cases and adds the ones they are missing (boundary, band class, instability). An operator does not lose anything by switching to CTM+; they strictly gain signals.
- **Runtime-only, model-agnostic.** No retraining, no attention-pattern change, no weight rewrite. An operator running Mistral, Llama, Qwen, or DeepSeek can adopt CTM+/PCAM without touching the model or the tokenizer — which is exactly why we ship into an existing vLLM deployment as a `KVCachePolicy` adapter and nothing else.
- **Spec-and-runtime separation is the moat.** CTM+ is a spec locked by an ADR and enforced by a 20-test bit-parity harness; PCAM is the runtime that implements it bit-for-bit. That discipline is what makes the policy trustworthy enough for a production SRE to turn on — and it is the thing research-paper methods on this list structurally cannot match, because they ship a single code artifact rather than a spec with independently testable consumers.
- **Software today, silicon tomorrow.** Because the policy is a scored math object (not a learned model, not a trained heuristic), it has a credible path from a PCAM software runtime → an FPGA prototype → a memory-controller ASIC or CXL expander. None of the other categories in this table — eviction, compression, prompt caching, attention modification — has a scored math spec that maps cleanly into RTL, and we already have SystemVerilog RTL with a cocotb parity harness as evidence of that path.
- **Composes with, rather than replaces, the rest of the stack.** CTM+/PCAM is additive to paged attention, chunked prefill, prompt caching, CXL tiering, and KV quantization. The competitive question is never *"CTM+ or vLLM?"* or *"CTM+ or prompt caching?"* — it is *"with or without the scored eviction layer underneath?"*

### In one sentence

Classical cache policies treat every block as fungible, research KV
compressors pick one attention-derived signal, provider prompt caches
answer hit/miss on whole prefixes, and hardware tiering makes the
cache bigger. **CTM+/PCAM is the only policy that knows a transformer
KV-block is not fungible** — that a sink is irreplaceable, a
late-layer local-syntax block is nearly free, and a boundary-anchoring
block must not be evicted a moment before it is re-read — and it is
the only one of these categories with a credible path from a Python
policy today to a memory-controller ASIC tomorrow.

---

## Page 4 — What Is Proven and What Is Next

### Serving-tier evidence (CTM+ Phase 4 on real GPU, Qwen2.5-7B-Instruct, vLLM 0.7.3)

The serving-tier closure run that this brief used to project — and
that earlier drafts inflated into a +50% concurrent-request claim —
has been executed. The honest measured outcome:

| Metric | LRU baseline | CTM+ Phase 4 | Delta | Status |
|---|---|---|---|---|
| **swap_out blocks per decode token** (algorithm quality) | reference | **−11.1%** | smarter evictions: real, durable | **GPU-measured** |
| **tokens/sec end-to-end** | reference | **−20%** | structural cost at vLLM 0.7.3 Evictor-ABC patching layer | **GPU-measured** |
| Hotspot (batch ML) | 76.4% hit rate | 94.2% | +17.8% | trace-replay |
| Database (TPC-C) | 125K txn/sec | 142K txn/sec | +13.6% | adjacent-domain transfer |

*Serving-tier rows bolded. The −11.1% swap_out result is the
algorithm quality win — fewer evictions per decode token under the
same workload. The −20% tokens/sec is the structural cost of how
vLLM 0.7.3 lets a custom policy plug into its Evictor-ABC: it is
not a CTM+-scoring overhead, it is the patching-layer overhead, and
it closes once the upstream `cache_kv` hook lands or a route-A
direct-pool integration replaces the route-B wrapper. Evidence:
`CTM_plus/Bench/bench_out/PHASE4_GPU_FINDINGS.md` §13.3.*

### KV-cache compression layer (KIVI-style INT4) — landed in the same session

A complementary KV-cache compression layer built on the same
codebase, validated end-to-end on the same model:

| Metric | Result | Evidence |
|---|---|---|
| Real-heap KV compression vs FP16 | **3.2× smaller** | §18 + §19.1 |
| Perplexity ratio vs FP16 baseline | **1.024×** (essentially flat) | §18 |
| MMLU accuracy delta @ 1000 questions | **−0.9 pt** (70.2% → 69.3%) | `track_e_audit_followups/int4_mmlu_1000.json` |
| Teacher-forced next-token agreement | **96.4% top-1, 100% top-5, mean KL 0.006** | `track_e_audit_followups/int4_generation_teacher_forced.json` |
| INT3 memory-bound variant | **−0.7 pt MMLU @ 1000q at ~4.5× theoretical compression** | `track_e_audit_followups/int3_mmlu_1000.json` |

KIVI INT4 stacks under CTM+: the KV-cache it compresses is the same
KV-cache CTM+ evicts from. The current honest combined-stack claim
is **~3-3.5× over an INT8+LRU baseline** from measured KIVI INT4
compression × measured Phase 4 eviction quality.

**Peer positioning vs Google's TurboQuant.** Google Research's
TurboQuant (Polar Quantization) targets the same 4-bit regime for
KV-cache, with a reported <1% MMLU degradation on Llama-2 and Gemma.
Our KIVI INT4 measurement on Qwen2.5-7B (−0.9 pt MMLU @ 1000q,
1.024× perplexity, 3.2× real-heap) lands in peer territory. The two
methods are complementary, not competitive: TurboQuant is primarily
a W4A4 weights+activations method (KV-cache is one application);
KIVI is KV-cache-specific. They can stack — TurboQuant W4A4 over
the model, KIVI INT4 over the cache, CTM+ Phase 4 over the eviction
decisions. Earlier drafts of this brief quoted an 8.8× combined-
stack figure anchored on a TurboQuant projection that did not
survive our Qwen2.5-7B reproduction (see negatives below); the
retired figure has been replaced with the measured 3-3.5× anchored
on KIVI INT4 + CTM+ Phase 4. If a future session reproduces
TurboQuant's published W4A4 result on Llama-2, the multiplicative
stack story extends cleanly without retraction.

### FSCS-derived signal integration (separate research thread, real Mistral-7B trace)

| Metric | Baseline (4 signals) | Enhanced (7 signals) |
|---|---|---|
| Eviction rounds | 4 | 4 |
| Eviction selections emitted | 1,022 | 192 |
| Rounds with changed decisions | 0 | **4 (100%)** |
| Individual block choices changed | — | **1,108** |

*Interpretation: policy behavior changed materially on a real
Mistral-7B trace. Whether the changed decisions improve downstream
serving quality (hit rate, latency, concurrent requests) requires
the same live-load closure that §13.3 just delivered for the
4-signal Phase 4 path — replicated for the 7-signal enhanced
configuration. Until that replication lands, the FSCS-derived
signals are validated as **decision-impacting**, not yet as
**quality-improving**. 276 unit tests pass with zero regressions.*

### What is implemented today

| Component | Status | Evidence |
|---|---|---|
| CTM+ scoring spec (4-signal, ADR-locked) | ✅ Production-ready | 20-test parity harness, vendored reference |
| PCAM Python runtime (`KVCachePolicy`) | ✅ Consumable API | Phase 1-5 complete, 276 tests |
| vLLM integration (shadow + active mode) | ✅ Implemented + GPU-measured | §13.3 closure run on Qwen2.5-7B |
| FSCS-derived signals (boundary, band, instability) | ✅ Integrated + decision-validated | 36 signal tests, real Mistral trace |
| Annotated trace capture from Mistral-7B | ✅ Pipeline working | `pcam_fscs_trace_capture.py` |
| KIVI-style INT4 KV compression | ✅ End-to-end measured | §18 + §19, route-B HF wrapper |
| FPGA hardware (SystemVerilog RTL) | ✅ Credibility artifact | cocotb parity harness |

### Honest Validation Status

We separate **measured** from **tested-and-failed** from **projected**
so partners can tell which is which.

**Measured on real GPUs (May 2026):**

- CTM+ Phase 4: −11.1% swap_out per decode token (algorithm quality win)
- CTM+ Phase 4: −20% tokens/sec end-to-end (structural at vLLM 0.7.3 Evictor-ABC; closes with route-A `cache_kv` hook or upstream patch)
- KIVI INT4 KV compression: 3.2× real-heap, 1.024× perplexity, −0.9 pt MMLU @ 1000q, 96.4% teacher-forced top-1
- INT3 memory-bound variant: −0.7 pt MMLU @ 1000q at ~4.5× theoretical compression
- FSCS-derived signals: 100% of eviction rounds make different choices on real Mistral-7B trace
- **FP8-vs-INT4 throughput (§20.1, four-cell GPU run, Qwen2.5-7B):** vLLM FP8 KV = **1.18× FP16** on the FlashInfer backend (FP8 is a small throughput *gain*, not a cost). Route-B INT4 KIVI = **0.47× FP16 in HF transformers** — the pure-PyTorch quantize/unpack round-trip is a ~2× decode cost. Decomposition: the HF↔vLLM stack gap (25×) is what a route-A `cache_kv` integration removes; the INT4-algorithm gap (2×) travels with it and needs the Marlin-style fused unpack-attend kernel (§20.6). **Honest verdict: route-A is necessary but not sufficient — the kernel is the gating item for FP8-competitive throughput.**

**Tested-and-failed (documented as negatives — partner-shareable):**

- TurboQuant *baseline* (random rotation, 3-bit, KV-only) on Qwen2.5-7B: perplexity ratio 3052×. Our implementation diverges from Google's published method on four axes (random vs learned rotation, 3-bit vs the paper's 4-bit headline, KV-only vs W4A4, Qwen2.5 vs Llama-2/Gemma). The negative rules out the baseline configuration as a drop-in KV-only compressor; it does **not** refute Google's published TurboQuant W4A4 result on Llama-2 / Gemma. Reproducing the full method is deferred follow-on work.
- TurboQuant baseline + per-channel scale rescue: 24× worse than baseline (KIVI's per-channel trick does not transfer to rotation-based designs)
- TurboQuant baseline + sink-skip rescue: modest 27% improvement, still catastrophic at 220×
- Static GPTQ-style calibration on INT4 KIVI: −6.80 pt MMLU @ 1000q — dynamic + group quantization beats static
- Autoregressive generation top-1 (64%) is misleading vs teacher-forced (96.4%) due to exposure bias — we report teacher-forced

Negatives are documented in `PHASE4_GPU_FINDINGS.md` §17 + §17.8 + §19.2.

**Harness-landed, GPU-run-pending (FP8-KV competitive gap closure track):**

- Sink-FP16 + body-INT4 mixed precision — sweep recipe landed for
  sink ∈ {0, 4, 16, 64} at the full KIVI rescue stack; ~$0.50 GPU to
  test the StreamingLLM-style quality-recovery hypothesis (§20.2)
- Multi-model replication on Llama-3-8B + Mistral-7B — runbook recipe
  landed; ~$2-3 GPU to remove the "one-model demo" caveat (§20.3)
- Long-context perplexity sweep at 16k/32k/50k — `--perplexity-text-path`
  flag landed; ~$0.50 GPU to validate at the context length where KV
  compression matters most (§20.4)
- Route-A vLLM `cache_kv` integration plan — engineer-day breakdown in
  `Bench/scripts/ROUTE_A_VLLM_CACHE_KV_PLAN.md`; same hook closes the
  −20% tokens/sec gap (§20.5)
- Marlin-style fused unpack-attend kernel — PyTorch reference + HBM-
  traffic counter in `KVPolicy/kv_policy/int4_fused_attention_sketch.py`
  showing 3.56× HBM-traffic ceiling speedup; ~1-2 weeks of GPU-kernel
  specialist work to realize (§20.6)

**Projected (not yet measured):**

- 7-signal FSCS-enhanced serving-tier numbers (decision-impact validated; quality-impact requires the same §13.3-style closure rerun)
- FSCS signal weight calibration (boundary=0.10, instability=0.15, band={1.3, 1.0, 0.8} are starting points, not calibrated values)
- Multi-model generalization (Llama-3, Mistral, Qwen sizes other than 7B)
- Long-context (≥32k)
- Route-A vLLM `cache_kv` direct-pool integration (~3-5 engineer-day effort that closes the −20% tokens/sec gap)
- FPGA prototype, ASIC controller, design-partner pilots

### Next steps

| Step | What it proves | Cost |
|---|---|---|
| **Route-A vLLM `cache_kv` integration** | Closes the −20% tokens/sec structural cost of route-B patching | ~3-5 engineer-days |
| **7-signal FSCS closure rerun** | Whether 1,108 changed decisions translate to throughput / p99 wins | Days (pipeline built; §13.3 harness reusable) |
| **Multi-model + long-context replication** | Whether KIVI INT4 + Phase 4 generalize off Qwen2.5-7B / 4-8k context | Weeks |
| **FPGA prototype** (Xilinx Alveo) | RTL at 250MHz, <50ns latency | 2–3 months |
| **Design-partner pilot** | Real inference workload with real quality/latency metrics | Quarters |
| **ASIC controller** | CXL memory expander or GPU-side HBM controller | 12–18 months |

### The ask

We are raising seed to (i) close the route-A `cache_kv` integration
and erase the −20% structural cost, (ii) replicate the §13.3 GPU
closure for the 7-signal FSCS-enhanced configuration and across
additional models / context lengths, (iii) fund the FPGA prototype,
and (iv) land the first design-partner deployments. The software
stack is built, GPU-measured for the 4-signal Phase 4 path and the
KIVI INT4 compression layer, and integrated end-to-end for trace-
driven validation of the 7-signal extension. The capital is for the
serving-tier closures still pending, the hardware path, and the
design partners that will exercise the policy under workloads we
cannot synthesise in-house.

> *"Seven signals. Every block in the right tier. Every eviction justified."*

---

*Contact: Rakesh Mohan — Cognade Labs*
*Repo: `rasaha/symbolu` · Modules: `CTM_plus/KVPolicy/`, `simulator/pcam/`, `symbolu/fscs/`*
*276 tests · 20-test parity harness · 36 signal tests · real Mistral-7B FSCS trace · GPU-measured Qwen2.5-7B vLLM 0.7.3 closure (May 2026)*
