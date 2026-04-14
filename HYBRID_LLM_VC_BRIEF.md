# Hybrid LLM — VC Brief

**Cognade Labs | `HybridPhaseTransformer` — Algorithmic Fusion of Linear, Sliding-Window, and Binding-Cache Attention**
*Prepared April 2026*

---

## Page 1 — The Problem

### The long-context attention tradeoff remains only partially solved.

Modern LLMs pay for their capability with a well-known attention
tradeoff, and no dominant production architecture fully resolves it.
Each of the three major families in production today makes a
deliberate compromise on one of the three properties teams actually
want from long-context attention — **global content-addressable
retrieval**, **local precision**, and **efficient scaling** — and
then compensates for that compromise with additional mechanisms:

| Attention family | What it does well | The compromise, and how the field has compensated |
|---|---|---|
| **Full quadratic softmax** (GPT, LLaMA, Claude API) | Rich, content-addressable retrieval across the whole context | O(n²) time and memory. The field has compensated with FlashAttention, KV-cache tricks, sparse patterns, and retrieval augmentation — all of which work *around* the quadratic cost rather than removing it. |
| **Sliding-window / local attention** (Mistral sliding-window, Longformer) | O(n·w) scaling, very fast, excellent for short-range syntax and fluency | No direct attention path to information outside the active window without extra mechanisms. Longformer itself pairs the window with explicit **task-motivated global attention tokens**; Mistral's sliding-window paper frames the window as an *efficiency* move rather than a full replacement for global attention. Local attention is not presented as a complete long-context solution even by its own authors. |
| **Linear / state-space attention** (Mamba, RWKV, Performer, S4) | O(n) scaling, constant per-step inference memory | The recurrent state is a compressed running sum, and recent work (including the 2024 "Stuffed Mamba" line of research on state collapse and state capacity) directly studies the limits of RNN-style state for strict long-range retrieval. Linear-time scaling is real; lossless long-range retrieval at arbitrary distances is still an active research question. |

In other words, the current production stack is *"partially solved,
with compensating mechanisms"*, not *"solved"*. In practice, teams
deploying long-context LLMs pick one of these families and then spend
significant engineering effort compensating for its weakness —
KV-cache tricks, sparse patterns, retrieval augmentation, aggressive
truncation, reranking. Those compensations usually act *around* the
attention mechanism rather than inside it.

### Why stacked hybrids so far have not fully closed the gap

A growing number of recent papers and open-source models layer two
attention mechanisms together — *some* layers full, *other* layers
local, or a linear recurrent state side-by-side with a small window.
These approaches help measurably, and we think they are directionally
right. But in most public hybrids we have studied, the two mechanisms
still **stack** rather than fuse: each runs on the same input tokens
in parallel, and the model is left to blend their outputs with a
weighted sum or a gate. In our view, that leaves two structural issues
on the table:

1. **Gradient competition.** When two attention heads attack the same
   token stream in parallel, they tend to fight over the same
   gradient signal during training. The stronger mechanism can
   dominate and the weaker one can become vestigial, which undercuts
   the point of the hybrid.
2. **No shared memory substrate.** A linear-attention branch produces
   a running state. A local-attention branch reads raw tokens.
   Because they typically operate on different representations,
   neither can use what the other has computed — they coexist, but
   they do not *compose*.

We think the interesting question is not *"which attention mechanism
is best?"* but *"can linear, local, and quadratic attention be
algorithmically fused so that each mechanism operates on the output of
the others, with a shared long-range memory substrate that all three
can read?"* If the answer is yes, the tradeoff in the table above
becomes a design axis rather than a forced choice, and the cost
profile of long-context inference changes materially. That is the
question our `HybridPhaseTransformer` is built around.

---

## Page 2 — The Architecture

### `HybridPhaseTransformer` — three attention mechanisms composed serially over a shared phase-memory state

Our Hybrid LLM is a transformer in which early layers use pure
sliding-window attention and later layers run a **Protected Phase**
block that composes linear phase attention, sliding-window attention,
and a top-K binding cache **serially** over a shared memory state —
plus an associative slot memory that stores content beyond what layer
weights can absorb.

### Layer structure

