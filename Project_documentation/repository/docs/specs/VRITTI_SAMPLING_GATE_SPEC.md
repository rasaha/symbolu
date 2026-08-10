# Vritti Sampling Gate: Design Spec

**Date:** 2026-04-07
**Status:** Design spec only. Not yet approved for implementation.
**Scope:** Post-forward Vritti-based sampling-parameter gate in `MistralCGAdapter.call()`
**Precedent:** `OntologicalBindingCacheInferenceEngine` V11.0.0 Vritti gate (lines 483-515)

---

## 1. Executive Summary

This spec defines a thin gate that reads the 5D Vritti slice from the already-computed 32D Sovereign State during Mistral CG inference and modulates **temperature only** before token sampling. It does not modify logits, widen the adapter input, or activate any dormant scorer heads.

The gate has two actions:
- **Cool** (reduce temperature) when ERROR is high -- makes generation more conservative
- **No-op** when the signal is ambiguous or dominated by FACT/MEMORY -- preserves baseline behavior

The gate is **off by default**, controlled by a single boolean toggle, and fully traceable.

---

## 2. Recommended Vritti-Gate Scope

### What the gate influences: **Temperature only**

**Rationale for excluding top-k and top-p:**

- **top-k adjustment** was considered. The V11.0.0 precedent uses it for Kosha depth control, not for Vritti. Mixing Vritti-driven top-k with Vritti-driven temperature creates two interacting knobs from one signal, making effects harder to attribute. Reserve top-k modulation for a future Kosha promotion.

- **top-p adjustment** was rejected. top-p (nucleus sampling) is a distribution-shape filter that interacts non-linearly with temperature. Adjusting both from the same signal creates unpredictable compounding effects. The V11.0.0 precedent does not touch top-p from Vritti.

- **Temperature-only** is the minimum surface that achieves the core goal: when the model's Vritti state indicates high error risk, cool the sampling distribution to prefer higher-probability tokens. This is the V11.0.0 pattern exactly.

---

## 3. Mapping from 5D Vritti to Sampling Behavior

### 3.1 Vritti Semantics (32D state ordering, softmax-normalized)

| Index | Name | Label | Semantic |
|-------|------|-------|----------|
| 0 | Pramana | FACT | Valid cognition / grounded truth |
| 1 | Viparyaya | ERROR | Misconception / hallucination risk |
| 2 | Vikalpa | IMAGINATION | Conceptualization / speculation |
| 3 | Nidra | VOID | Dormancy / absence of content |
| 4 | Smriti | MEMORY | Recall from weights |

Source: `agentic/sovereign_constants.py:110-150`, `symbolu_core/phase_transformer.py:149-155`

### 3.2 Decision Logic

The gate computes a single derived scalar, `error_risk`, and applies a single threshold test.

```
# Extract Vritti slice from state
vritti = state[0, 17:22]   # 5D, softmax-normalized, sums to ~1.0

# Derive error risk (same formula as sovereign_bridge._vritti_to_confidence)
error_risk = vritti[1] + 0.3 * vritti[2]   # ERROR + 0.3 * IMAGINATION
error_risk = clamp(error_risk, 0.0, 1.0)

# Decision
if error_risk > ERROR_THRESHOLD:
    effective_temperature = COOL_TEMPERATURE
else:
    effective_temperature = self.temperature   # unchanged
```

### 3.3 Why this mapping

| Vritti mode | Effect on gate | Rationale |
|-------------|---------------|-----------|
| **FACT dominant** | No-op (baseline temp) | High-confidence output, don't interfere |
| **ERROR dominant** | Cool temperature | High hallucination risk, prefer conservative tokens |
| **IMAGINATION high** | Partial contribution to error_risk (0.3x) | Speculation is mildly risky but not as bad as ERROR |
| **VOID dominant** | No-op | Absence of signal is not an error signal; cooling here would suppress exploration when the model is uncertain |
| **MEMORY dominant** | No-op | Recall is moderate quality; no reason to intervene |
| **Mixed/ambiguous** | No-op (threshold not met) | When no mode dominates, the threshold protects against overreaction |

