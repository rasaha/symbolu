# CG Signal Aggregation Audit: Mistral CG Path

**Date:** 2026-04-07
**Scope:** Full lifecycle audit of CSR, Guna, Ontological, and Vritti signal aggregation across training, checkpointing, and inference for the Mistral-based CG path.
**Method:** Code-truth analysis only. No design-doc assumptions unless confirmed by wiring.

---

## 1. Executive Summary

**Are CG signals correctly aggregated?**

**Partially.** The architecture provides a well-structured aggregation framework, but the current state is:

- **Training-time:** CG signals (CSR, Guna, Vritti, Ontological) **can** be computed and aggregated into the training loss -- but only when explicitly enabled via `enable_conscious_generation=True` AND each signal's lambda is set to a nonzero value. **All lambdas default to 0.0 and the master toggle defaults to False.** The canonical default training path therefore runs with **zero CG signal influence on gradients**.

- **Aggregation path:** When enabled, aggregation is mathematically explicit. Signals are combined via a weighted sum into the total loss: `L_total = L_LM + lambda_ont*L_ont + lambda_kosha*L_kosha + lambda_bliss*L_bliss + lambda_csr*L_csr + lambda_vritti*L_vritti + lambda_guna*L_guna`. They are also aggregated through the IntegratedTokenScorer (Kosha routing + Bliss gating over primitive scores) and optionally into FieldIntegratedSoftmax for Phase 4 end-to-end training.

- **The core structural signal path** (state_projector -> intent_projector -> phase_adapter -> logits) **is always active** for `mistral_cg` and encodes Bhava, Kosha, Vritti, and Guna dimensions into the 32D Sovereign State, which shapes logits via a gated residual adapter. This path is trained and checkpointed. It provides **indirect influence** from CG-related dimensions.

- **Inference-time:** The canonical Mistral CG inference path (`MistralCGAdapter.call()`) uses **only the core structural path** (state_projector -> phase_adapter -> logits). It does **NOT** invoke CSR/Guna/Vritti/Ontological scorers, the TwoStageGenerator, the IntegratedTokenScorer, the KoshaPrimitiveRouter, or the BlissTokenGate. These are **training-time and diagnostic-only** in the active inference code path.

- **GenerationTracer** can optionally invoke CSR/Vritti/Kosha/Bliss scorers, but for **observation/instrumentation only** -- it does not modify generation.

**Verdict: Correctly aggregated in training (when enabled), indirectly expressed at inference through the learned state projector and phase adapter, but CG primitive heads are NOT explicitly invoked during live generation. Most CG signal paths are dormant under default configuration.**

---

## 2. Lifecycle Matrix

| Signal Family | Computed in training? | Backprop active? | Aggregated into learned state? | Checkpointed? | Inference explicit? | Inference indirect? | Loaded but bypassed? | Verdict |
|---|---|---|---|---|---|---|---|---|
| **Bhava (12D)** | Yes, always (state_projector) | Yes (adapter is trainable) | Yes (32D state [0:12]) | Yes (state_projector weights) | No (no explicit Bhava head) | **Yes** (phase_adapter residual on logits) | N/A | **Trained and indirectly expressed** |
| **Kosha (5D)** | Yes, always (state_projector [12:17]) | Yes (adapter path) | Yes (32D state [12:17]) | Yes | No explicit router at inference | **Yes** (indirectly via state_projector) | KoshaPrimitiveRouter loaded if CG enabled, but not invoked in generation loop | **Trained indirectly; router bypassed at inference** |
| **Vritti (5D)** | Yes, always (state_projector [17:22]) | Yes (adapter path) | Yes (32D state [17:22]) | Yes | No explicit scorer at inference | **Yes** (indirectly via state_projector) | VrittiTokenScorer loaded if CG enabled, but not invoked in generation | **Trained indirectly; scorer bypassed at inference** |
| **Guna (6D)** | Yes, always (state_projector [22:28]) | Yes (adapter path) | Yes (32D state [22:28]) | Yes | No explicit scorer at inference | **Yes** (indirectly via state_projector) | GunaTokenScorer loaded if CG enabled, but not invoked in generation | **Trained indirectly; scorer bypassed at inference** |
| **CSR (12D phoneme)** | Only if lambda_csr_token > 0 AND enable_conscious_generation=True | Only if lambda > 0 | Via contrastive aux loss only (not in 32D state) | CSRTokenScorer weights in conscious_gen ModuleDict | No | **No** (CSR is outside the 32D state) | Yes, if loaded | **Auxiliary-only; not on generation path** |
| **Ontological (32D)** | Only if lambda_ont > 0 AND enable_conscious_generation=True | Only if lambda > 0 | TokenOntologyProjector learns 32D manifold | TokenOntologyProjector weights saved | No | **No** (not wired into logits path) | Yes, if loaded | **Auxiliary-only; not on generation path** |
| **Phase 4 Z\*** | Only if use_field_integrated_softmax=True | Yes, replaces L_LM | Through FieldIntegratedSoftmax | TwoStageGenerator weights saved | No (not invoked in MistralCGAdapter) | Via trained primitive weights (if scorer weights were shaped) | Yes, if loaded | **Training-only; bypassed at inference** |

