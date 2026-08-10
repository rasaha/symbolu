# P34 (Identity Harmonics) & P37 (Narrative Continuity) Specification

**Date:** 2025-12-21
**Status:** SPECIFICATION - Pre-Implementation
**Priority:** P1 (Short-term)

---

## Executive Summary

P34 (Identity Harmonics Layer) and P37 (Narrative Continuity / Adaptive Continuity Engine) are **currently implemented as formulas** but lack **pipeline integration wrappers**. This specification defines what exists, what's missing, why these phases are needed, and what implementation entails.

| Phase | Formula Location | Pipeline Location | Status |
|-------|------------------|-------------------|--------|
| **P34** | `symbolu/formulas/identity_harmonics.py` | Missing | Formula complete, pipeline wrapper needed |
| **P37** | `symbolu/formulas/adaptive_continuity_engine.py` | Missing | Formula complete, pipeline wrapper needed |

---

## Part 1: P34 - Identity Harmonics Layer (IHL)

### 1.1 What It Does

P34 computes **identity resonance patterns** across semantic, emotional, symbolic, and temporal dimensions. It produces three identity-resonance harmonics:

| Harmonic | Abbreviation | Description |
|----------|--------------|-------------|
| **Core Identity Harmonic** | CIH | Stability of identity signals across turns |
| **Adaptive Identity Harmonic** | AIH | Ability to shift identity expression coherently |
| **Relational Identity Harmonic** | RIH | Resonance between persona tone + symbolic harmonization |

### 1.2 Formula Already Implemented

**Location:** `symbolu/formulas/identity_harmonics.py`

```python
# Key components already exist:
IdentityHarmonicsSnapshot  # Immutable output dataclass
compute_identity_harmonics(...)  # Main computation function
```

**Output Fields:**
- `core_identity_harmonic` (CIH): [0.0, 1.0]
- `adaptive_identity_harmonic` (AIH): [0.0, 1.0]
- `relational_identity_harmonic` (RIH): [0.0, 1.0]
- `identity_harmonics_index` (IHI): Combined overall score
- `identity_entropy`: Entropy of harmonic components
- `identity_stability_score`: Derived stability measure
- `identity_flexibility_score`: Derived flexibility measure
- `notes`: Deterministic diagnostic tags

### 1.3 Authority Level

**OBSERVATIONAL / WITNESS**

Critical invariants (already enforced in formula):
- **Zero-LLM:** Purely rule-based, deterministic math only
- **Observation-only:** NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
- **Tone-level only:** NEVER semantic changes (bounded ±0.02)
- **Non-invasive:** Does not modify any existing coherence formulas
- **Deterministic:** Same inputs → same outputs always
- **Graceful degradation:** Returns None if core inputs missing

### 1.4 What's Missing (Pipeline Integration)

**Need to create:** `symbolu/mechanical/pipeline/p34_identity_harmonics/`

```
p34_identity_harmonics/
├── __init__.py                 # Public exports
├── p34_identity_harmonics_schema.py  # P34Authority, P34Output dataclasses
└── p34_integration.py          # extract_p34_signals(), maybe_run_p34(), get_p34_output()
```

**Integration Functions Needed:**

| Function | Purpose |
|----------|---------|
| `extract_p34_signals(ctx)` | Extract signals from PipelineContext |
| `run_p34_harmonics(signals)` | Run identity harmonics computation |
| `maybe_run_p34(ctx)` | Conditionally run P34 in orchestrator |
| `get_p34_output(ctx)` | Get P34 output from context |
| `get_p34_identity_harmonics_index(ctx)` | Get IHI score |
| `get_p34_stability_score(ctx)` | Get stability score |

### 1.5 Why It's Needed

| Benefit | Description |
|---------|-------------|
| **Downstream Dependency** | P35 (Predictive Persona Drift), P36 (Identity Resonance Memory) consume P34 output |
| **Persona Tone Modulation** | Enables micro-adjustments (±0.02) to persona delivery |
| **Session Analytics** | Powers identity coherence dashboards |
| **Diagnostic Tags** | Provides IDENTITY_STABLE, IDENTITY_FRAGILE, HARMONIC_ALIGNMENT_HIGH, etc. |
| **Coherence State Integration** | Already integrated into CoherenceState via `update_from_coherence()` |

### 1.6 Why It's Good to Have

1. **Completes the Identity Stack:** P34 bridges P26 (Consciousness) → P35 (Drift Prediction) → P36 (Identity Memory)
2. **Enables Identity-Aware Responses:** Without P34, downstream phases lack identity stability signals
3. **Already Referenced:** P35, P36, and formulas already expect P34 output
4. **Test Suite Exists:** `tests/test_phase34_identity_harmonics.py` already validates the formula
5. **Graceful Degradation:** Pipeline can run without P34, but loses identity coherence signals

---

