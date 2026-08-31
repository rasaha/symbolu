# 12D Ontological Architecture Migration Design Document

**Version:** 1.0
**Date:** 2024-12-24
**Status:** Active Migration Plan

---

## Executive Summary

This document outlines the comprehensive migration from the legacy 10-dimensional (10D) ontological system to the new 12-dimensional (12D) architecture. The migration affects approximately **80+ files** across the Symbol-U codebase, including core resonance modules, phoneme mappings, hybrid routing, training pipelines, and documentation.

---

## Part 1: Technical Assessment of the Ontological Training Engine

### 1.1 How the Training Engine Works

The ontological training engine operates through several key mechanisms:

```
Input Text → Encoder (MiniLM 384D) → MLP Backbone → Evidential Head → 12D Ontological Vector
                                           ↓
                                    Semantic Bhava Layer → 132D Relational Vector
```

**Key Components:**

| Component | Dimension | Purpose |
|-----------|-----------|---------|
| MiniLM Encoder | 384D | Semantic embedding of text |
| MLP Backbone | 256→128D | Feature extraction |
| Evidential Head | 12D | Ontological classification with uncertainty |
| Bhava Layer | 132D (11×12) | Relational dynamics between layers |

### 1.2 Why the Training is Effective

**Positive Scoping Mechanisms:**

1. **Contrastive Learning Separation**
   - Triplet loss ensures different domains occupy distinct regions in embedding space
   - Achieved 86% domain separation in early experiments

2. **Evidential Deep Learning**
   - Dirichlet-based uncertainty quantification
   - Model knows when it doesn't know (uncertainty ~0.56 mean)
   - KL-divergence regularization prevents overconfident predictions

3. **Multi-Label Soft Targets**
   - Labels aren't one-hot but probabilistic distributions
   - Allows text to span multiple ontological layers naturally
   - Label smoothing prevents overfitting to hard boundaries

4. **Hierarchical Architecture**
   - 12 layers follow a coherent progression: Potential → Absolving
   - Adjacent layer relationships (Bhava) capture gradients between states
   - Sub-layers within Bhava provide fine-grained relational detail

### 1.3 Training Results Analysis

| Model Variant | Accuracy | Uncertainty | Key Achievement |
|--------------|----------|-------------|-----------------|
| Multi-Domain (10D) | 99% | N/A | Baseline classification |
| Contrastive | 100% | N/A | Domain separation |
| Evidential | 96.5% | 0.563 | Uncertainty awareness |
| Unified | 94% | ~0.5 | Math→Reasoning fixed |

**Critical Insight:** The unified model with evidential learning correctly routes mathematical queries to O7_REASONING (previously misrouted to O3_EXECUTION). This demonstrates the architecture's ability to learn semantic intent beyond surface patterns.

### 1.4 Technical Opinion

**Strengths:**
- The 12D architecture is semantically richer than 10D
- The addition of O1_POTENTIAL and O11_INTEGRATION fills gaps in the ontological spectrum
- Bhava sub-layers matching ontological layers creates elegant self-similarity
- Evidential approach provides calibrated confidence

**Recommendations:**
- Training data should be regenerated with 12D layer semantics
- The phoneme affinity mappings need expert curation for 12D
- Consider transfer learning from the 10D trained weights

---

## Part 2: Migration Scope

### 2.1 System Architecture Conflict

**Current State:** The codebase has TWO parallel ontological systems in conflict:

| System | Location | Layers | Status |
|--------|----------|--------|--------|
| ML Training | `symbolu/ontological/` | 12D ✓ | Updated |
| Resonance/Phoneme | `symbolu/resonance/` | 10D ✗ | Legacy |
| Core Ontology | `symbolu/ontology/layers/` | 10D ✗ | Legacy |
| Hybrid Router | `symbolu/hybrid/` | 10D ✗ | Legacy |

### 2.2 Files Requiring Updates

#### TIER 1: Critical Core (Blocking)

| File | Lines Affected | Change Type |
|------|----------------|-------------|
| `symbolu/resonance/types.py` | 40-55, 59-70, 85-114 | Enum expansion, validation |
| `symbolu/resonance/phoneme_map.py` | 34-233 | 50+ phoneme tuples (10→12 elements) |
| `symbolu/ontology/layers/ontology_layer.py` | 40-68 | Enum expansion (10→12 members) |
| `symbolu/core/constants.py` | 146-160 | ONTOLOGICAL_LAYERS dict |
| `symbolu/resonance/varna_bridge.py` | 210-410 | Function renames, 12D vectors |

