# Symbolu Repository — Directory & File Normalization Plan

**Document Version:** 1.0
**Created:** 2024-12-14
**Status:** ANALYSIS & PLAN ONLY — NO CHANGES MADE
**Author:** Structural Architecture Analysis

---

## Executive Summary

This document provides a comprehensive analysis of the `rasaha/symbolu` repository structure, identifying:
- **711 total Python files** (471 production, 240 test modules)
- **1 confirmed naming conflict** requiring resolution (phase15_regression_guard)
- **1 confirmed code duplicate** (DriftRiskBand enum)
- **78 orphaned modules** (never imported)
- **54 test-only modules** (only imported by tests)
- **0 broken imports** (all references valid)

**Recommended Actions:**
1. Rename `phase15_regression_guard` → `p15_authority_guard` (HIGH priority)
2. Consolidate DriftRiskBand enum to single location (HIGH priority)
3. Review and integrate/archive orphaned pipeline phases P32-P54 (MEDIUM priority)
4. Consolidate fragmented test directories (LOW priority)

---

## Table of Contents

1. [Full Directory Inventory](#1-full-directory-inventory)
2. [Import & Dependency Map](#2-import--dependency-map)
3. [Duplication & Orphan Detection](#3-duplication--orphan-detection)
4. [Canonical Directory Proposal](#4-canonical-directory-proposal)
5. [Safe Migration Plan](#5-safe-migration-plan)
6. [Risk & Rollback Strategy](#6-risk--rollback-strategy)

---

## 1. Full Directory Inventory

### 1.1 Top-Level Structure

```
symbolu/
├── docs/                          # Documentation
├── examples/                      # Usage examples
├── scripts/                       # Utility scripts
├── tests/                         # Top-level integration tests (80 files)
│   └── tier3_invariance/          # Tier 3 invariance tests
└── symbolu/                       # Main package (711 .py files)
    ├── adapter/                   # External adapters (DilChat)
    ├── api/                       # API layer (coherence_api, unified_api)
    ├── core/                      # Core computation & models
    ├── formulas/                  # Mathematical formulas (40 files)
    ├── identity/                  # Identity signature engine
    ├── intent/                    # Intent arc engine
    ├── mechanical/                # Main execution engine (298 files)
    ├── motivation/                # Motivation engine
    ├── policy/                    # Governance & policy (12 files)
    ├── rag/                       # RAG pipeline (15 files)
    ├── renderer/                  # Surface rendering
    ├── service/                   # HTTP/WebSocket services
    ├── temporal/                  # Time-based tracking
    └── tools/                     # Dashboards & utilities
```

### 1.2 Mechanical Pipeline Directory — Phase Inventory

| Directory | Phase | Purpose | Files | Status |
|-----------|-------|---------|-------|--------|
| `grounding/` | P-1 | Pre-processing & grounding | 6 | ACTIVE |
| `phase_zero/` | PO2 | Intent Envelope & Response Posture | 3 | ACTIVE (legacy name) |
| `phase_one/` | PO3 | Intent → Allowed Action Contract | 3 | ACTIVE (legacy name) |
| `phase_po4/` | PO4 | Planner Proposal Envelope | 4 | ACTIVE |
| `phase_po5/` | PO5 | Planner Execution Gate | 4 | ACTIVE |
| `phase_p6/` | P6 | Regime Selection | 4 | ACTIVE |
| `p7_discourse/` | P7 | Discourse Act Resolution | 4 | ACTIVE |
| `p8_semantics/` | P8 | Semantic Analysis | 4 | ACTIVE |
| `p9_lexical/` | P9 | Lexical Pool Selection | 5 | ACTIVE |
| `p10_acoustic/` | P10 | Acoustic Shaping | 4 | ACTIVE |
| `p11_prosodic/` | P11 | Prosodic Evidence | 4 | ACTIVE |
| `p12_consistency/` | P12 | Consistency Validation | 4 | ACTIVE |
| `p13_acoustic_safety/` | P13 | Acoustic Safety | 4 | ACTIVE |
| `p14_surface/` | P14 | Surface Realization | 4 | ACTIVE |
| `p15_interaction/` | P15 | Interaction Mode Resolution | 4 | ACTIVE |
| `phase15_regression_guard/` | Guard | P15 Authority Protection | 4 | **NAMING CONFLICT** |
| `p16_regression_guard/` | P16 | Regression Guard (Hash-based) | 5 | ACTIVE |
| `p17_semantic_integrity/` | P17 | Semantic Integrity Rules | 5 | ACTIVE |
| `p18_temporal_entropy/` | P18 | Temporal Entropy Differential | 4 | ACTIVE |
| `p19_drift_fusion/` | P19 | Drift Fusion | 4 | ACTIVE |
| `p20_snapshot/` | P20 | Unified Snapshot | 4 | ACTIVE |
| `p21_delivery/` | P21 | Delivery Resolution | 4 | ACTIVE |
| `p22_acoustic_witness/` | P22 | Acoustic Witness (Observer) | 5 | ACTIVE |
| `p23_alignment/` | P23 | Inner-Outer Alignment | 4 | ACTIVE |
| `p24_projection/` | P24 | Projection Resolver | 4 | ACTIVE |
| `p25_counterfactual/` | P25 | Counterfactual Sandbox | 3 | ACTIVE |
| `p26_ucf/` | P26 | Unified Consciousness Field | 2 | ACTIVE |
| `p32_insight_window/` | P32 | Insight Window Gating | 2 | **ORPHANED** |
| `p33_schema_adaptive/` | P33 | Schema Adaptive Routing | 4 | ACTIVE |
| `p35_predictive_persona_drift/` | P35 | Predictive Persona Drift | 2 | **ORPHANED** |
| `p36_identity_resonance_memory/` | P36 | Identity Resonance Memory | 2 | **ORPHANED** |
| `p38_temporal_forecast/` | P38 | Temporal Forecasting | 3 | **ORPHANED** |
| `p39_multi_horizon/` | P39 | Multi-Horizon Forecasting | 5 | **ORPHANED** |
| `p40_cross_horizon_alignment/` | P40 | Cross-Horizon Alignment | 5 | **ORPHANED** |
| `p41_scenario_regime_mapper/` | P41 | Scenario Regime Mapper | 5 | **ORPHANED** |
| `p42_scenario_fusion/` | P42 | Scenario Fusion Engine | 5 | **ORPHANED** |
| `p43_scenario_what_if/` | P43 | Scenario What-If | 5 | **ORPHANED** |
| `p44_coherence_scenario_alignment/` | P44 | Coherence Scenario Alignment | 5 | **ORPHANED** |
| `p45_multi_trajectory_stability/` | P45 | Multi-Trajectory Stability | 5 | **ORPHANED** |
| `p46_trajectory_convergence/` | P46 | Trajectory Convergence | 5 | **ORPHANED** |
| `p47_unified_trajectory_scenario/` | P47 | Unified Trajectory Scenario | 5 | **ORPHANED** |
| `p48_macro_stability/` | P48 | Macro Stability Regulator | 5 | **ORPHANED** |
| `p49_temporal_stability/` | P49 | Temporal Stability | 5 | **ORPHANED** |
| `p50_cognitive_consistency/` | P50 | Cognitive Consistency | 3 | **ORPHANED** |
| `p51_governance_readiness/` | P51 | Governance Readiness | 5 | **ORPHANED** |
| `p52_governance_adapter/` | P52 | External Policy Binding | 5 | ACTIVE |
| `p53_policy_binding/` | P53 | Policy Binding Layer | 5 | ACTIVE |
| `p54_audit_trace/` | P54 | Audit & Compliance Trace | 5 | ACTIVE |

### 1.3 Core Directory Structure

| Directory | Purpose | Files | Status |
|-----------|---------|-------|--------|
| `core/bhava/` | Bhava geometry & temporal | 3 | ACTIVE |
| `core/coherence/` | Coherence engine (5349 lines) | 8 | ACTIVE (critical) |
| `core/consciousness/` | UCF formula, resolver, schema | 4 | ACTIVE |
| `core/counterfactual/` | Counterfactual analyzer | 4 | ACTIVE |
| `core/energy/` | Energy words, folded truth, calling | 4 | ACTIVE |
| `core/entropy/` | Entropy engine | 2 | ACTIVE |
| `core/phonetics/` | Phonetics (placeholder) | 1 | STUB |
| `core/predictive/` | Persona drift & identity memory | 8 | ACTIVE |
| `core/regulators/` | Ladder, mirror_time, fallback | 4 | ACTIVE |
| `core/smi/` | SMI engine, mappers | 5 | PARTIAL (some orphaned) |
| `core/stitching/` | Stitching engine | 4 | ACTIVE |

### 1.4 Largest Files by Size

| File | Lines | Size (KB) | Purpose |
|------|-------|-----------|---------|
| `core/coherence/coherence_engine.py` | 5,349 | 243 | Central coherence computation |
| `adapter/dilchat_adapter.py` | 2,547 | 119 | DilChat integration |
| `mechanical/persona/engine.py` | 2,499 | 105 | Persona/identity layer |
| `service/sessions/session_store.py` | 2,460 | 114 | Session management |
| `mechanical/pipeline/coherence_observer.py` | 1,894 | 97 | Pipeline observability |
| `api/unified_api.py` | 1,742 | 87 | Unified JSON output |
| `mechanical/pipeline/orchestrator.py` | 1,004 | 42 | Pipeline orchestration |

---

## 2. Import & Dependency Map

### 2.1 Entry Points

| Entry Point | File | Role | Outgoing Imports |
|-------------|------|------|------------------|
| **PRIMARY** | `mechanical/pipeline/orchestrator.py` | Main pipeline orchestrator | 19 |
| API Server | `service/api_server.py` | REST API | 13 |
| Core Pipeline | `core/pipeline.py` | Core pipeline (stub) | 2 |
| Unified API | `api/unified_api.py` | JSON output schema | 2 |

### 2.2 Most Critical Dependencies (Highest Incoming)

| Module | Incoming Imports | Type |
|--------|------------------|------|
| `mechanical/pipeline/phase_zero/phase_zero_schema.py` | 28 | Schema |
| `mechanical/pipeline/models.py` | 23 | Models |
| `core/coherence/coherence_state.py` | 22 | State |
| `mechanical/pipeline/grounding/phase_minus_one_schema.py` | 22 | Schema |
| `mechanical/pipeline/phase_p6/p6_schema.py` | 20 | Schema |
| `core/coherence/coherence_engine.py` | 19 | Engine |
| `mechanical/pipeline/p7_discourse/p7_discourse_schema.py` | 17 | Schema |

### 2.3 Module Dependency Summary

| Module | Production | Tests | Outgoing | Incoming | Role |
|--------|------------|-------|----------|----------|------|
| `mechanical/` | 298 | 171 | 426 | 720 | CORE execution |
| `core/` | 53 | 28 | 92 | 135 | FOUNDATIONAL |
| `formulas/` | 40 | 4 | 13 | 77 | MATH formulas |
| `service/` | 14 | 7 | 19 | 47 | API/SERVICE |
| `policy/` | 12 | 5 | 13 | 45 | GOVERNANCE |
| `tools/` | 22 | 4 | 24 | 25 | UTILITIES |
| `rag/` | 15 | 4 | 1 | 19 | RETRIEVAL |

### 2.4 Orphaned Modules (Never Imported)

**Total: 78 production modules**

#### By Area:

**mechanical/ (61 orphaned):**
- `fusion/fusion/` — examples, conflict_resolver, explanation, routing, scorer
- `mlcr/` — entropy_adapter, explainability, intent_classifier, ontology_mass, renderer_context, tier_selector
- `persona/` — examples, persona_resonance_mapping, schema_adaptive_routing
- `pipeline/` — examples, hrm_integration, lam_integration, lcm_integration
- `pipeline/grounding/` — phase_minus_one_clause_splitter, phase_minus_one_grounding
- `pipeline/p32-p51` — Most phase implementations (23 unintegrated phases)

**tools/ (7 orphaned):**
- `drift_dashboard/dashboard.py`
- `formula_fixtures/`
- `heatmaps/` (3 visualization modules)
- `scenario_simulator/`

**core/ (4 orphaned):**
- `constants.py`
- `smi/acoustic_mapper.py`, `aspect_mapping.py`, `vritti_mapping.py`

**policy/ (3 orphaned):**
- `phase32_hardening.py`
- `insight_window/insight_gating_engine.py`, `insight_gating_formula.py`

### 2.5 Test-Only Modules (54 total)

Modules imported only by test files:
- `core/stitching/objective.py`, `penalties.py`
- `mechanical/hrm/hrm_engine.py`
- `mechanical/lam/lam_engine.py`
- `mechanical/lcm/lcm_engine.py`
- `mechanical/pipeline/diagnostics/phase_minus_one_metrics.py`

---

## 3. Duplication & Orphan Detection

### 3.1 Confirmed Code Duplicates

| Item | Location 1 | Location 2 | Severity | Resolution |
|------|------------|------------|----------|------------|
| `DriftRiskBand` enum | `core/predictive/persona_drift/drift_report.py:60` | `mechanical/pipeline/p19_drift_fusion/p19_schema.py:38` | HIGH | Consolidate to core |

### 3.2 Naming Conflicts

| Conflict | Directory 1 | Directory 2 | Analysis | Resolution |
|----------|-------------|-------------|----------|------------|
| "P15" naming | `p15_interaction/` (Phase 15) | `phase15_regression_guard/` (Guard) | Different purposes, confusing names | Rename guard to `p15_authority_guard/` |

**Detail on P15 Conflict:**

- **`p15_interaction/`** — This IS Phase 15: Interaction Mode Resolution
  - Determines: READ_ONLY, ACK_ONLY, SUPPORTIVE, CLARIFYING, INFORMATIVE
  - 4 files, 36 KB total

- **`phase15_regression_guard/`** — This PROTECTS Phase 15 decisions
  - Ensures no phase >= 16 modifies P15 decisions
  - Guards immutable authority snapshots
  - 4 files, 43 KB total

Both are needed, but naming suggests they're the same phase.

### 3.3 Intentional Naming Variations (NOT Conflicts)

| Directory | Why Named This Way |
|-----------|-------------------|
| `phase_zero/` | PO2 — Backward compatibility alias |
| `phase_one/` | PO3 — Backward compatibility alias |
| `phase_p6/` | P6 — Intentional "phase_p" prefix pattern |
| `phase_po4/` | PO4 — Intentional "phase_po" prefix pattern |
| `phase_po5/` | PO5 — Intentional "phase_po" prefix pattern |

### 3.4 Orphan Classification

| Category | Count | Classification |
|----------|-------|----------------|
| Pipeline phases P32-P51 | 23 dirs | **NEEDS MANUAL REVIEW** — Complete implementations not wired to orchestrator |
| MLCR submodules | 9 files | **NEEDS MANUAL REVIEW** — May be experimental/disabled features |
| Tools/dashboards | 7 files | **SAFE TO ARCHIVE** — Development utilities, not production |
| Examples files | 6 files | **SAFE TO ARCHIVE** — Move to /examples |
| Integration stubs | 3 files | **KEEP SEPARATE** — hrm/lam/lcm integration hooks |

---

## 4. Canonical Directory Proposal

### 4.1 Principles

1. **Consistent phase naming**: `p{N}_{name}/` for all phases
2. **Guards separate from phases**: `guards/p{N}_guard/` for authority guards
3. **Single test location per phase**: Tests inside phase directory OR in `tests/`
4. **No legacy aliases in main path**: Keep backward-compat in `__init__.py` only
5. **Clear separation**: formulas / mechanical / observers / governance

### 4.2 BEFORE → AFTER Structure

#### 4.2.1 Naming Standardization

| BEFORE (Current) | AFTER (Proposed) | Reason |
|------------------|------------------|--------|
| `phase15_regression_guard/` | `guards/p15_authority_guard/` | Clarify it's a guard, not P15 |
| `phase_zero/` | `po2_intent_envelope/` | Consistent naming |
| `phase_one/` | `po3_action_contract/` | Consistent naming |
| `phase_p6/` | `p6_regime/` | Remove redundant prefix |
| `phase_po4/` | `po4_planner_proposal/` | Consistent naming |
| `phase_po5/` | `po5_planner_gate/` | Consistent naming |

#### 4.2.2 Test Directory Consolidation

| BEFORE (Current) | AFTER (Proposed) | Reason |
|------------------|------------------|--------|
| `tests_delta/` | `tests/delta/` | Consolidate under tests/ |
| `tests_fusion/` | `tests/fusion/` | Consolidate under tests/ |
| `tests_persona/` | `tests/persona/` | Consolidate under tests/ |
| `tests_persona_temporal/` | `tests/persona_temporal/` | Consolidate under tests/ |
| `tests_pipeline_snapshots/` | `tests/snapshots/` | Consolidate under tests/ |
| `tests_pipeline_temporal/` | `tests/temporal/` | Consolidate under tests/ |

#### 4.2.3 Proposed Directory Tree

```
symbolu/mechanical/pipeline/
├── __init__.py
├── models.py
├── orchestrator.py
├── coherence_observer.py
├── routing.py
├── validators.py
│
├── grounding/                    # P-1: Pre-processing
├── po2_intent_envelope/          # PO2 (was phase_zero)
├── po3_action_contract/          # PO3 (was phase_one)
├── po4_planner_proposal/         # PO4 (was phase_po4)
├── po5_planner_gate/             # PO5 (was phase_po5)
├── p6_regime/                    # P6 (was phase_p6)
├── p7_discourse/                 # P7: Discourse
├── p8_semantics/                 # P8: Semantics
├── p9_lexical/                   # P9: Lexical
├── p10_acoustic/                 # P10: Acoustic
├── p11_prosodic/                 # P11: Prosodic
├── p12_consistency/              # P12: Consistency
├── p13_acoustic_safety/          # P13: Acoustic Safety
├── p14_surface/                  # P14: Surface
├── p15_interaction/              # P15: Interaction Mode
├── p16_regression_guard/         # P16: Regression Guard
├── p17_semantic_integrity/       # P17: Semantic Integrity
├── p18_temporal_entropy/         # P18: Temporal Entropy
├── p19_drift_fusion/             # P19: Drift Fusion
├── p20_snapshot/                 # P20: Unified Snapshot
├── p21_delivery/                 # P21: Delivery
├── p22_acoustic_witness/         # P22: Acoustic Witness
├── p23_alignment/                # P23: Alignment
├── p24_projection/               # P24: Projection
├── p25_counterfactual/           # P25: Counterfactual
├── p26_ucf/                      # P26: UCF
│
├── guards/                       # Authority guards (NEW)
│   └── p15_authority_guard/      # (was phase15_regression_guard)
│
├── experimental/                 # Unintegrated phases (NEW)
│   ├── p32_insight_window/
│   ├── p33_schema_adaptive/      # or promote if active
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
│   └── p51_governance_readiness/
│
├── governance/                   # P50+ governance phases
│   ├── p52_governance_adapter/
│   ├── p53_policy_binding/
│   └── p54_audit_trace/
│
├── tests/                        # Consolidated tests
│   ├── integration/              # (was integration_tests)
│   ├── delta/                    # (was tests_delta)
│   ├── fusion/                   # (was tests_fusion)
│   ├── persona/                  # (was tests_persona)
│   ├── snapshots/                # (was tests_pipeline_snapshots)
│   └── phase/                    # Per-phase tests
│       ├── p7_discourse/
│       ├── p8_semantics/
│       └── ...
│
├── diagnostics/                  # Diagnostic tools
├── renderer_compliance/          # Renderer compliance
├── ttor/                         # TTOR router
└── snapshots/                    # Snapshot storage
```

### 4.3 Mapping Table

| Current Path | Proposed Path | Action |
|--------------|---------------|--------|
| `phase15_regression_guard/` | `guards/p15_authority_guard/` | RENAME |
| `phase_zero/` | `po2_intent_envelope/` | RENAME |
| `phase_one/` | `po3_action_contract/` | RENAME |
| `phase_p6/` | `p6_regime/` | RENAME |
| `phase_po4/` | `po4_planner_proposal/` | RENAME |
| `phase_po5/` | `po5_planner_gate/` | RENAME |
| `p32_insight_window/` | `experimental/p32_insight_window/` | MOVE |
| `p35_predictive_persona_drift/` | `experimental/p35_predictive_persona_drift/` | MOVE |
| `p36_identity_resonance_memory/` | `experimental/p36_identity_resonance_memory/` | MOVE |
| `p38_temporal_forecast/` | `experimental/p38_temporal_forecast/` | MOVE |
| `p39_multi_horizon/` | `experimental/p39_multi_horizon/` | MOVE |
| `p40_cross_horizon_alignment/` | `experimental/p40_cross_horizon_alignment/` | MOVE |
| `p41_scenario_regime_mapper/` | `experimental/p41_scenario_regime_mapper/` | MOVE |
| `p42_scenario_fusion/` | `experimental/p42_scenario_fusion/` | MOVE |
| `p43_scenario_what_if/` | `experimental/p43_scenario_what_if/` | MOVE |
| `p44_coherence_scenario_alignment/` | `experimental/p44_coherence_scenario_alignment/` | MOVE |
| `p45_multi_trajectory_stability/` | `experimental/p45_multi_trajectory_stability/` | MOVE |
| `p46_trajectory_convergence/` | `experimental/p46_trajectory_convergence/` | MOVE |
| `p47_unified_trajectory_scenario/` | `experimental/p47_unified_trajectory_scenario/` | MOVE |
| `p48_macro_stability/` | `experimental/p48_macro_stability/` | MOVE |
| `p49_temporal_stability/` | `experimental/p49_temporal_stability/` | MOVE |
| `p50_cognitive_consistency/` | `experimental/p50_cognitive_consistency/` | MOVE |
| `p51_governance_readiness/` | `experimental/p51_governance_readiness/` | MOVE |
| `p52_governance_adapter/` | `governance/p52_governance_adapter/` | MOVE |
| `p53_policy_binding/` | `governance/p53_policy_binding/` | MOVE |
| `p54_audit_trace/` | `governance/p54_audit_trace/` | MOVE |
| `tests_delta/` | `tests/delta/` | MOVE |
| `tests_fusion/` | `tests/fusion/` | MOVE |
| `tests_persona/` | `tests/persona/` | MOVE |
| `tests_persona_temporal/` | `tests/persona_temporal/` | MOVE |
| `tests_pipeline_snapshots/` | `tests/snapshots/` | MOVE |
| `tests_pipeline_temporal/` | `tests/temporal/` | MOVE |
| `integration_tests/` | `tests/integration/` | MOVE |

---

## 5. Safe Migration Plan

### 5.1 Pre-Migration Checklist

- [ ] All tests pass: `pytest symbolu/`
- [ ] Git working tree clean
- [ ] Create migration branch: `git checkout -b refactor/directory-normalization`
- [ ] Backup: `git stash` or tag current state

### 5.2 Migration Steps

---

#### **PHASE A: Code Consolidation (No Directory Changes)**

**Step A.1: Consolidate DriftRiskBand Enum**
- **What:** Remove duplicate enum from `p19_drift_fusion/p19_schema.py`
- **Change:** Update to import from `core/predictive/persona_drift/drift_report.py`
- **Update imports in:**
  - `symbolu/mechanical/pipeline/p19_drift_fusion/p19_schema.py`
  - Any file importing `DriftRiskBand` from p19
- **Verification:**
  ```bash
  grep -r "from.*p19.*DriftRiskBand" symbolu/
  pytest symbolu/mechanical/pipeline/tests/p19* -v
  ```
- **Risk:** LOW — Single file change
- **Rollback:** Revert single file

---

#### **PHASE B: Naming Conflict Resolution**

**Step B.1: Rename phase15_regression_guard → guards/p15_authority_guard**
- **What:** Move `phase15_regression_guard/` to `guards/p15_authority_guard/`
- **Why:** Clarifies this is a guard, not Phase 15 itself
- **Create:** `guards/__init__.py`
- **Update imports in:** (grep for all occurrences first)
  ```bash
  grep -r "phase15_regression_guard" symbolu/ --include="*.py"
  ```
  Files to update:
  - `symbolu/mechanical/pipeline/__init__.py`
  - `symbolu/mechanical/pipeline/orchestrator.py` (if referenced)
  - Any tests importing from this module
- **Internal file updates:**
  - `guards/p15_authority_guard/__init__.py` — update internal imports
  - `guards/p15_authority_guard/p15_integration.py` — update internal imports
- **Verification:**
  ```bash
  pytest symbolu/mechanical/pipeline/tests/p15_regression_guard/ -v
  python -c "from symbolu.mechanical.pipeline.guards.p15_authority_guard import P15RegressionGuard"
  ```
- **Risk:** MEDIUM — Multiple files reference this
- **Rollback:** `git checkout -- symbolu/mechanical/pipeline/`

---

#### **PHASE C: Legacy Phase Renaming**

**Step C.1: Create Backward Compatibility Layer**
- **What:** Add re-exports in `__init__.py` for all renamed phases
- **Why:** Ensures existing imports continue working
- **Files to modify:**
  - `symbolu/mechanical/pipeline/__init__.py`
- **Add:**
  ```python
  # Backward compatibility aliases
  from symbolu.mechanical.pipeline.po2_intent_envelope import *  # was phase_zero
  from symbolu.mechanical.pipeline.po3_action_contract import *  # was phase_one
  # etc.
  ```
- **Risk:** LOW — Additive only

**Step C.2: Rename phase_zero → po2_intent_envelope**
- **What:** `mv phase_zero/ po2_intent_envelope/`
- **Update imports in:**
  ```bash
  grep -r "phase_zero" symbolu/ --include="*.py" | grep -v "__pycache__"
  ```
  Expected files:
  - `orchestrator.py`
  - `models.py`
  - Multiple test files
  - `__init__.py` files
- **Verification:**
  ```bash
  pytest symbolu/mechanical/pipeline/tests/phase_zero/ -v
  python -c "from symbolu.mechanical.pipeline.po2_intent_envelope import phase_zero_schema"
  ```
- **Risk:** MEDIUM — Core phase, many references

**Step C.3: Rename phase_one → po3_action_contract**
- **What:** `mv phase_one/ po3_action_contract/`
- **Update imports:** Similar to C.2
- **Verification:**
  ```bash
  pytest symbolu/mechanical/pipeline/tests/phase_one/ -v
  ```

**Step C.4: Rename phase_p6 → p6_regime**
- **What:** `mv phase_p6/ p6_regime/`
- **Update imports:** All files referencing `phase_p6`
- **Verification:**
  ```bash
  pytest symbolu/mechanical/pipeline/tests/phase_p6/ -v
  ```

**Step C.5: Rename phase_po4 → po4_planner_proposal**
- **What:** `mv phase_po4/ po4_planner_proposal/`
- **Verification:**
  ```bash
  pytest symbolu/mechanical/pipeline/tests/phase_po4/ -v
  ```

**Step C.6: Rename phase_po5 → po5_planner_gate**
- **What:** `mv phase_po5/ po5_planner_gate/`
- **Verification:**
  ```bash
  pytest symbolu/mechanical/pipeline/tests/phase_po5/ -v
  ```

---

#### **PHASE D: Experimental Phase Organization**

**Step D.1: Create experimental/ directory**
- **What:** `mkdir -p experimental/__init__.py`
- **Risk:** LOW — No existing code affected

**Step D.2-D.19: Move orphaned phases to experimental/**
- **What:** Move each P32-P51 directory (excluding P33 if active)
- **Order:** Move in reverse order (P51 first) to minimize dependency issues
- **For each:**
  ```bash
  mv p51_governance_readiness/ experimental/
  # Update any imports (should be none for orphaned phases)
  grep -r "p51_governance_readiness" symbolu/
  ```
- **Verification:** Run any existing tests for moved phase
- **Risk:** LOW — These are orphaned (no imports to break)

---

#### **PHASE E: Governance Organization**

**Step E.1: Create governance/ directory**
- **What:** `mkdir -p governance/__init__.py`

**Step E.2: Move P52-P54 to governance/**
- **What:**
  ```bash
  mv p52_governance_adapter/ governance/
  mv p53_policy_binding/ governance/
  mv p54_audit_trace/ governance/
  ```
- **Update imports:**
  ```bash
  grep -r "p52_governance_adapter\|p53_policy_binding\|p54_audit_trace" symbolu/
  ```
- **Verification:**
  ```bash
  pytest symbolu/mechanical/pipeline/p52_governance_adapter/tests/ -v
  pytest symbolu/mechanical/pipeline/p53_policy_binding/tests/ -v
  pytest symbolu/mechanical/pipeline/p54_audit_trace/tests/ -v
  ```
- **Risk:** MEDIUM — Recently added, may have active imports

---

#### **PHASE F: Test Consolidation**

**Step F.1: Create tests/ subdirectory structure**
- **What:**
  ```bash
  mkdir -p tests/integration tests/delta tests/fusion tests/persona tests/snapshots tests/temporal
  ```

**Step F.2-F.7: Move test directories**
- **What:** Move each `tests_*` directory to `tests/`
- **Update any imports in conftest.py or fixtures**
- **Verification:** Run moved tests
- **Risk:** LOW — Tests are self-contained

---

### 5.3 Post-Migration Verification

```bash
# Full test suite
pytest symbolu/ -v --tb=short

# Import verification
python -c "from symbolu.mechanical.pipeline import orchestrator; print('OK')"
python -c "from symbolu.mechanical.pipeline.guards.p15_authority_guard import P15RegressionGuard; print('OK')"
python -c "from symbolu.mechanical.pipeline.governance.p52_governance_adapter import p52_integration; print('OK')"

# Grep for broken imports
grep -r "from symbolu.mechanical.pipeline.phase15_regression_guard" symbolu/
grep -r "from symbolu.mechanical.pipeline.phase_zero" symbolu/
# (should return nothing after migration)
```

---

## 6. Risk & Rollback Strategy

### 6.1 Risk Assessment

| Step | Risk Level | Impact if Failed | Dependencies |
|------|------------|------------------|--------------|
| A.1 (DriftRiskBand) | LOW | Single test failure | None |
| B.1 (phase15 rename) | MEDIUM | Authority guard broken | Orchestrator |
| C.2 (phase_zero) | HIGH | Core pipeline broken | All phases |
| C.3 (phase_one) | HIGH | Core pipeline broken | All phases |
| C.4-C.6 (PO phases) | MEDIUM | Specific phase failures | Orchestrator |
| D.x (experimental) | LOW | None (orphaned) | None |
| E.x (governance) | MEDIUM | Governance broken | P52-P54 |
| F.x (tests) | LOW | Test discovery | None |

### 6.2 Dependency Hotspots

**Critical files that many others depend on:**
1. `mechanical/pipeline/models.py` (23 incoming) — DO NOT MOVE
2. `mechanical/pipeline/phase_zero/phase_zero_schema.py` (28 incoming) — HIGH RISK
3. `core/coherence/coherence_state.py` (22 incoming) — DO NOT MOVE
4. `mechanical/pipeline/grounding/phase_minus_one_schema.py` (22 incoming) — DO NOT MOVE

### 6.3 Rollback Checkpoints

| After Step | Checkpoint Command | Description |
|------------|-------------------|-------------|
| A.1 | `git stash && git checkout -b checkpoint-a1` | Pre-rename |
| B.1 | `git stash && git checkout -b checkpoint-b1` | Guard renamed |
| C.6 | `git stash && git checkout -b checkpoint-c6` | Legacy phases renamed |
| D.19 | `git stash && git checkout -b checkpoint-d19` | Experimental organized |
| E.2 | `git stash && git checkout -b checkpoint-e2` | Governance organized |
| F.7 | `git stash && git checkout -b checkpoint-f7` | Tests consolidated |

### 6.4 Atomic Step Requirements

**These steps MUST be completed atomically (no partial commits):**

1. **Step B.1** (phase15 rename) — Internal imports + external imports + tests must all update together
2. **Step C.2** (phase_zero rename) — All 28+ importing files must update together
3. **Step E.2** (governance move) — All 3 directories + imports must update together

### 6.5 Emergency Rollback

```bash
# Full rollback to pre-migration state
git checkout main -- symbolu/mechanical/pipeline/
git checkout main -- symbolu/core/predictive/

# Partial rollback (specific phase)
git checkout main -- symbolu/mechanical/pipeline/phase15_regression_guard/
git checkout main -- symbolu/mechanical/pipeline/__init__.py
```

---

## 7. Items Requiring Human Review

| Item | Location | Question |
|------|----------|----------|
| P33 (schema_adaptive) | `p33_schema_adaptive/` | Active or experimental? Has imports but unclear if production |
| MLCR submodules | `mechanical/mlcr/` | 9 orphaned files — experimental features or dead code? |
| HRM/LAM/LCM integrations | `mechanical/pipeline/*_integration.py` | Should these be integrated or remain dormant? |
| Tool dashboards | `tools/drift_dashboard/`, `tools/heatmaps/` | Development tools or dead code? |
| Policy insight_window | `policy/insight_window/` | Different from P32 insight_window — intentional? |

---

## 8. Summary Checklist

- [ ] **PHASE A:** Consolidate DriftRiskBand enum
- [ ] **PHASE B:** Rename phase15_regression_guard → guards/p15_authority_guard
- [ ] **PHASE C:** Rename legacy phase directories (phase_zero, phase_one, phase_p6, phase_po4, phase_po5)
- [ ] **PHASE D:** Move orphaned P32-P51 to experimental/
- [ ] **PHASE E:** Move P52-P54 to governance/
- [ ] **PHASE F:** Consolidate test directories
- [ ] **VERIFY:** Full test suite passes
- [ ] **DOCUMENT:** Update any architecture docs

---

**END OF PLAN**

*This document is for analysis and planning only. No code changes have been made.*