## Part 2: P37 - Adaptive Continuity Engine (ACE)

### 2.1 What It Does

P37 computes **session-wide continuity** across narrative, identity, emotional, and symbolic dimensions. It produces three canonical continuity signals:

| Signal | Abbreviation | Description |
|--------|--------------|-------------|
| **Narrative Continuity Coefficient** | NCC | Stability of themes, intents, motivations, and symbolic patterns across turns |
| **Identity Continuity Coefficient** | ICC | Derived from P36 (IRM), P34 (IHL), and P35 (PPDM) |
| **Continuity Stability Score** | CSS | Aggregate measure of session-wide resilience, alignment, and predictability |

### 2.2 Formula Already Implemented

**Location:** `symbolu/formulas/adaptive_continuity_engine.py`

```python
# Key components already exist:
AdaptiveContinuitySnapshot  # Immutable output dataclass
compute_adaptive_continuity(...)  # Main computation function
```

**Output Fields:**
- `ncc`: Narrative Continuity Coefficient [0.0, 1.0]
- `icc`: Identity Continuity Coefficient [0.0, 1.0]
- `css`: Continuity Stability Score [0.0, 1.0]
- `continuity_band`: "LOW" / "MEDIUM" / "HIGH"
- `continuity_tags`: CONTINUITY_STRONG, CONTINUITY_FRAGMENTED, etc.
- `raw_signals`: All intermediate signals for API exposure

### 2.3 Authority Level

**PREDICTIVE / READ-ONLY**

Critical invariants (already enforced in formula):
- **Zero-LLM:** Purely rule-based, deterministic math only
- **Observation-only:** NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
- **Tone-level only:** NEVER semantic changes (bounded ±0.015)
- **Non-invasive:** Does not modify any existing coherence formulas
- **Deterministic:** Same inputs → same outputs always
- **Graceful degradation:** Returns None if insufficient data

### 2.4 What's Missing (Pipeline Integration)

**Need to create:** `symbolu/mechanical/pipeline/p37_continuity/`

```
p37_continuity/
├── __init__.py               # Public exports
├── p37_continuity_schema.py  # P37Authority, ContinuityBand enum, P37Output
└── p37_integration.py        # extract_p37_signals(), maybe_run_p37(), get_p37_output()
```

**Integration Functions Needed:**

| Function | Purpose |
|----------|---------|
| `extract_p37_signals(ctx)` | Extract signals from PipelineContext |
| `run_p37_continuity(signals)` | Run adaptive continuity computation |
| `maybe_run_p37(ctx)` | Conditionally run P37 in orchestrator |
| `get_p37_output(ctx)` | Get P37 output from context |
| `get_p37_ncc(ctx)` | Get Narrative Continuity Coefficient |
| `get_p37_icc(ctx)` | Get Identity Continuity Coefficient |
| `get_p37_css(ctx)` | Get Continuity Stability Score |
| `get_p37_continuity_band(ctx)` | Get continuity band classification |

### 2.5 Why It's Needed

| Benefit | Description |
|---------|-------------|
| **Downstream Dependency** | `macro_stability_regulator.py` consumes P37 NCC, ICC, CSS |
| **Trajectory Convergence** | `trajectory_field_convergence.py` uses P37 continuity signals |
| **Scenario Alignment** | `coherence_regime_scenario_mapper.py` uses P37 for stability computation |
| **Multi-Turn Coherence** | Measures how coherent the conversation feels as a continuous unfolding |

### 2.6 Why It's Good to Have

1. **Completes the Continuity Stack:** P37 bridges P27 (Symbolic) → P36 (Identity Memory) → P38 (Forecast)
2. **Session Resilience Metric:** CSS indicates whether session can withstand perturbations
3. **Already Referenced:** macro_stability_regulator.py, trajectory_field_convergence.py expect P37
4. **Diagnostic Tags:** CONTINUITY_STRONG, CONTINUITY_FRAGMENTED, continuity_excellence
5. **Core Implementation Exists:** Also at `symbolu/core/continuity/adaptive_continuity_engine.py`

---

## Part 3: Implementation Plan

### 3.1 P34 Implementation Steps

| Step | Task | Effort |
|------|------|--------|
| 1 | Create `p34_identity_harmonics/` directory structure | Low |
| 2 | Create `p34_identity_harmonics_schema.py` with P34Authority enum, P34Output dataclass | Low |
| 3 | Create `p34_integration.py` wrapping existing formula | Medium |
| 4 | Add `maybe_run_p34(ctx)` call site in CoherenceEngine (already exists) | Low |
| 5 | Create unit tests in `tests/unit/mechanical/pipeline/p34_identity_harmonics/` | Medium |
| 6 | Update PHASE_STATUS.yaml to mark P34 as active | Low |

### 3.2 P37 Implementation Steps

