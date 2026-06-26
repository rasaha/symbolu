# Clean-Softmax Symbol-U — Training & Diagnostics Report

**Question (not "is it better"):** when the active Symbol-U mechanisms (typed
heads → entropy, recursive refinement, deferred-insight memory) are trained
longer, how do they behave, and what should be improved next?

**Run:** CPU (`torch 2.x`), seed 0, char-level corpus (329k chars, vocab 176),
`d_model=128`, 2 layers, 4 heads, block 96, batch 16, **600 steps/ablation**,
val every 100. Reproduce: `python -m symbolu_neural.clean_softmax.run_training_study
--steps 600 --block 96`. No superiority claim is made; an equal-capacity control
(`baseline_plus_block`) matched the augmented runs in the earlier experiment, so
val-loss gains below are attributable to **added capacity, not the formula**.

## Training summary

| ablation | val_loss | ppl | ECE | H↔err | params | ms/step | actN | refineR | memR |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 2.830 | 16.94 | 0.033 | 0.286 | 560k | 45 | 444 | — | — |
| typed_heads_probe | 2.830 | 16.94 | 0.033 | 0.286 | 563k | 44 | 444 | — | — |
| entropy_refine | 2.763 | 15.85 | 0.024 | 0.305 | 825k | 99 | 458 | 171 | — |
| memory | 2.753 | 15.70 | 0.023 | 0.295 | 842k | 102 | 458 | 160 | 151 |
| full | 2.753 | 15.70 | 0.023 | 0.295 | 842k | 101 | 458 | 160 | 151 |

(`full` == `memory`: both presets = typed_heads + entropy_refine + memory.
`typed_heads_probe` == `baseline`: probes do not touch the LM path.)

## Training curves (val loss)

All curves decrease monotonically — **training is stable, no divergence**:

```
baseline       : 3.205 3.013 2.947 2.899 2.853 2.830
entropy_refine : 3.166 3.004 2.911 2.858 2.827 2.763
memory / full  : 3.156 2.977 2.905 2.834 2.811 2.753   (steps 100..600)
```

## Per-module diagnostics (the key finding)

Refinement gate / halting probability over training (`entropy_refine`):

| step | refine_gate_mean | refine_halt_p | refineResid | Hmean | Hstd |
|---|---|---|---|---|---|
| 1 | 0.893 | 0.881 | 305 | 1.514 | 0.485 |
| 200 | 0.105 | 0.005 | 210 | 0.444 | 0.501 |
| 400 | 0.104 | 0.004 | 176 | 0.543 | 0.598 |
| 600 | 0.101 | 0.001 | 171 | 0.654 | 0.555 |

**The optimizer drives the refinement halting probability to ≈0.001.** Refinement
stays active *only* because the `min_strength=0.1` floor pins the gate at ~0.10 —
i.e. the mechanism is **forced-on, not earned**. The earlier no-op fix made it
participate; this run shows training would re-collapse it if the floor allowed.
Memory's readiness gate behaves similarly (residual settles ~150). Typed-head
entropy does **not** collapse: `Hstd` stays ~0.5 (positions remain differentiated).

Residual-to-activation ratios at step 600: refinement 171/458 = **0.37**, memory
151/458 = **0.33** — substantial but **below 1.0**, so neither overpowers the
hidden state.

## Generation diagnostics (5 fixed prompts, seed 0, temp 0.8, top-k 40)

Honest: **all ablations are incoherent** at this scale (char-level, 600 CPU
steps). Samples are English-ish fragments plus corpus markdown artifacts
(`|`, `*`, `EQ-`, `τ`). Prompt `"The "`:

```
baseline       : '[ruteding, + ode sonfoliv`. ad | ` | Domecerche | mares `. | | (alimoncformer ...'
entropy_refine : 'truted blendy de torfolicher agad athe m pomecurche ans ias areis | -*********Curpupy ...'
memory / full  : 'trute; EQ-D4, denth, — I3 L2 agad athentretickery telereres areis. **** d perumurpuptats ...'
```

distinct-char ratio ~0.24–0.30 across all; longest repeat run: baseline 3,
**entropy_refine 9** (`-*********`), memory 4. So refinement introduces a *mild
repetition artifact* (a run of `*`), and no ablation is meaningfully more coherent
than baseline.

## Failure-mode assessment

| failure mode | observed? | evidence |
|---|---|---|
| refinement overpowering hidden state | No | refineR/actN = 0.37 (< 1.0) |
| memory overpowering hidden state | No | memR/actN = 0.33 (< 1.0) |
| entropy heads collapsing | No | Hstd ~0.5 maintained through training |
| loss instability | No | val curves monotone; grad norm not pinned at clip |
| generation repetition | **Mild** | entropy_refine longest run 9 (`****`); low distinct ratio is corpus-driven |
| no meaningful difference from baseline | Partial | refine/memory differ (Δval≈0.07) but it's **capacity**, not the formula; typed-probe ≡ baseline |
| high latency | **Yes** | refine/memory ~100 ms/step vs 45 (≈2.2×) |
| poor calibration | No | ECE 0.023–0.033 (refine/memory slightly *lower* than baseline) |
| exploding / vanishing residuals | No | residuals bounded & stable (~150–180) |

## Improvement plan (per active mechanism)

**Typed heads → entropy.** Active, stable, does not collapse — but its only effect
on generation is *indirect* (it gates refinement and memory; ablating heads ≡
ablating entropy). *Recommended:* **keep**, and **add a loss** — turn on the
entropy-calibration term (`--entropy-cal`) or a grounding objective so entropy
becomes a meaningful, supervised signal rather than a free latent. Do not increase
strength.

**Recursive refinement.** Active but **forced-on** (optimizer drives halt→0.001;
floor holds it at 0.10), adds ~2.2× latency and a mild repetition artifact, and its
val gain over plain baseline is matched by a plain extra block. *Recommended:*
**reduce strength + regularize** — lower `refine_min_strength` (0.1→0.05) and/or
`refine_steps` (3→1) to cut latency and the artifact; **add a contribution-gated
loss** that rewards refinement only when it lowers NLL (so it is earned, not
pinned). Do not increase strength; do not disable (it is genuinely wired now).

**Deferred-insight memory.** Active, stable, healthy residual (0.33 ratio), best
val of the three; readiness-gated. *Recommended:* **keep as-is**, lower priority to
change; **regularize** the readiness gate lightly and monitor it for the same
forced-on pattern. It is the most "earned" of the three.

## Final mechanism table

| Mechanism | Active? | Stable? | Helpful? | Problem | Recommended Fix |
|---|---|---|---|---|---|
| Typed heads → entropy | Yes (gates the others; no standalone Δ) | Yes (Hstd~0.5, no collapse) | Indirect only | ungrounded latent; effect only via refine/memory | add entropy-calibration / grounding loss; keep |
| Recursive refinement | Yes (gate floored at 0.10) | Yes (residual ~170, bounded) | Marginal (Δval = capacity, not formula) | optimizer drives halt→0.001 (forced-on); 2.2× latency; mild repetition | reduce min_strength/steps; add contribution-gated loss; regularize |
| Deferred-insight memory | Yes (readiness-gated) | Yes (residual ~150, stable) | Marginal (Δval = capacity) | same forced-on risk; latency | keep; regularize readiness; monitor |

## Answer

**What happens when the active Symbol-U algorithms are trained longer?** They train
**stably** (smooth monotone val-loss decrease, no divergence, no collapse, no
overpowering of the hidden state, good calibration). Refinement and memory are
genuinely active (33–37 % of activation norm) and don't destabilize training.

**What needs to be improved next?** Three things, in order: (1) **the mechanisms
are forced-on, not earned** — the optimizer pushes the refinement gate to ~0 and is
held up only by the min-strength floor, so they need an *objective that rewards
their contribution* before they can be said to help; (2) **generation is incoherent
and the val-loss gains are explained by added capacity** (a plain extra block
matches them) — so the next experiment must re-run the `baseline_plus_block`
control at this longer horizon and judge the formula against it, not against the
plain baseline; (3) **latency is ~2.2×** — cut refinement steps/strength. No
failure mode is catastrophic; the model is trainable, but there is **no evidence
yet that the Symbol-U mechanisms help beyond the parameters they add**.

## GPU / RunPod

No CUDA was available in this environment; the study ran on CPU. The runner
auto-detects CUDA (`--device cuda` to force). On a RunPod GPU pod:

```bash
# pod: any PyTorch image, e.g. runpod/pytorch:2.4.0-py3.11-cuda12.4
pip install torch --index-url https://download.pytorch.org/whl/cu124   # if needed
git clone <repo> && cd symbolu && git checkout claude/patent-research-spec-tsdnjv
python -m symbolu_neural.clean_softmax.prepare_data --out data/clean_lm/corpus.txt
# larger run (uses CUDA automatically):
python -m symbolu_neural.clean_softmax.run_training_study \
    --steps 4000 --block 256 --batch 64 --d-model 384 --layers 6 --val-every 200
# single ablation + checkpoint:
python -m symbolu_neural.clean_softmax.train --ablation full --steps 4000 \
    --block 256 --d-model 384 --layers 6 --out runs/clean/full --corpus data/clean_lm/corpus.txt
python -m symbolu_neural.clean_softmax.generate --ckpt runs/clean/full/ckpt.pt \
    --prompt "The model " --max-new-tokens 300 --temperature 0.8 --top-k 40
```