#### TIER 2: Integration Layer

| File | Changes Needed |
|------|----------------|
| `symbolu/hybrid/router.py` | LAYER_TO_MODEL mapping (12 entries) |
| `symbolu/resonance/engine.py` | 12D vector computation |
| `symbolu/resonance/analyzer.py` | 12D WordVector handling |
| `symbolu/hybrid/vocabulary.py` | 12D layer affinity |
| `symbolu/hybrid/attention.py` | 12D references |

#### TIER 3: Downstream Consumers

| Module | Files Affected |
|--------|----------------|
| Name Resonance | 3 files importing LAYER_NAMES |
| Dynamics Phase 5 | 2 files |
| Mechanical Renderer | 1 file |
| Benchmarks | 3 files |

#### TIER 4: Test Files

| Test File | Assertions to Update |
|-----------|---------------------|
| `tests/test_hybrid_router.py` | 10 expected layers |
| `tests/test_10d_backbone.py` | `len() == 10` checks |
| `tests/resonance/test_resonance_engine.py` | `len() == 10` |
| `restoration/.../test_k1_schema.py` | `len(ALL_LAYERS) == 10` |
| `restoration/.../test_phase11a_evaluation.py` | Layer count assertions |

#### TIER 5: Documentation

| Document | Updates Needed |
|----------|---------------|
| `docs/SYMBOLU_ENGINE_ARCHITECTURE.md` | 10D→12D throughout |
| `docs/AGI_CAPABILITIES.md` | "10D backbone" references |
| `docs/INVESTOR_PITCH.md` | "768D → 10D" reduction claims |
| `docs/PRODUCTION_IMPLEMENTATION.md` | 10D phoneme vectors |
| 8+ other markdown files | Various 10D references |

---

## Part 3: New 12D Layer Definitions

### 3.1 Layer Mapping (Old → New)

| # | Old (10D) | New (12D) | Semantic Shift |
|---|-----------|-----------|----------------|
| 1 | O1_THINKING | O1_POTENTIAL | Dormant→Active thinking |
| 2 | O2_FORMING | O2_IDENTITY | Tagging/classification |
| 3 | O3_ACTING | O3_EXECUTION | Action/karma |
| 4 | O4_TAGGING | O4_STRUCTURE | Forming/embodiment |
| 5 | O5_DIRECTING | O5_COGNITION | Perception/emotion |
| 6 | O6_REASONING | O6_AGENCY | Direction/control |
| 7 | O7_PURPOSING | O7_REASONING | Discrimination/logic |
| 8 | O8_META_OBSERVING | O8_PURPOSE | Meaning/motivation |
| 9 | O9_UNIFYING | O9_WITNESSES | Meta-observation |
| 10 | O10_ABSOLVING | O10_UNIFYING | Coherence/synthesis |
| 11 | (NEW) | O11_INTEGRATION | Resolution/consolidation |
| 12 | (NEW) | O12_ABSOLVING | Termination/release |

### 3.2 Phoneme Affinity Extension Strategy

Current phoneme mappings are 10-element tuples. Extension options:

**Option A: Interpolation**
```python
# Old: (0.8, 0.6, 0.9, 0.4, 0.7, 0.5, 0.3, 0.6, 0.4, 0.5)
# New: Interpolate positions 0-1 and 10-11
```

**Option B: Expert Curation**
- Map each phoneme to 12 layers based on semantic analysis
- Requires phonetics/linguistics expertise

**Option C: Training-Based**
- Initialize randomly, let model learn optimal mappings
- Risk: May diverge from phonetic grounding

**Recommendation:** Option B with fallback to Option A for rapid migration.

---

## Part 4: Migration Plan

### Phase 1: Core Types (Day 1)

1. **Update `symbolu/resonance/types.py`**
   ```python
   class OntologicalLayer(Enum):
       O1_POTENTIAL = 1      # NEW
       O2_IDENTITY = 2       # Was O1
       O3_EXECUTION = 3      # Was O3
       O4_STRUCTURE = 4      # Was O2
       O5_COGNITION = 5      # Was O4
       O6_AGENCY = 6         # Was O5
       O7_REASONING = 7      # Was O6
       O8_PURPOSE = 8        # Was O7
       O9_WITNESSES = 9      # Was O8
       O10_UNIFYING = 10     # Was O9
       O11_INTEGRATION = 11  # NEW
       O12_ABSOLVING = 12    # Was O10
   ```

