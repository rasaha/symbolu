# Ontology as Substrate — Execution Contract

**Status: FROZEN**
**Date: 2025-12-18**
**Authority: Phase-4A Ontology Loader**

---

## Core Principle

**The ontology is substrate, not logic.**

Ontology JSON files are equivalent to physical constants. They define the invariant mappings between varnas, layers, and interactions. They do not contain inference rules, heuristics, or runtime logic.

---

## Phase-4A: Sole Ontology Executor

Phase-4A is the **only authorized component** that accesses ontology JSON files.

```
Ontology Files (docs/data/*.json)
         │
         ▼
    ┌─────────┐
    │ Phase-4A│  ← ONLY access point
    │ Loader  │
    └────┬────┘
         │
         ▼
    lookup_interaction(varna, layer)
         │
         ├──► Phase-4B (Transform Engine)
         ├──► Phase-4C (PO4 Governance)
         ├──► Phase-5+ (Downstream)
         └──► Phase-14 (Audit ONLY)
```

---

## Hard Invariants

| Invariant | Enforcement |
|-----------|-------------|
| **NO INFERENCE** | Missing data triggers error, never defaults |
| **NO MODIFICATION** | Checksum validated on every load |
| **NO GAP-FILLING** | Absent mappings do not exist |
| **NO REINTERPRETATION** | Values used exactly as stored |
| **FAIL-FAST** | Any violation is fatal |

---

## Phase Access Rules

| Phase | Ontology Access | Notes |
|-------|-----------------|-------|
| Phase-4A | **ALLOWED** | Sole executor — load, validate, lookup |
| Phase-4B | PROHIBITED | Must call Phase-4A if ontology data needed |
| Phase-4C | PROHIBITED | Must call Phase-4A if ontology data needed |
| Phase-5+ | PROHIBITED | Receives data through Phase-4A API |
| Phase-14 | AUDIT ONLY | Validates compliance, never queries ontology |

---

## Experiments Are Non-Authoritative

All code under `docs/experiments/` is marked `EXPERIMENT_ONLY = True`.

Experimental code:
- MUST NOT be imported by production pipeline
- MUST NOT be reachable from Phase-4B, Phase-4C, or Phase-14
- Contains NO authoritative ontology data

---

## Frozen Ontology Files

| File | Status |
|------|--------|
| `docs/data/varna_bridge_map_v1.json` | FROZEN |
| `docs/data/ontological_layers_v1.json` | FROZEN |
| `docs/data/varna_layer_interaction_v1.json` | FROZEN |

Changes to frozen files require:
1. Explicit version bump (v1 → v2)
2. Full pipeline re-validation
3. Checksum registry update
4. Architectural review

---

## API Contract

```python
from symbolu.ontology.phase4a import (
    lookup_interaction,      # (varna, layer) → VarnaLayerInteraction
    validate_ontology,       # Validate file consistency
    get_all_varnas,          # FrozenSet of valid varnas
    get_all_layers,          # FrozenSet of valid layers
)

# Lookup example
result = lookup_interaction("ka", "O1_ACTING")
# result.manifestation_positive
# result.manifestation_negative
# result.distortion_vector
# result.sublimate_vector

# Fails loudly on:
# - Unknown varna → Phase4AVarnaMissingError
# - Unknown layer → Phase4ALayerMissingError
# - Missing interaction → Phase4AInteractionMissingError
# - Missing field → Phase4AFieldMissingError
# - Checksum mismatch → Phase4AValidationError
```

---

## Why This Matters

1. **Patent defensibility**: Clear substrate/execution separation
2. **Composability**: Higher phases can safely build on Phase-4A
3. **Auditability**: Single source of truth, traceable lookups
4. **Determinism**: Same input always produces same output

---

*After this freeze, the ontology is law. Phases are execution.*