```
  input tokens
      │
      ▼
  Token + position embedding (+ dropout)
      │
      ▼
  ┌─────────────────────────────────────────────────┐
  │  Layers 0..(L-1) — Local only                   │   O(n · w)
  │  LocalTransformerBlock (FlashAttention or SDPA) │   sliding-window
  │  Learns: bigrams, syntax, short-range patterns  │
  └─────────────────┬───────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────┐
  │  Layers L..(N-1) — Hybrid                        │
  │  HybridTransformerBlock (Protected Phase)       │
  │   ├── PhaseAttention       O(n)   ── produces    │
  │   │    memory_state  [B, N, H, D_h]              │
  │   ├── LocalAttention       O(n·w) ── cross-      │
  │   │    attends to memory_state (K, V), not x     │
  │   └── BindingCacheQuadQuery  O(n·k) ── Top-K     │
  │        proposals over memory_state                │
  │  + SlotMemory read/write per layer (assoc. KV)   │
  └─────────────────┬───────────────────────────────┘
                    │
                    ▼
  LayerNorm → LM Head (× learnable logit_scale)
```

The current default configuration is a 46M-param reference
(768 embed × 12 layers × 12 heads, 4 local + 8 hybrid, 256-token
window, 8K max seq len) and a 7B-class model (`train_hybrid_7b.py`:
4096 embed × 32 layers × 32 heads, GQA 8 KV heads, 16 local + 16
hybrid) for A100-80GB training. The 7B recipe uses 4-bit quantization,
gradient checkpointing, an 8-bit optimizer, and torch.compile.

### Phase attention — the linear core

Phase attention is our O(n) linear mechanism. Each token emits a
query and key as **complex phasors** — learned amplitude × complex
exponential at a learned phase angle, with the key phase conjugated.
The cumulative state at each position is the running sum of all prior
`k · v` outer products, computed via parallel scan:

```
  State_t = State_{t-1} + K_t · V_t         # O(n) cumulative sum
  Out_t   = Re( Q_t · State_t )             # real-part readout
```

Unlike Mamba / RWKV / Performer, there is no `γ < 1` decay baked into
the state. Information is encoded in **phase** rather than magnitude,
so the default phase branch does not impose mandatory exponential
decay, which in principle allows older information to remain
recoverable through phase-aligned queries. The amplitude gate is
sigmoided (with a floor to prevent gradient collapse), each head
learns its own phase offset, and an optional per-head decay factor
is available as an explicit forgetting knob when the task wants one. An internal
technical report on the phase-attention mechanism documents a small
(~240K-param) pure-phase model reaching 100% needle-in-haystack
retrieval accuracy at both 2K and 10K token recall distances on a
controlled retrieval task (full retrieval benchmarks on larger models
are on the roadmap — see Page 3).

### The algorithmic fusion — Protected Phase

This is the part we think is genuinely novel. In "Protected Phase"
mode, the three mechanisms do **not** run in parallel on the input
tokens. They run **serially, over a shared state**:

1. **Phase attention runs first** on the input tokens and produces a
   cumulative `memory_state` at every position. This state is
   RMS-normalized to keep its magnitude bounded.
2. **Sliding-window local attention then cross-attends to the
   memory_state**, not to the raw tokens. Its Q comes from the
   current tokens; its K and V come from the phase memory. Local
   attention is therefore doing *precise short-range extraction
   from a long-range representation*, rather than competing with
   phase for the same gradient.
3. **A Binding-Cache Quad Query** optionally runs on top, producing
   **Top-K proposals** from the phase memory at O(n·k) cost (not
   O(n²)), with a conditional-skip path that bypasses the quadratic
   branch entirely when phase confidence is already high enough.

The result is a single forward pass in which the linear branch
establishes long-range context, the windowed branch extracts local
detail from that context, and the quadratic branch is invoked only
where it is actually earning its cost. Because the three mechanisms
are composed serially over a shared state, **the design is intended
to reduce direct gradient competition and force clearer role
specialization** — phase has to learn a representation that local
and quad can consume, and local and quad have to learn to read from
it. A legacy parallel-blend mode is retained behind a flag for
ablation.

### Slot memory — associative recall beyond layer weights

