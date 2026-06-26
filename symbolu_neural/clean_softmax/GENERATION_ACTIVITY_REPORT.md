# Which Symbol-U Patent Algorithms Actually Participate in Generation

**Scope:** the `clean_softmax` pipeline only. Not quality, not accuracy, not a
comparison to any model. The single question: *which patent algorithms are truly
alive in the autoregressive generation graph today?*

**Method:** instrument one forward (execution order, I/O shapes, per-module hidden
Δ), run a reference generation, then **ablate one module at a time** (disable only
that module; identical prompt/seed/temperature/top-k/top-p) and diff the token
sequences. Reproduce with:

```bash
python -m symbolu_neural.clean_softmax.train --ablation full --steps 300 \
    --corpus data/clean_lm/corpus.txt --out runs/clean/full
python -m symbolu_neural.clean_softmax.inspect_generation \
    --ckpt runs/clean/full/ckpt.pt --prompt "The model " --n 120 \
    --temperature 0.8 --top-k 40 --seed 0
```

Settings used below: prompt `"The model "`, 120 new tokens, temp 0.8, top-k 40,
seed 0, `full` checkpoint (char-level, 2 layers, 300 CPU steps).

## Execution trace (one forward)

| order | module | exec | in → out shape | Δhidden L2 |
|---|---|---|---|---|
| 0 | backbone_softmax | yes | (1,10) → (1,10,128) | — |
| 1 | typed_heads (Vritti/Aspect/Guna/Kosha) | yes | (1,10,128) → (1,10,5) | — (probe) |
| 2 | entropy_calc | yes | (1,10,128) → (1,10,3) | — (scalar field) |
| 3 | recursive_refinement | yes | (1,10,128) → (1,10,128) | **2e-06** |
| 4 | deferred_insight_memory | yes | (1,10,128) → (1,10,128) | **2.66** |

## Per-module ablation (identical seed/settings)

| ablated module | differing tokens / 130 | first divergence | max logit Δ |
|---|---|---|---|
| typed_heads (⇒ entropy=0) | **83** | 29 | 5.6e-01 |
| entropy (⇒ entropy=0) | **83** | 29 | 5.6e-01 |
| recursive_refinement | **0** | — | 1.9e-06 |
| deferred_insight_memory | **71** | 13 | 8.3e-01 |

Two facts jump out:
- **Refinement changes nothing.** Its residual is `2e-06` and disabling it changes
  **0/130** tokens — it executes but is an **effective no-op** at this checkpoint
  (the ACT halting collapses its contribution to ≈0).
- **typed_heads and entropy ablations are identical** (83/130, same logit Δ). The
  heads influence generation *only* through the single entropy channel — ablating
  the heads ≡ ablating the entropy they feed. There is **one** causal sensor
  channel (entropy-from-heads) and **one** causal actuator (memory).

## Per-algorithm table