---

## 3. Aggregation Path (Code Detail)

### 3.1 Where per-signal outputs are produced

**In the forward pass** (`mistral_wrapper.py:310-444`):

1. **Frozen Mistral backbone** produces `hidden_states` [B, T, 4096] (line 336-342)
2. **SovereignStateProjector** (`state_projector`) projects pooled hidden -> 32D state with component-wise normalization:
   - `[0:12]` Bhava: softmax
   - `[12:17]` Kosha: sigmoid
   - `[17:22]` Vritti: softmax
   - `[22:28]` Guna: sigmoid
   - `[28:32]` Reserved: tanh
3. **IntentPhaseProjector** converts 12D Bhava delta -> per-head phase offsets [B, H]
4. **phase_adapter** maps phase offsets -> hidden-space correction [B, T, 4096]
5. **Gated residual**: `adapted_hidden = hidden + sigmoid(gate) * adapter_output`
6. **Mistral LM head** (frozen) produces logits from adapted_hidden

This is the **core structural path**. It is always active for `mistral_cg`.

**In the training loop** (`train.py:4878-5210`), when `enable_conscious_generation=True`:

7. **TokenPrimitiveCache** periodically refreshes O_tok, P_tok, R_tok, V_tok, G_tok buffers from embeddings
8. **OntologicalStructureLoss** computes L_ont (contrastive loss on 32D projections)
9. **TokenEvaluationTensor** scores top-K candidates across all primitives -> T [K, 6]
10. **IntegratedTokenScorer** applies KoshaPrimitiveRouter + BlissTokenGate -> Z* [K]
11. **PrimitiveAuxiliaryLosses** computes per-primitive contrastive losses (L_csr, L_vritti, L_guna, L_jepa)
12. **KoshaRoutingLoss** and **BlissCoherenceLoss** regularize routing/gating
13. (Phase 4 only) **FieldIntegratedSoftmax** replaces L_LM with field-integrated cross-entropy

### 3.2 How they are combined

**Loss-level aggregation** (train.py:4921, 5076, 5089, 5102-5128):
```
L_total = L_LM  (or L_field if Phase 4)
        + lambda_ont * L_ont
        + lambda_kosha_routing * L_kosha
        + lambda_bliss_token * L_bliss
        + lambda_csr_token * L_csr
        + lambda_vritti_token * L_vritti
        + lambda_guna_token * L_guna
```

This is a straightforward weighted sum. No gating, no projection, no learned combiner at the loss level.

**Representation-level aggregation** (IntegratedTokenScorer): KoshaPrimitiveRouter produces alpha [6] (routing weights per Kosha), which weights the primitive scores. BlissTokenGate produces B (coherence gate). The aggregated score Z* = B * (alpha-weighted primitive scores).

### 3.3 Whether the aggregated representation is what inference uses

**No.** At inference time (`MistralCGAdapter.call()`, lines 492-603 of `llm_adapters.py`):

- The generation loop calls `self.model(input_ids=..., attention_mask=...)` which runs MistralCGWrapper.forward()
- This produces logits through the **core structural path only** (state_projector -> intent_projector -> phase_adapter -> LM head)
- The logits are then sampled with standard top-k/top-p/temperature
- **No CG primitives, no TwoStageGenerator, no IntegratedTokenScorer, no FieldIntegratedSoftmax is invoked**
- CG metadata (state, delta_S, delta_bhava, intent_phase, adapter_gate) is captured for the sovereign bridge but is **not used to modify token selection**

---

## 4. Mistral-Specific End-to-End Call Path

### 4.1 Model Construction
```
config.model_type == "mistral_cg"
  -> model_factory.create_model(config)
    -> MistralCGWrapper(model_name, quantize, ...)
      -> Load/freeze Mistral backbone
      -> Create trainable: state_projector, intent_projector, phase_adapter, adapter_gate
    -> If enable_conscious_generation:
      -> Attach conscious_gen ModuleDict (TokenOntologyProjector, TokenPrimitiveCache,
         OntologyScorer, CSRTokenScorer, GunaTokenScorer, VrittiTokenScorer,
         KoshaPrimitiveRouter, BlissTokenGate, IntegratedTokenScorer, losses, ...)
```

