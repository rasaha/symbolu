# Phase 1-9 Architectural Substrate Audit

**Audit Date:** 2025-12-14
**Auditor:** Claude Code
**Scope:** Phase 1 through Phase 9 modules
**Classification:** SUBSTRATE vs GOVERNANCE determination

---

## Section 1: Executive Summary

### Overall Finding

**CRITICAL ARCHITECTURAL BOUNDARY DETECTED**

The Phase 1-9 designation in Symbol-U spans TWO distinct architectural layers:

| Layer | Phases | Classification | Authority Level |
|-------|--------|----------------|-----------------|
| **Formula Substrate Layer** | Phase 1-5 | SUBSTRATE-ONLY ✔ | Zero authority |
| **Mechanical Governance Pipeline** | P6-P9 | AUTHORITY-BEARING ❌ | Full governance authority |

### Summary Verdict

- **Phase 1**: SUBSTRATE-ONLY ✔ (Acoustic tokenization + temporal formulas)
- **Phase 2**: SUBSTRATE-ONLY ✔ (Temporal formula integration - test scaffold)
- **Phase 3**: SUBSTRATE-ONLY ✔ (Derived formula metrics - observability)
- **Phase 4**: SUBSTRATE-ONLY ✔ (Coherence v2 score - observability)
- **Phase 5**: SUBSTRATE-ONLY ✔ (Formula UI behavior - policy hints)
- **P6**: **VIOLATION ❌** (Regime Selection - GOVERNANCE)
- **P7**: **VIOLATION ❌** (Discourse Act Selection - GOVERNANCE)
- **P8**: **VIOLATION ❌** (Semantic Slot Resolution - GOVERNANCE)
- **P9**: **VIOLATION ❌** (Lexical Selection - GOVERNANCE)

**Finding:** Phases P6-P9 are intentionally designed as governance phases in the mechanical pipeline. They are NOT substrate phases and should NOT be classified as Phase 1-9 "formula substrate" modules.

---

## Section 2: Discovered Phase 1-9 File List

### Formula Substrate Layer (Phase 1-5)

#### Phase 1: Core Formula Files
| File Path | Purpose |
|-----------|---------|
| `symbolu/formulas/acoustic_unit_mapper.py` | Phonetic tokenization to AcousticUnit primitives |
| `symbolu/formulas/vritti_mapper.py` | Motion quality (vṛtti) assignment |
| `symbolu/formulas/resonance_formulas.py` | SMI, ΔSMI, Bhava Gap, Tension Corridor |
| `symbolu/formulas/phase1_snapshot.py` | Immutable Phase1Snapshot output contract |
| `symbolu/formulas/guna_kosha_resonance.py` | Phase 8 Guna/Kosha observability metrics |
| `symbolu/formulas/__init__.py` | Public API exports |

#### Phase 2-5: Integration Test Files (Verification Scaffolding)
| File Path | Purpose |
|-----------|---------|
| `symbolu/mechanical/pipeline/integration_tests/test_phase2_temporal_integration.py` | Temporal formula wiring tests |
| `symbolu/mechanical/pipeline/integration_tests/test_phase3_derived_formula_metrics.py` | Derived metric computation tests |
| `symbolu/mechanical/pipeline/integration_tests/test_phase4_coherence_v2_integration.py` | Coherence v2 score tests |
| `symbolu/mechanical/pipeline/integration_tests/test_phase5_formula_ui_behavior.py` | Formula-based UI modulation tests |

#### Light Invariance Tests (Tier 3)
| File Path | Phase |
|-----------|-------|
| `tests/tier3_invariance/test_phase1_light_invariance.py` | Phase 1 |
| `tests/tier3_invariance/test_phase2_light_invariance.py` | Phase 2 |
| `tests/tier3_invariance/test_phase3_light_invariance.py` | Phase 3 |
| `tests/tier3_invariance/test_phase4_light_invariance.py` | Phase 4 |
| `tests/tier3_invariance/test_phase5_light_invariance.py` | Phase 5 |

### Mechanical Governance Pipeline (P6-P9)