On top of the hybrid attention stack, each hybrid layer reads from
and writes to a 64-slot associative key-value store
(`SlotMemoryGCT`). Writes use competitive cosine routing and are
**detached from the LM loss**, so the main cross-entropy cannot
corrupt slot contents; slots are shaped by a separate retrieval loss
applied only at positions beyond the sliding window. An ablation eval
runs every 200 training steps that toggles slot reads off and reports
the resulting PPL delta, which is then used as an adaptive signal
for slot learning rate, gate ceiling, and retrieval loss weight. In
other words, the slots only keep earning their place if the
ablation says they are helping.

---

## Page 3 — Competitive Landscape

`HybridPhaseTransformer` lives in the most crowded, most actively
researched corner of modern LLM architecture — long-context attention.
Nearly every major lab has an answer to the quadratic problem, and
the open literature now contains a growing list of hybrid architectures
that stack two mechanisms together. The table below positions us
against each family of alternative, stating for every row both *how*
we differ and *why* that difference is an advantage.

| Category | Representative players | What they ship | How `HybridPhaseTransformer` differs — and why it is better |
|---|---|---|---|
| **Full quadratic transformers** | GPT-4/5, Claude, LLaMA 3, Mistral-7B, Qwen, DeepSeek | Standard dense softmax attention, scaled with FlashAttention, KV-cache tricks, and RoPE extensions to reach long contexts. | We do not fight quadratic attention on its own cost curve — we invoke it *conditionally*, only where phase confidence is already low, via the Binding-Cache Quad Query's Top-K O(n·k) path. **Better because:** the operator gets the content-addressable precision of quadratic attention exactly on the tokens that need it, and linear-cost phase memory everywhere else — the same model no longer has to pay the O(n²) tax on every position to earn occasional retrieval quality. |
| **Linear / state-space models** | Mamba / Mamba-2, RWKV, RetNet, Performer, Linear Transformer, S4 | O(n) recurrent or linearized state machines that compress context into a running hidden state, typically with an exponential decay (`γ < 1`) baked into the recurrence. | These models encode information in **magnitude** with a decaying running sum — which is why the recent "Stuffed Mamba" line of research finds structural state-capacity limits on strict long-range retrieval. Our phase branch encodes information in **phase**, not magnitude, with no mandatory `γ < 1` — older information remains recoverable via phase-aligned queries. **Better because:** the retrieval ceiling is a function of phase-angle resolution rather than geometric decay, which is the mechanism behind a 240K-param pure-phase model reaching 100% needle-in-haystack at 10K tokens on a controlled task. Linear cost is preserved; the decay tax is not. |
| **Sliding-window / local attention** | Longformer, BigBird, Mistral sliding-window, Sparse Transformer | O(n·w) local attention over a fixed window, usually paired with a handful of task-defined global tokens to reach long-range dependencies. | Local attention is strong at short-range syntax and silent outside its window. We keep sliding-window attention — but in the Protected Phase block, **it cross-attends to the phase memory, not to raw tokens**. Its queries come from current tokens; its keys and values come from the long-range phase state. **Better because:** the window now does *precise short-range extraction from a long-range representation*, instead of competing with a separate global mechanism for gradient. Longformer's hand-chosen global tokens are no longer necessary, because the global path is structural. |
| **Stacked / parallel hybrids** | Jamba (AI21), Zamba, Griffin / Hawk (DeepMind), Samba, Hymba, StripedHyena, RecurrentGemma | Interleave Mamba/SSM blocks with transformer blocks, or run two attention mechanisms in parallel and blend their outputs with a gate. | Stacked hybrids are directionally right but, in our view, leave two issues unresolved: two heads on the same token stream fight for the same gradient (the weaker mechanism often becomes vestigial), and a linear branch and a local branch operate on different representations and cannot compose. Our Protected Phase block runs the three mechanisms **serially over a single RMS-normalized `memory_state`** — phase produces the state, local attention reads it, quad proposes on top of it. **Better because:** the architecture *forces* role specialization rather than hoping for it — phase has to learn a representation that local and quad can consume, and each mechanism earns its place by operating on the output of the others, not by racing them. |
| **Retrieval-augmented generation** | LangChain / LlamaIndex + vector DBs (Pinecone, Weaviate, Chroma, pgvector), RETRO-style retrieval-conditioned LMs | Sidestep long context entirely by chunking corpora and retrieving top-K passages into a short context window at inference time. | RAG is a **preprocessing** strategy: it moves the long-range problem out of the model and into a separate retrieval system. That is fine for document Q&A and brittle for agentic tool chains, long chat histories, and ordered reasoning where the position of information matters. **Better because:** we give the model a learned long-range memory substrate *inside* the forward pass, so the same architecture handles both retrieval-shaped and continuation-shaped workloads. RAG remains usable on top; we are complementary to it, not a replacement for its use cases. |
| **External-memory / cached-context architectures** | Memorizing Transformers, Landmark Attention, Infini-attention, Transformer-XL segment recurrence, RMT | Attach an external KV store or segment-level recurrent state that the attention layer queries alongside its own window. | External-memory designs keep attention unchanged and bolt a second, often weakly-differentiable store alongside it. **Better because:** our `SlotMemoryGCT` is a 64-slot associative memory whose writes are detached from the LM loss and shaped by a separate retrieval loss applied beyond the window, with an every-200-step ablation eval that adaptively adjusts slot LR, gate ceiling, and retrieval-loss weight. Slots only keep earning their place if the ablation says they are helping — no silent dead weight, no "add more memory and hope" failure mode. |
| **Context-extension via position encoding** | RoPE extensions — YaRN, NTK-aware scaling, LongRoPE, PI (Positional Interpolation) | Rescale or interpolate existing rotary embeddings to make a model pre-trained at 4K–8K extrapolate to 32K–1M tokens, without architecture change. | Position-extension methods are a **patch** applied to quadratic models — they extend where the model *can look* without changing how expensively it looks. The model still pays O(n²) at the new context length, still has no long-range memory substrate, and still relies on training-time priors to recall distant information. **Better because:** we change the mechanism, not the coordinates. An operator is not picking between YaRN and our model; they are picking between "a 32K-capable quadratic stack whose cost scales with context" and "a hybrid stack whose long-range path is O(n) by construction and whose quadratic branch is invoked only where it is earning its cost." |
| **Efficient attention implementations** | FlashAttention (1/2/3), PagedAttention (vLLM), Ring Attention, xFormers | Kernel-level and memory-layout optimizations that make standard softmax attention faster and more memory-efficient on existing hardware. | These projects are **substrate**, not a thesis about long-range attention. They accelerate whichever attention mechanism is already chosen. **Better because:** `HybridPhaseTransformer` composes with FlashAttention exactly the way any other transformer does (the local branch uses SDPA / FlashAttention directly) — the operator gets the FlashAttention speedup *and* the hybrid's structural cost reduction, rather than having to choose between them. |

