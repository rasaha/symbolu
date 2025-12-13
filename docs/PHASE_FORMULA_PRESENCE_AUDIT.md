# Phase Formula Presence Audit Report

**Date:** 2025-12-13
**Audited Phases:** 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 15, 20, 28, 29, 30, 31, 32, 33

---

## Definition of "Formula" (STRICT)

A phase counts as having a formula **only** if it introduces:
- A new function that computes numeric outputs (scores, indices, metrics)
- Deterministic mathematical logic beyond simple assignment
- New calculations that affect coherence, stability, alignment, entropy, or gating

**DO NOT count as formulas:**
- Metadata extraction
- Presentation / renderer modulation
- Persona metadata assembly
- Routing, gating, or conditional logic without math
- Reuse or pass-through of existing formula outputs

---

## Audit Results

### Phase 2 — ⚠️ Uses existing formulas only

**Evidence:**
- `symbolu/mechanical/pipeline/integration_tests/test_phase2_temporal_integration.py:7-14`
- Purpose: Wires Phase 1 temporal formulas (SMI, ΔSMI, Bhava Gap, Tension Corridor) into coherence state, session summary, and unified output

**Conclusion:** No new formula introduced — Integration/propagation layer for existing Phase 1 formulas.

---

### Phase 3 — ✅ Introduces a new formula

**Evidence:**
- `symbolu/core/coherence/coherence_engine.py:211-212` — `_update_derived_formula_metrics()`
- `symbolu/core/coherence/coherence_engine.py:694-702` — arc_alignment_index formula

**New formulas:**
```python
resonance_index = f(SMI, bhava_gap, |ΔSMI|)
tension_index = f(tension_corridor, |ΔSMI|)
arc_alignment_index = 0.4 * SMI + 0.3 * gap_norm + 0.3 * improving
```

**Conclusion:** Computes three new derived metrics from Phase 1 inputs.

---

### Phase 4 — ✅ Introduces a new formula

**Evidence:**
- `symbolu/core/coherence/coherence_engine.py:704-714` — `_compute_coherence_score_v2()`

**New formula:**
```python
coherence_score_v2 = clamp(0.55 * base + resonance_boost - tension_penalty + arc_bonus)
```

**Conclusion:** Formula-aware coherence score incorporating Phase 1 + Phase 3 signals.

---

### Phase 5 — ❌ No formula involved

**Evidence:**
- `symbolu/mechanical/pipeline/integration_tests/test_phase5_formula_ui_behavior.py:7-13`
- `symbolu/policy/policy_engine.py:159-161` — `_refine_policy_with_formulas()`

**Conclusion:** No new formula — Rule-based policy refinement (conditional logic), not new computed metrics.

---

### Phase 6 — ❌ No formula involved

**Evidence:**
- `symbolu/mechanical/pipeline/integration_tests/test_phase6_behavioral_invariance.py:7-13`
- `symbolu/formulas/patent_tags.py` — Patent Formula Coverage Matrix

**Conclusion:** No formula — Pure metadata assembly for patent tagging, no mathematical computation.

---

### Phase 7 — ❌ No formula involved

**Evidence:**
- `symbolu/policy/trading_guardrail_engine.py:21-34` — Rule definitions
- `symbolu/mechanical/pipeline/integration_tests/test_phase7_trading_formula_guardrails.py:8-11`

**Guardrail rules (NOT formulas):**
```python
high_tension_risk = (tension_corridor > max) AND (resonance_index < 0.45)
negative_momentum_risk = (delta_smi < -max) AND (coherence < 0.55)
volatility_risk = (volatility > max) AND (drift > 0.45)
```

**Conclusion:** No new formula — Threshold-based conditional logic on existing metrics, produces boolean flags not numeric scores.

---

### Phase 9 — ⚠️ Uses existing formulas only

**Evidence:**
- `symbolu/mechanical/pipeline/integration_tests/test_phase9_guna_kosha_mapper_modulation.py:6-15`
- `symbolu/mechanical/mlcr/mapper_profile_builder.py` — `apply_resonance_biases()`

