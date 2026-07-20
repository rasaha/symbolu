# Hybrid LLM — Comparative Models Analysis

**Product:** `HybridPhaseTransformer` (Hybrid LLM) — the long-context reasoning substrate
of the Ugence Labs platform (a **Specialized AI System**; canonical taxonomy in
`UGENCE_PLATFORM_OVERVIEW.md`).
**Version:** 1.0 — July 2026
**Scope:** A model-to-model comparison of the Hybrid LLM against the competing
long-context attention families and named reference models, with an explicit
separation between *what is measured today*, *what is an analytical projection*,
and *what is roadmap*.

> **Reading discipline.** This document distinguishes three claim types and labels
> every quantitative statement as one of them:
> - **[MEASURED]** — observed in this repository's code/experiments at the stated scale.
> - **[PROJECTED]** — an analytical consequence of the architecture's complexity class
>   (a cost/complexity model), **not** a benchmarked head-to-head result.
> - **[ROADMAP]** — not yet run; named here so the comparison is honest about its gaps.
>
> The single strongest empirical result available today is a **mechanism-level** signal:
> a ~240K-parameter *pure-phase* model reaching 100% needle-in-haystack retrieval at
> 2K and 10K token distances on a **controlled synthetic task** — validating the phase
> memory mechanism, *not* the full hybrid LM stack. Head-to-head LM benchmarks
> (LRA, PPL, retrieval at scale vs. Mistral/Mamba) are **[ROADMAP]**. See
> `HYBRID_LLM_VC_BRIEF_v2.md` Page 4 for the full evidence posture.

---

## 1. What is being compared

The Hybrid LLM is a transformer whose **early layers use pure sliding-window
attention** and whose **later layers run a "Protected Phase" block** that composes
three attention mechanisms **serially over a single shared memory state**, plus an
associative slot memory:

1. **Phase attention** (O(n) linear) — complex-phasor query/key, cumulative state via
   parallel scan, information carried in **phase angle** rather than a decaying
   magnitude (no mandatory `γ < 1`).
2. **Sliding-window local attention** (O(n·w)) — cross-attends to the phase
   `memory_state` (K, V from phase memory; Q from current tokens), not to raw tokens.
3. **Binding-Cache Quad Query** (O(n·k)) — Top-K proposals over the phase memory, with
   a conditional-skip path that bypasses the quadratic branch when phase confidence is
   already high.
4. **SlotMemoryGCT** — a 64-slot associative store with writes detached from the LM
   loss, shaped by a separate retrieval loss, and re-justified by an ablation eval
   every 200 training steps.

**Reference configurations** (from the training code, `[MEASURED]` as implemented):

| Config | Params | Shape | Local / Hybrid | Window | Max seq |
|---|---|---|---|---|---|
| Reference | 46M | 768 embed × 12 layers × 12 heads | 4 local + 8 hybrid | 256 | 8K |
| 7B recipe | ~7B | 4096 embed × 32 layers × 32 heads, GQA 8 KV | 16 local + 16 hybrid | — | A100-80GB target |

The central architectural bet is **algorithmic fusion, not parallel stacking**: linear,
local, and quadratic attention are *composed* over one RMS-normalized phase memory,
rather than run in parallel and blended by a gate.

---

## 2. The comparison axis — the long-context "impossible triangle"

Every long-context attention design trades among three properties teams actually want.
The comparison below scores each family on all three:

| Property | Definition |
|---|---|
| **Global retrieval** | Content-addressable recall of distant tokens at arbitrary distance |
| **Local precision** | Sharp short-range extraction (syntax, fluency, exact copies) |
| **Efficient scaling** | Sub-quadratic time and bounded per-step memory as context grows |

The thesis of the Hybrid LLM is that these three stop being a *forced choice* and
become a *design axis* once the mechanisms are fused over a shared substrate.

---

## 3. Model-family comparison

Legend: ●●● strong · ●●○ partial · ●○○ weak. Scores for competitor families reflect
their **published design tradeoffs**; the Hybrid LLM row separates its **measured**
mechanism signal from its **projected/roadmap** system-level standing.

