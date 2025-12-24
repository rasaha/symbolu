# Patent Formula Coverage Matrix v1.0

## 1. Overview

This document maps patent formulas from the Symbol-U intellectual property to their current implementation status in the Symbol-U v3.0 codebase. It serves as an alignment and audit layer to track:

- Which patent formulas are implemented and where
- Test coverage and CI guardrails for implemented formulas
- Behavioral impact of each formula
- Drift detection mechanisms

**Important:** This is **not** an activation of patent logic. This is a documentation and alignment layer that ensures:
- Implemented formulas remain stable and deterministic
- Future patent formula integrations follow established patterns
- No unintended drift occurs in existing formula implementations
- All formula changes are tracked and auditable

## 2. Patent Formula Categories

The following table categorizes all patent formulas by type, implementation status, and behavioral impact:

| Patent Formula Category | Formula Name | Description | Exists in Code? | Module Path | Behavioral Impact | Drift Guard? |
|------------------------|--------------|-------------|-----------------|-------------|-------------------|--------------|
| Temporal Resonance | SMI | Weighted symbolic mental index | Yes | `symbolu/formulas/resonance_formulas.py` | Observation-only | Yes |
| Temporal Resonance | ΔSMI | Momentum of SMI | Yes | `symbolu/formulas/resonance_formulas.py` | Observation-only | Yes |
| Temporal Geometry | Bhava Gap | 12-bhava circular distance | Yes | `symbolu/formulas/resonance_formulas.py` | Observation-only | Yes |
| Temporal Geometry | Tension Corridor | Blended tension metric | Yes | `symbolu/formulas/resonance_formulas.py` | Observation-only | Yes |
| Derived Metrics | Resonance Index | Formula from Phase 3 | Yes | `symbolu/core/coherence/coherence_engine.py` | Observation-only | Yes |
| Derived Metrics | Tension Index | Formula from Phase 3 | Yes | `symbolu/core/coherence/coherence_engine.py` | Observation-only | Yes |
| Derived Metrics | Arc Alignment Index | Formula from Phase 3 | Yes | `symbolu/core/coherence/coherence_engine.py` | Observation-only | Yes |
| Behavioral Formulas | Hope/Growth Bias | (Patent only) | No | — | Not implemented | No |
| Behavioral Formulas | Greed Collapse Curve | (Patent only) | No | — | Not implemented | No |
| Kosha/Guna | Vrtti Distribution | (Patent only) | No | — | Not implemented | No |
| Kosha/Guna | Kosha-Delta Metric | (Patent only) | No | — | Not implemented | No |
| Unified Cognitive Formula | Cognitive Arc Equation | (Patent only) | No | — | Not implemented | No |

## 3. Implementation Status Summary

### 3.1 Implemented Under Phase 1–5

The following patent formulas are currently implemented in the Symbol-U v3.0 codebase:

#### Phase 1: Temporal Resonance Formulas
- **SMI (Symbolic Mental Index)**: `symbolu/formulas/resonance_formulas.py:compute_smi()`
  - Weighted combination of dimensional resonance, vrtti intensity, and bhava position
  - Output range: [0.0, 1.0]
  - Drift guard: `symbolu/core/formula_drift_tests/test_phase1_resonance_formulas.py`

- **ΔSMI (Delta SMI)**: `symbolu/formulas/resonance_formulas.py:compute_delta_smi()`
  - Momentum tracking of SMI changes across turns
  - Output range: [-1.0, 1.0]
  - Drift guard: `symbolu/core/formula_drift_tests/test_phase1_resonance_formulas.py`

#### Phase 1: Temporal Geometry Formulas
- **Bhava Gap**: `symbolu/formulas/resonance_formulas.py:compute_bhava_gap()`
  - Circular distance in the 12-bhava consciousness cycle
  - Output range: [0.0, 1.0]
  - Drift guard: `symbolu/core/formula_drift_tests/test_phase1_resonance_formulas.py`

- **Tension Corridor**: `symbolu/formulas/resonance_formulas.py:compute_tension_corridor()`
  - Composite tension dynamics signal combining ΔSMI and Bhava Gap
  - Output range: [0.0, 1.0]
  - Drift guard: `symbolu/core/formula_drift_tests/test_phase1_resonance_formulas.py`