#### P6: Regime Selection Gate
| File Path | Purpose |
|-----------|---------|
| `symbolu/mechanical/pipeline/phase_p6/__init__.py` | Public API |
| `symbolu/mechanical/pipeline/phase_p6/p6_schema.py` | OperationalRegime enum, RegimeEnvelope |
| `symbolu/mechanical/pipeline/phase_p6/p6_regime_gate.py` | P6RegimeGate - regime selection logic |
| `symbolu/mechanical/pipeline/phase_p6/p6_integration.py` | P6 integration module |

#### P7: Discourse Act Resolver
| File Path | Purpose |
|-----------|---------|
| `symbolu/mechanical/pipeline/p7_discourse/__init__.py` | Public API |
| `symbolu/mechanical/pipeline/p7_discourse/p7_discourse_schema.py` | DiscourseAct enum, DiscourseEnvelope |
| `symbolu/mechanical/pipeline/p7_discourse/p7_discourse_resolver.py` | P7DiscourseResolver - discourse selection |
| `symbolu/mechanical/pipeline/p7_discourse/p7_discourse_integration.py` | P7 integration module |

#### P8: Semantic Slot Resolver
| File Path | Purpose |
|-----------|---------|
| `symbolu/mechanical/pipeline/p8_semantics/__init__.py` | Public API |
| `symbolu/mechanical/pipeline/p8_semantics/p8_semantic_schema.py` | SemanticSlot enum, SemanticFrame |
| `symbolu/mechanical/pipeline/p8_semantics/p8_semantic_resolver.py` | P8SemanticResolver - semantic resolution |
| `symbolu/mechanical/pipeline/p8_semantics/p8_semantic_integration.py` | P8 integration module |

#### P9: Lexical Selection Engine
| File Path | Purpose |
|-----------|---------|
| `symbolu/mechanical/pipeline/p9_lexical/__init__.py` | Public API |
| `symbolu/mechanical/pipeline/p9_lexical/p9_lexical_schema.py` | LexicalFrame dataclass |
| `symbolu/mechanical/pipeline/p9_lexical/p9_lexical_resolver.py` | P9LexicalResolver - word selection |
| `symbolu/mechanical/pipeline/p9_lexical/p9_lexical_pools.py` | Curated lexical synonym pools |
| `symbolu/mechanical/pipeline/p9_lexical/p9_integration.py` | P9 integration module |

---

## Section 3: File-by-File Audit Table

### Formula Substrate Layer (Phase 1-5)

| File | Inputs | Outputs | Substrate-Only? | Authority Leakage? | Notes |
|------|--------|---------|-----------------|-------------------|-------|
| `acoustic_unit_mapper.py` | Raw text string | `List[AcousticUnit]` | ✔ YES | NO | Pure phonetic decomposition, no semantics |
| `vritti_mapper.py` | `AcousticUnit` | `AcousticVritti` | ✔ YES | NO | Motion quality from acoustic properties only |
| `resonance_formulas.py` | float parameters | float (SMI, ΔSMI, etc.) | ✔ YES | NO | Deterministic math, no LLM, no routing |
| `phase1_snapshot.py` | text | `Phase1Snapshot` | ✔ YES | NO | Immutable data contract, no authority |
| `guna_kosha_resonance.py` | guna/kosha probs | `GunaKoshaResonance` | ✔ YES | NO | Observability metrics only, no routing |
| `test_phase2_temporal_integration.py` | N/A (test) | N/A | ✔ YES | NO | Test file, verifies observation-only |
| `test_phase3_derived_formula_metrics.py` | N/A (test) | N/A | ✔ YES | NO | Test file, verifies non-invasive metrics |
| `test_phase4_coherence_v2_integration.py` | N/A (test) | N/A | ✔ YES | NO | Test file, v2 is feature-flag gated |
| `test_phase5_formula_ui_behavior.py` | N/A (test) | N/A | ✔ YES | NO | Test file, UI hints only |

### Mechanical Governance Pipeline (P6-P9) - VIOLATIONS