| Family | Representative models | Global retrieval | Local precision | Efficient scaling | Long-range memory | Primary compromise |
|---|---|---|---|---|---|---|
| **Full quadratic softmax** | GPT-4/5, Claude, LLaMA 3, Mistral-7B (dense), Qwen, DeepSeek | ●●● | ●●● | ●○○ | none (recompute) | O(n²) time/memory; KV cache grows linearly with context |
| **Linear / state-space** | Mamba/Mamba-2, RWKV, RetNet, Performer, S4, Linear Transformer | ●●○ | ●●○ | ●●● | decaying running sum | `γ < 1` decay tax; state-capacity limit on strict long-range recall ("Stuffed Mamba") |
| **Sliding-window / local** | Longformer, BigBird, Mistral sliding-window, Sparse Transformer | ●○○ | ●●● | ●●● | none outside window | blind beyond the window without hand-added global tokens |
| **Stacked / parallel hybrids** | Jamba, Zamba, Griffin/Hawk, Samba, Hymba, StripedHyena, RecurrentGemma | ●●○ | ●●● | ●●● | branch-local, unshared | two mechanisms compete for gradient; branches don't compose (no shared substrate) |
| **RAG** | LangChain/LlamaIndex + vector DB, RETRO | ●●○ (external) | ●●● | ●●● | external index | retrieval lives *outside* the model; brittle for ordered/agentic reasoning |
| **External-memory** | Memorizing Transformers, Landmark, Infini-attention, Transformer-XL, RMT | ●●○ | ●●● | ●●○ | bolt-on KV store | memory weakly differentiable; degrades to dead weight without a feedback loop |
| **Position-extension** | YaRN, NTK-aware, LongRoPE, PI | ●●○ | ●●● | ●○○ | none | a patch on quadratic models — extends *where* it looks, not *how expensively* |
| **`HybridPhaseTransformer`** | This work | **[MEASURED]** ●●● at pilot scale (240K pure-phase); **[ROADMAP]** at 46M/7B | ●●● (windowed branch retained) | ●●● **[PROJECTED]** by construction | shared phase state + 64-slot store | benchmarks at scale not yet run; system-level parity is the open question |

### 3.1 How the Hybrid LLM differs from each family — and why that is the bet

- **vs. full quadratic:** quadratic precision is invoked **conditionally** (Top-K,
  O(n·k), skipped when phase confidence is high) instead of paid on every token. The
  model keeps content-addressable precision *where it is earned* and linear-cost phase
  memory everywhere else.
- **vs. linear/SSM:** information is encoded in **phase**, not decaying magnitude — the
  retrieval ceiling is a function of phase-angle resolution rather than geometric decay.
  This is the mechanism behind the pilot's clean long-distance recall.
- **vs. sliding-window:** the window is **kept**, but it cross-attends to the phase
  memory rather than raw tokens — precise short-range extraction *from a long-range
  representation*, so hand-chosen global tokens are unnecessary (the global path is
  structural).
- **vs. stacked hybrids:** the three mechanisms run **serially over one RMS-normalized
  state**, forcing role specialization (phase produces a representation local and quad
  must consume) instead of hoping a gate balances two competing branches.
- **vs. RAG / external memory:** a learned long-range substrate lives **inside the
  forward pass**; RAG remains usable on top (complementary, not replaced). The slot
  store must re-earn its place every 200 steps via ablation, avoiding the silent
  dead-weight failure mode of bolt-on stores.
- **vs. position-extension:** the *mechanism* changes, not the coordinates — the
  long-range path is O(n) by construction rather than an O(n²) stack stretched to a
  longer window.

---

## 4. Head-to-head scorecard vs. named reference models

This is the comparison an operator actually runs. **Retrieval and PPL columns for the
Hybrid LLM are [ROADMAP] at matched parameter count** — the honest state is "runnable
recipe + validated mechanism," not a published win.