**Conclusion:** No new formula — Applies existing Phase 8 Guna/Kosha resonance indices to mapper profile biases.

---

### Phase 10 — ✅ Introduces a new formula

**Evidence:**
- `symbolu/core/coherence/coherence_engine.py:896-911` — `_compute_coherence_score_v3()`

**New formula (megafusion):**
```python
v3 = clamp(
    base_weight * v2 +
    guna_weight * guna_resonance_index +
    kosha_weight * kosha_resonance_index +
    harmonics_bonus * expression_harmonics_coherence
)
```

**Conclusion:** First formula-layer megafusion integrating Phase 1, 3, 8, 9 metrics.

---

### Phase 11 — ⚠️ Uses existing formulas only

**Evidence:**
- `symbolu/policy/domain_profiles.py:66,86` — Sets `use_coherence_v3: True` flag for therapy/identity domains
- `symbolu/mechanical/pipeline/integration_tests/test_phase11_coherence_v3_activation.py`

**Conclusion:** No new formula introduced — Phase 11 only activates the existing v3 formula (from Phase 10) for specific domains via configuration flags.

---

### Phase 12 — ✅ Introduces a new formula

**Evidence:**
- `symbolu/core/coherence/coherence_engine.py:993-1069` — `_compute_coherence_v3_quality()`

**New formula:**
```python
stability_core = 0.4 * w_r + 0.3 * w_a + 0.3 * w_t
divergence_penalty = smooth_penalty(|v3 - base|)
quality = stability_core * (1.0 - 0.6 * divergence_penalty)
```

**Conclusion:** Computes `coherence_v3_quality` metric [0.0, 1.0] for gating v3 usage in policy.

---

### Phase 15 — ❌ No formula involved

**Evidence:**
- `symbolu/policy/interaction_modes.py:42-71` — Defines `InteractionMode` enum (ANALYTICS_ONLY, SMART_INSIGHT, DEEP_ADAPTIVE)
- `symbolu/policy/interaction_modes.py:74-100` — `resolve_interaction_mode()` is pure conditional routing logic

**Conclusion:** No mathematical formula — Only mode definitions and priority cascade logic.

---

### Phase 20 — ❌ No formula involved

**Evidence:**
- `symbolu/tools/unified_dashboard/aggregators.py` — Extracts and aggregates existing metrics
- `symbolu/tools/unified_dashboard/renderers.py` — Pure text rendering for visualization
- `symbolu/tools/unified_dashboard/models.py` — Data models for dashboard display

**Conclusion:** No mathematical formula — Pure presentation layer, metadata extraction, and visualization.

---

### Phase 28 — ⚠️ Uses existing formulas only

**Evidence:**
- `symbolu/formulas/symbolic_harmonization.py:1-2` — SHF formula is **Phase 27**, not Phase 28
- `symbolu/mechanical/renderer/fusion_renderer.py:1105-1162` — Applies SHF outputs for presentation modulation
- `symbolu/mechanical/pipeline/models.py:219-221` — `symbolic_harmony_bias` and `symbolic_resonance_tags` fields

**Conclusion:** No new formula introduced — Phase 28 uses existing SHF (Phase 27) outputs for renderer-level presentation modulation only.

---

### Phase 29 — ⚠️ Uses existing formulas only

**Evidence:**
- `symbolu/mechanical/persona/engine.py:580-600` — `_apply_resonance_to_persona_tone()` maps SHF outputs
- `symbolu/mechanical/persona/models.py:214-217` — `PersonaResonanceProfile` model

**Conclusion:** No new formula introduced — Phase 29 uses existing SHF (Phase 27) outputs for persona tone micro-adjustments (presentation layer only).

---

### Phase 30 — ❌ No formula involved

**Evidence:**
- `symbolu/mechanical/persona/persona_resonance_mapping.py:112-155` — `compute_cross_layer_persona_map()`
- Computes `metaphor_weight`, `warmth_weight`, `structure_weight` etc.

