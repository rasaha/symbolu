# Hybrid LLM — VC Brief

**Cognade Labs | `HybridPhaseTransformer` — Algorithmic Fusion of Linear, Sliding-Window, and Binding-Cache Attention**
*Prepared April 2026*

---

## Page 1 — The Problem

### The attention tradeoff that has not actually been solved.

Modern LLMs pay for their capability with a fundamental attention
tradeoff. The three families in production today each give up
something material:

| Attention family | What it does well | What it gives up |
|---|---|---|
| **Full quadratic softmax** (GPT, LLaMA, Claude API) | Rich, content-addressable retrieval across the whole context | O(n²) time and memory — pushes long-context inference into hardware regimes that burn cost and latency |
| **Sliding-window / local attention** (Mistral, Longformer-style) | O(n·w) scaling, very fast, excellent for syntax, bigrams, and short-range fluency | No mechanism to reach information outside the window; long-range retrieval degrades quickly |
| **Linear / state-space attention** (Mamba, RWKV, Performer, S4) | O(n) scaling, constant per-step inference memory | State is a compressed running sum; older tokens fade via exponential decay, so strict long-range *retrieval* is lossy |

In practice, teams deploying LLMs in production pick one of these
families and then spend significant engineering effort compensating
for its weakness — KV-cache tricks, sparse patterns, retrieval
augmentation, aggressive truncation, reranking. Each compensation is
*around* the attention mechanism, not inside it.

### Why hybrids so far have not closed the gap

Several recent papers and open-source models have layered two
attention mechanisms together — *some* layers full, *other* layers
local, or a linear recurrent state side-by-side with a small window.
These approaches help, but they usually stop at **stacking**: each
mechanism runs on the same input tokens in parallel, and the model is
left to blend their outputs with a weighted sum or a gate. That has
two structural issues:

1. **Gradient competition.** When two attention heads attack the same
   token stream in parallel, they fight over the same gradient signal
   during training. The stronger mechanism tends to dominate and the
   weaker one becomes vestigial, which undercuts the point of the
   hybrid.
2. **No shared memory substrate.** A linear-attention branch produces
   a running state. A local-attention branch reads raw tokens.
   Because they operate on different representations, neither can use
   what the other has computed — they coexist, but they do not
   *compose*.

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
so old tokens do not vanish exponentially — they can be "tuned back
in" by a query at a matching phase. The amplitude gate is sigmoided
(with a floor to prevent gradient collapse), each head learns its own
phase offset, and an optional per-head decay factor is available as
an explicit forgetting knob when the task wants one. An internal
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
are serial, **they do not compete for gradient** — phase is forced
to learn a representation that local and quad can consume, and local
and quad are forced to learn to read from it. A legacy parallel-blend
mode is retained behind a flag for ablation.

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

## Page 3 — Evidence, Training Recipe & Roadmap

### What is built and training today

| Area | State |
|---|---|
| `HybridPhaseTransformer` end-to-end | Implemented in `symbolu/phase_transformer.py` with Local-only, Protected-Phase, Binding-Cache Quad Query, and SlotMemoryGCT modules composed in a single training loop. |
| Reference configuration | 46M params — 768 embed × 12 layers × 12 heads, 4 local + 8 hybrid, 256 window, 8K max seq len, tied embeddings, learnable logit scale. |
| 7B-class training recipe | `train_hybrid_7b.py` — 4096 embed × 32 layers × 32 heads, GQA 8 KV heads, 16 local + 16 hybrid, 4-bit quantization, 8-bit optimizer, gradient checkpointing, torch.compile, A100-80GB target. |
| Linear / phase branch | O(n) cumulative-sum scan with complex phasors, three readout modes (`standard`, `shifted`, `complex`), per-head phase offsets, optional per-head decay, chunked sequence support for arbitrarily long documents. |
| Binding-Cache Quad Query (V10.4) | Top-K proposal mode with conditional skip when phase confidence exceeds a threshold. |
| Slot memory | 64 slots, detached write path, retrieval loss beyond the window, every-200-step ablation eval, adaptive slot LR controller with bootstrap → adaptive → stabilize phases. |
| Inference path | `symbolu/inference/` module with Fast / Standard / Sovereign modes, Phase State Cache for O(1) per-step phase update, and V11.0.0 inference filters (Vritti gate, Kosha depth control, Sovereign Bridge). `generate_sovereign.py` CLI is wired end-to-end. Status doc: `docs/INFERENCE_HYBRID_TRANSFORMER_GAPS.md` (all phases marked complete). |
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
and the engineering risk is manageable because the training recipe,
inference path, and adaptive controllers are already built. What
capital funds is specifically: benchmarking against open-weights
baselines at matched parameter count, finishing and publishing the
7B training run, and maturing the hybrid backend into a first-class
option behind the Agentic Framework.

---

*Contact: Rakesh Mohan — Cognade Labs*
*Repo: `rasaha/symbolu` · Modules: `symbolu/phase_transformer.py`, `train_hybrid_7b.py`, `symbolu_training/training/unified/mistral_hybrid_wrapper.py`, `symbolu/inference/`*
*Architecture ref: `docs/HYBRID_PHASE_QUAD_ARCHITECTURE.md` · Training CLI: `docs/TRAIN_HYBRID_7B.md` · Inference status: `docs/INFERENCE_HYBRID_TRANSFORMER_GAPS.md` · Mechanism report: `docs/PHASE_ATTENTION_PAPER.md`*