### Why the overall bet is better, not just different

- **Serial fusion over a shared state, not parallel stacking.** Every hybrid architecture we know of runs its two mechanisms in parallel and blends the outputs. We run three mechanisms — linear phase, sliding-window local, and Top-K binding-cache quad — **serially over a single RMS-normalized phase memory**. That is the architectural bet: composition, not blending, and a shared substrate that forces each mechanism to earn its role by consuming what the previous one produced.
- **Phase, not magnitude, carries long-range information.** The entire linear-model family encodes state as a decaying running sum. We encode it as a running sum of complex phasors with per-head phase offsets and no mandatory `γ < 1`. The mechanism-level evidence — a 240K-param pure-phase model hitting 100% needle-in-haystack at 10K tokens on a controlled task — is the first signal that the decay tax is not necessary for linear-time attention to work at long distances.
- **Quadratic is a tool, not a default.** The Binding-Cache Quad Query runs at O(n·k) on Top-K proposals and is conditionally skipped when phase confidence is already high enough. Quadratic precision is spent exactly where it is needed and saved everywhere else — the opposite of the status quo, which pays quadratic cost on every token to earn occasional retrieval quality.
- **Memory that has to prove itself every 200 steps.** `SlotMemoryGCT` is the only long-term memory in this landscape that runs its own ablation eval against the live model during training and adaptively shrinks or grows itself based on the PPL delta. An external KV-store bolted onto a transformer has no such feedback loop, which is why most of them quietly degrade into dead weight.
- **Honest scope on what is validated today.** We do not claim benchmark wins on LRA, Path-X, or head-to-head vs. Mamba / Mistral at 7B — those are explicitly the Q1 roadmap item. What we claim is a working training stack, a validated phase-memory mechanism at pilot scale, and an architecture whose structural bet (serial fusion over shared phase memory) is implemented, runnable, and ready to be measured against the baselines in the table above.

### In one sentence

