# Core/Substrate vs Pipeline Architecture

**Document Version:** 1.0
**Last Updated:** 2025-12-14
**Status:** Authoritative Architectural Reference

---

## Executive Summary

Symbol-U maintains a strict separation between two architectural layers:

1. **Core/Substrate Layer** - Stateless formula utilities (no governance authority)
2. **Pipeline Governance Layer** - Authoritative decision-making stack (full governance)

This document clarifies that legacy "Phase 1–9" docstrings in the formula modules refer to **Core/Substrate** utilities, NOT to the authoritative pipeline phases.

---

## Layer Definitions

### Core/Substrate Layer

**Location:** `symbolu/formulas/`

**Purpose:** Stateless computational utilities that produce numeric signals, metrics, and acoustic/symbolic tokenizations.

**Key Characteristics:**
- **Deterministic:** Same inputs → same outputs (no LLM, no randomness)
- **Stateless:** No persistent state, no side effects
- **Read-only:** Never modifies context or upstream state
- **Zero Authority:** Cannot influence routing, gating, or policy decisions
- **Observation-only:** Outputs may be observed but never steer governance

**Core Formula Files:**
| File | Purpose |
|------|---------|
| `acoustic_unit_mapper.py` | Phonetic tokenization to AcousticUnit primitives |
| `vritti_mapper.py` | Motion quality (vṛtti) assignment to acoustic units |
| `resonance_formulas.py` | SMI, ΔSMI, Bhava Gap, Tension Corridor computations |
| `phase1_snapshot.py` | Immutable Phase1Snapshot output contract |
| `guna_kosha_resonance.py` | Guna/Kosha observability metrics |
| `enhanced_smi.py` | Phase 13 patent-level SMI formula |
| `temporal_entropy_differential.py` | Phase 18 temporal entropy metrics |

**Historical Note on "Phase" Naming:**
The docstrings in these files reference "Phase 1", "Phase 8", "Phase 13", etc. These labels are **historical markers** indicating when the formula was introduced, NOT pipeline execution phases. All formula files are Core/Substrate utilities regardless of their phase label.

---

### Pipeline Governance Layer

**Location:** `symbolu/mechanical/pipeline/`

**Purpose:** Authoritative governance stack that makes binding decisions about intent, regime, discourse, semantics, and lexical selection.

**Key Characteristics:**
- **Authoritative:** Decisions are binding on downstream processing
- **Sequential:** Phases execute in defined order (PO1 → PO2 → ... → P9 → ...)
- **Governance-bearing:** Each phase has specific decision authority
- **Policy-enforced:** Subject to policy constraints and gating

**Authoritative Pipeline Phases:**

| Phase | Location | Authority |
|-------|----------|-----------|
| PO1 (Phase -1) | `grounding/` | Ambiguity resolution, clause splitting |
| PO2 (Phase 0) | `phase_zero/` | Intent inference |
| PO3 (Phase 1) | `phase_one/` | Allowed action set |
| PO4 | `phase_po4/` | Ontology routing |
| PO5 | `phase_po5/` | Policy gate |
| P6 | `phase_p6/` | Regime selection (HOLD/STABILIZE/REFLECT/INFORM/etc.) |
| P7 | `p7_discourse/` | Discourse act selection |
| P8 | `p8_semantics/` | Semantic slot resolution |
| P9 | `p9_lexical/` | Lexical selection |
| P10+ | Various | Acoustic realization, consistency, delivery |

---

## Dependency Direction

The dependency direction between layers is strictly enforced:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Core/Substrate Layer                            │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  acoustic_unit_mapper.py                                      │  │
│  │  vritti_mapper.py                                             │  │
│  │  resonance_formulas.py                                        │  │
│  │  phase1_snapshot.py                                           │  │
│  │  guna_kosha_resonance.py                                      │  │
│  │  enhanced_smi.py                                              │  │
│  │  temporal_entropy_differential.py                             │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              ↑                                      │
│                              │ (may be consumed by)                 │
│                              │                                      │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                              │                                      │
│         Allowed Sinks (Observation-Only)                            │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Observers: P22, P23, P24                                     │  │
│  │  Diagnostics: dashboards, telemetry                           │  │
│  │  Coherence Engine (observation only)                          │  │
│  │  Temporal Trackers (observation only)                         │  │
│  │  Tests and verification tools                                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

                               ✗ (FORBIDDEN)

┌─────────────────────────────────────────────────────────────────────┐
│                    Pipeline Governance Layer                        │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  PO1 (grounding/) → PO2 (phase_zero/) → PO3 (phase_one/)     │  │
│  │  → PO4 (phase_po4/) → PO5 (phase_po5/) → P6 (phase_p6/)      │  │
│  │  → P7 (p7_discourse/) → P8 (p8_semantics/) → P9 (p9_lexical/)│  │
│  │  → P10+ (acoustic realization, delivery)                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  MUST NOT import from Core/Substrate Layer                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Rules

