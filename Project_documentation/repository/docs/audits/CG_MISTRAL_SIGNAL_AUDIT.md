# Audit: CG/Mistral Training Auxiliaries for Signal Families

**Date**: 2026-04-07
**Scope**: CSR, Guna, Ontological, Vritti signal families in the Mistral CG training/inference path
**Method**: Static analysis of source code, call graphs, default configuration, and design documents

---

## 1. Executive Answer

**Are CSR, Guna, Ontological, and Vritti all genuinely built as training auxiliaries in the Mistral CG model path?**

**Partially yes, but with critical caveats.**

All four signal families have:
- Fully implemented scorer modules (`CSRTokenScorer`, `GunaTokenScorer`, `VrittiTokenScorer`, `OntologyCompatibilityScorer`)
- Explicit auxiliary loss functions (InfoNCE contrastive losses)
- Integration into the Token Evaluation Tensor (6-column `T` matrix)
- Code paths in `train.py` that compute and add their losses to the total loss

However, **none of them are active by default**:

1. **`enable_conscious_generation` defaults to `False`** (`config.py:985`), so the entire CG module tree is never instantiated unless explicitly enabled.
2. **All four lambda weights default to `0.0`** (`config.py:1008-1010`): `lambda_csr_token=0.0`, `lambda_vritti_token=0.0`, `lambda_guna_token=0.0`, `lambda_ont=0.0`.
3. **The code guards on `any(v > 0 for v in _cg_prim_lambdas.values())`** (`train.py:5102`), so with default config, primitive auxiliary losses are never computed.
4. **None of these signals are wired into the inference/generation path.** The design document explicitly acknowledges this (Appendix F, line 5523): *"these systems exist as training-time modules and observation instruments but are not wired into the generation loop."*
5. **The field-integrated softmax (Phase 4)** that would replace standard logits with multi-field scores is gated behind `use_field_integrated_softmax`, which is controlled by a curriculum manager that requires explicit activation.

### Classification

| Signal | Status |
|--------|--------|
| **CSR** | Implemented module + loss, disabled by default, training-only, not in generation |
| **Guna** | Implemented module + loss, disabled by default, training-only, not in generation |
| **Ontological** | Implemented module + loss, disabled by default, training-only, not in generation |
| **Vritti** | Implemented module + loss, disabled by default, training-only, not in generation |

---

## 2. Signal-by-Signal Table

| Signal Family | Trained auxiliary head/loss? | Derived post-hoc? | Live inference output? | Used downstream in generation? | Verdict |
|---|---|---|---|---|---|
| **CSR** | Yes — `CSRTokenScorer` + `L_csr` (InfoNCE). But lambda=0.0 by default. | Also has `CSRInferenceGuard` (entropy sink, separate from training head) and `CSRPhonemeProvider` (deterministic phoneme lookup). | Not in generation loop. `CSRInferenceGuard` is a separate inference-time entropy monitor, not the trained scorer. | No — generation uses standard `lm_head(hidden)` logits. | **Implemented but dormant.** Module exists, loss exists, never activated by default, never influences token selection at inference. |
| **Guna** | Yes — `GunaTokenScorer` + `L_guna` (InfoNCE). But lambda=0.0 by default. | Also has: (1) `guna_derivation.py` — deterministic closed-form S/R/T from coherence+motion+entropy; (2) `SovereignGunaComputer` — information-theoretic from attention weights; (3) `InferenceGunas` — stateful approximation from token probabilities. | Multiple derived Guna representations exist at inference, but the *trained scorer* is not in the generation loop. | Inference Guna variants exist for monitoring/modulation but are separate systems from the trained auxiliary. | **Implemented but dormant (training head). Derived variants active at inference but are separate, untrained systems.** |
| **Ontological** | Yes — `TokenOntologyProjector` (linear, embed→32D) + `OntologyCompatibilityScorer` (bilinear) + `OntologicalStructureLoss` (contrastive/prototype). Lambda=0.0 by default. | The 32D Sovereign State is produced by `SovereignStateProjector` in the Mistral forward pass (always active when CG enabled), but this is not the same as the *token-level* ontological scoring. | Sovereign State (32D) is produced in forward pass. Token-level ontological scores are not in the generation loop. | Sovereign State feeds into the phase adapter (which modifies logits), but *ontological token scoring* does not influence token selection. | **Partially active.** State projection runs in forward pass. Token-level ontological scoring/loss is dormant by default. |
| **Vritti** | Yes — `VrittiTokenScorer` + `L_vritti` (InfoNCE). Also `VrittiHead` (2-layer MLP, 48D→5 classes) with separate `VrittiLoss`. Lambda=0.0 by default for token scorer. | `VrittiHead` produces 5-class predictions from R-Signal. `SovereignStateMonitor` reads Vritti slice [17:22] from 32D state. | Vritti slice exists in Sovereign State (always produced when CG active). `VrittiHead` is a separate trained classifier. Token-level Vritti scorer is not in generation loop. | `VrittiHead` + `PIDGovernor` influence gradient scaling during training. Not used in token generation at inference. | **Multiple Vritti systems exist at different levels.** `VrittiHead` is trained (with its own loss). Token-level scorer is dormant. Neither influences generation token selection. |

