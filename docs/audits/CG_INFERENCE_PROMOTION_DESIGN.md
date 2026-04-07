# CG Inference Promotion Design Audit

**Date:** 2026-04-07
**Scope:** Design audit for promoting CG dimensions into the live Mistral CG inference path.
**Method:** Evidence-based analysis of code, architectural fit, risk, and existing precedent.
**Status:** Design/audit only. No implementation.

---

## 1. Executive Summary

**Which CG dimensions should be promoted first, if any?**

**Vritti**, promoted as a post-generation sampling gate (not a logit modifier), is the safest and most justified first promotion.

**Which should definitely NOT be promoted first?**
- CSR (outside the 32D state, requires entirely new wiring, high latency)
- Explicit primitive scorers / TwoStageGenerator (too large a surface, forces per-token scorer invocation, high risk)

**What is the safest next step?**

Extend the Mistral CG inference path with a **Vritti-based quality gate** that reads the Vritti slice `[17:22]` from the already-computed 32D Sovereign State and uses it to modulate sampling parameters (temperature, top-k). This is the smallest possible promotion because:

1. The state is **already computed** on every forward pass (state_projector runs during inference)
2. It does **not** modify logits or the adapter path
3. It has **direct precedent** in the existing `OntologicalBindingCacheInferenceEngine` which already implements exactly this pattern (V11.0.0 Vritti gate)
4. The sovereign bridge already provides `_vritti_to_confidence()` and `signals_from_sovereign_state()` for converting the raw 5D Vritti tensor to actionable signals
5. It can be toggled off with zero generation impact

---

## 2. Candidate-by-Candidate Evaluation

### A. Vritti (5D: FACT, ERROR, IMAGINATION, VOID, MEMORY)

**Architectural fit: Excellent**
- Already lives in the 32D Sovereign State at `[17:22]`, softmax-normalized
- Already computed on every forward pass by `state_projector`
- The `sovereign_bridge.py` module already has `_vritti_to_confidence()` which maps the 5D Vritti to `quality_score`, `correctness_score`, `prediction_reversal_risk`, and `coherence_score`
- `OntologicalBindingCacheInferenceEngine` (lines 483-515) already implements the exact pattern: read Vritti from state, check if `prediction_reversal_risk > threshold`, if so cool temperature for resampling

**Likely value: High**
- Vritti directly encodes epistemic reliability -- whether the model "believes" its output is factual, erroneous, imaginative, empty, or recalled
- This is the most semantically actionable CG signal for generation quality: it can suppress hallucination-prone tokens by cooling temperature when ERROR dominates
- It adds something not covered by Bhava: Bhava encodes *ontological identity* (what mode of being), while Vritti encodes *cognitive reliability* (how trustworthy the current state is)
- The semantics are well-defined and stable (FACT vs ERROR is unambiguous)

**Risks: Low**
- Does NOT modify logits or the adapter path -- only post-logit sampling parameters
- Can be toggled off (gated by config flag) with zero impact
- Cannot destabilize the model's learned representations
- No double-counting with Bhava (orthogonal semantics: identity vs reliability)
- Latency: zero incremental compute -- state is already computed; only adds a few float comparisons per token
- Risk of incorrect gating: Vritti predictions may not be well-calibrated initially, but since the action is conservative (cooling temperature, not rejecting tokens), a miscalibration only causes slightly more conservative generation

**Recommendation: Promote first**

---

### B. Guna (6D: Sattva, Rajas, Tamas, Velocity, Accel, Stable)

**Architectural fit: Good but less direct**
- Lives in the 32D state at `[22:28]`, sigmoid-normalized (independent activations)
- Already computed on every forward pass
- `sovereign_bridge.py` has `_kosha_to_budget()` but the Guna-specific mapping is less well-defined in existing inference code
- No existing inference-time Guna gate in any model path (unlike Vritti which has the V11.0.0 gate)

**Likely value: Moderate**
- Guna encodes abstract dynamics (energy/mode). Sattva (clarity), Rajas (activity), Tamas (inertia) have semantic meaning but it's less clear how to translate this into a concrete generation control action
- The "Guna bias" in the ablation config currently maps to the adapter gate on/off -- not to a Guna-specific modulation of sampling
- Guna semantics overlap partially with Bhava (both describe mode/energy) making the incremental value less clear