| Algorithm | Implemented | Executed | ΔHidden | ΔLogits | ΔOutput | Status |
|---|---|---|---|---|---|---|
| syllable / phoneme preprocessing | elsewhere | No | No | No | No | NOT CONNECTED |
| Vritti head | Yes | Yes | No | Indirect | Yes | ACTIVE |
| Aspect head | Yes | Yes | No | Indirect | Yes | ACTIVE |
| Guna head | Yes | Yes | No | Indirect | Yes | ACTIVE |
| Kosha head | Yes | Yes | No | Indirect | Yes | ACTIVE |
| Context–Vritti coupling | elsewhere | No | No | No | No | NOT CONNECTED |
| Entropy calculation | Yes | Yes | No | Indirect | Yes | ACTIVE |
| Entropy modulation (α'/β'/γ') | elsewhere | No | No | No | No | NOT CONNECTED |
| Recursive refinement | Yes | Yes | No | No | No | **INACTIVE** |
| Resonance coefficient (λ_res) | elsewhere | No | No | No | No | NOT CONNECTED |
| Stitching | elsewhere | No | No | No | No | NOT CONNECTED |
| Deferred Insight memory | Yes | Yes | Yes | Yes | Yes | ACTIVE |
| Experience anchors | elsewhere | No | No | No | No | NOT CONNECTED |
| Mirror logic | flag only | No | No | No | No | PLACEHOLDER |
| DHA / delivery | elsewhere | No | No | No | No | NOT CONNECTED |
| Governance gates | elsewhere | No | No | No | No | NOT CONNECTED |
| Safety boundary | elsewhere | No | No | No | No | NOT CONNECTED |
| Personalization | elsewhere | No | No | No | No | NOT CONNECTED |
| Multimodal fusion | elsewhere | No | No | No | No | NOT CONNECTED |

"elsewhere" = implemented in `symbolu_neural/modules/` (or the broader repo) but
**not wired** into this `clean_softmax` generation graph.

## Dependency graph (where each algorithm sits)

```
Prompt
  ↓
Char embedding + abs positional
  ↓
Causal softmax Transformer blocks      ← the only thing the patent does NOT touch
  ↓  hidden h
  ├─► Vritti head ┐
  ├─► Aspect head ┤
  ├─► Guna head   ┼─► entropy_calc ─► entropy_vec [B,L,3]   (SENSOR; gates below)
  └─► Kosha head  ┘                         │
  ↓                                          │ gates
recursive_refinement(h, entropy_vec)  ◄──────┘   ← executes but Δh≈2e-6  ⇒ NO-OP
  ↓  h (unchanged in practice)
deferred_insight_memory(h, entropy_vec) ◄────┘   ← Δh≈2.66, readiness-gated  ⇒ ACTIVE
  ↓  h'
LM head (tied)  ─►  logits  ─►  temp/top-k/top-p sampling  ─►  Next token

   NOT in this graph at all (bypassed):
   syllable/phoneme preprocessing · Context–Vritti coupling · entropy modulation
   (α'/β'/γ') · resonance λ_res · stitching · experience anchors · mirror logic
   (placeholder) · DHA · governance gates · safety boundary · personalization ·
   multimodal fusion
```

## Final counts

1. **Implemented (wired into this pipeline): 7** — 4 typed heads + entropy + refinement + memory.
2. **Executed during generation: 7** — all 7 run on every step.
3. **Influence hidden states: 1** — only deferred-insight memory (refinement's Δ is ~2e-6).
4. **Influence logits: 1** — only memory directly; entropy/heads act indirectly through memory's gate.
5. **Influence generated text: 6** — the 4 heads + entropy (one causal channel) + memory.
6. **Placeholders: 1** — mirror logic (a flag, never an operation here).
7. **Disconnected: 11** — segmentation, coupling, entropy modulation, resonance, stitching, anchors, DHA, governance, safety, personalization, multimodal.

## Final answer

**How many patent algorithms are genuinely participating in text generation today?**

**Six** named algorithms change the generated tokens — the **Vritti, Aspect, Guna,
and Kosha heads**, the **entropy calculation**, and the **deferred-insight
memory** — but they reduce to **two independent causal mechanisms**:

1. an **entropy signal** computed from the four typed heads (ablating the heads is
   identical to ablating entropy — they are one channel), which
2. **gates the deferred-insight memory**, the only module that actually writes the
   hidden state and moves the logits.

**Recursive refinement is wired and executes but is an effective no-op** (hidden
Δ≈2e-6; 0/130 tokens change). **Mirror logic is a placeholder.** The remaining
**eleven** patent algorithms are **not connected** to this generation graph at all.

So: of 19 patent algorithms inspected, **2 mechanisms (driven by 6 modules) are
truly alive** in the current generation pipeline; 1 is a wired no-op, 1 is a
placeholder, and 11 are disconnected. (Numbers are for this tiny char-level `full`
checkpoint; the *wiring* conclusions — what is connected vs. not — hold regardless
of training, but which wired modules are no-ops can change with a different
checkpoint.)