| File | Inputs | Outputs | Substrate-Only? | Authority Leakage? | Notes |
|------|--------|---------|-----------------|-------------------|-------|
| `p6_regime_gate.py` | PO2 Intent, PO5 Eligibility, Coherence Regime | `RegimeEnvelope` | **❌ NO** | **YES** | **SELECTS REGIME** (line 71-218) |
| `p6_schema.py` | N/A | `OperationalRegime` enum | **❌ NO** | **YES** | Defines authority enum values |
| `p7_discourse_resolver.py` | PO1-PO3, P6 Regime | `DiscourseEnvelope` | **❌ NO** | **YES** | **SELECTS DISCOURSE ACT** (line 125-327) |
| `p7_discourse_schema.py` | N/A | `DiscourseAct` enum | **❌ NO** | **YES** | Defines authority enum values |
| `p8_semantic_resolver.py` | PO1, PO2, P6, P7 | `SemanticFrame` | **❌ NO** | **YES** | **RESOLVES SEMANTIC SLOTS** (line 101-634) |
| `p8_semantic_schema.py` | N/A | `SemanticSlot` enum | **❌ NO** | **YES** | Defines slot allow-lists |
| `p9_lexical_resolver.py` | P6, P7, P8 | `LexicalFrame` | **❌ NO** | **YES** | **SELECTS WORDS** (line 90-356) |
| `p9_lexical_pools.py` | N/A | Lexical pools | **❌ NO** | **YES** | Curated word constraints |

---

## Section 4: Authority Leakage Check

### a) Does ANY Phase 1-9 module infer intent?

| Phase | Infers Intent? | Evidence |
|-------|---------------|----------|
| Phase 1 (formulas) | **NO** | No intent fields in AcousticUnit/AcousticVritti (phase1_snapshot.py:369-388) |
| Phase 2-5 (integration) | **NO** | Observation-only, no intent inference |
| **P6** | **READS** intent | Consumes PO2 IntentEnvelope (p6_regime_gate.py:31-33) but does NOT infer |
| **P7** | **READS** intent | Consumes PO2 IntentEnvelope (p7_discourse_resolver.py:34-37) but does NOT infer |
| **P8** | **READS** intent | Consumes PO2 IntentEnvelope (p8_semantic_resolver.py:46-48) but does NOT infer |
| P9 | NO | Does not access intent directly |

**Verdict:** No Phase 1-9 module INFERS intent. P6-P8 READ already-inferred intent from PO2.

### b) Does ANY Phase 1-9 module infer emotion?

| Phase | Infers Emotion? | Evidence |
|-------|----------------|----------|
| Phase 1-5 | **NO** | No emotion fields anywhere |
| P6-P9 | **NO** | No emotion inference logic |

**Verdict:** NO emotion inference anywhere in Phase 1-9.

### c) Does ANY Phase 1-9 module select regime?

| Phase | Selects Regime? | Evidence |
|-------|----------------|----------|
| Phase 1-5 | **NO** | Pure formulas and metrics |
| **P6** | **YES ❌** | `p6_regime_gate.py:147-218` - _apply_rules() selects STABILIZE/REFLECT/INFORM/CLARIFY/DE_ESCALATE/HOLD |

**Verdict:** P6 SELECTS REGIME - this is a **VIOLATION** of substrate-only constraint.

### d) Does ANY Phase 1-9 module influence discourse?

| Phase | Influences Discourse? | Evidence |
|-------|----------------------|----------|
| Phase 1-5 | **NO** | No discourse logic |
| **P7** | **YES ❌** | `p7_discourse_resolver.py:218-327` - _apply_rules() selects QUESTION/REFLECTION/ACKNOWLEDGMENT/EXPLANATION/INSTRUCTION/DEFERRAL |

**Verdict:** P7 SELECTS DISCOURSE ACT - this is a **VIOLATION** of substrate-only constraint.

### e) Does ANY Phase 1-9 module influence ontology decisions directly?

| Phase | Influences Ontology? | Evidence |
|-------|---------------------|----------|
| Phase 1-5 | **NO** | Formulas produce vectors, do not select ontology categories |
| P6-P9 | **NO** | No ontology selection; P8 fills semantic slots but does not select ontology |

**Verdict:** NO direct ontology selection in Phase 1-9.

### f) Does ANY Phase 1-9 module influence delivery/tone/rendering?

