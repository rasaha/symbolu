# Symbol-U Formulas — Core/Substrate Layer

## Overview

This directory contains **Core/Substrate utilities** — stateless, deterministic mathematical formulas that have **zero governance authority**.

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         CORE/SUBSTRATE LAYER                                   ║
║                                                                                ║
║  All modules in this directory are non-authoritative.                          ║
║  They may NOT influence regime, discourse, semantics, lexicon, or policy.      ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

## Architectural Role

These formulas compute numeric signals, acoustic tokenizations, and metrics that may be **observed** by allowed sinks (Observer phases, dashboards, logs) but **never** influence governance decisions.

### What Core/Substrate Modules Do
- Compute deterministic numeric outputs
- Measure acoustic/phonetic properties
- Produce immutable snapshots
- Support observability and diagnostics

### What Core/Substrate Modules Do NOT Do
- Interpret meaning
- Infer emotion or intent
- Affect delivery decisions
- Influence routing, gating, or policy
- Make authoritative decisions of any kind

## Historical Note on "Phase" Labels

Docstrings in these files may reference "Phase 1", "Phase 8", "Phase 14", etc. These are **historical development milestone labels**, NOT pipeline execution phases.

| Old Label | Correct Interpretation |
|-----------|----------------------|
| "Phase 1" formulas | Core/Substrate utility introduced during early development |
| "Phase 8" metrics | Observability metric introduced during Phase 8 development |
| "Phase 14" formulas | Temporal formula introduced during Phase 14 development |

The authoritative pipeline phases (PO1, PO2, P6, P7, etc.) are separate and do not correspond to these formula phase numbers.

## Key Modules

| Module | Purpose | Authority |
|--------|---------|-----------|
| `acoustic_unit_mapper.py` | Phonetic tokenization to AcousticUnit primitives | ZERO |
| `vritti_mapper.py` | Motion quality (vṛtti) assignment | ZERO |
| `resonance_formulas.py` | SMI, ΔSMI, Bhava Gap, Tension Corridor | ZERO |
| `phase1_snapshot.py` | Immutable snapshot output contract | ZERO |
| `guna_kosha_resonance.py` | Guṇa/Koṣa observability metrics | ZERO |
| `vritti_momentum.py` | Vṛtti momentum formula | ZERO |
| `enhanced_smi.py` | Patent-level SMI computation | ZERO |

## Invariants

All formulas in this directory MUST maintain:

1. **Deterministic**: Same inputs → same outputs (no LLM, no randomness)
2. **Stateless**: No persistent state, no side effects
3. **Zero-LLM**: No language model calls
4. **No semantics**: Cannot access or produce semantic content
5. **No intent**: Cannot infer or access user intent
6. **No regime**: Cannot access or influence operational regime
7. **No routing**: Cannot influence pipeline routing decisions
8. **Non-authoritative**: Cannot gate, block, allow, or decide anything

## Related Documentation

For the complete architectural specification, see:
- `Project_documentation/repository/docs/architecture/core_vs_pipeline.md`
- `Project_documentation/repository/docs/architecture/core_substrate_observer_boundary.md`

## Flow Diagram

```
Core/Substrate Utilities
        │
        │ (outputs consumed by)
        ▼
Observer Phases (P22, P23, P24)
        │
        │ (witness-only, no authority)
        ▼
Allowed Sinks Only:
  - Snapshots/Logs
  - Dashboards
  - Observability payloads

        ✗ ✗ ✗

Governance Phases (PO1-PO5, P6-P9)
  - MUST NOT import from this directory
  - MUST NOT consume formula outputs
```

---

*This documentation is part of the Symbol-U terminology normalization effort.*