#### Phase 3: Derived Metrics
- **Resonance Index**: `symbolu/core/coherence/coherence_engine.py:compute_derived_formula_metrics()`
  - Derived from SMI and temporal arc score
  - Output range: [0.0, 1.0]
  - Drift guard: `symbolu/mechanical/pipeline/integration_tests/test_phase3_derived_formula_metrics.py`

- **Tension Index**: `symbolu/core/coherence/coherence_engine.py:compute_derived_formula_metrics()`
  - Derived from Tension Corridor and mapper volatility
  - Output range: [0.0, 1.0]
  - Drift guard: `symbolu/mechanical/pipeline/integration_tests/test_phase3_derived_formula_metrics.py`

- **Arc Alignment Index**: `symbolu/core/coherence/coherence_engine.py:compute_derived_formula_metrics()`
  - Derived from temporal arc score and persona drift
  - Output range: [0.0, 1.0]
  - Drift guard: `symbolu/mechanical/pipeline/integration_tests/test_phase3_derived_formula_metrics.py`

### 3.2 Patent-Defined but Not Implemented

The following patent formulas are documented in the Symbol-U intellectual property but **not yet implemented** in the codebase:

- **Hope/Growth Bias**: Behavioral formula for tracking optimism vs. growth mindset dynamics
- **Greed Collapse Curve**: Behavioral formula for detecting greed-driven instability patterns
- **Vrtti Distribution**: Kosha/Guna formula for mental fluctuation patterns across koshas
- **Kosha-Delta Metric**: Kosha/Guna formula for tracking changes in consciousness layers
- **Cognitive Arc Equation**: Unified cognitive formula combining all patent formulas into a holistic consciousness trajectory model

### 3.3 Planned Integration Phases

Future integration of patent-only formulas is planned across the following phases:

- **Phase 7: Trading Safety Formulas** (Hope/Growth Bias, Greed Collapse Curve)
  - Focus: Trading domain safety enhancements
  - Behavioral impact: Risk detection and grounding triggers
  - Activation: Feature-flagged, domain-specific

- **Phase 8: Kosha/Guna Integration** (Vrtti Distribution, Kosha-Delta Metric)
  - Focus: Consciousness layer tracking
  - Behavioral impact: Deepened symbolic/mirror output
  - Activation: Feature-flagged, therapy/identity domains only

- **Phase 9: Hope–Greed Harmonics**
  - Focus: Cross-domain behavioral pattern detection
  - Behavioral impact: Enhanced coherence scoring
  - Activation: Feature-flagged, all domains

- **Phase 10+: Cognitive Arc Full Equation**
  - Focus: Unified consciousness trajectory model
  - Behavioral impact: Holistic coherence and arc tracking
  - Activation: Feature-flagged, requires Phases 7–9 completion

## 4. CI Drift Guardrails

### Current Drift Protection

The Symbol-U codebase employs comprehensive drift detection for all implemented patent formulas:

#### Phase 1 Drift Tests
- **Test Suite**: `symbolu/core/formula_drift_tests/test_phase1_resonance_formulas.py`
- **Coverage**: SMI, ΔSMI, Bhava Gap, Tension Corridor
- **Mechanism**: Canonical fixture comparison (12-sample grid)
- **CI Workflow**: `.github/workflows/formula-drift-ci.yml`
- **Tolerance**: ±1e-7 (floating-point precision)

#### Phase 3 Derived Metric Tests
- **Test Suite**: `symbolu/mechanical/pipeline/integration_tests/test_phase3_derived_formula_metrics.py`
- **Coverage**: Resonance Index, Tension Index, Arc Alignment Index
- **Mechanism**: Integration test with pipeline outputs
- **CI Workflow**: `.github/workflows/pipeline-ci.yml`
- **Tolerance**: Deterministic equality checks

#### Unified Canonical Fixtures
- **Phase 1 Fixtures**: `symbolu/core/formula_drift_tests/phase1_resonance_fixtures.json`
- **Generation**: `python symbolu/tools/formula_fixtures/generate_phase1_resonance_fixtures.py`
- **Update Policy**: Only regenerate when intentionally updating formulas
- **Schema Validation**: Automated schema checks in drift tests