### 4.2 Forward Pass (MistralCGWrapper.forward)
```
input_ids -> frozen Mistral backbone -> hidden_states [B, T, 4096]
  -> state_projector(mean_pool(hidden)) -> state [B, 32]
  -> intent_projector(delta_bhava) -> intent_phase [B, H]
  -> phase_adapter(intent_phase) -> adapter_output [B, T, 4096]
  -> adapted_hidden = hidden + sigmoid(gate) * adapter_output
  -> LM_head(adapted_hidden) -> logits [B, T, V]
```

### 4.3 Auxiliary Computation (train.py, only when enabled)
```
If enable_conscious_generation AND lambda_ont > 0:
  -> TokenOntologyProjector(target_embeddings) -> codes [B, T, 32]
  -> OntologicalStructureLoss(codes, targets) -> L_ont

If enable_conscious_generation AND any primitive lambda > 0:
  -> TokenEvaluationTensor(logits, hidden, o_ctx) -> T [B, T, K, 6]
  -> IntegratedTokenScorer(T, hidden, o_ctx) -> Z*, alpha, B, D
  -> PrimitiveAuxiliaryLosses(T, targets, candidates) -> L_csr, L_vritti, L_guna
  -> KoshaRoutingLoss(...) -> L_kosha
  -> BlissCoherenceLoss(...) -> L_bliss

If use_field_integrated_softmax (Phase 4):
  -> FieldIntegratedSoftmax(Z*, candidates, T) -> field_log_probs
  -> Replace L_LM with field-integrated cross-entropy
```

### 4.4 Loss Participation
```
loss = compute_ontological_loss(outputs, targets, config, ...)  # L_LM + sovereign terms
loss += lambda_ont * L_ont                    # Only if > 0
loss += lambda_kosha_routing * L_kosha        # Only if > 0
loss += lambda_bliss_token * L_bliss          # Only if > 0
loss += lambda_csr_token * L_csr              # Only if > 0
loss += lambda_vritti_token * L_vritti        # Only if > 0
loss += lambda_guna_token * L_guna            # Only if > 0
```

### 4.5 Checkpoint Save/Load
```
save_checkpoint:
  -> {stem}_model.pt  : model.state_dict() (includes conscious_gen ModuleDict if attached)
  -> {stem}_optim.pt  : optimizer state
  -> {stem}_meta.pt   : scheduler, step, cg_stage_manager_state, ...
  -> {stem}_aux.pt    : SRK, EvoFlow, KV supervisor, JEPA projector

load_checkpoint:
  -> model.load_state_dict(model_state, strict=False)
  -> Restores conscious_gen modules if they exist in checkpoint
```

Key: `conscious_gen` modules (primitive scorers, router, gate) are part of model.state_dict() and are saved/loaded with the model. The CG curriculum stage manager state is saved in meta.

### 4.6 Inference/Generation Path
```
MistralCGAdapter.__init__:
  -> MistralCGWrapper(model_name, ...)   # No CG modules attached (no enable_conscious_generation)
  -> model.eval()

MistralCGAdapter.call(prompt):
  -> tokenize(prompt)
  -> model.forward(input_ids)  # Core structural path only
  -> Store CG metadata (state, delta_S, delta_bhava, intent_phase, adapter_gate)
  -> Autoregressive loop:
      -> model.forward(generated_ids) -> logits
      -> Standard sampling (top-k, top-p, temperature)
      -> No CG primitive invocation
  -> Return decoded text
```

---

## 5. Canonical Path vs Optional Path

### 5.1 Default Config Path
- `enable_conscious_generation = False`
- `lambda_ont = 0.0`, `lambda_csr_token = 0.0`, `lambda_vritti_token = 0.0`, `lambda_guna_token = 0.0`, `lambda_kosha_routing = 0.0`, `lambda_bliss_token = 0.0`
- `use_field_integrated_softmax = False`
- Result: **No CG primitives computed. Only the core structural path (state_projector + phase_adapter) trains.**

### 5.2 Optional CG-Enabled Path
- Requires: `--enable_conscious_generation --lambda_ont 0.01 --lambda_csr_token 0.01 ...` (all nonzero)
- Attaches conscious_gen ModuleDict to model
- Computes CG auxiliary losses
- With `--use_field_integrated_softmax`, enables Phase 4 end-to-end training

### 5.3 Canonical Training Path (mistral_cg)
The canonical path for `mistral_cg` trains:
- **Always:** state_projector (32D with Bhava/Kosha/Vritti/Guna planes), intent_projector, phase_adapter, adapter_gate
- **Optionally:** All CG primitive modules (scorers, router, gate, losses) -- only if explicitly enabled

The 32D Sovereign State always encodes Kosha, Vritti, and Guna dimensions, and these participate in backprop through the phase_adapter -> logits path. **This is the key indirect influence mechanism.**