**Risks: Moderate**
- Guna semantics are more ambiguous than Vritti for generation control
- What action do you take when Tamas is high? Slow down? Increase temperature? The mapping is less obvious
- Risk of double-counting with Bhava's mode signal
- Six independent sigmoid dimensions are harder to interpret than Vritti's single-peaked softmax

**Recommendation: Second promotion, after Vritti is validated. Consider only a reduced mapping (e.g. Sattva/Tamas ratio as a temperature modulator).**

---

### C. Kosha (5D: Material, Vital, Mental, Intellectual, Blissful)

**Architectural fit: Good**
- Lives in the 32D state at `[12:17]`, sigmoid-normalized
- Already computed on every forward pass
- `OntologicalBindingCacheInferenceEngine` already implements Kosha depth control (lines 517+): boost top-k when stuck at MATERIAL, cool temperature at INTELLECTUAL
- `sovereign_bridge.py` has `_kosha_to_budget()` for mapping Kosha to complexity/budget signals

**Likely value: Moderate**
- Kosha encodes processing depth -- useful for adaptive compute allocation
- The actions are concrete: surface tasks get broader sampling, deep reasoning tasks get sharper sampling
- But: Kosha's influence on token quality is *indirect* -- depth doesn't directly predict hallucination or quality the way Vritti does

**Risks: Moderate**
- Kosha's sigmoid mode means all sheaths can be high simultaneously, making interpretation less clear than Vritti's softmax
- The MATERIAL/INTELLECTUAL split is potentially useful but could fight with prompt-level temperature settings
- Less actionable than Vritti for the primary goal of "make generation more CG-shaped"

**Recommendation: Promote alongside or slightly after Guna. Kosha + Vritti together form a natural pair (reliability + depth), but Vritti alone is safer first.**

---

### D. CSR (12D phoneme affinity, outside 32D state)

**Architectural fit: Poor for the current path**
- CSR is explicitly outside the 32D Sovereign State (documented: "Manomaya/Mental Plane is handled by CSR, operating outside the 32D state as a separate scoring primitive")
- Requires `CSRTokenScorer` which is a bilinear scorer operating on token embeddings -- needs per-token evaluation, not just per-sequence state reading
- No existing inference-time wiring for CSR in the Mistral path
- The `CSRInferenceGuard` mentioned in V11.0.0 docs is in `InferenceManager` but is for the non-Mistral model

**Likely value: Low for generation quality, potentially interesting for phonemic grounding**
- CSR measures phonemic resonance -- whether a token "sounds right" in context
- This is useful for poetry/prose but not for general-purpose generation
- It adds a different *kind* of signal (phonological vs semantic) but the incremental value for typical inference is low

**Risks: High**
- Requires per-token scorer invocation (not just reading a state slice)
- Significantly increases inference latency
- Phonemic scoring may fight with semantic quality
- Large new code surface on the inference path
- Would need the TwoStageGenerator or equivalent to integrate

**Recommendation: Do NOT promote first. Only consider after Vritti + Guna/Kosha are validated and if phonemic grounding is explicitly desired.**

---

### E. Explicit Primitive Scorers / TwoStageGenerator

**Architectural fit: Designed for this purpose but large surface**
- `TwoStageGenerator` was designed as the inference-time CG integration point
- Orchestrates: top-K extraction -> TokenEvaluationTensor -> IntegratedTokenScorer -> FieldIntegratedSoftmax
- Requires all primitive scorers (Ontology, Plausibility, CSR, Vritti, Guna) to be instantiated and invoked per token
- Requires `TokenPrimitiveCache` to be populated with vocab-level embeddings

**Likely value: Highest eventual value but premature now**
- This is the "endgame" path: full CG-aware token re-ranking
- But it is the most complex path and requires all auxiliary modules to be well-trained

**Risks: Very high for a first promotion**
- Adds significant latency: per-token evaluation of K candidates across 6 dimensions
- Requires `enable_conscious_generation` and all CG modules to be loaded and trained
- Large blast radius: replaces the entire sampling path
- If primitive weights are poorly trained, generation quality degrades severely
- No gradual rollout -- it's all-or-nothing

