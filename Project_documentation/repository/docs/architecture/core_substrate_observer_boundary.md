# Core/Substrate → Observer → Governance Boundary Specification

**Document Version:** 1.0
**Document Status:** AUTHORITATIVE
**Last Updated:** 2025-12-14
**Classification:** Formal Architectural Specification
**Suitable For:** Patent Documentation, Architecture Review, System Audit

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Terminology Corrections](#2-terminology-corrections)
3. [Three-Tier Architecture](#3-three-tier-architecture)
4. [Tier Definitions](#4-tier-definitions)
5. [Allowed and Forbidden Flow Table](#5-allowed-and-forbidden-flow-table)
6. [Code-Level Enforcement Checklist](#6-code-level-enforcement-checklist)
7. [Validation Evidence](#7-validation-evidence)
8. [Why Acoustic and Vṛtti Mapping Exist](#8-why-acoustic-and-vṛtti-mapping-exist)
9. [Glossary](#9-glossary)

---

## 1. Executive Summary

Symbol-U implements a strict **three-tier architectural separation** that isolates:

| Tier | Components | Authority Level |
|------|------------|-----------------|
| **Tier 1: Core/Substrate** | Formula utilities (`symbolu/formulas/`) | ZERO authority |
| **Tier 2: Observer** | P22, P23, P24 witness phases | ZERO authority |
| **Tier 3: Governance** | PO1-PO5, P6-P9, P10+ pipeline | FULL authority |

### Critical Architectural Invariant

```
┌────────────────────────────────────────────────────────────────────────┐
│  UPWARD DATA FLOW IS STRICTLY FORBIDDEN                                │
│                                                                        │
│  Core/Substrate → Observer → Governance (allowed: downward only)       │
│  Governance → Observer → Core/Substrate (FORBIDDEN: never upward)      │
└────────────────────────────────────────────────────────────────────────┘
```

This document removes all historical ambiguity around "Phase 1-9" naming and formalizes the boundary that is already enforced in code.

---

## 2. Terminology Corrections

### Historical Ambiguity: "Phase 1-9"

The Symbol-U codebase contains two distinct usages of "Phase" numbering that have historically caused confusion:

| Usage | Location | Meaning | Authority |
|-------|----------|---------|-----------|
| **Legacy docstrings** | `symbolu/formulas/*.py` | Development milestone labels | ZERO |
| **Pipeline phases** | `symbolu/mechanical/pipeline/` | Authoritative execution stages | FULL |

### Authoritative Terminology (Effective Immediately)

**DEPRECATED TERMS:**
- "Phase 1" formulas → Use "Core/Substrate utility"
- "Phase 8" observability → Use "Core/Substrate metric"
- "Phase 13" enhanced SMI → Use "Core/Substrate formula"

**CORRECT TERMS:**

| Old Term | Correct Term | Definition |
|----------|--------------|------------|
| Phase 1-9 (in formulas/) | Core/Substrate Utilities | Stateless mathematical/acoustic functions with zero governance authority |
| Phase 1-5 (integration tests) | Substrate Integration Tests | Test scaffolding for Core/Substrate verification |
| P6, P7, P8, P9 | Governance Phases | Authoritative pipeline phases with binding decision authority |
| P22, P23, P24 | Observer Phases | Witness-only phases with zero governance authority |

### Declaration of Non-Authority

**HEREBY DECLARED:**

Any "Phase X" label appearing in docstrings or comments within `symbolu/formulas/` files refers to **historical development milestones only** and confers **ZERO pipeline authority**. These labels are:

1. **Non-authoritative** - They do not grant execution privileges
2. **Non-sequential** - They do not execute in numbered order
3. **Non-binding** - They do not influence governance decisions
4. **Historical metadata only** - They indicate when a formula was introduced

---

## 3. Three-Tier Architecture

### ASCII Architecture Diagram

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                           SYMBOL-U THREE-TIER ARCHITECTURE                     ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                                ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │                    TIER 1: CORE/SUBSTRATE UTILITIES                      │  ║
║  │                         symbolu/formulas/                                │  ║
║  │                                                                          │  ║
║  │  ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐ │  ║
║  │  │ acoustic_unit_      │  │ vritti_mapper.py    │  │ resonance_       │ │  ║
║  │  │ mapper.py           │  │                     │  │ formulas.py      │ │  ║
║  │  │                     │  │ Motion quality      │  │                  │ │  ║
║  │  │ Phonetic tokenizer  │  │ assignment          │  │ SMI, ΔSMI,       │ │  ║
║  │  │ → AcousticUnit      │  │ → AcousticVritti    │  │ Bhava Gap        │ │  ║
║  │  └─────────────────────┘  └─────────────────────┘  └──────────────────┘ │  ║
║  │                                                                          │  ║
║  │  ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐ │  ║
║  │  │ guna_kosha_         │  │ enhanced_smi.py     │  │ temporal_entropy_│ │  ║
║  │  │ resonance.py        │  │                     │  │ differential.py  │ │  ║
║  │  │                     │  │ Patent-level SMI    │  │                  │ │  ║
║  │  │ Observability       │  │ computation         │  │ Temporal metrics │ │  ║
║  │  │ metrics             │  │                     │  │                  │ │  ║
║  │  └─────────────────────┘  └─────────────────────┘  └──────────────────┘ │  ║
║  │                                                                          │  ║
║  │  Properties: Deterministic | Stateless | Zero-LLM | No semantics        │  ║
║  │              No intent | No regime | No routing | No authority          │  ║
║  └──────────────────────────────────┬──────────────────────────────────────┘  ║
║                                     │                                          ║
║                                     │ (outputs consumed by)                    ║
║                                     ▼                                          ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │                      TIER 2: OBSERVER PHASES                             │  ║
║  │                         (Witness-Only)                                   │  ║
║  │                                                                          │  ║
║  │  ┌──────────────────────────────────────────────────────────────────┐   │  ║
║  │  │ P22: Acoustic-Vṛtti Witness Extractor                            │   │  ║
║  │  │ Location: symbolu/mechanical/pipeline/p22_acoustic_witness/       │   │  ║
║  │  │ Inputs: user_raw_text, delivery_mode                              │   │  ║
║  │  │ Outputs: pressure_band, motion_balance, vritti_vector             │   │  ║
║  │  │ Authority: ZERO - witness_only = True                             │   │  ║
║  │  └──────────────────────────────────────────────────────────────────┘   │  ║
║  │                                     │                                    │  ║
║  │                                     ▼                                    │  ║
║  │  ┌──────────────────────────────────────────────────────────────────┐   │  ║
║  │  │ P23: Inner-Outer Alignment Observer                              │   │  ║
║  │  │ Location: symbolu/mechanical/pipeline/p23_alignment/              │   │  ║
║  │  │ Inputs: P22.pressure_band, P6.regime (read-only), P7.act (r/o)   │   │  ║
║  │  │ Outputs: alignment_state, tension_score, alignment_tags          │   │  ║
║  │  │ Authority: ZERO - observer_only = True                            │   │  ║
║  │  └──────────────────────────────────────────────────────────────────┘   │  ║
║  │                                     │                                    │  ║
║  │                                     ▼                                    │  ║
║  │  ┌──────────────────────────────────────────────────────────────────┐   │  ║
║  │  │ P24: Acoustic-Ontology Projection Observer                       │   │  ║
║  │  │ Location: symbolu/mechanical/pipeline/p24_projection/             │   │  ║
║  │  │ Inputs: P22, P23, P6-P9 (all read-only observation)              │   │  ║
║  │  │ Outputs: projection_report, mismatch_type, risk_band             │   │  ║
║  │  │ Authority: ZERO - observer_only = True                            │   │  ║
║  │  └──────────────────────────────────────────────────────────────────┘   │  ║
║  │                                                                          │  ║
║  │  Observers may ONLY write to: Snapshot objects | Logs | to_dict()       │  ║
║  └──────────────────────────────────────────────────────────────────────────┘  ║
║                                                                                ║
║                          ✗ ✗ ✗ FORBIDDEN UPWARD FLOW ✗ ✗ ✗                   ║
║                                                                                ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │                    TIER 3: GOVERNANCE & DELIVERY                         │  ║
║  │                  symbolu/mechanical/pipeline/                            │  ║
║  │                                                                          │  ║
║  │  ┌────────────────────────────────────────────────────────────────────┐ │  ║
║  │  │ AUTHORITATIVE PIPELINE (PO1 → PO2 → PO3 → PO4 → PO5 → P6 → ...)   │ │  ║
║  │  │                                                                    │ │  ║
║  │  │  PO1 (P-1): Grounding/Ambiguity Resolution                        │ │  ║
║  │  │  PO2 (P0):  Intent Inference                                       │ │  ║
║  │  │  PO3 (P1):  Allowed Action Set                                     │ │  ║
║  │  │  PO4:       Ontology Routing                                       │ │  ║
║  │  │  PO5:       Policy Gate                                            │ │  ║
║  │  │                                                                    │ │  ║
║  │  │  P6:  Regime Selection (HOLD/STABILIZE/REFLECT/INFORM/CLARIFY)    │ │  ║
║  │  │  P7:  Discourse Act Selection                                      │ │  ║
║  │  │  P8:  Semantic Slot Resolution                                     │ │  ║
║  │  │  P9:  Lexical Selection                                            │ │  ║
║  │  │  P10+: Acoustic Realization, Consistency, Delivery                 │ │  ║
║  │  └────────────────────────────────────────────────────────────────────┘ │  ║
║  │                                                                          │  ║
║  │  Authority: FULL - Binding decisions on intent, regime, discourse,      │  ║
║  │             semantics, lexical selection, routing, gating               │  ║
║  │                                                                          │  ║
║  │  ❌ MUST NOT import, call, or depend on P22/P23/P24                     │  ║
║  │  ❌ MUST NOT import from symbolu/formulas/ (Core/Substrate)             │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                                                                ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

### Information Flow Summary

```
ALLOWED FLOWS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Core/Substrate ──────► Observer Phases (P22 imports acoustic_unit_mapper)
Observer Phases ─────► Snapshot/Logs (to_dict() serialization)
Observer Phases ─────► Dashboards (observability payloads)
Observer Phases ─────► Other Observers (P23 reads P22, P24 reads P22+P23)

FORBIDDEN FLOWS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Core/Substrate ──✗──► Governance (formulas cannot influence P6-P9)
Observer Phases ─✗──► Governance (P22/P23/P24 cannot influence P6-P9)
Governance ──────✗──► Core/Substrate (P6-P9 cannot import formulas)
Governance ──────✗──► Observer Phases (P6-P9 cannot import P22/P23/P24)
```

---

## 4. Tier Definitions

### 4.1 Tier 1: Core/Substrate Utilities

**Location:** `symbolu/formulas/`

**Purpose:** Stateless computational utilities producing numeric signals, acoustic tokenizations, and mathematical metrics.

#### Files Classified as Core/Substrate

| File | Function | Zero-Authority Constraint |
|------|----------|--------------------------|
| `acoustic_unit_mapper.py` | Phonetic decomposition → AcousticUnit | No semantic inference |
| `vritti_mapper.py` | Motion quality assignment | No intent inference |
| `resonance_formulas.py` | SMI, ΔSMI, Bhava Gap, Tension Corridor | Pure math, no routing |
| `phase1_snapshot.py` | Immutable snapshot contract | Data structure only |
| `guna_kosha_resonance.py` | Guna/Kosha observability metrics | Metrics only, no gating |
| `enhanced_smi.py` | Patent-level SMI computation | Formula only, no decisions |
| `temporal_entropy_differential.py` | Temporal entropy metrics | Observation only |

#### Core/Substrate Invariants (MUST be asserted)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CORE/SUBSTRATE INVARIANTS                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ ☑ Deterministic:     Same inputs → same outputs (no LLM, no randomness)    │
│ ☑ Stateless:         No persistent state, no side effects                  │
│ ☑ Zero-LLM:          No language model calls                               │
│ ☑ No intent:         Cannot infer or access user intent                    │
│ ☑ No semantics:      Cannot access or produce semantic content             │
│ ☑ No regime:         Cannot access or influence operational regime         │
│ ☑ No routing:        Cannot influence pipeline routing decisions           │
│ ☑ No authority:      Cannot gate, block, allow, or decide anything         │
│ ☑ No pipeline:       No awareness of pipeline execution state              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Tier 2: Observer Phases (Witness-Only)

**Location:** `symbolu/mechanical/pipeline/p22_acoustic_witness/`, `p23_alignment/`, `p24_projection/`

**Purpose:** Observe and witness internal acoustic motion and alignment without influencing decisions.

#### P22: Acoustic-Vṛtti Witness Extractor

```python
# P22 ALLOWED INPUTS (read-only):
- user_raw_text (string)
- delivery_mode (from P21)

# P22 FORBIDDEN INPUTS:
FORBIDDEN_ATTRS = {
    "intent", "intent_type", "user_intent",      # No intent access
    "regime", "p6_regime", "operational_regime", # No regime access
    "discourse", "discourse_act",                 # No discourse access
    "semantic_slots", "semantic_frame",           # No semantic access
    "lexical_items", "p9_lexical",               # No lexical access
}

# P22 OUTPUTS (attach to ctx.p22_acoustic_witness only):
- acoustic_signature: str
- unit_count: int
- vritti_vector: Dict[str, float]
- dominant_motion: MotionPrimitive
- motion_balance: MotionBalance
- pressure_band: "low" | "moderate" | "high"
- witness_only: True  # HARD INVARIANT
```

#### P23: Inner-Outer Alignment Observer

```python
# P23 ALLOWED INPUTS (read-only observation):
- ctx.p22_acoustic_witness.pressure_band
- ctx.p22_acoustic_witness.motion_balance
- ctx.p6_regime.regime (READ-ONLY, does not influence)
- ctx.p7_discourse.act (READ-ONLY, does not influence)

# P23 FORBIDDEN INPUTS:
FORBIDDEN_ATTRS = {
    "user_raw_text", "text", "input_text",  # No raw text
    "tokens", "token_list", "words",         # No tokens
    "semantic_slots", "semantic_frame",      # No semantics
    "intent", "intent_type",                 # No intent
    "ontology", "ontology_mapping",          # No ontology
}

# P23 OUTPUTS (attach to ctx.p23_alignment_report only):
- alignment_state: ALIGNED | NEUTRAL | TENSION | CONTRADICTION
- tension_score: float [0.0, 1.0]
- alignment_tags: frozenset[str]
- observer_only: True  # HARD INVARIANT
```

#### P24: Acoustic-Ontology Projection Observer

```python
# P24 ALLOWED INPUTS (read-only observation):
- ctx.phase_minus_one.is_blocked()
- ctx.p6_regime.regime
- ctx.p7_discourse_envelope.act
- ctx.semantic_frame.slots (observation only)
- ctx.lexical_frame.selections (observation only)
- ctx.grammar_evidence
- ctx.p22_acoustic_witness
- ctx.p23_alignment_report

# P24 FORBIDDEN INPUTS:
FORBIDDEN_ATTRS = {
    "user_raw_text", "raw_text", "text",  # No raw text
    "tokens", "token_list",                # No tokens
}

# P24 OUTPUTS (attach to ctx.p24_projection_report only):
- projected_layers: tuple[OntologyLayer]
- projection_risk_band: LOW | MODERATE | HIGH
- mismatch_type: NONE | SOFT_MISMATCH | STRONG_MISMATCH
- projection_tags: frozenset[str]
- confidence: float
- observer_only: True  # HARD INVARIANT
```

#### Observer Invariants (MUST be enforced)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ OBSERVER INVARIANTS                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ ☑ Read-only access:  May read PipelineContext but NOT modify it            │
│ ☑ May consume:       Core/Substrate outputs                                │
│ ☑ May compute:       Derived observational metrics                         │
│                                                                             │
│ ❌ May NOT influence: Regime (P6)                                          │
│ ❌ May NOT influence: Discourse act (P7)                                   │
│ ❌ May NOT influence: Semantic slots (P8)                                  │
│ ❌ May NOT influence: Lexical selection (P9)                               │
│ ❌ May NOT influence: Policy, routing, or eligibility                      │
│                                                                             │
│ ALLOWED SINKS ONLY:                                                         │
│   → Snapshot objects (to_dict())                                            │
│   → Logs and tracing                                                        │
│   → Observability payloads                                                  │
│   → Other observer phases (P23 → P24)                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Tier 3: Authoritative Pipeline Governance

**Location:** `symbolu/mechanical/pipeline/`

**Purpose:** Make binding decisions about intent, regime, discourse, semantics, and lexical selection.

#### Governance Phase Sequence

```
PO1 (P-1) → PO2 (P0) → PO3 (P1) → PO4 → PO5 → P6 → P7 → P8 → P9 → P10+
   │           │          │        │      │     │     │     │     │
   │           │          │        │      │     │     │     │     └─ Delivery
   │           │          │        │      │     │     │     └─ Lexical Selection
   │           │          │        │      │     │     └─ Semantic Resolution
   │           │          │        │      │     └─ Discourse Selection
   │           │          │        │      └─ Regime Selection
   │           │          │        └─ Policy Gate
   │           │          └─ Ontology Routing
   │           └─ Allowed Action Set
   └─ Intent Inference
   Grounding/Ambiguity
```

#### Governance Phase Authority Matrix

| Phase | Location | Authority | Decision Type |
|-------|----------|-----------|---------------|
| PO1 (P-1) | `grounding/` | Ambiguity resolution | Clause splitting, blocking |
| PO2 (P0) | `phase_zero/` | Intent inference | IntentType, ResponsePosture |
| PO3 (P1) | `phase_one/` | Action permission | AllowedActionSet |
| PO4 | `phase_po4/` | Ontology routing | Category assignment |
| PO5 | `phase_po5/` | Policy gating | ExecutionEligibility |
| **P6** | `phase_p6/` | **Regime selection** | HOLD/STABILIZE/REFLECT/INFORM/CLARIFY |
| **P7** | `p7_discourse/` | **Discourse selection** | QUESTION/REFLECTION/EXPLANATION/... |
| **P8** | `p8_semantics/` | **Semantic resolution** | Slot population, allow-lists |
| **P9** | `p9_lexical/` | **Lexical selection** | Word choices from pools |
| P10+ | Various | Delivery | Acoustic realization, consistency |

#### Governance Constraints (ABSOLUTE)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ GOVERNANCE CONSTRAINTS (ABSOLUTE)                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  No authoritative phase may:                                                │
│                                                                             │
│  ❌ import from symbolu/formulas/                                          │
│  ❌ import from p22_acoustic_witness/                                      │
│  ❌ import from p23_alignment/                                             │
│  ❌ import from p24_projection/                                            │
│  ❌ read ctx.p22_acoustic_witness                                          │
│  ❌ read ctx.p23_alignment_report                                          │
│  ❌ read ctx.p24_projection_report                                         │
│  ❌ condition decisions on pressure_band, tension_score, or vritti_vector  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Allowed and Forbidden Flow Table

### Complete Flow Matrix

| Source | Can Read | Can Write | Forbidden To |
|--------|----------|-----------|--------------|
| **Core/Substrate** (formulas/) | None | Numeric outputs, AcousticUnit, AcousticVritti | Pipeline decisions, context modification, governance |
| **Observer P22** | user_raw_text, delivery_mode | ctx.p22_acoustic_witness only | Intent, regime, discourse, semantics, lexical, routing |
| **Observer P23** | P22 outputs, P6 regime (r/o), P7 act (r/o) | ctx.p23_alignment_report only | Raw text, tokens, semantic modification, governance |
| **Observer P24** | P22, P23, P6-P9 (all r/o) | ctx.p24_projection_report only | Raw text, tokens, governance modification |
| **Governance (PO1-P9)** | Context fields as needed | Authoritative envelopes | Core/Substrate, Observer outputs, formula imports |
| **Snapshots/Logs** | All tiers | Serialized payloads | Nothing (terminal sink) |

### Import Direction Rules

```
ALLOWED IMPORT DIRECTION:
══════════════════════════════════════════════════════════════════════════

    formulas/     →     Observer     →     Tests/Diagnostics
    (can be             (can be            (can import
     imported by         imported by        anything)
     Observers)          Snapshots)

FORBIDDEN IMPORT DIRECTION:
══════════════════════════════════════════════════════════════════════════

    Governance    ←✗←    formulas/        (P6-P9 cannot import formulas)
    Governance    ←✗←    Observer         (P6-P9 cannot import P22/P23/P24)
    formulas/     ←✗←    Governance       (formulas cannot import P6-P9)
    formulas/     ←✗←    Observer         (formulas cannot import P22/P23/P24)
```

---

## 6. Code-Level Enforcement Checklist

### 6.1 Import Direction Rules

| Rule | Enforcement Location |
|------|---------------------|
| Authoritative modules must NOT import `symbolu.formulas.*` | `test_core_substrate_noninterference.py` |
| Authoritative modules must NOT import `p22_acoustic_witness` | `test_observer_noninterference.py` |
| Authoritative modules must NOT import `p23_alignment` | `test_observer_noninterference.py` |
| Authoritative modules must NOT import `p24_projection` | `test_observer_noninterference.py` |
| Formula modules must NOT import governance modules | `test_core_substrate_noninterference.py` |

### 6.2 Naming Conventions

| Pattern | Meaning | Authority |
|---------|---------|-----------|
| `witness_only = True` | Observer phase marker | ZERO authority |
| `observer_only = True` | Observer phase marker | ZERO authority |
| `FORBIDDEN_*_ATTRS` | Attribute access prohibition | Hard error if accessed |
| `symbolu/formulas/` path | Core/Substrate utility | ZERO authority |
| `ctx.p22_*`, `ctx.p23_*`, `ctx.p24_*` | Observer output fields | Write-only by that phase |

### 6.3 Observer-Only Enforcement

All observer resolvers MUST implement:

```python
# Required attributes in observer schemas:
witness_only: bool = True    # For P22
observer_only: bool = True   # For P23, P24

# Required FORBIDDEN_ATTRS sets:
FORBIDDEN_INTENT_ATTRS = frozenset({...})
FORBIDDEN_REGIME_ATTRS = frozenset({...})
FORBIDDEN_SEMANTIC_ATTRS = frozenset({...})
ALL_FORBIDDEN_ATTRS = FORBIDDEN_INTENT_ATTRS | FORBIDDEN_REGIME_ATTRS | ...

# Required methods:
def _validate_no_forbidden_access(self, ctx): ...
```

### 6.4 Future Contributor Validation Checklist

Before merging any PR that touches `symbolu/formulas/` or `symbolu/mechanical/pipeline/`:

- [ ] Run `pytest tests/audits/test_core_substrate_noninterference.py -v`
- [ ] Run `pytest symbolu/mechanical/pipeline/integration_tests/test_observer_noninterference.py -v`
- [ ] Verify no new imports of `symbolu.formulas.*` in governance modules
- [ ] Verify no new imports of `p22_*/p23_*/p24_*` in governance modules
- [ ] Verify any new observer phase has `observer_only = True`
- [ ] Verify any new formula file has zero governance imports

### 6.5 CI Enforcement (Recommended)

Add to CI pipeline:

```yaml
- name: Verify Core/Substrate Boundary
  run: pytest tests/audits/test_core_substrate_noninterference.py -v --tb=short

- name: Verify Observer Non-Interference
  run: pytest symbolu/mechanical/pipeline/integration_tests/test_observer_noninterference.py -v --tb=short
```

---

## 7. Validation Evidence

### 7.1 Audit Results Summary

**Audit Date:** 2025-12-14
**Audit Files:**
- `docs/audits/core_substrate_boundary_report.md`
- `docs/audit/PHASE_1_9_SUBSTRATE_AUDIT.md`

**Results:**

| Check | Result |
|-------|--------|
| Authoritative modules import formulas | **NONE FOUND** ✔ |
| Formula modules import governance | **NONE FOUND** ✔ |
| P6 imports P22/P23/P24 | **NONE FOUND** ✔ |
| P7 imports P22/P23/P24 | **NONE FOUND** ✔ |
| P8 imports P22/P23/P24 | **NONE FOUND** ✔ |
| P9 imports P22/P23/P24 | **NONE FOUND** ✔ |
| Observer outputs influence governance | **NO EVIDENCE** ✔ |
| Behavioral non-interference verified | **PASS** ✔ |

### 7.2 Test Evidence

**Test Location:** `symbolu/mechanical/pipeline/tests/audits/test_core_substrate_noninterference.py`

**Test Classes:**
1. `TestAuthorativeModulesDoNotImportFormulas` - Per-directory import scans
2. `TestGlobalFormulaImportScan` - Full codebase scan
3. `TestFormulaDependencyDirection` - Reverse dependency checks
4. `TestAllowedSinksAreCorrect` - Sink classification verification
5. `TestBehavioralNonInterference` - Runtime non-interference proof
6. `TestRegressionGuards` - Source-level regression tests

**Test Location:** `symbolu/mechanical/pipeline/integration_tests/test_observer_noninterference.py`

**Test Classes:**
1. `TestObserverNonInterference` - Context pair comparison
2. `TestImportIsolation` - Structural import verification
3. `TestAllowedSinks` - Observer output sink verification
4. `TestForbiddenAttributeAccess` - FORBIDDEN_ATTRS enforcement
5. `TestDeterminism` - Observer determinism verification

### 7.3 Behavioral Non-Interference Proof

The test suite creates context pairs with:
- **IDENTICAL** authoritative fields (PO1-P9 inputs)
- **DIFFERENT** observer fields (P22/P23/P24 outputs)

And verifies:
- Regime (P6) is IDENTICAL in both contexts
- Discourse (P7) is IDENTICAL in both contexts
- Semantics (P8) is IDENTICAL in both contexts
- Lexical (P9) is IDENTICAL in both contexts

This proves that observer variation does not cause governance variation.

### 7.4 Declaration

**THIS BOUNDARY IS ALREADY ENFORCED IN CODE.**

The tests referenced above have been run and pass. The audit reports document zero violations. This document formalizes what the codebase already implements.

---

## 8. Why Acoustic and Vṛtti Mapping Exist

### The Core Question

> "Why do acoustic and vṛtti mapping exist if they have no authority?"

### The Authoritative Answer

Acoustic and vṛtti mapping modules (`acoustic_unit_mapper.py`, `vritti_mapper.py`) exist for the following purposes:

#### 1. They Witness Internal Motion

These modules observe and record the internal acoustic motion patterns present in user utterances. They decompose speech into motion primitives (expansion, contraction, oscillation, friction, inertia, neutral) without interpreting what those motions mean.

**Key Insight:** Witnessing is not deciding. A thermometer witnesses temperature without controlling the furnace.

#### 2. They Enable Delivery Modulation

Observer outputs (pressure_band, motion_balance, tension_score) flow to **allowed sinks only**:
- Renderer hints (presentation style, not semantic content)
- DHA tone hints (delivery adaptation, not meaning change)
- Observability dashboards (monitoring, not control)

**Example:** If P22 detects high acoustic pressure and P23 detects tension, this information may:
- ✔ Hint to the renderer to use calmer presentation
- ✔ Log the observation for later analysis
- ✗ NOT change what the system says (semantic content)
- ✗ NOT change the regime, discourse, or lexical selection

#### 3. They Enable Long-Term Truth Detection

Over time, acoustic/vṛtti observations can be aggregated to detect:
- Patterns of inner-outer misalignment
- Drift in motion coherence
- Early indicators of dysregulation

This aggregation happens in **observation sinks**, never in governance paths.

#### 4. They Never Decide Meaning, Intent, or Action

**ABSOLUTE DECLARATION:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  Acoustic and vṛtti mapping modules:                                        │
│                                                                             │
│  ❌ NEVER decide what the user meant                                       │
│  ❌ NEVER infer user intent                                                │
│  ❌ NEVER select what action to take                                       │
│  ❌ NEVER influence semantic content                                       │
│  ❌ NEVER gate, block, or route                                            │
│                                                                             │
│  ☑ ONLY witness internal acoustic motion                                   │
│  ☑ ONLY produce deterministic numeric signals                              │
│  ☑ ONLY enable downstream observation                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Summary Statement

> Acoustic and vṛtti mapping exist to witness internal motion, enable delivery modulation, and support long-term truth detection—**without ever deciding meaning, intent, or action.**

---

## 9. Glossary

| Term | Definition |
|------|------------|
| **Core/Substrate** | Stateless formula utilities with zero governance authority |
| **Observer** | Witness-only phase that reads without influencing decisions |
| **Governance** | Authoritative pipeline phase with binding decision authority |
| **Authority** | The power to make binding decisions that affect system output |
| **Witness-Only** | Can observe but cannot influence |
| **Allowed Sink** | Destination where observer data may flow (logs, snapshots) |
| **Forbidden Sink** | Destination where observer data may NOT flow (governance) |
| **Non-Interference** | Property that observer variation does not cause governance variation |
| **Deterministic** | Same inputs always produce same outputs |
| **Stateless** | No persistent state between invocations |
| **Acoustic Unit** | Phonetic primitive from text decomposition |
| **Vṛtti** | Motion quality (expansion, contraction, oscillation, etc.) |
| **Pressure Band** | Coarse acoustic energy classification (low/moderate/high) |
| **Regime** | Operational mode selected by P6 (HOLD, STABILIZE, etc.) |
| **Discourse Act** | Communication type selected by P7 (QUESTION, REFLECTION, etc.) |

---

## Document Certification

This document constitutes the **authoritative formal specification** of the Core/Substrate → Observer → Governance boundary in Symbol-U.

**Effective Date:** 2025-12-14

**Supersedes:** All prior informal or ambiguous references to "Phase 1-9"

**Enforcement:** Code-level tests exist and must pass before any merge to main

---

*End of Specification*
