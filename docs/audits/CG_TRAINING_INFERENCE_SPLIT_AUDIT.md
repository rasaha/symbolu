# CG Training / Inference Split Audit

**Date:** 2026-04-07
**Scope:** Mistral-CG path only
**Branch:** `claude/audit-cg-signal-aggregation-HltyO`

## Desired Architectural Policy

| Layer     | Policy                                                        |
|-----------|---------------------------------------------------------------|
| Training  | Full CG stack: Bhava, Vritti, Guna, Ontological, CSR          |
| Inference | Minimal safe causal subset only                               |

### Desired Inference Allowances

| Signal       | Desired inference role          |
|--------------|--------------------------------|
| Bhava        | Direct (causal via phase adapter) |
| Vritti       | Small bounded gate (temperature only, cool-only) |
| Ontological  | Indirect / audit-only          |
| Guna         | Indirect / audit-only          |
| CSR          | Not direct                     |

---

## Signal-by-Signal Comparison Matrix

### 1. Bhava (state\[0:12\], softmax)

| Aspect | Training | Inference | Desired | Verdict |
|--------|----------|-----------|---------|---------|
| Produced | Yes — `SovereignStateProjector` emits 32D; Bhava = \[0:12\] | Yes — `MistralCGWrapper.forward()` returns full state including Bhava | Produced in both | **Matches** |
| Consumed causally | Yes — `IntentPhaseProjector` takes delta-Bhava (12D) → phase adapter → gated residual on logits | Yes — same forward pass executes at inference; phase adapter output modulates logits | Direct causal link at inference | **Matches** |
| Loss contribution | `phase_alignment_loss` on Bhava delta; `sovereign_state_loss` on full 32D | N/A | Training only | **Matches** |

**Overall: Matches desired split.**
Bhava is the only signal with a direct causal path into logit generation. The `IntentPhaseProjector` (V11.0.0) explicitly narrowed its input from 32D to 12D Bhava-only, and its docstring states that control signals (Koshas/Vrittis/Gunas) belong in the control plane, not phase rotation. This is exactly the desired architecture.

---

### 2. Vritti (state\[17:22\], softmax)

| Aspect | Training | Inference | Desired | Verdict |
|--------|----------|-----------|---------|---------|
| Produced | Yes — `SovereignStateProjector` with softmax constraint | Yes — state tensor contains Vritti at \[17:22\] | Produced in both | **Matches** |
| Training loss | `VrittiTokenScorer` when `lambda_vritti_token > 0` (default: 0.0) | N/A | Training only | **Matches** |
| Inference consumption | N/A | Vritti gate reads `state[0, 17:22]`, computes `error_risk = ERROR + 0.3 * IMAGINATION`, cools temperature to `min(temp, 0.5)` when risk > 0.5. Gate is off by default (`enable_vritti_gate=False`). | Small bounded, cool-only | **Matches** |
| Causal impact | Through loss gradient only (when enabled) | Temperature modulation only — no logit modification, no token filtering | Bounded, non-destructive | **Matches** |

**Overall: Matches desired split.**
The Vritti gate (added in this branch) implements exactly the desired "small bounded gate" policy: temperature-only, cool-only, off by default, hardcoded thresholds, no logit manipulation. The `VrittiTokenScorer` CG primitive is training-only and defaults to off. The V11.0.0 `OntologicalBindingCacheInferenceEngine` precedent (non-Mistral path) uses an analogous Vritti gate with the same pattern.

---

### 3. Guna (state\[22:28\], sigmoid)

| Aspect | Training | Inference | Desired | Verdict |
|--------|----------|-----------|---------|---------|
| Produced | Yes — `SovereignStateProjector` with sigmoid constraint | Yes — state tensor contains Guna at \[22:28\] | Produced in both | **Matches** |
| Training loss | `GunaTokenScorer` when `lambda_guna_token > 0` (default: 0.0) | N/A | Training only | **Matches** |
| Ablation role | `use_guna_bias` controls adapter gate on/off in `MistralCGWrapper` | Same forward pass — adapter gate active if trained with it | Training structural | **Matches** |
| Inference consumption | N/A | Not consumed by any inference-side code beyond being carried in `last_cg_metadata['state']` | Indirect / audit-only | **Matches** |
| Sovereign bridge | N/A | `sovereign_bridge._kosha_to_budget()` reads Kosha, not Guna; no Guna-specific bridge exists | Audit-only | **Matches** |

**Overall: Matches desired split.**
Guna values are present in the 32D state at inference but are not read by any inference-time decision logic. The `use_guna_bias` ablation config controls whether the adapter gate was trained with Guna influence, but at inference time the gate simply applies whatever weights were learned — the Guna slice is not separately extracted or acted upon. This matches the "indirect / audit-only" desired policy.

---

### 4. Ontological (via `OntologyCompatibilityScorer`)

| Aspect | Training | Inference | Desired | Verdict |
|--------|----------|-----------|---------|---------|
| Training loss | `OntologyCompatibilityScorer` when `lambda_ontology_compat > 0` (default: 0.0) | N/A | Training only | **Matches** |
| Ontological loss | `compute_ontological_loss()` operates on token embeddings + concept graph, not on the 32D state | N/A | Training only | **Matches** |
| Inference consumption | N/A | Not consumed. `TwoStageGenerator` was designed for ontological re-ranking at inference but is **never wired** into `MistralCGAdapter.call()`. | Indirect / audit-only | **Matches** |
| V11.0.0 precedent | N/A | `OntologicalBindingCacheInferenceEngine` uses ontological compatibility in the non-Mistral path | Separate path | N/A |

