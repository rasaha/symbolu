# Phase Formula Presence Audit Report

**Date:** 2025-12-13
**Audited Phases:** 11, 12, 15, 20, 28, 29, 30, 31, 32

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

## Summary Table

| Phase | Classification | Formula Present? |
|-------|----------------|------------------|
| 11 | ⚠️ Uses existing formulas only | No new formula — enables v3 |
| 12 | ✅ Introduces a new formula | `coherence_v3_quality` |
| 15 | ❌ No formula involved | Mode definitions only |
| 20 | ❌ No formula involved | Dashboard presentation |
| 28 | ⚠️ Uses existing formulas only | Uses SHF (Phase 27) |
| 29 | ⚠️ Uses existing formulas only | Uses SHF (Phase 27) |
| 30 | ❌ No formula involved | Persona tone mapping |
| 31 | ❌ No formula involved | APEL UI control |
| 32 | ✅ Introduces a new formula | `insight_depth` |

---

## Recommendations

**Phases requiring invariance audit suites:** 12, 32

These phases introduce new mathematical formulas that compute numeric scores affecting coherence quality gating (Phase 12) and insight window gating (Phase 32).

**Phases NOT requiring formula-level invariance audits:**
- Phase 11, 28, 29: Use existing formulas (may need integration/activation tests)
- Phase 15, 20, 30, 31: Structural/presentation phases (behavioral tests sufficient)
