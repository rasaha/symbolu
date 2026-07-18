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

## Update — recursive refinement fixed (was a no-op, now ACTIVE)

The first pass found **recursive refinement was an effective no-op** (hidden
Δ≈2e-6, 0/130 tokens). Root cause, confirmed by the new diagnostics: the module
accumulated the **absolute** refined state gated by an ACT halting probability and
added it as `h + out`; training drove the halting prob toward 0 to suppress that
ill-scaled perturbation, collapsing the residual. The fix (no new algorithms):
accumulate gated **deltas** `block(state) − state`, add a **minimum-strength gate
floor** so it cannot reach zero, a **fixed residual scale**, an **engaged
halt-bias init**, and a **fixed-step smoke mode**.

| metric (trained `full`) | before | after |
|---|---|---|
| refinement residual norm (post-gate) | ~2e-6 | **17.5** |
| ablate refinement → tokens changed | **0 / 130** | **106 / 130** |
| ablate refinement → max logit Δ | 1.9e-6 | **5.0** |
| refinement status | **INACTIVE** | **ACTIVE** |

Refinement diagnostics after the fix (trained model): `halt_p_mean=0.031`,
`gate_mean=0.128` (floored at `min_strength=0.1`), `residual_pre_gate_norm=146.7`,
`residual_post_gate_norm=17.5`, `entropy_gate_mean=0.451`. Note the raw halting
prob is still ~0.03 — **training still tried to collapse refinement**, but the
min-strength floor held the gate at 0.128, so the delta survives. Causality is
preserved (`test_clean.py` still shows 0.0 pre-position logit change).

Everything below reflects the **after-fix** trained checkpoint.

## Execution trace (one forward)

| order | module | exec | in → out shape | Δhidden L2 |
|---|---|---|---|---|
| 0 | backbone_softmax | yes | (1,10) → (1,10,128) | — |
| 1 | typed_heads (Vritti/Aspect/Guna/Kosha) | yes | (1,10,128) → (1,10,5) | — (probe) |
| 2 | entropy_calc | yes | (1,10,128) → (1,10,3) | — (scalar field) |
| 3 | recursive_refinement | yes | (1,10,128) → (1,10,128) | **17.5** |
| 4 | deferred_insight_memory | yes | (1,10,128) → (1,10,128) | **~2.7** |

## Per-module ablation (identical seed/settings)

| ablated module | differing tokens / 130 | first divergence | max logit Δ |
|---|---|---|---|
| typed_heads (⇒ entropy=0) | **47** | 41 | 6.4e-01 |
| entropy (⇒ entropy=0) | **47** | 41 | 6.4e-01 |
| recursive_refinement | **106** | 10 | 5.0e+00 |
| deferred_insight_memory | **58** | 19 | 7.7e-01 |

Two facts jump out:
- **Refinement is now the strongest contributor** (post-fix): disabling it changes
  **106/130** tokens (max logit Δ 5.0). Before the fix it changed 0/130. See the
  "Update" section above for the root cause and minimal fix.
- **typed_heads and entropy ablations are identical** (47/130, same logit Δ). The
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
| Recursive refinement | Yes | Yes | Yes | Yes | Yes | **ACTIVE** |
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
recursive_refinement(h, entropy_vec)  ◄──────┘   ← Δh≈17.5 (post-fix)  ⇒ ACTIVE
  ↓  h'
deferred_insight_memory(h', entropy_vec) ◄───┘   ← Δh≈2.7, readiness-gated  ⇒ ACTIVE
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
3. **Influence hidden states: 2** — recursive refinement (Δ≈17.5) and deferred-insight memory (Δ≈2.7).
4. **Influence logits: 2** — refinement (logit Δ 5.0) and memory directly; entropy/heads act indirectly.
5. **Influence generated text: 7** — the 4 heads + entropy (one channel) + refinement + memory.
6. **Placeholders: 1** — mirror logic (a flag, never an operation here).
7. **Disconnected: 11** — segmentation, coupling, entropy modulation, resonance, stitching, anchors, DHA, governance, safety, personalization, multimodal.

## Final answer

**How many patent algorithms are genuinely participating in text generation today?**

**Seven** named modules change the generated tokens — the **Vritti, Aspect, Guna,
and Kosha heads**, the **entropy calculation**, **recursive refinement**, and the
**deferred-insight memory** — reducing to **three independent causal mechanisms**:

1. an **entropy signal** computed from the four typed heads (ablating the heads is
   identical to ablating entropy — they are one channel), which gates both
   actuators below;
2. **recursive refinement** — now ACTIVE after the fix (Δh≈17.5; ablation changes
   106/130 tokens; max logit Δ 5.0); and
3. the **deferred-insight memory** (Δh≈2.7; ablation changes 58/130 tokens).

**Mirror logic is a placeholder.** The remaining **eleven** patent algorithms are
**not connected** to this generation graph at all.

So: of 19 patent algorithms inspected, **3 mechanisms (driven by 7 modules) are
truly alive** in the current generation pipeline (up from 2 before the refinement
fix); 0 wired no-ops remain, 1 is a placeholder, and 11 are disconnected. (Numbers
are for this tiny char-level `full` checkpoint; the *wiring* conclusions — what is
connected vs. not — hold regardless of training, but which wired modules are
no-ops can change with a different checkpoint.)