**Recommendation: Do NOT promote first. This is the final-stage integration after individual signals are validated. A stepped approach (Vritti gate -> Guna/Kosha modulation -> TwoStageGenerator) is vastly safer.**

---

### F. Bhava-Only Status Quo

**Architectural fit: Already live (the current state)**
- Bhava delta feeds into IntentPhaseProjector -> phase_adapter -> gated residual on logits
- This is the only CG dimension currently on the causal inference path

**Likely value: Baseline**
- Bhava encodes ontological identity, which influences how tokens relate to each other
- The phase adapter is trained to produce meaningful corrections based on Bhava
- But Bhava alone does not encode reliability, depth, or energy

**Risks: Zero additional risk**
- This is the current state; no change needed

**Recommendation: Acceptable baseline. But the gap between "Bhava shapes logits" and "Vritti/Kosha/Guna also exist in the state but do nothing at inference" is a real incompleteness that the Vritti gate can close cheaply.**

---

## 3. Recommended Promotion Order

| Rank | Candidate | Justification | Prerequisites |
|------|-----------|---------------|---------------|
| **1** | **Vritti quality gate** | Smallest surface, direct precedent (V11.0.0), clear semantics (hallucination gating), zero latency increase, non-invasive (sampling-only) | State already computed; sovereign_bridge already provides conversion |
| **2** | **Kosha depth control** | Good precedent (V11.0.0), clear action (top-k/temp modulation by depth), pairs naturally with Vritti | Vritti gate validated; confirm Kosha calibration |
| **3** | **Guna temperature bias** | Sattva/Tamas ratio as a soft temperature modulator, extends the state-reading pattern | Vritti + Kosha validated; define clear Guna->action mapping |
| **4** | **Full state adapter input** | Extend phase_adapter input from 12D Bhava-only to 20D (Bhava + Kosha + Guna) or 32D full state | All sampling-level gates validated; retrain adapter with extended input |
| **5** | **TwoStageGenerator** | Full primitive re-ranking at inference | All individual signals validated; all primitive scorers trained; latency budget confirmed |
| -- | **CSR** | Only if phonemic grounding is explicitly desired | TwoStageGenerator active; CSR scorer trained |

---

## 4. Proposed First Promotion Shape

### Vritti Quality Gate for MistralCGAdapter

**Shape:** Add a post-forward, pre-sampling gate in `MistralCGAdapter.call()` that reads the Vritti slice from the already-computed 32D state and modulates `effective_temperature` and `effective_top_k` before sampling.

**What changes:**
- In `MistralCGAdapter.call()`, after `outputs = self.model(...)` and before sampling:
  - Extract `state = outputs['state']` (already returned by MistralCGWrapper.forward)
  - Extract Vritti slice `state[0, 17:22]` (5D softmax-normalized)
  - Use `signals_from_sovereign_state(state, delta_S)` or inline the Vritti extraction
  - If `prediction_reversal_risk > vritti_error_resample_threshold`: cool temperature
  - If `quality_score < vritti_low_quality_threshold`: slightly boost diversity
- Add config flags: `enable_vritti_gate: bool = False` (off by default, opt-in)
- Add config values: `vritti_error_resample_threshold`, `vritti_resample_temperature`, `vritti_max_resamples` (copy from `OntologicalBindingCacheInferenceConfig`)
- Log gate events in `self.last_cg_metadata['vritti_gate_events']`

**What does NOT change:**
- The MistralCGWrapper.forward() path (state_projector, intent_projector, phase_adapter, logits)
- The core sampling logic (top-k, top-p, temperature)
- No new modules loaded
- No new forward passes
- No primitive scorers invoked
- No TwoStageGenerator
- The gate is purely a function of already-computed state

**Why this shape:**
- It's the exact pattern already validated in `OntologicalBindingCacheInferenceEngine` (lines 483-515)
- It requires zero new training -- it reads state dimensions the state_projector already produces
- It can be toggled off for A/B testing
- It preserves the current causal path entirely and only adds a thin post-processing layer