### 3.4 Why no "boost diversity" action

The V11.0.0 precedent includes a second branch: when `quality < low_quality_threshold`, boost temperature by 1.2x. This spec **omits that branch** for the first version because:

1. Temperature boosting increases risk of degenerate output
2. The quality_score formula (`_vritti_to_confidence`) involves all 5 Vritti with different weights -- more complex than pure error_risk, harder to audit
3. One action (cool) is safer to validate than two opposing actions (cool + warm)
4. The boost branch can be added in a follow-up after the cool branch is validated

### 3.5 Constants

| Constant | Value | Source / Rationale |
|----------|-------|--------------------|
| `ERROR_THRESHOLD` | 0.5 | Matches V11.0.0 `vritti_error_resample_threshold` |
| `COOL_TEMPERATURE` | 0.5 | Matches V11.0.0 `vritti_resample_temperature`; firm cooling without going greedy |
| `IMAGINATION_WEIGHT` | 0.3 | Matches sovereign_bridge `_vritti_to_confidence` reversal_risk formula |

These are hardcoded in the first version (not configurable). Rationale: fewer knobs means easier audit.

---

## 4. Exact Inference Insertion Point

### Current flow in `MistralCGAdapter.call()` (llm_adapters.py:536-598)

```
for _ in range(self.max_new_tokens):
    outputs = self.model(input_ids=generated_ids, attention_mask=past_mask)
    logits = outputs['logits'][:, -1, :]
    
    # [A] Repetition penalty applied
    # [B] Temperature applied: logits / self.temperature
    # [C] Top-k filtering
    # [D] Top-p filtering
    # [E] Softmax + multinomial sampling
```

### Proposed insertion: between [A] and [B]

```
for _ in range(self.max_new_tokens):
    outputs = self.model(input_ids=generated_ids, attention_mask=past_mask)
    logits = outputs['logits'][:, -1, :]
    
    # [A] Repetition penalty applied (unchanged)
    
    # [NEW] Vritti gate: compute effective_temperature
    effective_temperature = self.temperature
    if self.enable_vritti_gate and self.temperature > 0:
        state = outputs.get('state')
        if state is not None:
            vritti = state[0, 17:22]
            error_risk = (vritti[1] + 0.3 * vritti[2]).clamp(0.0, 1.0).item()
            if error_risk > 0.5:
                effective_temperature = 0.5
                # Record gate event (details in §5)
    
    # [B] Temperature applied: logits / effective_temperature (was self.temperature)
    # [C] Top-k filtering (unchanged)
    # [D] Top-p filtering (unchanged)
    # [E] Sampling (unchanged)
```

### Why between [A] and [B]

- **After repetition penalty [A]:** Repetition penalty is prompt-specific and should not be affected by Vritti. It operates on raw logits. Order does not matter (multiplicative on individual logits), but placing the gate after keeps the existing code structure cleaner.
- **Before temperature [B]:** The gate's entire purpose is to modulate temperature. It must run before temperature is applied to logits.
- **Not after [E]:** This is not a token-rejection gate. It modulates the distribution, not the sampled result. No resampling in version 1.

### State availability

`outputs['state']` is always returned by `MistralCGWrapper.forward()` (confirmed: `mistral_wrapper.py:418`). No additional forward pass or return flag needed.

---

## 5. Minimal Control Surface

### Total: 1 parameter on MistralCGAdapter

```python
enable_vritti_gate: bool = False    # Off by default
```

That's it. No `vritti_gate_strength`, no `vritti_error_threshold`, no `vritti_cool_temperature`.

### Rationale for hardcoding the thresholds

