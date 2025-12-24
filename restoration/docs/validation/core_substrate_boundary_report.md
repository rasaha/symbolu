# Core/Substrate Boundary Audit Report

**Audit Date:** 2025-12-14
**Auditor:** Claude Code
**Scope:** Legacy "Phase 1-9" formula files vs Authoritative Pipeline
**Classification:** Core/Substrate Boundary Verification

---

## Executive Summary

### Audit Result: **ZERO VIOLATIONS**

The audit confirms that legacy "Phase 1-9" formula files in `symbolu/formulas/` are correctly isolated as Core/Substrate utilities and do NOT steer authoritative governance decisions.

**Key Findings:**
1. No authoritative pipeline module imports formula modules
2. No formula module imports governance modules
3. Formula imports are confined to allowed sinks (observers, tests, diagnostics)
4. Observer phases (P22/P23/P24) correctly implement witness-only patterns

---

## Section 1: Target Formula Files Audited

| File | Location | Classification |
|------|----------|----------------|
| `acoustic_unit_mapper.py` | `symbolu/formulas/` | Core/Substrate |
| `vritti_mapper.py` | `symbolu/formulas/` | Core/Substrate |
| `resonance_formulas.py` | `symbolu/formulas/` | Core/Substrate |
| `phase1_snapshot.py` | `symbolu/formulas/` | Core/Substrate |
| `guna_kosha_resonance.py` | `symbolu/formulas/` | Core/Substrate |
| `enhanced_smi.py` | `symbolu/formulas/` | Core/Substrate |
| `temporal_entropy_differential.py` | `symbolu/formulas/` | Core/Substrate |

---

## Section 2: Authoritative Modules Scanned

| Module | Location | Formula Imports Found |
|--------|----------|----------------------|
| Grounding (PO1) | `mechanical/pipeline/grounding/` | **NONE** |
| Phase Zero (PO2) | `mechanical/pipeline/phase_zero/` | **NONE** |
| Phase One (PO3) | `mechanical/pipeline/phase_one/` | **NONE** |
| Phase PO4 | `mechanical/pipeline/phase_po4/` | **NONE** |
| Phase PO5 | `mechanical/pipeline/phase_po5/` | **NONE** |
| P6 Regime | `mechanical/pipeline/phase_p6/` | **NONE** |
| P7 Discourse | `mechanical/pipeline/p7_discourse/` | **NONE** |
| P8 Semantics | `mechanical/pipeline/p8_semantics/` | **NONE** |
| P9 Lexical | `mechanical/pipeline/p9_lexical/` | **NONE** |
| P10 Acoustic | `mechanical/pipeline/p10_acoustic/` | **NONE** |
| P15 Interaction | `mechanical/pipeline/p15_interaction/` | **NONE** |
| Governance | `mechanical/pipeline/governance/` | **NONE** |
| Router | `mechanical/router/` | **NONE** |

**Verdict:** All authoritative modules are CLEAN - no formula imports detected.

---

## Section 3: Allowed Dependencies

### Importers of Formula Modules (Classified as Allowed Sinks)

| Importing Module | Imports | Classification | Allowed? |
|-----------------|---------|----------------|----------|
| `p22_acoustic_witness/p22_resolver.py` | `acoustic_unit_mapper`, `vritti_mapper` | Observer (witness-only) | YES |
| `core/coherence/coherence_engine.py` | `guna_kosha_resonance`, `temporal_entropy_differential` | Observation-only coherence | YES |
| `temporal/temporal_bhava_tracker.py` | `resonance_formulas`, `enhanced_smi` | Temporal observation | YES |
| `formulas/__init__.py` | All formula modules | Internal re-export | YES |
| `formulas/phase1_snapshot.py` | `acoustic_unit_mapper`, `vritti_mapper` | Internal composition | YES |
| `formulas/vritti_mapper.py` | `acoustic_unit_mapper` | Internal composition | YES |
| `tools/formula_fixtures/` | Various formulas | Test fixture generation | YES |

### Test Files Importing Formulas (All Allowed)