**Rationale:** Per strict definition, these are **persona tone parameters** (presentation/renderer modulation), NOT coherence/stability/alignment/entropy/gating metrics. Zero impact on routing, coherence scoring, or policy gating.

---

### Phase 31 — ❌ No formula involved

**Evidence:**
- `symbolu/mechanical/persona/persona_echo_layer.py:128-185` — `compute_adaptive_persona_echo_profile()`
- Computes `echo_strength`, `echo_mode`, `echo_length_hint`

**Rationale:** Per strict definition, these are **UI/presentation control parameters** (persona metadata assembly), NOT coherence/stability/alignment/entropy/gating metrics. Observation-only, tone-level only.

---

### Phase 32 — ✅ Introduces a new formula

**Evidence:**
- `symbolu/policy/insight_window_gating.py:103-115` — `compute_insight_window()`

**New formula:**
```python
raw_depth = 0.40 * COI + 0.40 * CSI + 0.20 * CIP
```

**Conclusion:** Computes `insight_depth` score [0.0, 1.0] that **affects gating** (determines whether insight window is open). Uses existing UCF outputs (COI, CSI, CIP from Phase 26) as inputs.

---

### Phase 33 — ✅ Introduces a new formula

**Evidence:**
- `symbolu/mechanical/persona/schema_adaptive_routing.py:31-69` — `SchemaAdaptiveRoutingSnapshot`
- `tests/test_phase33_schema_adaptive_routing.py:54-56` — "Group A: Formula Math" tests

**New formulas compute:**
```python
schema_alignment_scores = weighted_alignment(shf, guna, kosha, semantic_integrity, ...)
schema_confidence = f(signal_availability, coherence_fused)
schema_drift = f(cognitive_drift_v3, persona_drift_score, volatility)
schema_stability = f(consciousness_stability_index, temporal_entropy_volatility)
```

**Conclusion:** Computes stability/alignment metrics for persona schema analytics. While observation-only, these are new numeric outputs measuring stability and alignment (which count per definition).

---

## Summary Table

| Phase | Classification | Formula Present? |
|-------|----------------|------------------|
| 2 | ⚠️ Uses existing formulas only | No new formula — wires Phase 1 |
| 3 | ✅ Introduces a new formula | `resonance_index`, `tension_index`, `arc_alignment_index` |
| 4 | ✅ Introduces a new formula | `coherence_score_v2` |
| 5 | ❌ No formula involved | Rule-based policy refinement |
| 6 | ❌ No formula involved | Metadata/patent tags only |
| 7 | ❌ No formula involved | Threshold-based guardrails |
| 9 | ⚠️ Uses existing formulas only | Applies Phase 8 resonance |
| 10 | ✅ Introduces a new formula | `coherence_score_v3` (megafusion) |
| 11 | ⚠️ Uses existing formulas only | No new formula — enables v3 |
| 12 | ✅ Introduces a new formula | `coherence_v3_quality` |
| 15 | ❌ No formula involved | Mode definitions only |
| 20 | ❌ No formula involved | Dashboard presentation |
| 28 | ⚠️ Uses existing formulas only | Uses SHF (Phase 27) |
| 29 | ⚠️ Uses existing formulas only | Uses SHF (Phase 27) |
| 30 | ❌ No formula involved | Persona tone mapping |
| 31 | ❌ No formula involved | APEL UI control |
| 32 | ✅ Introduces a new formula | `insight_depth` |
| 33 | ✅ Introduces a new formula | `schema_alignment`, `schema_drift`, `schema_stability` |

---

## Recommendations

**Phases requiring invariance audit suites:** 3, 4, 10, 12, 32, 33

These phases introduce new mathematical formulas that compute numeric scores affecting coherence, alignment, stability, or gating.

**Phases NOT requiring formula-level invariance audits:**
- Phase 2, 9, 11, 28, 29: Use existing formulas (may need integration/activation tests)
- Phase 5, 6, 7, 15, 20, 30, 31: Structural/presentation phases (behavioral tests sufficient)