2. **Update validation in types.py**
   - Change `len(layer_affinities) == 10` → `== 12`
   - Change `len(vector) == 10` → `== 12`

3. **Update `symbolu/core/constants.py`**
   - Expand ONTOLOGICAL_LAYERS dict to 12 entries

### Phase 2: Phoneme Mappings (Day 2-3)

1. **Extend all tuples in `symbolu/resonance/phoneme_map.py`**
   - 50+ phoneme entries
   - Each tuple: 10 values → 12 values
   - Add O1_POTENTIAL and O11_INTEGRATION affinities

2. **Update varna_bridge.py**
   - Rename `varna_to_10d_vector()` → `varna_to_12d_vector()`
   - Update all internal computations

### Phase 3: Integration Layer (Day 4)

1. **Update `symbolu/hybrid/router.py`**
   - Expand LAYER_TO_MODEL mapping
   - Add model assignments for O1_POTENTIAL and O11_INTEGRATION

2. **Update engine and analyzer**
   - Ensure 12D vector handling throughout

### Phase 4: Tests (Day 5)

1. **Fix all assertions**
   - `len() == 10` → `len() == 12`
   - Update expected layer lists

2. **Rename test file**
   - `test_10d_backbone.py` → `test_12d_backbone.py`

### Phase 5: Documentation (Day 6)

1. **Update all markdown files**
   - Search/replace "10D" → "12D"
   - Update architecture diagrams
   - Update investor materials

---

## Part 5: Training Data Requirements

### 5.1 New Layer Training Examples

| Layer | Example Texts |
|-------|---------------|
| O1_POTENTIAL | "This could become...", "Seeds of possibility", "Dormant capacity" |
| O2_IDENTITY | "I am a...", "Labels and roles", "Classification" |
| O3_EXECUTION | "Run the command", "Execute now", "Action taken" |
| O4_STRUCTURE | "The form is...", "Architectural design", "Pattern structure" |
| O5_COGNITION | "I feel...", "Perceiving the...", "Emotional response" |
| O6_AGENCY | "I decide to...", "Taking control", "Directing action" |
| O7_REASONING | "Calculate...", "Logically...", "The inference is" |
| O8_PURPOSE | "The meaning of...", "Why we...", "Motivated by" |
| O9_WITNESSES | "Observing the...", "Meta-awareness", "Reflecting on" |
| O10_UNIFYING | "Everything connects", "Synthesis of", "Coherent whole" |
| O11_INTEGRATION | "Consolidating all", "Resolution achieved", "Parts complete" |
| O12_ABSOLVING | "Letting go", "Final release", "Termination" |

### 5.2 Dataset Regeneration

The `multi_domain_dataset.py` templates need complete rewrite for 12D semantics:

```python
DOMAIN_TEMPLATES = {
    "O1_POTENTIAL": [...],  # 100+ examples
    "O2_IDENTITY": [...],
    # ... all 12 domains
}
```

---

## Part 6: Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking phoneme mapping | High | Extensive testing, gradual rollout |
| Test failures cascade | Medium | Update tests before code |
| Training regression | Medium | Preserve 10D model checkpoints |
| Documentation drift | Low | Automated doc generation |

---

## Part 7: Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Test pass rate | 100% | CI pipeline |
| Training accuracy | >90% | Benchmark script |
| Domain separation | >85% | Contrastive evaluation |
| Uncertainty calibration | <0.6 mean | Evidential metrics |

---

## Appendix A: File Change Summary

**Total Files: ~80+**

| Category | Count | Effort |
|----------|-------|--------|
| Core Types | 5 | 4 hours |
| Phoneme Maps | 1 (50+ tuples) | 8 hours |
| Integration | 10 | 6 hours |
| Tests | 15 | 4 hours |
| Documentation | 12+ | 3 hours |
| Training Scripts | 5 | 2 hours |

**Total Estimated Effort: 27+ hours**

---

## Appendix B: Backward Compatibility

For systems that cannot immediately migrate:

```python
# Compatibility shim
def to_10d_vector(vec_12d):
    """Convert 12D vector to legacy 10D format."""
    # Map: [0,1,2,3,4,5,6,7,8,9,10,11] → [1,3,2,4,5,6,7,8,9,11]
    mapping = [1, 3, 2, 4, 5, 6, 7, 8, 9, 11]
    return [vec_12d[i] for i in mapping]
```

**Not recommended for long-term use.**

---

*Document maintained by: Symbol-U Development Team*
*Last Updated: 2024-12-24*