- `tests/test_phase1_acoustic_symbolic.py`
- `tests/tier3_invariance/test_phase1_light_invariance.py`
- `tests/tier3_invariance/test_phase3_light_invariance.py`
- `tests/test_phase13_enhanced_smi_invariance_audit.py`
- `tests/test_phase18_temporal_entropy_invariance_audit.py`
- `symbolu/formulas/tests/test_guna_kosha_resonance.py`
- `symbolu/core/formula_drift_tests/test_phase*.py`
- Various integration tests in `mechanical/pipeline/integration_tests/`

**Verdict:** All formula imports are in allowed sink directories.

---

## Section 4: Violations Found

### Import Violations: **NONE**

No authoritative module imports any target formula module.

### Reverse Dependency Violations: **NONE**

No formula module imports any governance module.

---

## Section 5: Dependency Direction Verification

### Formula → Governance Imports (Should be ZERO)

| Formula File | Governance Imports |
|--------------|-------------------|
| `acoustic_unit_mapper.py` | **NONE** |
| `vritti_mapper.py` | **NONE** (imports only `acoustic_unit_mapper`) |
| `resonance_formulas.py` | **NONE** |
| `phase1_snapshot.py` | **NONE** (imports only internal formulas) |
| `guna_kosha_resonance.py` | **NONE** |
| `enhanced_smi.py` | **NONE** |
| `temporal_entropy_differential.py` | **NONE** |

**Verdict:** Formula layer correctly isolated - no reverse dependencies.

---

## Section 6: Observer Non-Interference Confirmation

### P22 Acoustic-Vrtti Witness

**Status:** COMPLIANT

Evidence:
- Module docstring explicitly states "witness-only"
- Module docstring explicitly states "zero authority"
- Contains FORBIDDEN_ATTRS sets preventing semantic access
- Outputs attach to `ctx.p22_acoustic_witness` only
- NOT imported by P6, P7, P8, P9, or any governance module

### P23 Alignment Observer

**Status:** COMPLIANT

Evidence:
- Module classified as "observer-only"
- Contains FORBIDDEN_ATTRS sets
- Reads P22 and P6/P7 outputs (observation only)
- NOT imported by any governance module

### P24 Projection Observer

**Status:** COMPLIANT

Evidence:
- Module classified as "observer-only"
- Contains FORBIDDEN_ATTRS sets
- Reads multiple upstream phases (observation only)
- NOT imported by any governance module

---

## Section 7: Static Import Graph

```
Core/Substrate Layer
├── acoustic_unit_mapper.py (standalone)
├── vritti_mapper.py → acoustic_unit_mapper.py
├── resonance_formulas.py (standalone)
├── phase1_snapshot.py → acoustic_unit_mapper.py, vritti_mapper.py
├── guna_kosha_resonance.py (standalone)
├── enhanced_smi.py (standalone)
└── temporal_entropy_differential.py (standalone)

Allowed Importers
├── p22_acoustic_witness/ → acoustic_unit_mapper, vritti_mapper
├── core/coherence/ → guna_kosha_resonance, temporal_entropy_differential
├── temporal/ → resonance_formulas, enhanced_smi
├── tests/**/ → various (all test files)
└── tools/**/ → various (fixture generators)

Forbidden Importers (NONE FOUND)
├── grounding/ → (clean)
├── phase_zero/ → (clean)
├── phase_one/ → (clean)
├── phase_p6/ → (clean)
├── p7_discourse/ → (clean)
├── p8_semantics/ → (clean)
├── p9_lexical/ → (clean)
├── governance/ → (clean)
└── router/ → (clean)
```

---

## Section 8: Test Artifacts Created

### Import Constraint Tests

**Location:** `symbolu/mechanical/pipeline/tests/audits/test_core_substrate_noninterference.py`

**Test Classes:**
1. `TestAuthorativeModulesDoNotImportFormulas` - Per-directory import scans
2. `TestGlobalFormulaImportScan` - Full codebase scan
3. `TestFormulaDependencyDirection` - Reverse dependency checks
4. `TestAllowedSinksAreCorrect` - Sink classification verification
5. `TestBehavioralNonInterference` - Runtime non-interference proof
6. `TestRegressionGuards` - Source-level regression tests

### Documentation Created

1. `docs/architecture/core_vs_pipeline.md` - Architectural clarification
2. `docs/audits/core_substrate_boundary_report.md` - This report

---

## Section 9: Enforcement Recommendations

### Already Implemented

