# CG Wrapper Bootstrap Analysis + Active-CG Variant

Quantitative analysis of whether the as-designed CG wrapper can bootstrap an *active* gate under
an LM objective, and the rationale for the opt-in **Active-CG** init. Generation-quality research
track only — no governance code.

## TL;DR (the decisive answer)

**The current (ORIGINAL) design cannot bootstrap a useful active wrapper.** Not because of the
learning rate — because of the geometry of the objective:

- At init the phase_adapter output is **exactly 0**, so `adapted_hidden = hidden` and
  `∂L/∂gate ≡ 0`. The gate has **no first-order force** to move.
- The backbone is **frozen and already competent** (PPL ≈ 7 from step 0). Any non-zero correction
  to an already-good hidden state, on average, *raises* LM loss → the adapter gradient is a
  **restoring force toward 0** (observed: `phase` grad 0.83 → 0.04 in 3 steps).
- The **only systematic force on the gate is weight decay** (`wd=0.1`), which mechanically drifts
  the raw gate up but simultaneously opens the door to a correction the LM loss trains back toward
  zero. Gate *number* drifts; *useful correction* does not appear.

So **Active-CG is required** to obtain a non-inert head to ablate — but even Active-CG most likely
yields *"active but no objective benefit"*, because the LM objective never rewards the correction.
Active-CG's value is making the pre-registered ablation **meaningful** (it tests the real
hypothesis) instead of **trivially inert**.

## 1. Gradient path (where the signal is lost)

Forward (Mistral-7B: D=4096, H=32, V=32768):
```
p   = phase_adapter(φ)                 # final Linear zero-init  → p = 0 at init
a   = RMSNorm(p)                        # eps = finfo(bf16).eps ≈ 7.8e-3
ĥ   = h + g·a,   g = sigmoid(γ), γ=-2  → g = 0.1192
L   = CE(lm_head(ĥ))
```

**Gate gradient:**
```
∂L/∂γ = g(1-g) · ⟨∂L/∂ĥ, a⟩
```
At init `a = RMSNorm(0) = 0`  ⇒  **∂L/∂γ = 0 exactly**, independent of `∂L/∂ĥ`. The gate cannot
move on signal. (`g(1-g)=0.105`, so even later the gate gradient is small.)

