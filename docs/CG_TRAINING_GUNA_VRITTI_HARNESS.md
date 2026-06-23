# Guna-Sigmoid + Vritti Auxiliary-Training Harness (over Mistral hidden states)

> **This harness tests whether Guna/Vritti auxiliary targets can be represented or learned from Mistral
> hidden states. It does not validate Conscious Generation training, does not modify runtime behavior, and
> does not claim cognitive-state or consciousness detection.**
>
> **Bhava is not trained directly. Bhava remains an interpretive/emergent construct, not a supervised
> target in this harness.**

## Purpose
A CPU-safe / GPU-ready harness to probe whether a 32-D auxiliary symbolic-state projection over Mistral
hidden states can support a **Guna sigmoid head** and a **Vritti head** with learnable signal. First
question is representational/learnability, NOT generation quality or runtime use.

## Architecture
```
h_t ∈ R^4096                      # Mistral hidden state (NOT an attention head; head_dim = 128)
s_t = SymbolicStateProjector(h_t) # 32-D auxiliary SOVEREIGN-STATE projection (LayerNorm → Linear)
guna_scores  = sigmoid(W_g s_t + b_g) ∈ [0,1]^6      # Guna head  (multi-label → BCE)
vritti_probs = softmax(W_v s_t + b_v) ∈ Δ^4 (5 cls)  # Vritti head (single-label → cross-entropy)
```
Pooling: `last_token` (default) or `mean`. Configurable `hidden_layer` (default −1).

## Why this is NOT an attention head
Mistral's native **attention head dimension is 128-D**; the **hidden state is 4096-D**. The **32-D
auxiliary symbolic state** is a *separate trained projection over the hidden state* — a **sovereign-state
projection head**, not an attention head. Correct terms: *32-D auxiliary symbolic-state projector*,
*sovereign-state projection head*, *Guna auxiliary head*, *Vritti auxiliary head*. Do **not** say "32-D
attention head", "consciousness head", or "validated cognitive state".

## Formula provenance (sourced, NOT invented)
- **Design:** `docs/design/CONSCIOUS_GENERATION_DESIGN.md`, **Appendix D Phase 1**.
- **Canonical code:** `symbolu_training/training/conscious_generation/token_ontology.py` — 32-D layout +
  per-slice activations:
  `Bhava[0:12] softmax · Kosha[12:17] softmax · Vritti[17:22] softmax · Guna[22:28] sigmoid ·
  Reserved[28:32] tanh`.
- **Guna head = SIGMOID 6-D** (sovereign-state slice [22:28]; independent energy activations) → BCE.
  Names (`symbolu_training/jepa/state_projector.py`): `SATTVA · RAJAS · TAMAS · VELOCITY · ACCEL · STABLE`.
- **Vritti head = SOFTMAX 5-class** (slice [17:22]; cognitive-mode distribution) → cross-entropy.
  Canonical names: `PRAMANA · VIPARYAYA · VIKALPA · NIDRA · SMRITI`.
- **Disambiguation:** the token-side Guna *scorer* (`primitives/guna_scorer.py`) uses **softmax-3**
  (Sattva/Rajas/Tamas) for bilinear token–context scoring; the **sovereign-state Guna slice is
  sigmoid-6**. This harness follows the **sovereign-state Guna-SIGMOID** formula (the task's spec). The
  canonical future `p_g` (softmax-3D) is a *separate* projection and is **not** used here.

## Guna sigmoid definition
`guna_scores = sigmoid(W_g · s_t + b_g)` → 6 independent activations in [0,1]; multi-label → binary
cross-entropy with logits. Do **not** treat as a probability distribution / compute entropy unless
explicitly normalized.

## Vritti definition
5-class cognitive-mode distribution `softmax(W_v · s_t + b_v)`; single-label → cross-entropy.

## Training modes
- **dry-run** — random hidden states, no model download; verify shapes / loss / grad. CPU-safe (needs
  torch; a CPU pod is fine). → `CG_GUNA_VRITTI_SHAPE_ONLY_PASS`.
- **probe / head-only (default)** — load Mistral **frozen**, extract hidden states, train **projector +
  heads only**. Base model is not modified.
- **LoRA (optional, future)** — hook present but **DISABLED by default**; enabling requires a separate
  pre-registration.

## Dataset schema (JSONL)
```json
{ "id": "ex_001", "prompt": "...", "response": "...",
  "labels": { "guna": [0,1,0,0,1,0], "vritti": "pramana" },
  "metadata": { "source": "audit_derived | human | synthetic | placeholder",
                "term": "...", "domain": "...", "split": "train" } }
```
`labels.guna` = 6 binary values (sigmoid targets). `labels.vritti` ∈
{pramana, viparyaya, vikalpa, nidra, smriti}. Only a tiny **synthetic fixture** exists today
(`data/cg_training/guna_vritti_synthetic_fixture.jsonl`), every row tagged
`SYNTHETIC_FIXTURE_ONLY_NOT_VALIDATION` — it is for **plumbing only** and cannot validate learnable signal.

## Metrics
- **Guna (sigmoid):** BCE · per-dimension AUROC · macro/micro AUROC · calibration (mean pred vs mean
  label) · label prevalence.
- **Vritti (softmax):** cross-entropy · accuracy · macro-F1 · per-class F1 · confusion matrix · prevalence.
- **General:** split counts · synthetic-vs-real label source · seed · model id · hidden layer · pooling.

## Decision labels
`CG_GUNA_VRITTI_HARNESS_READY · CG_GUNA_VRITTI_FORMULA_UNAVAILABLE · CG_GUNA_VRITTI_SHAPE_ONLY_PASS ·
CG_GUNA_VRITTI_SYNTHETIC_ONLY · CG_GUNA_VRITTI_NO_LEARNABLE_SIGNAL · CG_GUNA_VRITTI_LEARNS_SIGNAL ·
CG_GUNA_VRITTI_ENV_UNAVAILABLE`.
- Synthetic labels → `SYNTHETIC_ONLY` (cannot validate signal). Real labels + macro-AUROC ≥ 0.60 or
  Vritti macro-F1 above chance → `LEARNS_SIGNAL`; else `NO_LEARNABLE_SIGNAL`.
- **If formulas were ever missing/ambiguous → `FORMULA_UNAVAILABLE` and NO formula is invented.** (Not the
  case here — formulas were sourced.)

## Limitations
- **No real labels.** Only a synthetic plumbing fixture exists, so the harness cannot yet show learnable
  signal — any run on it is `SYNTHETIC_ONLY`.
- Probe over a single pooled hidden state; not a sequence model.
- A positive `LEARNS_SIGNAL` would mean the targets are *decodable from hidden states*, NOT that they are
  useful for generation or runtime (that would need separate pre-registrations).

## Current validation status
*Guna/Vritti auxiliary-training harness is implemented and shape-tested. It is ready for a real
labelled-data probe on Mistral hidden states, but it does not yet validate Guna/Vritti as useful training
signals.* Bhava is not trained directly; no runtime path changed; LoRA off by default.