1. **Static Import Tests** - AST-based and string-based import scanning
2. **Behavioral Tests** - Mock context pairs with different formula values
3. **Regression Guards** - Source-level string checks for formula references
4. **FORBIDDEN_ATTRS** - Observer modules define forbidden attribute sets

### Future Recommendations

1. **CI Integration** - Run `test_core_substrate_noninterference.py` in CI pipeline
2. **Pre-commit Hook** - Add hook to check new imports before commit
3. **Architecture Documentation** - Keep `core_vs_pipeline.md` updated

---

## Section 10: Summary

### Final Verdict: **ZERO VIOLATIONS**

| Check | Result |
|-------|--------|
| Authoritative modules import formulas | **NO** |
| Formula modules import governance | **NO** |
| Formula imports in allowed sinks only | **YES** |
| Observers implement witness-only pattern | **YES** |
| Behavioral non-interference verified | **YES** |

### Confirmation

The audit confirms that:

1. **Legacy "Phase 1-9" formula modules are Core/Substrate utilities** with zero governance authority
2. **Authoritative governance is PO1 → PO2 → PO3 → P6 → P7 → P8 → P9 → P10+**
3. **No backdoor exists** where formula outputs influence governance decisions
4. **Observer phases (P22/P23/P24)** correctly implement witness-only patterns
5. **Import boundaries are enforced** by tests going forward

---

## Appendix A: Command Evidence

### Import Scans Performed

```bash
# Grep for formula imports in authoritative modules
grep -r "from symbolu.formulas" symbolu/mechanical/pipeline/grounding/
# Result: No matches

grep -r "from symbolu.formulas" symbolu/mechanical/pipeline/phase_zero/
# Result: No matches

grep -r "from symbolu.formulas" symbolu/mechanical/pipeline/phase_one/
# Result: No matches

grep -r "from symbolu.formulas" symbolu/mechanical/pipeline/phase_p6/
# Result: No matches

grep -r "from symbolu.formulas" symbolu/mechanical/pipeline/p7_discourse/
# Result: No matches

grep -r "from symbolu.formulas" symbolu/mechanical/pipeline/p8_semantics/
# Result: No matches

grep -r "from symbolu.formulas" symbolu/mechanical/pipeline/p9_lexical/
# Result: No matches

grep -r "from symbolu.formulas" symbolu/mechanical/pipeline/governance/
# Result: No matches

grep -r "from symbolu.formulas" symbolu/mechanical/router/
# Result: No matches

# Only P22 observer imports formulas (ALLOWED)
grep -r "from symbolu.formulas" symbolu/mechanical/pipeline/p22_acoustic_witness/
# Result: p22_resolver.py imports acoustic_unit_mapper, vritti_mapper (ALLOWED - witness-only)
```

---

## Appendix B: Line-Level Evidence

### P6 Regime Gate - CLEAN

File: `symbolu/mechanical/pipeline/phase_p6/p6_regime_gate.py`

Imports:
```python
from symbolu.mechanical.pipeline.grounding.phase_minus_one_schema import (...)
from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import (...)
from symbolu.mechanical.pipeline.phase_po5.po5_schema import (...)
from symbolu.mechanical.pipeline.phase_p6.p6_schema import (...)
```

**No formula imports.**

### P7 Discourse Resolver - CLEAN

File: `symbolu/mechanical/pipeline/p7_discourse/p7_discourse_resolver.py`

Imports:
```python
from symbolu.mechanical.pipeline.grounding.phase_minus_one_schema import (...)
from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import (...)
from symbolu.mechanical.pipeline.phase_one.phase_one_schema import (...)
from symbolu.mechanical.pipeline.phase_p6.p6_schema import (...)
```

**No formula imports.**

### P22 Acoustic Witness - ALLOWED

File: `symbolu/mechanical/pipeline/p22_acoustic_witness/p22_resolver.py`

Imports:
```python
from symbolu.formulas.acoustic_unit_mapper import (
    AcousticUnit,
    map_acoustic_units,
    get_acoustic_signature,
)
from symbolu.formulas.vritti_mapper import (
    VrittiType,
    AcousticVritti,
    assign_vritti_sequence,
    get_vritti_distribution,
)
```

**Imports ALLOWED - P22 is witness-only observer with zero authority.**

---

*End of Audit Report*