**Overall: Matches desired split.**
The ontological signal is training-only in the Mistral-CG path. The `TwoStageGenerator` exists in code but is dead code at inference — it is imported but never called from `MistralCGAdapter.call()`. This matches the desired "indirect / audit-only" policy. The non-Mistral inference engine (`OntologicalBindingCacheInferenceEngine`) does use ontological signals, but that is a separate path and out of scope for this audit.

---

### 5. CSR (Cognitive State Regulation)

| Aspect | Training | Inference | Desired | Verdict |
|--------|----------|-----------|---------|---------|
| Standalone CSR path | `enable_csr` + `csr_provider` in `train.py` (lines 321-338, 817-838). Older system, separate from CG primitives. | Not wired into `MistralCGAdapter`. | Not direct at inference | **Matches** |
| CG primitive CSR path | `CSRTokenScorer` when `lambda_csr_token > 0` (default: 0.0) in CG primitive system. | Not wired into `MistralCGAdapter`. | Not direct at inference | **Matches** |
| Dual-path concern | Two independent CSR systems exist in training code with separate toggles (`enable_csr` vs `lambda_csr_token`). Both default to off. | Neither reaches inference. | Training-side complexity | **Partially matches** |

**Overall: Matches desired split (with caveat).**
Neither CSR path reaches inference, matching the "not direct" desired policy. However, the existence of two independent CSR training paths (older standalone and newer CG primitive) is a maintenance concern — it is not a split violation but is noted as a design-hygiene issue. If CSR were ever promoted to inference, the dual-path ambiguity would need resolution first.

---

### 6. Kosha (state\[12:17\], sigmoid)

| Aspect | Training | Inference | Desired | Verdict |
|--------|----------|-----------|---------|---------|
| Produced | Yes — `SovereignStateProjector` with sigmoid constraint | Yes — state tensor contains Kosha at \[12:17\] | Produced in both | **Matches** |
| Training loss | Part of `sovereign_state_loss` on full 32D; no dedicated Kosha scorer | N/A | Training only | **Matches** |
| Inference consumption | N/A | `sovereign_bridge._kosha_to_budget()` reads Kosha → `action_complexity`, `completeness_score`. Used by agentic framework for budget decisions, not for logit/token generation. | Indirect / audit-only | **Matches** |
| V11.0.0 precedent | N/A | `OntologicalBindingCacheInferenceEngine` has Kosha depth control (top-k/temp by depth). Not in Mistral path. | Separate path | N/A |

**Overall: Matches desired split.**
Kosha is present in the 32D state and read by the sovereign bridge for agentic budget signals, but does not influence token generation. This matches "indirect / audit-only". The V11.0.0 Kosha depth control in `OntologicalBindingCacheInferenceEngine` is a separate non-Mistral path.

---

### 7. Reserved (state\[28:32\], tanh)

| Aspect | Training | Inference | Desired | Verdict |
|--------|----------|-----------|---------|---------|
| Produced | Yes — `SovereignStateProjector` with tanh constraint | Yes — carried in state tensor | N/A | **Matches** |
| Consumed | Not consumed by any training loss or inference logic | Not consumed | N/A — reserved | **Matches** |

**Overall: Matches desired split.** Reserved dimensions are inert.

---

## Summary Matrix

| Signal       | Training  | Inference            | Desired Inference    | Verdict              |
|--------------|-----------|----------------------|----------------------|----------------------|
| Bhava        | Full      | Direct (phase adapter) | Direct             | **Matches**          |
| Vritti       | Full      | Bounded gate (off by default) | Small bounded gate | **Matches**        |
| Guna         | Full      | Audit-only (in state) | Indirect / audit    | **Matches**          |
| Ontological  | Full      | Dead code (`TwoStageGenerator` unwired) | Indirect / audit | **Matches**    |
| CSR          | Dual-path (both off by default) | Not wired | Not direct      | **Matches** (caveat) |
| Kosha        | Full      | Bridge-only (budget) | Indirect / audit     | **Matches**          |
| Reserved     | Produced  | Carried              | N/A                  | **Matches**          |

## Findings

### No mismatches detected.

The current Mistral-CG implementation matches the desired training/inference split on every signal family. The architecture enforces the split structurally:

1. **Structural narrowing**: `IntentPhaseProjector` (V11.0.0) explicitly takes only 12D Bhava, rejecting all other state dimensions from the causal logit path.

2. **Default-off everything**: `enable_conscious_generation=False`, all `lambda_*` values default to 0.0, `enable_vritti_gate=False`. No CG signal has inference impact unless explicitly enabled.

3. **No accidental leakage**: CG primitives (`CSRTokenScorer`, `VrittiTokenScorer`, `GunaTokenScorer`, `OntologyCompatibilityScorer`) are training-only modules. They are never imported or called from inference-side code (`MistralCGAdapter`).

4. **Vritti gate follows spec**: The only non-Bhava inference-time consumer is the Vritti gate, which is exactly the "small bounded" gate the desired policy allows — temperature-only, cool-only, off by default.

### Design-hygiene observations (not split violations)

| Observation | Severity | Recommendation |
|-------------|----------|----------------|
| Dual CSR training paths (`enable_csr` standalone vs `lambda_csr_token` CG primitive) | Low | Consolidate before any CSR inference promotion |
| `TwoStageGenerator` is dead code at inference | Low | Either wire it (with appropriate gating) or remove the import |
| Vritti index ordering mismatch between training `VrittiState` enum (SMRITI=3, NIDRA=4) and inference 32D layout (VOID=3, MEMORY=4) | Medium | Verify `SovereignStateProjector` output ordering matches inference constants; add a mapping test |
| All CG lambdas default to 0.0 | Info | Intentional safety — training effectively skips CG unless explicitly configured |