**Latency impact:** Negligible. A few float comparisons per token. No additional forward passes.

**Precedent code to follow:**
- `agentic/inference/ontological_binding_cache_inference.py:483-515` (Vritti gate)
- `agentic/agentic_framework/sovereign_bridge.py:141-181` (_vritti_to_confidence)

---

## 5. Anti-Roadmap (What NOT To Do First)

1. **Do NOT activate the TwoStageGenerator at inference.** It requires all primitive scorers to be loaded and invoked per-token. The latency cost is substantial and the blast radius is the entire sampling path. This is the endgame, not step one.

2. **Do NOT promote CSR first.** CSR is outside the 32D state, requires per-token embedding-level scoring, and adds significant latency. Its value for general generation is marginal.

3. **Do NOT extend the phase_adapter input from 12D to 32D yet.** This changes the learned representation and would require retraining. The comment in the IntentPhaseProjector docstring (V11.0.0) explicitly explains why it was *narrowed* from 32D to 12D: "Phase rotation should encode WHAT the system IS (ontological identity), not control signals (Koshas/Vrittis/Gunas) which belong in the control plane." Widening it back would reverse an intentional design decision.

4. **Do NOT activate all dormant scorer heads at once.** If multiple signal families are activated simultaneously without individual validation, it's impossible to attribute changes in generation quality to specific signals.

5. **Do NOT bypass the current latent path with a large new control stack.** The existing architecture (frozen backbone -> trainable adapter -> gated residual) is sound. The promotion should add thin post-processing gates, not restructure the forward pass.

6. **Do NOT force the Vritti gate to reject/resample tokens.** The safest action is temperature modulation (cooling/warming), not hard rejection. Hard rejection can cause degenerate loops. The V11.0.0 precedent uses temperature adjustment, not rejection.

7. **Do NOT assume Vritti predictions are well-calibrated.** The initial gate should be conservative: small temperature adjustments, high thresholds for activation, and a maximum resample count. Calibration can be tuned after observing real gate firing rates.

---

## 6. Final Recommendation

**Promote Vritti next, as a sampling-parameter gate, gated by a config flag (off by default).**

Specifically:

> **"Promote Vritti as a post-forward temperature/top-k gate in MistralCGAdapter, following the exact pattern from OntologicalBindingCacheInferenceEngine V11.0.0, enabled only when `enable_vritti_gate=True`."**

This is justified because:
- Zero incremental compute (state already computed)
- Zero change to the learned forward path
- Direct code precedent exists and is tested
- Sovereign bridge mapping already written and tested
- Clear semantics (hallucination gating)
- Toggleable (opt-in)
- Non-destructive (temperature modulation, not token rejection)

After Vritti is validated through A/B testing and gate-firing-rate analysis, promote Kosha depth control using the same pattern.

---

## Appendix: Key Evidence Sources

| Evidence | File | Lines | Finding |
|----------|------|-------|---------|
| Vritti is in 32D state, softmax-normalized | `jepa/state_projector.py` | 9, 175-196 | Vritti at [17:22], 5D softmax |
| Vritti gate already exists for non-Mistral | `agentic/inference/ontological_binding_cache_inference.py` | 102-107, 483-515 | Temperature modulation on reversal_risk |
| Sovereign bridge converts Vritti to confidence | `agentic/agentic_framework/sovereign_bridge.py` | 141-181 | `_vritti_to_confidence()` with quality_score, reversal_risk |
| MistralCGAdapter has no Vritti gate | `agentic/agentic_framework/llm_adapters.py` | 492-603 | Standard sampling only |
| State is already computed at inference | `training/unified/mistral_wrapper.py` | 353-354 | `compute_state_delta()` runs on every forward |
| IntentPhaseProjector was intentionally narrowed | `symbolu_core/phase_transformer.py` | 1796-1813 | V11.0.0: 32D->12D, control signals routed elsewhere |
| Ablation uses Vritti/Guna for state/gate control | `training/unified/mistral_wrapper.py` | 157-167 | `use_vritti_modulation`, `use_guna_bias` |
| All CG lambdas default to 0.0 | `training/unified/config.py` | 988-1010 | Dormant by default |