---

## 3. Evidence by Signal

### 3.A — CSR

**Module**: `CSRTokenScorer`
- **File**: `symbolu_training/training/conscious_generation/primitives/csr_scorer.py`
- **Architecture**: Two MLPs (token-side: 12D phoneme affinity → 16D; context-side: [hidden; onto_state] → 16D) + bilinear form (low-rank `A@B^T` or full `M`)
- **Tensor source**: Token-side from ARPABET phoneme lookup via `csr_phoneme_provider.py` → 12D affinity vector. Context-side from transformer hidden state + 32D ontological state.
- **Loss**: InfoNCE contrastive on column index 3 of Token Evaluation Tensor `T[..., 3]`
- **Instantiation**: `model_factory.py:662-668` — always instantiated when `enable_conscious_generation=True`
- **Training activation**: `train.py:5096-5115` — only computed when `lambda_csr_token > 0` (default: `0.0`)
- **Inference use**: NOT in generation loop. Separate `CSRInferenceGuard` (`agentic/inference/csr_inference.py`) is an entropy-sink mechanism that modifies logits via entropy monitoring — this is architecturally unrelated to the trained CSRTokenScorer.

**Verdict**: Trained auxiliary head exists in code. Never activated by default. Not wired into generation.

### 3.B — Guna

**Module**: `GunaTokenScorer`
- **File**: `symbolu_training/training/conscious_generation/primitives/guna_scorer.py`
- **Architecture**: Token-side: `softmax(Linear(embed_dim, 3))` → 3-class Guna profile. Context-side: `softmax(Linear(embed_dim+32, 3))`. Compatibility: `q_ctx @ G @ q_tok^T` with learnable 3×3 matrix `G`.
- **Loss**: InfoNCE contrastive on column index 5 of Token Evaluation Tensor `T[..., 5]`
- **Instantiation**: `model_factory.py:675-678`
- **Training activation**: `train.py:5096-5115` — only when `lambda_guna_token > 0` (default: `0.0`)

**Other Guna systems** (separate from training auxiliary):
1. `guna_derivation.py` — deterministic: `S = C_s*(1-H)`, `R = M*(1-|H-0.5|)`, `T = H*(1-C_s)`, normalized. Zero parameters.
2. `SovereignGunaComputer` (`agentic/sovereign/guna.py`) — information-theoretic from attention weights. Has one learnable parameter (temperature) + linear expansion 3→16D.
3. `InferenceGunas` (`agentic/inference/guna_inference.py`) — stateful approximation from token probability statistics during generation.
4. `SignalReconciliation` (`agentic/inference/signal_reconciliation.py`) — weighted blend of multiple Guna sources.

**Verdict**: Trained auxiliary exists in code, dormant by default. Multiple *derived* Guna systems active at inference, none of which are the trained auxiliary.

### 3.C — Ontological