| Model | Params | Attention | Long-ctx cost curve | Strict long-range recall | Status of head-to-head vs. Hybrid LLM |
|---|---|---|---|---|---|
| **Mistral-7B** | 7B | Sliding-window + GQA | O(n·w), strong local | window-bounded; RAG/global tokens compensate | **[ROADMAP]** — matched-param PPL + retrieval is the top Q1 item |
| **Mamba-2 (2.8B)** | 2.8B | Selective SSM | O(n), constant per-step | decay-limited; "Stuffed Mamba" studies the ceiling | **[ROADMAP]** — the key linear-vs-phase comparison |
| **LLaMA 3 (8B)** | 8B | Dense softmax + RoPE/scaling | O(n²), FlashAttention constant-factor | strong (pays full cost) | **[ROADMAP]** — dense-quality reference |
| **Jamba (AI21)** | 52B (MoE) | Mamba + attention **interleaved** | mixed | branch-local, unshared | Architectural contrast: stacked vs. **serial-fused** (Section 3.1) |
| **RWKV-v6** | up to 14B | Linear RNN | O(n), constant per-step | decay-limited | **[ROADMAP]** — second linear-family point |
| **GPT-4/5, Claude** | undisclosed | Dense softmax (+ optimizations) | O(n²) class | strong (pays full cost) | Frontier quality reference; not a matched-param comparison |

**How to read this table honestly:** the Hybrid LLM's claim is *structural* — a cost
curve that is O(n) on the long-range path with quadratic precision spent conditionally —
plus a *mechanism-level* retrieval result at pilot scale. It is **not** yet a claim of
beating any row above on a standard LM benchmark. Turning each cell from [ROADMAP] to
[MEASURED] is precisely the funded work.

---

## 5. Complexity and cost analysis (analytical)

All figures in this section are **[PROJECTED]** — they follow from each mechanism's
complexity class, not from a wall-clock benchmark. They describe *what the architecture
is designed to cost*, and the throughput report that would confirm them is **[ROADMAP]**
(Pillar 1, Q2).

### 5.1 Per-mechanism complexity

| Mechanism | Time | Per-step inference memory | Role |
|---|---|---|---|
| Dense softmax (baseline) | O(n²·d) | O(n) KV cache | reference |
| Phase attention | O(n·d) | O(d²) bounded phase state (Phase State Cache, O(1) update/step) | long-range substrate |
| Sliding-window local | O(n·w·d) | O(w) | local precision, reads phase memory |
| Binding-Cache Quad Query | O(n·k·d), k ≪ n; conditionally skipped | O(k) | precision on demand |
| SlotMemoryGCT | O(n·s), s = 64 slots | O(s·d) | associative recall |

### 5.2 Cost-scaling shape vs. context length

The point of the table below is the **shape of the curve**, not a specific speedup on
specific hardware. A dense stack's compute grows with n²; the Hybrid LLM's long-range
path grows with n and invokes its quadratic branch only on Top-K proposals.

| Context | Dense softmax (relative work) | Hybrid LLM long-range path (relative work) |
|---|---|---|
| 4K | 1× | ~1× |
| 32K | ~64× | grows ~linearly + conditional Top-K |
| 128K | ~1,024× | grows ~linearly + conditional Top-K |
| 1M | ~62,500× | grows ~linearly + conditional Top-K |

> The exact multiplier at each length depends on `w`, `k`, the skip rate, and kernel
> efficiency, and must be **measured** before being quoted as a number. The defensible
> claim today is the **complexity class**, not a headline "N× cheaper" figure.

### 5.3 Memory posture

- **Dense KV cache** grows linearly with context and dominates long-context serving
  (the problem PagedAttention/PCAM manage but do not remove).
- **Phase state** is a **bounded** cumulative state with an O(1) per-step update, so the
  long-range memory footprint does not grow with n the way a KV cache does — a
  **[PROJECTED]** structural advantage whose measured magnitude is a Q2 throughput-report
  deliverable.

---

## 6. Where the Hybrid LLM should win — and where it may not

### 6.1 Favorable regimes (design-motivated)
- **Long, ordered contexts** where information position matters (agentic tool chains,
  long chat history, ordered reasoning) — RAG's weak spot, the substrate's strong spot.
- **Strict long-range retrieval at distance** — phase-angle encoding avoids the decay
  ceiling that limits linear/SSM models; this is exactly what the 240K pilot exercised.
- **Mixed retrieval + continuation workloads** in one model, without a separate
  retrieval system in the loop.

### 6.2 Regimes where it is not yet differentiated (honest)
- **Short-context, quality-bound tasks** at frontier scale — a well-tuned dense model
  pays the O(n²) tax but at 4K–8K that tax is small; the hybrid's structural advantage
  is muted where context is short.