| Phase | Influences Delivery? | Evidence |
|-------|---------------------|----------|
| Phase 1-5 | **NO** | Pure signal generation |
| P6 | **CONSTRAINS** | Regime constrains downstream tone (e.g., DE_ESCALATE) |
| P7 | **CONSTRAINS** | Discourse act constrains response type |
| P8 | **CONSTRAINS** | Semantic slots constrain meaning expression |
| **P9** | **YES ❌** | `p9_lexical_resolver.py` - SELECTS WORDS, directly influences delivery |

**Verdict:** P6-P9 all influence delivery to varying degrees. P9 **SELECTS LEXICAL ITEMS** - this is a **VIOLATION** of substrate-only constraint.

---

## Section 5: Dependency Direction Report

### Phase 1-5 (Formula Substrate) - CLEAN

| Module | Imports from PO1-PO5? | Imports from P6-P9? | Verdict |
|--------|----------------------|---------------------|---------|
| `acoustic_unit_mapper.py` | NO | NO | ✔ CLEAN |
| `vritti_mapper.py` | NO | NO | ✔ CLEAN (imports acoustic_unit_mapper only) |
| `resonance_formulas.py` | NO | NO | ✔ CLEAN (no imports from pipeline) |
| `phase1_snapshot.py` | NO | NO | ✔ CLEAN (imports acoustic_unit_mapper, vritti_mapper) |
| `guna_kosha_resonance.py` | NO | NO | ✔ CLEAN (standalone math module) |

### P6-P9 (Mechanical Governance) - INTENTIONAL DEPENDENCIES

| Module | Imports from PO Phases | Imports from P Phases | Authority Flow |
|--------|----------------------|----------------------|----------------|
| `p6_regime_gate.py` | PO1 (OverallPolicy), PO2 (IntentEnvelope), PO5 (ExecutionEligibility) | None | ✔ Correct: PO → P6 |
| `p7_discourse_resolver.py` | PO1 (PhaseMinusOneEnvelope), PO2 (IntentEnvelope), PO3 (AllowedActionSet) | P6 (RegimeEnvelope) | ✔ Correct: PO → P6 → P7 |
| `p8_semantic_resolver.py` | PO1 (PhaseMinusOneEnvelope), PO2 (IntentEnvelope) | P6 (RegimeEnvelope), P7 (DiscourseEnvelope) | ✔ Correct: PO → P6 → P7 → P8 |
| `p9_lexical_resolver.py` | None | P6 (RegimeEnvelope), P7 (DiscourseEnvelope), P8 (SemanticFrame) | ✔ Correct: P6 → P7 → P8 → P9 |

### Exception Analysis

**Does Phase 1-5 import any governance modules?**

NO. The formula substrate layer (Phase 1-5) has ZERO imports from:
- PO1, PO2, PO3, PO4, PO5 (grounding/intent/action governance)
- P6, P7, P8, P9 (mechanical pipeline governance)

**Dependency Direction:**
```
Formula Substrate (Phase 1-5)
          ↑ (formulas consumed by)
          |
Governance Pipeline (PO1 → PO2 → PO3 → PO4 → PO5 → P6 → P7 → P8 → P9)
```

The direction is CORRECT - governance phases may consume formula outputs, but formula phases never import governance logic.

---

## Section 6: Final Verdict

### Classification Summary

| Component | Classification | Substrate-Only? | Recommendation |
|-----------|---------------|-----------------|----------------|
| **Phase 1 (acoustic/temporal)** | SUBSTRATE | ✔ YES | COMPLIANT |
| **Phase 2 (temporal integration)** | SUBSTRATE | ✔ YES | COMPLIANT |
| **Phase 3 (derived metrics)** | SUBSTRATE | ✔ YES | COMPLIANT |
| **Phase 4 (coherence v2)** | SUBSTRATE | ✔ YES | COMPLIANT |
| **Phase 5 (UI formulas)** | SUBSTRATE | ✔ YES | COMPLIANT |
| **P6 (regime gate)** | GOVERNANCE | ❌ NO | **VIOLATION** - Regime selection authority |
| **P7 (discourse resolver)** | GOVERNANCE | ❌ NO | **VIOLATION** - Discourse selection authority |
| **P8 (semantic resolver)** | GOVERNANCE | ❌ NO | **VIOLATION** - Semantic slot authority |
| **P9 (lexical resolver)** | GOVERNANCE | ❌ NO | **VIOLATION** - Lexical selection authority |