**Module**: `TokenOntologyProjector` + `OntologyCompatibilityScorer`
- **File (projector)**: `symbolu_training/training/conscious_generation/token_ontology.py`
- **File (scorer)**: `symbolu_training/training/conscious_generation/primitives/ontology_scorer.py`
- **File (loss)**: `symbolu_training/training/conscious_generation/losses/ontological_structure.py`
- **Architecture**: Projector: `LayerNorm → Linear(embed_dim, 32)` with subgroup constraints (softmax for Bhava[0:12]/Vritti[17:22], sigmoid for Kosha[12:17]/Guna[22:28], tanh for Reserved[28:32]). Scorer: bilinear `o_t^T @ M @ o_w` (low-rank or full).
- **Loss**: Contrastive (InfoNCE) or prototype-based on 32D ontological codes.
- **Training activation**: `train.py:4909-4924` — only when `lambda_ont > 0` (default: `0.0`)

**Separate ontological system in forward pass**:
- `MistralCGWrapper.forward()` always computes `SovereignStateProjector(hidden) → 32D state` (line 269 of `mistral_wrapper.py`). This state feeds into the phase adapter that modifies logits.
- However, this is a *global* state projection (mean-pooled over sequence), not token-level ontological scoring.

**Verdict**: Token-level ontological scoring/loss exists but is dormant. Sequence-level 32D state projection is active in forward pass and affects logits through the phase adapter — but this is a different mechanism from the designed token-level ontological auxiliary.

### 3.D — Vritti

**Module (token scorer)**: `VrittiTokenScorer`
- **File**: `symbolu_training/training/conscious_generation/primitives/vritti_scorer.py`
- **Architecture**: Token-side: `softmax(Linear(embed_dim, 5))` → 5-class Vritti profile. Context-side: `softmax(Linear(embed_dim+32, 5))`. Score: dot product of two probability vectors.
- **Loss**: InfoNCE contrastive on column index 4 of Token Evaluation Tensor `T[..., 4]`
- **Training activation**: `train.py:5096-5115` — only when `lambda_vritti_token > 0` (default: `0.0`)

**Separate Vritti system**:
- `VrittiHead` (`symbolu/sovereign/vritti.py:187`): 2-layer MLP (48D R-Signal → 5 classes). Has its own `VrittiLoss` (`agentic/sovereign/train_loss.py:271-418`) with CE + transition penalty + stiffness scaling.
- `PIDGovernor` (`symbolu/sovereign/vritti.py:100-184`): Converts Vritti predictions to PID gains (Kp, Ki, Kd) that modulate gradient scaling during training.
- Vritti slice [17:22] of 32D Sovereign State: always present when CG active.

**Verdict**: Two separate Vritti systems. Token-level scorer is dormant by default. `VrittiHead` + `PIDGovernor` is a separate trained system for gradient modulation — NOT for token scoring.

---

## 4. Mistral CG Call Graph

### Model Construction
```
model_factory.py:create_model()
  └─ config.model_type == "mistral_cg"
     └─ MistralCGWrapper(model_name, quantize, ...)
        ├─ self.backbone = AutoModelForCausalLM.from_pretrained(...)  [FROZEN]
        ├─ self.state_projector = SovereignStateProjector(4096 → 32D)  [TRAINABLE]
        ├─ self.intent_projector = IntentPhaseProjector(12D → num_heads)  [TRAINABLE]
        ├─ self.phase_adapter = Linear(H→1024) → GELU → Linear(1024→4096)  [TRAINABLE]
        └─ self.adapter_gate = Parameter([-2.0])  [TRAINABLE]

  └─ if config.enable_conscious_generation:  [DEFAULT: False]
     └─ model.conscious_gen = ModuleDict({
          "token_projector": TokenOntologyProjector(4096→32D),
          "token_cache": TokenPrimitiveCache(...),
          "ontology_scorer": OntologyCompatibilityScorer(32D bilinear),
          "csr_scorer": CSRTokenScorer(12D phoneme + hidden → score),
          "vritti_scorer": VrittiTokenScorer(hidden → 5-class),
          "guna_scorer": GunaTokenScorer(hidden → 3-class),
          "token_eval_tensor": TokenEvaluationTensor(all 6 scorers),
          [+ optional: ontology_loss, integrated_scorer, field_softmax, ...]
        })
```