- The threshold (0.5) and cool temperature (0.5) are taken directly from the V11.0.0 precedent that was designed, reviewed, and tested for the OntologicalBindingCache path
- Exposing them as parameters invites tuning before the base behavior is validated
- If tuning is needed, it can be added in a follow-up after the gate is proven useful
- The hardcoded values are documented in the constants table (§3.5) and can be found by searching for them

### Trace output

When the gate fires, append to `self.last_cg_metadata`:

```python
self.last_cg_metadata['vritti_gate_events'].append({
    'step': step_index,
    'error_risk': error_risk,
    'action': 'cool',
    'base_temperature': self.temperature,
    'effective_temperature': 0.5,
})
```

When the gate does not fire (including when disabled), `vritti_gate_events` is an empty list. This makes it trivially auditable: if the list is empty, the gate had zero effect.

---

## 6. Safety Constraints

### SC-1: Off by default
`enable_vritti_gate` defaults to `False`. No user gets the gate without explicitly opting in.

### SC-2: No logits modification
The gate modulates `effective_temperature` only. It never writes to `logits` or `next_token_logits`. The logits tensor passes through the existing code path unchanged.

### SC-3: Bounded temperature shift
The gate can only **reduce** temperature (from `self.temperature` to 0.5). It cannot increase temperature above the user's configured value. This means:
- If user sets `temperature=0.7`, the gate can cool to 0.5 but never warm above 0.7
- If user sets `temperature=0.3`, the gate does nothing (0.3 < 0.5, so cooling to 0.5 would actually warm; the gate should no-op in this case)
- If user sets `temperature=0` (greedy), the gate is skipped entirely (guarded by `self.temperature > 0`)

**Additional bound:** `effective_temperature = min(self.temperature, 0.5)` when the gate fires. This ensures cooling never accidentally *raises* temperature if the user already set it below the cool target.

### SC-4: No resampling / no recursion
The gate makes a single decision per token step. It does not resample, loop, or call forward() again. There is no `vritti_max_resamples` in version 1.

### SC-5: Neutral on ambiguity
When the error_risk is below threshold (i.e., no single strong ERROR signal), the gate does nothing. This includes:
- Mixed states where no Vritti dominates
- VOID-dominant states
- MEMORY-dominant states
- States where ERROR is present but below 0.5

### SC-6: Deterministic mapping
The mapping from Vritti -> effective_temperature is a pure function of the 5D Vritti vector. Same Vritti values always produce the same temperature decision. No randomness, no history dependence, no EMA smoothing.

### SC-7: Full trace visibility
Every gate firing is logged to `last_cg_metadata['vritti_gate_events']` with the exact error_risk value, the action taken, and both the base and effective temperatures. A consumer can reconstruct the gate's behavior for every token.

### SC-8: No interaction with adapter path
The gate does not modify the state_projector, intent_projector, phase_adapter, or adapter_gate. It reads state as a side output. The learned forward path is untouched.

---

## 7. Risks and Anti-Patterns

### R-1: Noisy Vritti in untrained models
**Risk:** If the state_projector was trained without CG auxiliary losses (`enable_conscious_generation=False`, all lambdas 0), the Vritti slice may contain noise rather than meaningful epistemic signal.
**Mitigation:** The 0.5 threshold is high enough that random softmax outputs (expected ~0.2 per mode) are unlikely to trigger the gate. In a uniform 5-way softmax, max error_risk = 0.2 + 0.3*0.2 = 0.26, well below 0.5.
**Residual risk:** Low. Gate should be a near-no-op on untrained states.

### R-2: Over-cooling makes generation flat
**Risk:** If the gate fires too often, generation becomes uniformly conservative, losing diversity and producing repetitive output.
**Mitigation:** The gate only fires when ERROR > ~0.38 (since 0.38 + 0.3*0.2 ≈ 0.44 < 0.5, and 0.38 + 0.3*0.4 ≈ 0.5). This requires ERROR to genuinely dominate. In a well-trained model, ERROR should not dominate most tokens.
**Monitoring:** Track gate firing rate. If > 20% of tokens trigger the gate, the Vritti signal is likely miscalibrated and the gate should be disabled.

