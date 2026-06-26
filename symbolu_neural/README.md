# Symbol-U — Trainable Neural Architecture Skeleton

A **module-interface design** that turns the Symbol-U differentiability review
into concrete PyTorch `nn.Module`s — one per major equation group — assembled
onto a conventional backbone. This is a *serious interface skeleton*, **not** a
finished or trained model: forward passes thread the documented tensor shapes,
but the full training loop is intentionally out of scope (see milestones).

Companion documents:
- `docs/SYMBOL_U_TECHNICAL_RESEARCH_SPECIFICATION.md` — the formalized spec (EQ-ids).
- The differentiability review (this skeleton's parent analysis).

> **Status / caveats.** Smoke-tested with PyTorch 2.x CPU: `python -m
> symbolu_neural.smoke_test` constructs every ablation rung on a DummyBackbone,
> verifies the documented output shapes, composes the active losses, and confirms
> a backward pass produces gradients on the Symbol-U heads across the whole
> ladder (the `backbone_only` floor has a frozen backbone, so grad is N/A there).
> This validates the **interface contracts**, not model quality. The hard/novel
> modules (refinement, stitching, memory)
> ship **minimal reference implementations** (ACT halting, soft-top-k, NTM-style
> memory); the research-grade upgrades (DEQ implicit diff, perturbed top-k) are
> flagged in each module docstring.

---

## 1. Folder structure

```
symbolu_neural/
├── __init__.py            # package exports
├── config.py              # SymbolUConfig + patent-fixed cardinalities
├── backbone.py            # BackboneWrapper (HF causal LM) + DummyBackbone
├── model.py               # SymbolUModel — assembles all modules, returns aux dict
├── losses.py              # the 6 training objectives (+ safety BCE); stubs flagged
├── ablations.py           # the ablation ladder as config presets
├── README.md              # this design doc
└── modules/
    ├── __init__.py
    ├── segmentation.py     # EQ-A1  SoftSyllableSegmenter
    ├── typed_heads.py      # EQ-A2/A3/A4/B2 + Guna/Kosha heads
    ├── entropy.py          # EQ-C1..C5 EntropyEngine
    ├── refinement.py       # EQ-F1..F4/F6 EntropyGatedRefinementCore (ACT/DEQ)
    ├── stitching.py        # EQ-D1..D4 SoftStitchingSelector (soft top-k)
    ├── memory.py           # EQ-G1..G4 DeferredInsightMemory (KV/NTM)
    ├── anchors.py          # EQ-H1..H4 ExperienceAnchorRouter
    ├── delivery.py         # EQ-J1/J2 DeliveryHarmonizationHead (Gumbel)
    └── safety.py           # EQ-I1..I8 HardSafetyBoundary (soft scorer / hard gate)
```

## 2. Module skeleton list (one nn.Module per EQ group)

| Module | EQ | Slot in the architecture |
|---|---|---|
| `SoftSyllableSegmenter` | A1 | tokenizer-augmenting pooling bias |
| `VrittiHead` / `AspectHead` | A2/A3 | typed latent-factor heads |
| `AspectAggregator` | B2 | syllable→utterance aspect pooling |
| `GunaHead` / `KoshaHead` | (MRQ-7) | typed latent heads (pooled) |
| `ContextVrittiCoupling` | A4 | alignment scalar/regularizer |
| `EntropyEngine` | C1–C5 | control features (FiLM gate) |
| `EntropyGatedRefinementCore` | F1–F4/F6 | adaptive-depth recurrent core + router |
| `SoftStitchingSelector` | D1–D4 | differentiable selection/rerank |
| `DeferredInsightMemory` | G1–G4 | episodic memory, readiness-gated |
| `ExperienceAnchorRouter` | H1–H4 | anchor slot-memory / routing prior |
| `DeliveryHarmonizationHead` | J1/J2 | controllable tone/style head |
| `HardSafetyBoundary` | I1–I8 | soft scorer + hard constraint gate |

## 3. Tensor interface table

`B`=batch, `L`=tokens, `n`=syllable units (≈`L/stride`), `d`=`d_model`, `V`=vocab.
Cardinalities fixed: Vritti=5, aspect=10, Guna=3, Kosha=5, anchors=10, modes=3.

| Module | Input(s) | Output(s) | Params | Grad? | Aux loss | Failure mode |
|---|---|---|---|---|---|---|
| Segmenter (A1) | `x:[B,L,d]`, `mask:[B,L]` | `u:[B,n,d]`, `align:[B,n,L]` | scorer+proj | Yes (soft) | none (opt. boundary) | stride≠syllable; n heuristic |
| VrittiHead (A2) | `u:[B,n,d]` | `log p_v:[B,n,5]` | linear | Yes | **typed CE (req.)** | uninterpretable clusters |
| AspectHead (A3) | `u:[B,n,d]` | `log p_w_syl:[B,n,10]` | linear | Yes | **typed CE (req.)** | head collapse |
| AspectAggregator (B2) | `p_w_syl`, `u` | `log p_w:[B,10]` | attn | Yes | (via typed) | pooling washes out signal |
| Guna/Kosha | `h:[B,d]` | `log p_g:[B,3]`/`log p_k:[B,5]` | linear | Yes | label CE if available | provenance unknown (MRQ-7) |
| Coupling (A4) | `p_v`, `C:[B,d]` | `s_c:[B,n]` | bilinear+emb | Yes | none | weak signal |
| EntropyEngine (C1–C5) | `log p_w/g/k` | `H_D,H_G,H_K:[B]`, `λ_res:[B]`, `mod:[B,3]` | ρ,base,τ,κ | Yes | **entropy-cal** | entropy gaming; perm-invariant |
| Refinement (F1–F4/F6) | `x:[B,n,d]`, `H:[B,3]` | `refined:[B,n,d]`, `ponder`,`delta` | block+router+halt | Yes (unroll) | **stability** | no fixed-point guarantee |
| Stitching (D1–D4) | `cand:[B,K,d]`, `cand_aspect` | `stitched:[B,d]`, `sel_w:[B,K]` | rel head+θ | Soft only | task reward | grad variance; soft↔hard gap |
| Memory (G1–G4) | `state:[B,d]`, `feats:[B,4]` | `recall:[B,d]`, `readiness:[B,1]` | k/v/q/gate | Read yes | **recall (stub)** | write/read collapse; style-only |
| Anchors (H1–H4) | `state:[B,d]`, `H:[B,3]` | `mix:[B,d]`, `w:[B,10]` | anchors+query | Yes | none | dead anchors; re-oscillation |
| DHA (J1/J2) | `pooled:[B,d]`, `ctrl:[B,4]` | `style:[B,d]`, `mode_logits:[B,3]` | φ+style emb | Yes (Gumbel) | **preference (stub)** | style≠task; mode collapse |
| Safety (I1–I8) | `pooled:[B,d]`, `prov:[B]` | `admit:[B]` (hard), `soft_scores:[B,3]` | scorers | Scorer only | **safety BCE** | miscalibration; constraint boundary |

## 4. Loss table

| Loss | Fn (`losses.py`) | Inputs | When | Status |
|---|---|---|---|---|
| Next-token | `next_token_loss` | `logits`, `target_ids` | always | implemented |
| Vritti/aspect supervision | `typed_supervision_loss` | `log_p_v/w_syl`, labels | grounding | implemented (needs labels) |
| Entropy calibration | `entropy_calibration_loss` | `H_D`, per-example error | with entropy | implemented |
| Stability/convergence | `stability_loss` | `ponder_cost`, `final_delta` | with refinement | implemented |
| Safety supervision | `safety_supervision_loss` | `soft_scores`, labels | with safety | implemented (needs labels) |
| Memory recall/helpfulness | `memory_recall_loss` | rollouts | with memory | **stub (needs signal)** |
| DHA preference/style | `dha_preference_loss` | preferences | with DHA | **stub (needs labels)** |

`total_loss(aux, batch, weights)` composes only the terms whose inputs+labels
are present, so it runs unchanged across the ablation ladder.

## 5. Ablation table

| Rung | Preset (`ablations.py`) | Adds | Primary question / kill criterion |
|---|---|---|---|
| A0 | `backbone_only` | — | floor: backbone LM loss |
| A1 | `typed_heads` | A1–B2 heads | do Vritti/aspect heads beat chance? (**K1**) |
| A2 | `entropy_gating` | C1–C5 | does entropy correlate with uncertainty? (**K2**) |
| A3 | `recurrent_refinement` | F1–F4/F6 | does refinement improve loss/calibration? (**K3**) |
| A4 | `memory` | G1–G4 | does recall improve **task quality**, not just style? (**K4**) |
| A5 | `dha` | J1/J2 | does tone control help without hurting task? (**K4**) |
| A6 | `full` | +anchors+safety | does full model beat simpler adapters? (**K5**) |

## 6. Kill criteria (stop-the-program gates)

- **K1 — Grounding.** If the Vritti/aspect heads do not beat chance on held-out
  labels (or do not yield a usable downstream signal), the symbolic story is
  cosmetic → stop or redesign supervision. *This is the highest-priority gate.*
- **K2 — Entropy validity.** If entropy does not correlate with predictive
  uncertainty/error, every entropy-gated mechanism downstream is unmotivated.
- **K3 — Refinement value.** If the recurrent refinement core does not improve
  loss or calibration over A2 at matched compute, drop it (it is the costliest module).
- **K4 — Substance over style.** If memory/DHA change style/tone but not task
  quality, they are not architecture-justifying.
- **K5 — Beat the baseline.** If full Symbol-U underperforms a simple
  LoRA/adapter on the same backbone at matched parameter/compute budget, the
  architecture is not earning its complexity.

## 7. Minimum viable prototype & milestones

**MVP staging (config flags in `config.py`):**
1. **Stage 1 — heads only.** `freeze_backbone=True`, enable segmentation+typed
   heads(+entropy). Train `L_lm`(through frozen backbone is a no-op) + `L_typed`
   + `L_entcal`. Answers **K1/K2** cheaply on a small backbone.
2. **Stage 2 — partial unfreeze.** `unfreeze_last_n_backbone_layers=k`, add the
   refinement core; train `+L_stab`. Answers **K3**.
3. **Stage 3 — memory/DHA/anchors/safety** on top, with their (stubbed) losses
   implemented once labels exist. Answers **K4/K5**.
4. **Never** attempt from-scratch pretraining until A1–A3 clear K1–K3.

**Recommended first implementation milestone (Milestone 1):**
> On a tiny pretrained backbone (e.g. `sshleifer/tiny-gpt2`) with the backbone
> **frozen**, run the `typed_heads` and `entropy_gating` ablations on a small
> labeled syllable set; report (a) Vritti/aspect head accuracy vs. chance (K1),
> and (b) correlation between `H_D` and per-token NLL (K2). Ship nothing else
> until both clear. This is ~a few hundred lines of training glue on top of this
> skeleton and directly de-risks the two assumptions the whole architecture rests on.

### Quick construction example

```python
import torch
from symbolu_neural import SymbolUConfig, BackboneWrapper, SymbolUModel
from symbolu_neural.ablations import get_ablation

cfg = get_ablation("entropy_gating")
cfg.d_model = 64                              # match the backbone
bb = BackboneWrapper.dummy(vocab_size=256, d_model=64)
model = SymbolUModel(cfg, bb)

ids = torch.randint(0, 256, (2, 16))
aux = model(ids)                              # returns dict of logits + latents
print(aux["log_p_v"].shape, aux["H_D"].shape)  # [2,8,5] [2]
```