- **Anything requiring a published benchmark today** — LRA/Path-X, matched-param PPL,
  retrieval at 32K/100K on the 46M/7B models are **[ROADMAP]**, so a procurement
  decision that demands third-party numbers cannot yet be met.

### 6.3 Principal risks to the comparison
1. **Scale transfer.** The 100% needle result is on a 240K pure-phase model; it is *not*
   yet replicated on the 46M reference or the 7B recipe. Mechanism signal ≠ system result.
2. **Fusion overhead.** Serial composition adds sequencing and normalization work; the
   throughput advantage is a projection until the Phase State Cache report lands.
3. **Ablation-negative outcomes are possible.** The slot memory and the Protected-Phase
   vs. parallel-blend ablations are designed to be able to say "this component isn't
   helping" — a scientifically honest design that can also return a null for a component.

---

## 7. Validation-state matrix (the honest bottom line)

| Claim | State | Evidence |
|---|---|---|
| Full end-to-end hybrid implemented (Local + Protected Phase + Quad + Slots) | **[MEASURED]** | `symbolu/phase_transformer.py`, `train_hybrid_7b.py` |
| Phase memory achieves long-distance recall | **[MEASURED]** at ~240K pure-phase, controlled synthetic task | internal phase-attention report |
| O(n) long-range path / bounded phase state | **[PROJECTED]** by complexity class | Section 5; Phase State Cache in `symbolu/inference/` |
| Matched-param PPL/retrieval vs. Mistral-7B / Mamba-2 | **[ROADMAP]** | Pillar 1, Q1 |
| LRA / Path-X sweep vs. Transformer/Performer/S4/Mamba | **[ROADMAP]** | Pillar 1, Q1 |
| Inference-throughput report vs. KV-cache transformer (8K–32K) | **[ROADMAP]** | Pillar 1, Q2 |
| Protected-Phase vs. parallel-blend / quad-skip / slot ablations | **[ROADMAP]** | Pillar 1, Q2 |
| 7B recipe run to a reproducible checkpoint on FineWeb | **[ROADMAP]** | Pillar 1, Q3 |

---

## 8. Summary

Positioned against the field, the Hybrid LLM is not "another linear model" or "another
stacked hybrid." Its distinguishing bets are:

1. **Serial fusion over a shared phase-memory state**, not parallel stacking with a gate —
   forcing role specialization instead of gradient competition.
2. **Phase, not magnitude**, carries long-range information — removing the `γ < 1` decay
   tax that bounds the linear/SSM family.
3. **Quadratic attention as a conditional tool**, not a default — precision spent on
   Top-K proposals where phase confidence is low, saved everywhere else.
4. **Memory that re-earns its place** via an every-200-step ablation, avoiding the
   dead-weight failure mode of bolt-on external stores.

What is **validated today** is a working training/inference stack and a mechanism-level
retrieval signal at pilot scale. What is **claimed structurally** is a long-context cost
curve that is O(n) on the long-range path with conditional quadratic precision. What is
**not yet claimed** is a benchmark win against any named model at matched parameter count —
that is the top roadmap item, and this analysis is written so that the gap between the
three is unambiguous.

---

## References (in-repo)

- `HYBRID_LLM_VC_BRIEF_v2.md` — full product brief (Pillar 1 architecture, evidence, roadmap)
- `docs/HYBRID_PHASE_QUAD_ARCHITECTURE.md` — architecture spec
- `docs/PHASE_ATTENTION_PAPER.md`, `docs/PHASE_ATTENTION_ALGORITHM.md` — phase mechanism
- `docs/FOUNDATIONAL_AI_MODELS_VS_PHASE_QUAD.md` — industry landscape (2025–2026 model efforts)
- `docs/alternative-attention-models.md` — normalization / FlashAttention / PagedAttention taxonomy
- `docs/INFERENCE_HYBRID_TRANSFORMER_GAPS.md` — inference-stack status
- `symbolu/phase_transformer.py`, `train_hybrid_7b.py` — implementation
- `UGENCE_PLATFORM_OVERVIEW.md` — canonical product taxonomy

*Contact: Rakesh Mohan — Ugence Labs · Repo: `rasaha/symbolu`*
