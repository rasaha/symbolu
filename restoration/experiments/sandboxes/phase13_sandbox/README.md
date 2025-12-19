# Phase-13: K1 Knowledge Layer

## Overview

K1 is the first canonical knowledge layer that binds ontological artifacts to retrievable, composable "meaning scaffolds".

**Critical Rules:**
- K1 NEVER stores raw text
- K1 stores structure about text
- Interpretation/rendering happens outside K1
- Discourse acts are routing/control signals only (not intent/emotion/truth)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     K1 KNOWLEDGE LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  K1Atom (minimal) ─────────────────────────────────────────────  │
│    ├── atom_id: str (hash-stable)                               │
│    ├── layer: OntologicalLayer (O1-O10)                         │
│    ├── slot: K1Slot (17 typed slots)                            │
│    ├── discourse_act: DiscourseAct (14 structural acts)         │
│    ├── payload_ref: str (opaque pointer, NOT text)              │
│    └── provenance: str                                          │
│                                                                  │
│  K1Query ────────────────────────────────────────────────────── │
│    Primary Index: (layer, slot, discourse_act)                  │
│                                                                  │
│  K1ResultSet ────────────────────────────────────────────────── │
│    Deterministic, ledger-recorded, replay-provable              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Slot Taxonomy (17 Slots, 4 Tiers)

### Tier 1: Core Structural (Mandatory)
| Slot | Description |
|------|-------------|
| TARGET | What the expression is oriented toward |
| CAUSE | Upstream condition or trigger |
| EFFECT | Downstream outcome (must pair with CAUSE) |
| CONSTRAINT | Restrictive boundary |
| EVIDENCE | Supportive structural justification |

### Tier 2: Control & Flow (Recommended)
| Slot | Description |
|------|-------------|
| CONDITION | Gate that must be satisfied |
| ALTERNATIVE | Parallel possible path (mutually exclusive) |
| SEQUENCE | Ordered relationship |
| DEPENDENCY | Non-causal reliance |

### Tier 3: Perspective & Framing (Optional)
| Slot | Description |
|------|-------------|
| ASSUMPTION | Declared premise |
| SCOPE | Applicability boundary |
| REFERENCE | Pointer to external/prior atom |
| EXCEPTION | Explicit carve-out |

### Tier 4: Meta & Governance (Advanced)
| Slot | Description |
|------|-------------|
| RULE | Structural rule |
| JUSTIFICATION | Why a rule/constraint exists |
| RISK | Declared potential negative outcome |
| MITIGATION | Counter-measure to RISK |

## Discourse Acts (14 Acts, 4 Tiers)

**Hard Rules:**
- Discourse acts do NOT imply intent
- They do NOT imply emotion
- They do NOT imply truth
- They are routing and control signals ONLY

### Tier A: Structural Flow
`DECLARE`, `QUERY`, `LINK`, `COMPARE`, `NEGATE`

### Tier B: Directional
`CONDITION`, `TRIGGER`, `RESOLVE`

### Tier C: Reflective/Meta
`OBSERVE`, `SUMMARIZE`, `CANONICALIZE`

### Tier D: Terminal/Governance
`BOUND`, `RELEASE`, `ABORT`

## Implementation Status

| Component | Status | Tests |
|-----------|--------|-------|
| K1Atom (minimal) | ✅ Complete | 27 |
| K1Query | ✅ Complete | - |
| K1Store with indices | ✅ Complete | 28 |
| Ledger recording | ✅ Complete | - |
| Replay proof | ✅ Complete | - |

**Total: 55 tests passing**

## Files

```
phase13_sandbox/
├── README.md           # This file
├── k1_schema.py        # K1Atom, K1Query, K1ResultSet, enums ✅
├── k1_store.py         # K1Store with indices, ledger ✅
└── tests/
    ├── __init__.py
    ├── test_k1_schema.py   # 27 tests ✅
    └── test_k1_store.py    # 28 tests ✅
```

## Key Invariants

1. **Deterministic Retrieval**: Same query over same store → same ordered results
2. **Ledger Recording**: Every operation (query, add, remove) is logged
3. **Replay Provable**: Query results include step-by-step proof
4. **Index Rebuildable**: Indices are derived; rebuildable from atoms
5. **No Free Text**: payload_ref is an opaque pointer only

## How K1 Feeds Generation

K1 is the structural skeleton that generation hangs from:

```
Phase-11B.3 (routing)
    ↓
K1 (knowledge retrieval)
    ↓
Phase-12 (generation + verification)
```

1. Request K1 atoms with K1Query
2. Use returned atoms as conditioning context
3. Generate text (probabilistic)
4. Verify output against K1 structure

## Deferred (Not in Minimal K1)

- Entity graph
- RelType ontologies
- Semantic embeddings
- Cross-slot inference
- LLM integration