**Adapter (final-layer) gradient:**
```
∂L/∂W₂ = g · J_RMS(0) · ∂L/∂a ⊗ GELU(W₁φ+b₁),    J_RMS(0) = 1/√eps · I ≈ 11.3·I (bf16)
```
Non-zero (RMSNorm's Jacobian at 0 amplifies by ≈11×), so the adapter *does* get an initial kick
(matches observed `phase=0.83`). But it is a **restoring** gradient — it reduces the loss-raising
correction — so it **decays** (0.83→0.07→0.04). The adapter is being trained toward `p≈0`.

**Where signal is lost:** the gate needs `a≠0` to get gradient; `a` needs the gate open to be
worth training non-zero; and the LM loss wants `a=0` anyway. The fixed point `(a≈0, γ≈init)` is
**stable**.

## 2. Dynamics over 2k / 10k / 50k steps (ORIGINAL)

Only weight decay moves the raw gate: AdamW decoupled `Δγ = -lr·wd·γ = +0.2·lr` (γ=-2, wd=0.1).
With cosine-decayed lr (avg ≈1.5e-4):

| Steps | Δγ (WD) | γ | gate=σ(γ) | useful correction |
|------:|--------:|----:|----------:|-------------------|
| 0 | — | -2.00 | 0.119 | 0 |
| 2k | +0.06 | -1.94 | 0.126 | ≈0 |
| 10k | +0.30 | -1.70 | 0.154 | ≈0 |
| 50k | +1.5 | -0.50 | 0.378 | ≈0 (LM loss trains adapter to cancel) |

The gate *number* creeps up via weight decay, but it is not signal — and the adapter is trained to
keep the correction non-harmful (≈0). **Verdict is identical (inert / no-effect) at 2k, 10k, 50k.**
Training longer wastes GPU.

## 3. Options

| Option | P(gate active via signal) | P(affects logits meaningfully) | P(ablation measurable effect vs A) | P(measurable *benefit*) | Destabilize risk |
|--------|--------------------------:|-------------------------------:|-----------------------------------:|------------------------:|-----------------:|
| **A** current init, 50k | ~0.05 | ~0.15 | ~0.05 | ~0.03 | low (~0.05) |
| **B** gate −1.0 + adapter N(0,1e-3) | ~0.90 | ~0.90 | ~0.70 | ~0.15 | moderate (~0.15) |
| **C** separate higher LR group only | ~0.15 | ~0.40 | ~0.20 | ~0.05 | higher (~0.30) |
| **D** B + C | ~0.95 | ~0.95 | ~0.80 | ~0.20 | moderate-high (~0.25) |

Notes: **A** can't bootstrap on signal (§1–2). **C alone fails** — higher LR on a *zero* gate
gradient is still zero; it only speeds the adapter being trained toward 0 and amplifies the WD
drift. **B** is the minimal change that actually escapes the fixed point. **D** trains faster but
needs care (gate warmup, grad clip) and changes more at once. Every "benefit" probability is low
because the **objective**, not the init, is the real ceiling.

## 4. Active-CG implementation (committed, backward-compatible)

`CGBootstrapMode` in `symbolu_training/training/unified/mistral_wrapper.py`:
- `ORIGINAL` (default): gate −2.0, adapter output zero-init. **Unchanged baseline** — existing
  checkpoints, tests, and the gate=0≡base (K0) guarantee are all preserved.
- `ACTIVE` (opt-in): gate −1.0 (σ≈0.269), adapter output `N(0,1e-3)`. Non-inert from step 0.

Wired via `--cg_bootstrap_mode {original,active}` (config → model_factory → wrapper). The ablation
loader is unaffected: it loads trained weights into a fresh wrapper, so the init regime is
overwritten by the checkpoint. Tests: `tests/test_cg_wrapper_ablation.py::TestCGBootstrapMode`.

## 5. Recommended training plan (A100 80GB, Mistral-7B-v0.3, bf16)

1. **Variant:** `--cg_bootstrap_mode active` (Option B). Do **not** train ORIGINAL — it provably
   stays inert.
2. **Dataset:** wikitext-103 (real, diverse; wikitext-2 is too small to learn a useful state).
3. **Steps:** 5k, checkpointing every 1k. **Gate the run**: if by step 1k the probe shows
   `gate` rising past ~0.25 and `corr/hidden` > ~0.05, continue; else stop and reassess (don't
   burn 50k).
4. **LR:** 3e-4 base (Option B needs no separate group; add `--cg_*_lr_scale` only if adopting D).
5. **Stage-8:** keep **disabled** (`--no-stage8`) — the ablation ignores the synthesizer, so
   including it wastes capacity and confounds attribution.
6. **GPU hours:** observed ≈5.5 s/step at batch 4×accum 8. Raise to batch 16×accum 2 (80 GB has
   the room; ~14.5 GB used at batch 4) → fewer, larger steps. Budget ≈ **4–8 A100-hours** for 5k
   steps, plus **1–2 h** for the ablation eval (cap `MAX_NEW_TOKENS=128` for the first pass; the
   generation loop has no KV cache).
7. **Command:** see `train_cg_active.sh` in this directory.

Instrument every run: `CG_BOOTSTRAP_PROBE_EVERY=50` (logs gate / gate_grad / adapter_output_norm /
corr-hidden ratio / state+intent grad norms).

## Honest expectation

Active-CG makes the wrapper **active**, which is necessary for a meaningful ablation. It does **not**
make it **useful** — under LM loss on a frozen competent backbone there is no pressure for the
phase correction to improve generation. The most probable pre-registered verdict remains
`NO_EFFECT_DEPRIORITIZE` (active, changes logits, no objective gain) or a small regression. A real
quality gain would require changing the *objective* (reward the correction on a task where
ontological conditioning helps) — which is out of scope for this ablation.
