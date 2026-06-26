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

## Generation smoke test (`generate.py`)

**This is only a generation smoke test** — it answers one question: *can the clean
softmax Symbol-U model load a checkpoint and emit tokens autoregressively, end to
end?* It is **not a quality benchmark** and makes **no claim of improvement** over
any baseline.

`generate.py` supports: `--prompt`, `--max-new-tokens`, `--temperature` (0 = greedy),
`--top-k`, `--top-p`, `--seed`, and `--ckpt` (any ablation's checkpoint). It builds
the tokenizer from the checkpoint's saved vocab (no corpus needed).

```bash
# 1) train a tiny checkpoint (checkpoints are gitignored; regenerate locally)
python -m symbolu_neural.clean_softmax.prepare_data --out data/clean_lm/corpus.txt
python -m symbolu_neural.clean_softmax.train --corpus data/clean_lm/corpus.txt \
    --ablation full --steps 300 --d-model 128 --layers 2 --block 128 \
    --out runs/clean/full          # -> runs/clean/full/ckpt.pt

# 2) generate
python -m symbolu_neural.clean_softmax.generate --ckpt runs/clean/full/ckpt.pt \
    --prompt "The model " --max-new-tokens 200 --temperature 0.8 --top-k 40 --seed 0
```

**Observed output (honest, full ablation, 300 CPU steps, char-level, val ppl≈17.5):**

```
prompt    : 'The model '
generated : 'trute; patededethse, aithhererisinathe me ticour, s llllios areis |
             — | | | | | |# | fd | | |-| | (1 |-| |-| |-| | R14 pr-1;-Dat | Rensy
             D1 Tlontetrencherlancee | bindatindecteandinthinde preal p_ri'
```

It is **incoherent** — as expected for a tiny char-level model trained for 300 CPU
steps. But it is unmistakably autoregressive: it emits English-like character
fragments (`are`, `pr`, `preal`) and reproduces the markdown table pipes (`| | |`)
that dominate the corpus. Greedy (`--temperature 0`) collapses into a repeat loop
(`ate (at (at …`), and `--top-p 0.9` produces different but equally incoherent text
— all three sampling paths run end to end without error.

**Answer to the only question asked — can it load and generate tokens end-to-end?**
**Yes.** The checkpoint loads, the tokenizer rebuilds from saved vocab, and the
model generates tokens autoregressively under temperature / top-k / top-p / greedy.
Output quality is not evaluated and not claimed.

## Which patent algorithms are actually active? (`inspect_generation.py`)

`inspect_generation.py` instruments the generation graph and ablates one module at
a time (same prompt/seed/temp/top-k/top-p) to determine, per patent algorithm,
whether it is connected, executed, changes hidden states/logits/tokens, or is an
effective no-op. Full results and the dependency graph are in
[`GENERATION_ACTIVITY_REPORT.md`](GENERATION_ACTIVITY_REPORT.md).

```bash
python -m symbolu_neural.clean_softmax.inspect_generation \
    --ckpt runs/clean/full/ckpt.pt --prompt "The model " --n 120 \
    --temperature 0.8 --top-k 40 --seed 0 --json-out runs/clean/inspect.json
```

**Headline finding (tiny `full` checkpoint):** of 19 patent algorithms inspected,
7 are wired into this pipeline and execute; only **2 independent mechanisms truly
move the generated tokens** — the entropy signal (from the 4 Vritti/Aspect/Guna/
Kosha heads) and the deferred-insight memory it gates. **Recursive refinement is a
wired no-op** (hidden Δ≈2e-6; 0/130 tokens change), **mirror logic is a
placeholder**, and the other **11** algorithms are **not connected**.

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
