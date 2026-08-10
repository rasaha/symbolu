# Repository Refactoring Plan: Phase Structure Normalization

**Version:** 2.0
**Date:** 2024-12-14
**Status:** IN PROGRESS
**Scope:** Minimal viable normalization to eliminate naming conflicts

---

## 1. Overview

This document describes the targeted refactoring performed to normalize phase directory naming and eliminate duplication/conflicts without changing runtime behavior.

### 1.1 Non-Negotiable Constraints

- NO behavioral changes
- NO formula math changes
- ONLY move/rename files, normalize comments/docstrings
- Preserve imports via:
  - (a) updating imports repo-wide, OR
  - (b) leaving stub module at old path re-exporting symbols (preferred for public modules)

---

## 2. Canonical Folder Layout

The canonical structure for pipeline phases is:

```
symbolu/mechanical/pipeline/
├── phases with pXX_<name>/ format:
│   ├── p7_discourse/
│   ├── p8_semantics/
│   ├── p9_lexical/
│   ├── p10_acoustic/
│   ├── p11_prosodic/
│   ├── p12_consistency/
│   ├── p13_acoustic_safety/
│   ├── p14_surface/
│   ├── p15_interaction/         # P15: Interaction Mode Resolver
│   ├── p15_authority_guard/     # NEW: P15 boundary authority guard
│   ├── p16_regression_guard/    # P16: Input Contract Guard
│   ├── p17_semantic_integrity/
│   ├── p18_temporal_entropy/
│   ├── p19_drift_fusion/
│   ├── p20_snapshot/
│   ├── p21_delivery/
│   ├── p22_acoustic_witness/
│   ├── p23_alignment/
│   ├── p24_projection/
│   ├── p25_counterfactual/
│   ├── p26_ucf/
│   ├── p32_insight_window/
│   ├── p33_schema_adaptive/
│   ├── p35_predictive_persona_drift/
│   ├── p36_identity_resonance_memory/
│   ├── p38_temporal_forecast/
│   ├── p39_multi_horizon/
│   ├── p40_cross_horizon_alignment/
│   ├── p41_scenario_regime_mapper/
│   ├── p42_scenario_fusion/
│   ├── p43_scenario_what_if/
│   ├── p44_coherence_scenario_alignment/
│   ├── p45_multi_trajectory_stability/
│   ├── p46_trajectory_convergence/
│   ├── p47_unified_trajectory_scenario/
│   ├── p48_macro_stability/
│   ├── p49_temporal_stability/
│   ├── p50_cognitive_consistency/
│   ├── p51_governance_readiness/
│   ├── p52_governance_adapter/
│   ├── p53_policy_binding/
│   ├── p54_audit_trace/
│
├── Legacy-named phases (preserved for stability):
│   ├── phase_zero/              # PO2: Intent Envelope (many imports)
│   ├── phase_one/               # PO3: Action Contract (many imports)
│   ├── phase_po4/               # PO4: Planner Proposal
│   ├── phase_po5/               # PO5: Planner Gate
│   ├── phase_p6/                # P6: Regime Selection
│
├── Supporting directories:
│   ├── grounding/               # P-1: Pre-processing
│   ├── governance/              # Governance utilities
│   ├── diagnostics/             # Diagnostic tools
│   ├── renderer_compliance/     # Renderer compliance checks
│   ├── snapshots/               # Snapshot storage
│   ├── ttor/                    # TTOR router
│   └── tests/                   # Phase-specific tests
```

---

## 3. List of Moves/Renames

### 3.1 Executed Renames

| Original Path | New Path | Reason |
|---------------|----------|--------|
| `phase15_regression_guard/` | `p15_authority_guard/` | Resolves naming conflict with `p15_interaction/`. Both are P15-related but serve different purposes: `p15_interaction/` IS Phase 15 (Interaction Mode Resolution), while `phase15_regression_guard` GUARDS the P15 authority boundary. Renamed to `p15_authority_guard/` to clarify purpose. |

### 3.2 Preserved Legacy Names (No Rename)

| Directory | Reason for Preservation |
|-----------|------------------------|
| `phase_zero/` | 28+ incoming imports; too many files to update safely |
| `phase_one/` | 28+ incoming imports; too many files to update safely |
| `phase_p6/` | 20+ incoming imports; working and consistent |
| `phase_po4/` | Consistently referenced in PO4 documentation |
| `phase_po5/` | Consistently referenced in PO5 documentation |

### 3.3 Not Renamed (Already Canonical)

All `p{N}_{name}/` directories are already in canonical format and were not renamed.

---

## 4. List of Compatibility Shims Created

| Old Path | New Path | Shim Type |
|----------|----------|-----------|
| `symbolu.mechanical.pipeline.phase15_regression_guard` | `symbolu.mechanical.pipeline.p15_authority_guard` | Re-export stub module |

The shim at `phase15_regression_guard/__init__.py` re-exports all symbols from the new location, ensuring backward compatibility for any existing imports.

---

## 5. Comment/Docstring Normalization

### 5.1 Standard Phase Header Format

All phase modules should have a header docstring following this format:

```python
"""
Phase: PXX
Authority: HIGH/MEDIUM/ZERO
observer_only: True/False
Determinism: yes/no

<Description of the phase purpose>
"""
```

### 5.2 Phases Updated

Files with normalized headers:
- `p15_authority_guard/__init__.py` - Authority: HIGH, observer_only: False, Determinism: yes
- Internal files of `p15_authority_guard/` (p15_integration.py, p15_regression_guard.py, p15_regression_schema.py)

---

## 6. __init__.py Normalization

### 6.1 Rules Applied

1. **Packages that need `__init__.py`:** All directories under `symbolu/mechanical/pipeline/` that contain Python modules
2. **Accidental packages:** Not removed (too risky without thorough testing)
3. **New `__init__.py` created:** `tools/refactor/__init__.py`

---

## 7. Formula Modules

### 7.1 Protected Modules (Must Keep Backward-Compatible Shims if Renamed)

The following formula modules are protected and were NOT renamed:

| Module | Status |
|--------|--------|
| `symbolu/formulas/acoustic_unit_mapper.py` | Not renamed |
| `symbolu/formulas/vritti_mapper.py` | Not renamed |
| `symbolu/formulas/phase1_snapshot.py` | Not renamed |
| `symbolu/formulas/resonance_formulas.py` | Not renamed |

No formula modules required renaming - no naming collisions were found.

---

## 8. Verification

### 8.1 Import Verification

Run `tools/refactor/verify_imports.py` to check all imports:

```bash
python tools/refactor/verify_imports.py
```

### 8.2 Smoke Test

Run the smoke test to verify key imports work:

```bash
pytest tests/test_repo_refactor_smoke.py -v
```

### 8.3 Full Compilation Check

```bash
python -m compileall symbolu
```

---

## 9. Rollback Procedure

If issues are found:

1. The shim at `phase15_regression_guard/__init__.py` ensures backward compatibility
2. To fully rollback:
   ```bash
   git checkout HEAD~1 -- symbolu/mechanical/pipeline/
   ```

---

## 10. Summary

| Metric | Count |
|--------|-------|
| Directories renamed | 1 |
| Compatibility shims created | 1 |
| Files with normalized headers | 4 |
| Formula modules protected | 4 |
| Test files created | 1 |
| Tool scripts created | 1 |

**Result:** The P15 naming conflict has been resolved. `p15_interaction/` remains the actual Phase 15 implementation, and `p15_authority_guard/` is now clearly named as the authority guard that protects P15 decisions from being overridden by phases >= 16.