### 5.4 Canonical Inference Path (mistral_cg)
`MistralCGAdapter` constructs a bare `MistralCGWrapper` without `enable_conscious_generation`. No `conscious_gen` ModuleDict is attached. Generation uses only the core structural path.

Even if a checkpoint with `conscious_gen` modules were loaded, the inference adapter's generation loop (`call()` method) does not reference or invoke any CG primitive modules. They would be loaded but completely bypassed.

---

## 6. Design-vs-Code Mismatches

| Expectation (from docs/architecture) | Code Reality | Gap |
|---|---|---|
| "CG signals shape inference" | CG primitive scorers (CSR, Vritti, Guna, Ontological) are NOT invoked during generation in MistralCGAdapter | **Major gap**: Only indirect influence through trained state_projector/phase_adapter weights |
| "TwoStageGenerator for inference" | TwoStageGenerator exists and is instantiated during model creation, but MistralCGAdapter.call() never invokes it | **Bypassed module**: Training-only |
| "FieldIntegratedSoftmax replaces standard logits" | Only active during Phase 4 training. Not wired into inference | **Training-only** |
| "IntegratedTokenScorer combines primitives" | Combines during training loss computation. Not invoked at inference | **Training-only** |
| "KoshaPrimitiveRouter routes signals" | Routes during training. Not invoked at inference | **Training-only** |
| "All lambdas active by default" | All CG lambdas default to 0.0 | **Config-disabled by default** |
| "enable_conscious_generation enables CG" | Defaults to False | **Off by default** |
| "GenerationTracer captures CG signals" | Captures but does NOT modify generation (observation-only by design) | **Correct behavior** (diagnostic tool) |

---

## 7. Final Verdict

**Classification: Correctly aggregated in training (when enabled), indirectly expressed at inference through learned latent projections.**

More precisely:

### What works correctly:
1. **The 32D Sovereign State** (Bhava/Kosha/Vritti/Guna) is always trained as part of the core path and causally influences logits via the phase adapter. This is genuine, causal, indirect CG influence.
2. **When CG is explicitly enabled**, the primitive scorers, router, gate, and losses are correctly wired and aggregated via weighted sum into the training loss. The aggregation is mathematically sound.
3. **Checkpointing** correctly saves and loads all CG-related weights (both core and conscious_gen modules).
4. **The curriculum system** (Stages A-D) provides staged lambda ramp-up and is correctly wired.

### What is partially wired or dormant:
1. **CG primitive heads** (CSR, Vritti, Guna, Ontological) are NOT invoked during live generation. Their learned weights exist in the checkpoint but are bypassed in the inference loop.
2. **TwoStageGenerator** and **FieldIntegratedSoftmax** are never used at inference time despite being designed as the inference-time CG integration point.
3. **Default configuration** disables all CG-specific computation, making the canonical default path a pure Mistral + minimal state adapter.

### Causal truth by signal family:

| Signal | Causal on generation? | How? |
|---|---|---|
| **Bhava** | **Yes** | state_projector -> intent_projector -> phase_adapter -> logit modification |
| **Kosha** | **Weakly indirect** | state_projector encodes [12:17] but only Bhava delta feeds into phase_adapter; Kosha contributes to state loss but not directly to phase signal |
| **Vritti** | **Weakly indirect** | Same as Kosha -- encoded in state [17:22] but not directly fed to phase_adapter |
| **Guna** | **Weakly indirect** | Same -- encoded in state [22:28] but not directly fed to phase_adapter |
| **CSR** | **No** | Outside 32D state; auxiliary loss only; not on generation path |
| **Ontological** | **No** | Manifold loss only; not on generation path |

**Critical subtlety:** The phase_adapter takes `intent_phase` as input, which comes from `IntentPhaseProjector(delta_bhava)`. Only the 12D Bhava slice feeds into the adapter. Kosha, Vritti, and Guna dimensions exist in the 32D state and participate in the state loss through `compute_ontological_loss`, but they do **not** directly influence the phase adapter or logit modification. Their influence on logits is therefore **doubly indirect**: they participate in the state projector's backprop only insofar as the sovereign loss (not the CG primitive losses) uses the full 32D state.

### Bottom line:
The CG signal aggregation system is **architecturally complete but operationally dormant in the standard configuration and inference path**. The only signal family with a direct causal link from training to inference logit modification is **Bhava**, through the phase adapter. CSR, Guna, Vritti, and Ontological signals are either auxiliary-training-only or encoded into state dimensions that are not directly consumed by the logit-shaping adapter.

To make CG signals fully live at inference, the inference loop would need to invoke the TwoStageGenerator or IntegratedTokenScorer per generation step -- code that exists but is not wired into `MistralCGAdapter.call()`.