Every other entry in this landscape either **pays the quadratic tax
everywhere**, **stacks two mechanisms in parallel and lets them
fight for gradient**, **decays its long-range memory into a running
sum**, or **sidesteps long context by retrieving around it**.
`HybridPhaseTransformer` is a bet that the next step is **algorithmic
fusion** — linear, local, and quadratic attention composed serially
over a shared phase-memory substrate — so that the tradeoff in the
Page 1 table becomes a design axis rather than a forced choice.

### The broader stake (honest framing)

The structural bet here — **linear-time long-range recall without a
decay tax** — is the kind of primitive that future, more ambitious
architectures will need whether they reach AGI or not; we are not
claiming to solve intelligence, we are claiming to remove one of the
limits that any solution to it will have to navigate.

---

## Page 4 — Evidence, Training Recipe & Roadmap

### What is built and training today

| Area | State |
|---|---|
| `HybridPhaseTransformer` end-to-end | Implemented in `symbolu/phase_transformer.py` with Local-only, Protected-Phase, Binding-Cache Quad Query, and SlotMemoryGCT modules composed in a single training loop. |
| Reference configuration | 46M params — 768 embed × 12 layers × 12 heads, 4 local + 8 hybrid, 256 window, 8K max seq len, tied embeddings, learnable logit scale. |
| 7B-class training recipe | `train_hybrid_7b.py` — 4096 embed × 32 layers × 32 heads, GQA 8 KV heads, 16 local + 16 hybrid, 4-bit quantization, 8-bit optimizer, gradient checkpointing, torch.compile, A100-80GB target. |
| Linear / phase branch | O(n) cumulative-sum scan with complex phasors, three readout modes (`standard`, `shifted`, `complex`), per-head phase offsets, optional per-head decay, chunked sequence support for arbitrarily long documents. |
| Binding-Cache Quad Query (V10.4) | Top-K proposal mode with conditional skip when phase confidence exceeds a threshold. |
| Slot memory | 64 slots, detached write path, retrieval loss beyond the window, every-200-step ablation eval, adaptive slot LR controller with bootstrap → adaptive → stabilize phases. |
| Inference path | `symbolu/inference/` module with Fast / Standard / Sovereign modes, Phase State Cache for O(1) per-step phase update, and V11.0.0 inference filters (Vritti gate, Kosha depth control, Sovereign Bridge). `generate_sovereign.py` CLI is wired end-to-end. Status doc: `docs/INFERENCE_HYBRID_TRANSFORMER_GAPS.md` — the inference stack is implemented end-to-end; remaining work is benchmark and scale validation. |
| Training-time instrumentation | `SovereignPhaseController`, `AdaptiveTrainingController`, and `AdaptiveSlotLRController` — surgical gradient clipping per numerical regime (slot keys on unit sphere, phase sin/cos amplification, global norm), PPL-alpha curriculum, adaptive warmup on validation PPL rather than fixed steps. |

### Preliminary retrieval signal (separate research report)

An internal phase-attention technical report documents a **small
240K-parameter pure-phase model** hitting **100% accuracy on a
controlled needle-in-haystack retrieval task at 2,048 and 10,000
token recall distances**. This is a deliberately isolated retrieval
benchmark — it validates the core phase-memory mechanism, not the
full hybrid language-modeling stack, and it does not replace standard
LM benchmarks. We treat it as a **mechanism-level signal**, not a
product-level claim. A formal LM benchmarking pass on the hybrid model
is explicitly on the roadmap below.

### Training recipe (honest summary)

| Setting | Default |
|---|---|
| Optimizer | AdamW with separate parameter groups for main and slot weights; optional 8-bit via bitsandbytes |
| LR schedule | Linear warmup → cosine annealing, warmup can be driven by PPL threshold instead of fixed step count |
| PPL-α curriculum | `alpha_phase` and `alpha_local` interpolated between 0.8 and 0.3 based on current PPL regime; post-curriculum adaptive α driven by slot ablation delta |
| Loss composition | `L_CE + L_router + w_retr · L_retrieval + w_pred · L_slot_prediction + L_entropy_band (opt) + L_decorrelation (opt)` |
| Gradient management | Per-element clip 0.005 on phase fused projections, per-element clip 0.01 on slot keys, separate norm clips for slot and phase, global norm clip, gradient throttle on spikes |
| Dataset support | WikiText-103, FineWeb (7B recipe), synthetic smoke harnesses |