| Step | Task | Effort |
|------|------|--------|
| 1 | Create `p37_continuity/` directory structure | Low |
| 2 | Create `p37_continuity_schema.py` with P37Authority, ContinuityBand enums, P37Output | Low |
| 3 | Create `p37_integration.py` wrapping existing formula | Medium |
| 4 | Add `maybe_run_p37(ctx)` call site (determine correct position in pipeline) | Low |
| 5 | Create unit tests in `tests/unit/mechanical/pipeline/p37_continuity/` | Medium |
| 6 | Update PHASE_STATUS.yaml to mark P37 as active | Low |

### 3.3 Estimated Total Effort

| Phase | Schema | Integration | Tests | Total |
|-------|--------|-------------|-------|-------|
| P34 | 1 hour | 2 hours | 2 hours | **5 hours** |
| P37 | 1 hour | 2 hours | 2 hours | **5 hours** |
| **Total** | 2 hours | 4 hours | 4 hours | **10 hours** |

---

## Part 4: Dependencies

### 4.1 P34 Input Dependencies

| Dependency | Phase | Required? |
|------------|-------|-----------|
| `semantic_integrity` | P17 | At least 1 from this group |
| `symbolic_harmonization_index` | P27 | At least 1 from this group |
| `consciousness_order_index` | P26 | At least 1 from this group |
| `cognitive_drift_v3` | P17 | At least 1 from this group |
| `temporal_entropy_volatility` | P18 | At least 1 from this group |
| `loop_alignment` | - | At least 1 from this group |
| `persona_drift_score` | P35 | At least 1 from this group |
| `guna_resonance_index` | - | At least 1 from this group |
| `kosha_resonance_index` | - | At least 1 from this group |

### 4.2 P37 Input Dependencies

| Dependency | Phase | Required? |
|------------|-------|-----------|
| `symbolic_harmonization_index` | P27 | At least 1 narrative signal |
| `semantic_integrity` | P17 | At least 1 narrative signal |
| `consciousness_order_index` | P26 | At least 1 narrative signal |
| `identity_memory_strength` (IMS) | P36 | At least 1 identity signal |
| `identity_echo_persistence` (IEP) | P36 | At least 1 identity signal |
| `core_identity_harmonic` (CIH) | P34 | At least 1 identity signal |
| `adaptive_identity_harmonic` (AIH) | P34 | At least 1 identity signal |

### 4.3 Downstream Consumers

**P34 (Identity Harmonics) is consumed by:**
- P35 (Predictive Persona Drift Model)
- P36 (Identity Resonance Memory)
- P37 (Adaptive Continuity Engine)
- CoherenceState (`update_from_coherence()`)

**P37 (Adaptive Continuity) is consumed by:**
- `macro_stability_regulator.py`
- `trajectory_field_convergence.py`
- `coherence_regime_scenario_mapper.py`
- `coherence_scenario_alignment.py`

---

## Part 5: Alternative: Document as Deferred

If implementation is deferred, the following steps should be taken:

1. **Document in PHASE_STATUS.yaml:**
   ```yaml
   P34:
     status: deferred
     reason: "Pipeline wrapper not yet implemented, formula exists"
     formula_location: symbolu/formulas/identity_harmonics.py

   P37:
     status: deferred
     reason: "Pipeline wrapper not yet implemented, formula exists"
     formula_location: symbolu/formulas/adaptive_continuity_engine.py
   ```

2. **Remove references that expect pipeline wrappers**
   - Update downstream consumers to call formulas directly (not via pipeline)

3. **Update architecture docs**
   - Mark P34/P37 as "Formula-only, no pipeline integration"

---

## Recommendation

**Implement P34 and P37 pipeline wrappers.**

**Rationale:**
1. Formulas are complete and tested
2. Downstream phases already reference them
3. Implementation effort is low (10 hours total)
4. Completes the identity/continuity stack
5. Enables consistent pipeline integration pattern

---

## Appendix A: Existing Test Coverage

| Phase | Test File | Status |
|-------|-----------|--------|
| P34 | `tests/test_phase34_identity_harmonics.py` | EXISTS |
| P37 | (Need to create or verify) | NEEDS VERIFICATION |

---

## Appendix B: Schema Patterns to Follow

The P34/P37 pipeline wrappers should follow the same patterns as P27-P31:

```
p34_identity_harmonics/
├── __init__.py                         # Re-export public API
├── p34_identity_harmonics_schema.py    # VERSION, P34Authority, P34InputSignals, P34Output
└── p34_integration.py                  # extract_p34_signals(), run_p34_harmonics(), maybe_run_p34(), get_p34_output()
```

Key conventions:
- `VERSION = "1.0.0"`
- Frozen dataclasses for immutability
- `to_dict()` methods for serialization
- `maybe_run_pXX()` for conditional execution
- `get_pXX_output()` for context retrieval
- Singleton pattern for expensive initializations

---

*End of Specification*