### Architectural Clarification Required

The "Phase 1-9" naming convention conflates two distinct architectural layers:

1. **Formula Integration Phases (Phase 1-5)**: Pure computational substrate producing numeric signals, metrics, and observations. These are correctly designed as substrate-only modules with zero authority.

2. **Mechanical Pipeline Phases (P6-P9)**: Intentionally designed governance modules that:
   - P6: Selects operational regime
   - P7: Selects discourse act type
   - P8: Resolves semantic slot requirements
   - P9: Selects lexical items

### Recommendation

If the architectural requirement is that "Phase 1-9 must be substrate-only":

**Option A - Rename P6-P9:**
Rename P6-P9 to distinguish them from the formula substrate phases. Example:
- P6 → MG1 (Mechanical Governance 1: Regime)
- P7 → MG2 (Mechanical Governance 2: Discourse)
- P8 → MG3 (Mechanical Governance 3: Semantics)
- P9 → MG4 (Mechanical Governance 4: Lexical)

**Option B - Accept Current Design:**
If P6-P9 are intentionally governance phases that follow PO1-PO5, then the naming "P6-P9" should be distinguished from "Phase 1-5" in documentation. The current design is internally consistent:
- PO1-PO5: Primary governance (intent, grounding, action)
- P6-P9: Secondary governance (regime, discourse, semantics, lexical)
- Phase 1-5: Formula substrate (non-authoritative observability)

### Compliance Statement

**Phase 1-5 Formula Substrate: FULLY COMPLIANT** ✔
- Deterministic, zero-LLM
- No intent inference
- No regime selection
- No discourse selection
- No semantic slot decisions
- No routing or gating authority
- No delivery or tone control
- No ontology authority

**P6-P9 Mechanical Governance: NOT COMPLIANT** with substrate-only requirement ❌
- P6: SELECTS regime (HOLD/STABILIZE/REFLECT/INFORM/CLARIFY/DE_ESCALATE)
- P7: SELECTS discourse act (QUESTION/REFLECTION/ACKNOWLEDGMENT/EXPLANATION/INSTRUCTION/DEFERRAL)
- P8: DETERMINES semantic slots (AGENT/TARGET/STATE/CAUSE/etc.)
- P9: SELECTS lexical items (words from curated pools)

---

## Appendix: Line-Level Evidence for Violations

### P6 Regime Selection (p6_regime_gate.py)

```python
# Lines 147-218: _apply_rules() method
def _apply_rules(
    self,
    intent_type: IntentType,
    eligibility: ExecutionEligibility,
    coherence_regime: str,
    overall_policy: OverallPolicy,
) -> tuple[OperationalRegime, str]:
    """Apply deterministic rules to select regime."""
    # Rule 1: If execution.eligibility == PROHIBITED → HOLD
    if eligibility == ExecutionEligibility.PROHIBITED:
        return (OperationalRegime.HOLD, ...)
    # ... Rules 2-7 selecting different regimes
```

### P7 Discourse Selection (p7_discourse_resolver.py)

```python
# Lines 218-327: _apply_rules() method
def _apply_rules(...) -> tuple[DiscourseAct, bool, str]:
    """Apply deterministic rules to resolve discourse act."""
    # Rule 1: If regime == HOLD → DEFERRAL
    if regime == OperationalRegime.HOLD:
        return (DiscourseAct.DEFERRAL, True, ...)
    # ... Rules 2-7 selecting different discourse acts
```

### P8 Semantic Resolution (p8_semantic_resolver.py)

```python
# Lines 101-201: resolve() method
def resolve(...) -> SemanticFrame:
    """Resolve semantic slots based on deterministic rules."""
    # ... Slot resolution logic determining which semantic slots to populate
```

### P9 Lexical Selection (p9_lexical_resolver.py)

```python
# Lines 90-171: resolve() method
def resolve(...) -> LexicalFrame:
    """Resolve lexical selections based on deterministic rules."""
    # ... Word selection from curated pools
```

---

*End of Audit Report*