### Honest scope caveats

We want VCs to see exactly what is validated at what scale, because
the interesting benchmarks on this architecture are still ahead of us:

| Topic | Current reality |
|---|---|
| Needle-in-haystack retrieval accuracy | Validated on a small (~240K-param) pure-phase model on a controlled synthetic task. Not yet replicated on the full 46M reference or the 7B recipe. |
| Long Range Arena / LRA tasks | Discussed in the internal report, **not yet run end-to-end** on our hybrid model at competitive scale. |
| Head-to-head vs. open-weights baselines | Side-by-side comparisons against Mistral, LLaMA, or Mamba at matched parameter count are **not yet published**. They are the top roadmap item. |
| 7B training status | `train_hybrid_7b.py` is runnable and the recipe is set, but the training run is operator-driven on an A100-80GB environment, not a push-button repo result. |
| Binding-Cache Quad Query | Implemented with Top-K proposal mode and conditional skip; ablation data vs. pure Protected-Phase is the most useful next experiment and is planned. |
| Slot memory ablation | The every-200-step ablation eval is live and feeds adaptive controllers — but "slots helping / hurting" is a relative signal inside our own training run, not an external benchmark. |

### Next 12 months

**Quarter 1 — External benchmarking pass**
- Full Long Range Arena (LRA) sweep at matched parameter count against Transformer, Performer, Linear Transformer, S4, Mamba baselines — specifically on Path-X and Retrieval where linear-decay models struggle.
- Needle-in-haystack retrieval at 2K / 10K / 32K / 100K tokens on the 46M reference model and a 1.3B intermediate, not just on the 240K pilot.
- Publish a head-to-head report (PPL and retrieval) vs. Mistral-7B and Mamba-2.8B at matched parameter budget.

**Quarter 2 — Binding-Cache Quad Query ablations and inference throughput**
- Publish ablation data isolating the contribution of (i) Protected Phase vs. parallel blend, (ii) Binding-Cache Quad Query with and without conditional skip, (iii) slot memory with and without reads.
- Ship an inference-throughput report using the Phase State Cache (O(1) per-step phase update) against a standard KV-cache transformer at matched context length, focused on the 8K–32K range where hybrid should shine.

**Quarter 3 — Scale the 7B recipe end-to-end**
- Run the `train_hybrid_7b.py` recipe to completion on FineWeb against a reproducible checkpoint.
- Validate the same hybrid recipe on an open-weights backbone-hybrid path (`mistral_hybrid_wrapper.py`) so the architecture is shown to be backbone-agnostic, not tied to our from-scratch model.
- First external research preview release (weights + eval harness).

**Quarter 4 — Product coupling**
- Expose the Hybrid LLM as a first-class backend adapter for the Agentic Framework, so governed agents get long-context hybrid inference without rewiring.
- Begin work on a paper submission documenting the Protected-Phase serial-fusion architecture and the LRA / retrieval ablations.

### The ask

We are raising seed capital to take `HybridPhaseTransformer` from a
working training stack with a validated phase-memory mechanism to a
**benchmarked, published, and productized** long-context LLM
architecture. The research risk is concentrated in well-identified
places — LRA and retrieval sweeps at scale, the 7B training run, and
ablations that isolate each of the three fused attention mechanisms —
and the implementation risk is reduced because the training recipe,
inference path, and adaptive controllers are already built; the
remaining uncertainty is concentrated in scale training and external
benchmarking. What capital funds is specifically: benchmarking
against open-weights baselines at matched parameter count, finishing
and publishing the 7B training run, and maturing the hybrid backend
into a first-class option behind the Agentic Framework.

---

*Contact: Rakesh Mohan — Cognade Labs*
*Repo: `rasaha/symbolu` · Modules: `symbolu/phase_transformer.py`, `train_hybrid_7b.py`, `symbolu_training/training/unified/mistral_hybrid_wrapper.py`, `symbolu/inference/`*
*Architecture ref: `docs/HYBRID_PHASE_QUAD_ARCHITECTURE.md` · Training CLI: `docs/TRAIN_HYBRID_7B.md` · Inference status: `docs/INFERENCE_HYBRID_TRANSFORMER_GAPS.md` · Mechanism report: `docs/PHASE_ATTENTION_PAPER.md`*