### Future Requirement: Formula Tagging

**All future patent formula implementations must be tagged before activation.**

Starting with Phase 6, all formulas (implemented and patent-only) are tagged in `symbolu/formulas/patent_tags.py`. This tagging system enables:
- Automated tracking of formula implementation status
- Drift detection for formula metadata
- Clear lineage from patent to implementation
- Audit trail for formula changes

See Section 5 for developer instructions on adding formula tags.

## 5. Developer Instructions

### How to Add a Formula to the Matrix

When implementing a new patent formula:

1. **Implement the formula** in the appropriate module:
   - Temporal formulas: `symbolu/formulas/resonance_formulas.py`
   - Derived metrics: `symbolu/core/coherence/coherence_engine.py`
   - Behavioral formulas: `symbolu/formulas/behavioral_formulas.py` (future)

2. **Add a tag** in `symbolu/formulas/patent_tags.py`:
   ```python
   PATENT_FORMULA_TAGS = {
       # ...existing tags...
       "new_formula_name": "phaseN_category",
   }
   ```

3. **Update the snapshot** in `symbolu/core/formula_drift_tests/test_patent_alignment_tags.py`:
   ```python
   EXPECTED_TAGS = {
       # ...existing tags...
       "new_formula_name": "phaseN_category",
   }
   ```

4. **Create drift tests** for the formula:
   - Add canonical fixtures
   - Add drift detection tests
   - Add range/monotonicity/determinism tests

5. **Update this document** to reflect the new formula:
   - Add row to Section 2 table
   - Add entry to Section 3.1 (if implemented)
   - Update CI guardrails section if needed

### How to Tag Formulas

Formula tags follow this naming convention:

- **Implemented formulas**: `phase{N}_{category}`
  - Examples: `phase1_temporal`, `phase3_derived`, `phase7_behavioral`

- **Patent-only formulas**: `patent_only`
  - These formulas are documented in patent but not yet implemented

Tag categories:
- `temporal`: Temporal resonance and geometry formulas
- `derived`: Derived metrics computed from base formulas
- `behavioral`: Behavioral pattern formulas (trading safety, etc.)
- `kosha_guna`: Kosha/Guna consciousness layer formulas
- `unified`: Unified cognitive formulas

### When to Regenerate Fixtures

Regenerate canonical fixtures **only** when:
- Intentionally updating formula coefficients or logic
- Fixing a bug that changes formula outputs
- Adding new formula test cases

**Never** regenerate fixtures to make failing tests pass without understanding why outputs changed.

Regeneration workflow:
1. Understand why outputs changed
2. Verify change is intentional and correct
3. Run fixture generator: `python symbolu/tools/formula_fixtures/generate_phase1_resonance_fixtures.py`
4. Commit updated fixtures with clear explanation in commit message
5. Ensure all drift tests pass with new fixtures

### Safety Rules

All patent formula implementations must follow these rules:

1. **Non-invasive**: New formulas must not modify existing behavior for domains where they are disabled
2. **Feature-flagged**: New formulas must be controlled by `formula_ui_mode` in domain profiles
3. **Zero-LLM**: All formulas must be deterministic, pure mathematical functions
4. **Observation-only**: Formulas should not directly control routing, mappers, or core safety flags
5. **Backward compatible**: Formula metrics must be optional; pipeline must work when metrics are `None`
6. **CI-safe**: All tests must pass before merging; drift tests must catch unintended changes
7. **Documented**: All formulas must be tagged and documented in this matrix

## 6. Version History

- **v1.0** (2025-12-10): Initial Patent Formula Coverage Matrix created in Phase 6
  - Documented all Phase 1–5 implemented formulas
  - Documented all patent-only formulas
  - Established formula tagging system
  - Defined future integration roadmap

---

**Maintained by**: Symbol-U Development Team
**Last Updated**: 2025-12-10
**Related Documents**:
- Symbol-U Formula Integration Plan v1.0
- Phase 1–5 Implementation Summaries
- Patent Documentation (internal)