1. **Core/Substrate → Governance: FORBIDDEN**
   - Formula modules must never import from governance modules
   - This prevents circular dependencies and maintains layer isolation

2. **Governance → Core/Substrate: FORBIDDEN**
   - Authoritative pipeline phases (PO1-P9) must NOT import formulas
   - This ensures governance decisions are independent of formula computations

3. **Observers → Core/Substrate: ALLOWED**
   - Observer phases (P22, P23, P24) may import formulas
   - Observers are witness-only and have zero governance authority

4. **Sinks → Core/Substrate: ALLOWED**
   - Diagnostics, dashboards, and telemetry may consume formula outputs
   - These are observation-only sinks with no upstream influence

---

## Observer Non-Interference

Observer phases (P22, P23, P24) are allowed to import and consume formula outputs, but they MUST NOT influence governance decisions:

### P22 - Acoustic-Vrtti Witness Extractor
- **Imports:** `acoustic_unit_mapper.py`, `vritti_mapper.py`
- **Authority:** ZERO - witness-only
- **Invariants:**
  - Deterministic (same inputs → same outputs)
  - Read-only (does not modify context)
  - No semantic access
  - No feedback to P1-P21

### P23 - Inner-Outer Alignment Observer
- **Reads:** P22 pressure_band, P6 regime (observation only)
- **Authority:** ZERO - observer-only
- **Invariants:**
  - Does not modify any upstream state
  - Produces alignment_report for observation only

### P24 - Acoustic-Ontology Projection Observer
- **Reads:** P22, P23, P6-P9 outputs (observation only)
- **Authority:** ZERO - observer-only
- **Invariants:**
  - Does not modify any upstream state
  - Produces projection_report for observation only

---

## Enforcement Mechanisms

### 1. Import Constraint Tests
Location: `symbolu/mechanical/pipeline/tests/audits/test_core_substrate_noninterference.py`

Tests verify:
- Authoritative modules do NOT import formula modules
- Formula modules do NOT import governance modules
- All formula imports are in allowed sink directories

### 2. Behavioral Non-Interference Tests
Tests verify:
- Pipeline outputs are identical regardless of formula snapshot differences
- Two contexts with identical authoritative fields but different formula values produce identical governance outputs

### 3. Regression Guards
Source-level checks ensure no formula references appear in:
- P6 regime gate
- P7 discourse resolver
- P8 semantic resolver
- P9 lexical resolver

---

## Clarification: Legacy "Phase" Docstrings

Many formula files contain docstrings referencing "Phase 1", "Phase 8", etc.:

```python
# Example from resonance_formulas.py:
"""
Phase 1 Foundational Temporal Math
...
"""
```

**These are historical labels, NOT pipeline phases.**

The correct interpretation:
- "Phase 1" in `resonance_formulas.py` = Core/Substrate utility introduced during "Phase 1" of development
- "Phase 8" in `guna_kosha_resonance.py` = Observability metrics introduced during "Phase 8" of development
- "Phase 13" in `enhanced_smi.py` = Patent-level SMI formula introduced during "Phase 13" of development

All formula files are Core/Substrate regardless of their phase label. The pipeline phases (PO1, PO2, P6, P7, etc.) are separate and do not correspond to these formula phase numbers.

---

## Summary Table

| Component | Layer | Authority | Can Import Formulas? |
|-----------|-------|-----------|---------------------|
| `symbolu/formulas/*` | Core/Substrate | ZERO | N/A (is the formula layer) |
| `grounding/` | Governance | Full | NO |
| `phase_zero/` | Governance | Full | NO |
| `phase_one/` | Governance | Full | NO |
| `phase_p6/` | Governance | Full | NO |
| `p7_discourse/` | Governance | Full | NO |
| `p8_semantics/` | Governance | Full | NO |
| `p9_lexical/` | Governance | Full | NO |
| `governance/` | Governance | Full | NO |
| `router/` | Governance | Full | NO |
| `p22_acoustic_witness/` | Observer | ZERO | YES |
| `p23_alignment/` | Observer | ZERO | YES |
| `p24_projection/` | Observer | ZERO | YES |
| Tests | N/A | N/A | YES |
| Diagnostics | Sink | ZERO | YES |

---

## Conclusion

The Symbol-U architecture maintains a strict separation between:

1. **Core/Substrate formulas** - Stateless utilities with zero governance authority
2. **Pipeline governance phases** - Authoritative decision-making stack

Legacy "Phase 1–9" docstrings in formula modules are historical markers and should be interpreted as "Core/Substrate" utilities. The authoritative governance stack is PO1 → PO2 → PO3 → P6 → P7 → P8 → P9 → P10+.

This boundary is enforced by:
- Import constraint tests (static analysis)
- Behavioral non-interference tests (runtime verification)
- Regression guards (source-level checks)

Observers (P22/P23/P24) may read Core outputs but NEVER influence governance authority.

---

*End of Document*