### Forward Pass (`MistralCGWrapper.forward()`)
```
input_ids
  │
  ▼
backbone(input_ids) ── [FROZEN, no_grad] ──→ hidden_states[-1]  [B, T, 4096]
  │
  ▼
state_projector(mean_pool(hidden)) ──→ state [B, 32]  (Bhava/Kosha/Vritti/Guna/Reserved)
  │
  ├─ delta_bhava = state[:,0:12] - prev_bhava
  │     │
  │     ▼
  │   intent_projector(delta_bhava) ──→ intent_phase [B, H]
  │     │
  │     ▼
  │   phase_adapter(intent_phase) ──→ adapter_output [B, T, 4096]
  │     │
  │     ▼
  │   adapted_hidden = hidden + sigmoid(gate) * adapter_output
  │
  ▼
backbone.lm_head(adapted_hidden) ──→ logits [B, T, V]

OUTPUTS: {logits, state, delta_S, delta_bhava, intent_phase}
```

**Key observation**: The forward pass produces `logits` and `state`. It does NOT produce CSR, Guna, Vritti, or Ontological token-level scores. Those are computed in the training loop only.

### Training Loss Computation
```
train.py training step:
  │
  ├─ outputs = model.forward(input_ids) → {logits, state, ...}
  ├─ loss = cross_entropy(logits, targets)  ── [ALWAYS]
  │
  └─ if config.enable_conscious_generation:  [DEFAULT: False]
     │
     ├─ cache.maybe_refresh(embeddings, step)  ── refresh O_tok, P_tok, R_tok, V_tok, G_tok
     │
     ├─ if lambda_ont > 0:  [DEFAULT: 0.0]
     │     loss += lambda_ont * OntologicalStructureLoss(projected_codes, targets)
     │
     ├─ if any(lambda_* > 0) AND integrated_scorer exists:  [DEFAULT: all 0.0]
     │     │
     │     ├─ T = TokenEvaluationTensor(logits, hidden, o_ctx, cache)  [B,T,K,6]
     │     │     columns: [S_base, S_ont, S_jepa, S_csr, S_vritti, S_guna]
     │     │
     │     ├─ IntegratedTokenScorer(T, hidden, o_ctx) → alpha, B, D, Z_star
     │     │
     │     ├─ if use_field_integrated_softmax:  [Phase 4, curriculum-gated]
     │     │     loss = loss - old_lm_loss + field_integrated_loss(Z_star)
     │     │
     │     ├─ if lambda_csr_token > 0:   loss += lambda * L_csr    [DEFAULT: 0.0]
     │     ├─ if lambda_vritti_token > 0: loss += lambda * L_vritti [DEFAULT: 0.0]
     │     └─ if lambda_guna_token > 0:   loss += lambda * L_guna  [DEFAULT: 0.0]
```

### Tracer/Monitor Outputs (Inference-Time, Observational)
```
GenerationTracer  ── observes logits, hidden, onto_state → trace entries (NO FEEDBACK)
SovereignStateMonitor ── reads 32D state (detached) → metrics (NO FEEDBACK)
CSRInferenceGuard ── entropy sink on hidden → possibly modifies logits (SEPARATE from trained CSR)
InferenceGunas ── token probability statistics → S/R/T approximation (SEPARATE from trained Guna)
EntropyEngine ── Guna/Kosha/domain entropy → gate decisions (T2/T3 tiers)
SignalReconciliation ── blends multiple Guna/Vritti sources → reconciled signals
```

---

## 5. Design-vs-Code Mismatch List

The design document (`Project_documentation/repository/docs/design/CONSCIOUS_GENERATION_DESIGN.md`) explicitly acknowledges these gaps in its own Appendix A and Appendix F:

| # | Design Claim | Code Reality | Source |
|---|---|---|---|
| 1 | CSR evaluates each candidate token through phonemic resonance scoring `S_csr(w) = f_csr(r_t, r_w)` | `CSRTokenScorer` exists but is never called during generation. CSR in inference is a separate entropy-sink mechanism. | Design doc Gap A1 (line ~3720) |
| 2 | Vritti produces per-token cognitive mode compatibility scores `S_vritti(w)` | `VrittiTokenScorer` exists but defaults to lambda=0.0. Vritti in practice is context-level classification via `VrittiHead`, not token-level scoring. | Design doc Gap A2 (line ~3733) |
| 3 | Guna produces per-token energetic compatibility scores | `GunaTokenScorer` exists but defaults to lambda=0.0. Runtime Guna is a separate deterministic/information-theoretic derivation, not the trained scorer. | Design doc Gap A3 (line ~3746) |
| 4 | Central equation: `Z*(w) = B(w) · Σ_f α_f · S_f(w)` replaces standard softmax | Standard `logits = lm_head(hidden)` followed by softmax. Field-integrated softmax is gated behind Phase 4 curriculum (not default). | Design doc Gap A4 (line ~3793) |
| 5 | "evaluates each candidate token through distinct but coordinated fields" (Abstract) | All four primitive scorers are training-time-only modules. Generation uses standard transformer logits. | Design doc Appendix F (line ~5523) |
| 6 | `enable_conscious_generation` implies CG is an active feature | Defaults to `False` in `config.py:985`. All four signal lambdas default to `0.0` in `config.py:1008-1010`. | `config.py:985,1008-1010` |
| 7 | Curriculum stages A→D suggest progressive activation of all primitives | Curriculum stages are specified but `CG Stage Manager` requires explicit `--enable_cg_curriculum`. Without it, no lambdas are ever ramped up. | `train.py:4881-4887` |
| 8 | Design suggests CSR, Guna, Vritti, Ontological are all "Phase 2 primitives" that score tokens | These modules are instantiated into `model.conscious_gen` but the `integrated_scorer` (Phase 3) and `field_softmax` (Phase 4) that would actually USE the scores also require their own instantiation and lambda activation. | `model_factory.py:698-721` vs `train.py:4932-4941` |

---

## 6. Summary of Findings

### What IS genuinely wired in the Mistral CG forward pass:
1. **SovereignStateProjector**: hidden → 32D state (always active when CG wrapper used)
2. **IntentPhaseProjector**: Bhava delta → phase rotation (always active)
3. **Phase adapter**: phase → hidden-space correction (always active, gated)
4. These produce a **modified hidden state** that flows through Mistral's frozen LM head

### What EXISTS as code but is DORMANT by default:
1. All four token-level scorers (CSR, Guna, Vritti, Ontological)
2. All four auxiliary losses
3. Token Evaluation Tensor assembly
4. Kosha routing, Bliss gating
5. Field-integrated softmax (Phase 4)
6. CG curriculum stage manager

### What is DERIVED (not trained) at inference:
1. Guna: deterministic `guna_derivation.py`, information-theoretic `SovereignGunaComputer`, stateful `InferenceGunas`
2. Vritti: slice [17:22] of 32D Sovereign State, `VrittiHead` predictions
3. CSR: `CSRInferenceGuard` entropy monitoring (architecturally separate from training scorer)
4. Ontological: 32D Sovereign State (sequence-level, not token-level)

### What influences generation at inference:
1. Phase adapter output (via gated residual on hidden states) — this is the ONLY CG mechanism that modifies actual token probabilities
2. `CSRInferenceGuard` can modify logits via entropy sink — but this is separate from the trained CSR auxiliary
3. `EntropyEngine` at T3 tier can gate expression — but this operates on derived signals, not trained auxiliaries

### Bottom line:
The four signal families (CSR, Guna, Ontological, Vritti) are **architecturally designed and fully implemented as training auxiliary modules**, but they are **disabled by default** and **not wired into the generation/inference path**. The Mistral CG model's actual influence on token generation comes exclusively from the phase adapter mechanism (state→phase→hidden correction), which is a coarser signal than the designed per-token multi-field scoring system.
