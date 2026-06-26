# Clean-Softmax Symbol-U Experiment

**Question:** *Does the Symbol-U patent formula improve or stabilize a normal
softmax Transformer, independent of the Hybrid Phase / Sovereign-State / JEPA / CSR
mechanisms?*

This package builds a **plain softmax decoder-only Transformer** and attaches the
Symbol-U modules as **optional, causal** augmentations, then runs an ablation
ladder with **capacity-matched controls**. It is deliberately isolated from the
Hybrid Phase stack.

## Why this is different from the Hybrid Phase LLM

| | Hybrid Phase LLM (`phase_transformer.py`) | This experiment |
|---|---|---|
| Attention | complex-phasor `a·e^{iφ}`, O(n) cumsum, `cos(φ_i−φ_j)` | **standard softmax** `scaled_dot_product_attention(is_causal=True)` |
| Latent | 32-D Sovereign State (Bhava/Kosha/Vritti/Guna) driving phase rotation | **none** — plain hidden states only |
| JEPA | EMA target + stop-grad + VICReg predictor | **none** |
| CSR | phoneme→12-D affinity injected into embeddings | **none** |
| Phase rotation | ΔBhava → per-head θ | **none** |
| Symbol-U role | fused into the backbone | **bolt-on, ablatable, causal** augmentation |

It imports **only** the generic pointwise typed heads + the Shannon-entropy helper
from `symbolu_neural.modules`. It does **not** import `symbolu_core`,
`phase_transformer`, `csr_phoneme_provider`, `jepa`, or any Sovereign code.

> **Causality is the load-bearing correctness property.** Several Symbol-U modules
> pool over the whole sequence (which would leak future tokens into earlier
> positions and fake an improvement). Here every LM-path augmentation is causal:
> the entropy-gated refinement uses causal self-attention, and the "deferred
> insight" memory reads only a causal decayed prefix. `test_clean.py` asserts that
> perturbing token *p* leaves all logits at positions `< p` **bit-identical**
> (observed max diff `0.0`).

## Files

| File | Role |
|---|---|
| `backbone.py` | `SoftmaxTransformerLM` (embed + abs-pos + causal SDPA + SwiGLU + RMSNorm + tied head) |
| `augment.py` | causal Symbol-U attachments: `TypedHeadBank`, `CausalEntropyRefinement`, `CausalPrefixMemory` |
| `model.py` | `SymbolUSoftmaxModel` — backbone + optional causal augmentations |
| `config.py` | `ExpConfig` + ablation presets |
| `data.py` / `prepare_data.py` | char-level tokenizer/dataset + corpus builder (offline, from repo `.md`) |
| `trainer.py` | `train_and_eval`, `head_grounding_control` (shuffled-label control) |
| `train.py` / `eval.py` | single-ablation CLIs |
| `run_ablations.py` | runs the ladder, prints the comparison table + adversarial verdict |
| `metrics.py` | val loss/PPL, ECE, entropy↔error corr, generation sampling |
| `test_clean.py` | shapes/backward + **causality** + param-overhead checks |

## Ablation ladder (with controls)

| Preset | What it is | Purpose |
|---|---|---|
| `baseline` | plain softmax LM | floor |
| `baseline_plus_block` | + **one plain causal block** | **fair-compute control** (does added depth alone help?) |
| `random_aug` | + Symbol-U path, **frozen random** | **capacity control** (does the path help even untrained?) |
| `typed_heads_probe` | + typed heads as probes (off LM path) | do probes harm the LM? |
| `entropy_refine` | + entropy-gated **causal** refinement on LM path | the core formula |
| `memory` | + causal deferred-insight memory | + memory |
| `full` | all causal augmentations on the LM path | full Symbol-U-on-softmax |

## How to run (CPU, no downloads)

```bash
python -m symbolu_neural.clean_softmax.prepare_data --out data/clean_lm/corpus.txt
python -m symbolu_neural.clean_softmax.run_ablations \
    --corpus data/clean_lm/corpus.txt --steps 350 --d-model 128 --layers 2 \
    --ablations baseline,baseline_plus_block,random_aug,typed_heads_probe,entropy_refine,memory,full \
    --grounding-control --sample
python -m symbolu_neural.clean_softmax.test_clean    # correctness incl. causality
```

## PASS / FAIL criteria

The formula is credited **only** if a **trained** Symbol-U ablation
(`entropy_refine` / `memory` / `full`) beats, on val loss:
1. the plain `baseline`, **and**
2. the **equal-capacity controls** (`baseline_plus_block`, `random_aug`), by a
   margin (>0.002 nats), **at comparable or lower compute** (ms/step).

If gains are matched by an equal-size plain block or by a frozen-random path, the
Symbol-U mechanism gets **no credit** — the improvement is capacity/compute, not
the formula.

## Observed result (smoke-scale; char-level; 350 steps; CPU; seed 0)

| ablation | val_loss | Δ vs base | ppl | ECE | params | ms/step |
|---|---|---|---|---|---|---|
| baseline | 2.8509 | +0.0000 | 17.30 | 0.0281 | 564k | 69 |
| baseline_plus_block (control) | **2.7816** | −0.0693 | 16.15 | 0.0284 | 826k | 98 |
| random_aug (frozen, control) | **2.7746** | −0.0763 | 16.03 | 0.0251 | 829k | 137 |
| typed_heads_probe | 2.8509 | +0.0000 | 17.30 | 0.0281 | 567k | 66 |
| **entropy_refine (formula)** | 2.8549 | **+0.0040** | 17.37 | 0.0259 | 829k | 158 |
| memory (formula) | 2.8309 | −0.0200 | 16.96 | 0.0308 | 846k | 232 |
| full (formula) | 2.8309 | −0.0200 | 16.96 | 0.0308 | 846k | 236 |

Typed-head grounding control (synthetic char labels): real vritti/aspect acc
**0.92 / 0.94** vs chance 0.20 / 0.10; globally-shuffled labels collapse to
**0.27 / 0.22** — the harness discriminates signal from leakage, but these are
**synthetic surface labels**, not real Vritti structure.

## Verdict — answer to the final question

**NO. The Symbol-U patent formula does not improve or stabilize a normal softmax
Transformer here.**

- The best **trained** formula ablation (`memory`/`full`, 2.8309) is **worse** than
  an equal-capacity **plain extra block** (2.7816) and worse than a **frozen-random**
  version of the same path (2.7746) — by ~0.05–0.06 nats — while costing **2–3×**
  the latency.
- The trained `entropy_refine` is **worse than the plain baseline** (+0.004) despite
  ~50% more parameters: training the entropy-gated refinement *hurt* relative to
  leaving it random.
- Every "−Δloss" in the table is explained by **added capacity/compute**, not the
  formula: a plain block and a random path both beat the trained mechanism.
- No calibration (ECE) or entropy↔error advantage is attributable to the formula
  (the control `random_aug` has the lowest ECE).
- Generation samples are equally incoherent across ablations at this scale (char-LM,
  350 steps) — no controllability difference observed.

**Caveats (kept honest):** this is **smoke-scale** (char-level, 2 layers, 350
steps, one seed, CPU). It is evidence of *no benefit at small scale*, not proof of
impossibility at scale. The refinement also spends more FLOPs (it re-applies its
block up to `refine_steps` times), so it is not even a compute-fair win. To
overturn this you would need a Symbol-U ablation that beats `baseline_plus_block`
at matched ms/step across multiple seeds and a larger model — which this experiment
did not find.