### R-3: Double-counting with indirect Bhava influence
**Risk:** The Bhava delta already shapes logits via the phase adapter. Vritti is correlated with Bhava through shared training. The gate may cool temperature when the adapter has already made the distribution more conservative.
**Mitigation:** The gate operates on a different axis (sampling parameters vs logit modification). Temperature cooling and logit shaping are additive effects that do not conflict -- one narrows the distribution shape, the other narrows which tokens are considered. The risk is not conflict but redundancy. If the adapter already handles ERROR states, the gate simply has less to do.

### R-4: Developer confusion about what the gate does
**Risk:** Without clear documentation, developers may not understand whether the gate modifies logits, rejects tokens, or adjusts sampling. They may attribute generation quality changes to the wrong component.
**Mitigation:** The gate appends trace events to metadata. The spec constrains it to temperature-only. The code comment at the insertion point should state: "Vritti gate: temperature modulation only, no logit modification."

### R-5: Index ordering mismatch
**Risk:** The training-side `VrittiState` enum in `vritti.py` uses SMRITI=3, NIDRA=4. The 32D state layout uses NIDRA=3, SMRITI=4 (`sovereign_constants.py:111-122`). If the state_projector applies constraints in the wrong order, the gate would read MEMORY as VOID and vice versa.
**Mitigation:** The state_projector (`jepa/state_projector.py:179-196`) applies softmax to raw[17:22] without reordering. The order matches whatever the projector learned. The sovereign_bridge and phase_transformer both use the 32D ordering (FACT/ERROR/IMAGINATION/VOID/MEMORY). The gate reads from the same state tensor, so the ordering is consistent at the inference layer. This is a documentation concern, not a runtime bug. The spec uses hardcoded indices [1] and [2] for ERROR and IMAGINATION, matching `sovereign_constants.VRITTI_ERROR=1` and `VRITTI_IMAGINATION=2`.

---

## 8. Validation Requirements Before Implementation

Before the gate is approved for merge (even behind the `enable_vritti_gate` flag), verify:

### V-1: Bounded temperature effect
Confirm that `effective_temperature` is always in `[min(0.5, self.temperature), self.temperature]`. No path produces a temperature outside this range.

### V-2: No-op on untrained state
Run inference with a checkpoint trained without `enable_conscious_generation`. Confirm the gate fires on < 5% of tokens (near-zero firing rate on noise).

### V-3: Gate fires on high-error states
Construct or find a scenario where the state_projector produces high ERROR activation (Vritti[1] > 0.4). Confirm the gate fires and temperature drops.

### V-4: Trace completeness
Generate 50+ tokens with the gate enabled. Confirm `last_cg_metadata['vritti_gate_events']` contains one entry per gate firing with all required fields (step, error_risk, action, base_temperature, effective_temperature).

### V-5: No generation degeneration
Compare 100 generations with gate on vs off (same prompts, same seed). Confirm:
- No empty/truncated responses introduced by the gate
- No infinite loops or stuck generation
- Perplexity/quality does not degrade catastrophically

### V-6: Greedy mode bypass
Confirm that when `temperature=0`, the gate is entirely skipped (no state extraction, no trace events).

### V-7: Low-temperature no-op
Confirm that when `temperature < 0.5` (e.g., 0.3), the gate does not accidentally *raise* temperature to 0.5.

---

## 9. Final Recommendation

**Implement behind an experimental flag (`enable_vritti_gate=False`), merge, and validate with the V-1 through V-7 checklist before enabling by default.**

The spec is minimal:
- 1 boolean toggle
- 1 derived scalar (error_risk)
- 1 threshold test
- 1 action (cool temperature to 0.5)
- 0 new modules, 0 new forward passes, 0 logit modifications
- Full trace output

This is the smallest possible causal promotion of a CG signal beyond Bhava. It can be validated, measured, and reverted trivially.
