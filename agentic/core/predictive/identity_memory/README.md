# Phase 36 - Identity Resonance Memory

## Purpose

Phase 36 answers one question only:

> "What identity resonance patterns persist over time, independent of momentary fluctuations?"

It is a **memory** of identity behavior, **NOT** a decision system.

It:
- Remembers stability and drift patterns
- Smooths short-term noise
- Preserves historical identity context

It does **NOT**:
- Predict futures (Phase 35 does that)
- Influence regime, discourse, semantics, or tone
- Gate insights or actions
- Modify persona behavior

---

## Authority Boundaries

### MUST NOT:
- Influence P6-P9 (regime, discourse, semantics, lexical)
- Influence DHA, Persona Engine, Renderer
- Influence Phase 32 insight gating
- Influence any action eligibility

### MUST:
- Be read-only memory
- Be append-only
- Be fully deterministic

### MAY:
- Remember stability and drift patterns
- Smooth short-term noise
- Preserve historical identity context

---

## Inputs (Read-Only)

From PipelineContext:

**Current snapshot:**
- `ucf_score` (P26)
- `identity_harmonics_score` (P34)
- `schema_stability` (P33)
- `predicted_drift_score` (P35)
- `drift_risk_band` (P35)

**Historical:**
- Prior `IdentityResonanceMemoryState` entries (if any)

**FORBIDDEN inputs:**
- Acoustic observers (P22-P24)
- Lexical content
- User text
- Intent or emotion

---

## Output

`IdentityResonanceMemoryState` (immutable dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `identity_resonance_index` | float [0.0, 1.0] | Composite resonance measure |
| `identity_stability_band` | "stable" \| "soft" \| "fragile" | Stability classification |
| `persistence_score` | float [0.0, 1.0] | How consistent resonance has been |
| `volatility_index` | float [0.0, 1.0] | Average change magnitude |
| `memory_depth` | int | Number of snapshots used |
| `memory_timestamp` | datetime | When this snapshot was created |

This object is stored in context history and **never mutated**.

---

## Core Formulas (Locked)

### Step 1 - Identity Resonance Index

```
identity_resonance_index =
    0.40 * ucf_score
  + 0.30 * identity_harmonics_score
  + 0.20 * schema_stability
  + 0.10 * (1 - predicted_drift_score)
```

Clamped to [0.0, 1.0].

---

### Step 2 - Persistence Score

Persistence measures how consistent identity resonance has been.

```
persistence_score =
    1.0 - variance(identity_resonance_index over last N snapshots)
```

Clamped to [0.0, 1.0].

Default N = 5 (configurable, max capped at 7).

---

### Step 3 - Volatility Index

```
volatility_index =
    average(|delta identity_resonance_index| over last N-1 transitions)
```

Clamped to [0.0, 1.0].

---

### Step 4 - Stability Band (Rule-Based)

| Band | Condition |
|------|-----------|
| stable | persistence >= 0.75 AND volatility < 0.20 |
| soft | otherwise |
| fragile | persistence < 0.40 OR volatility >= 0.45 |

---

## Memory Rules

- Append new `IdentityResonanceMemoryState` per run
- Never delete prior states
- Never overwrite history
- If history < 2 snapshots:
  - volatility = 0.0
  - persistence = 1.0

---

## Module Structure

```
symbolu/core/predictive/identity_memory/
├── __init__.py          # Public API exports
├── memory_state.py      # IdentityResonanceMemoryState dataclass
├── memory_formula.py    # Formula computation
├── memory_store.py      # Append-only storage orchestration
└── README.md            # This file
```

---

## Required Invariants

| Invariant | Description |
|-----------|-------------|
| **INV-P36-1** | Memory never alters present cognition |
| **INV-P36-2** | Memory is append-only |
| **INV-P36-3** | No authority escalation |
| **INV-P36-4** | Deterministic math only |
| **INV-P36-5** | Acoustic signals forbidden |

---

## Usage

```python
from symbolu.core.predictive.identity_memory import (
    IdentityResonanceMemoryState,
    compute_identity_resonance_memory,
    compute_identity_resonance_index,
    stability_band_from_scores,
)

# Compute memory state from inputs
state = compute_identity_resonance_memory(
    ucf_score=0.75,
    identity_harmonics_score=0.80,
    schema_stability=0.70,
    predicted_drift_score=0.30,
)

# Access outputs
print(state.identity_resonance_index)  # 0.755
print(state.identity_stability_band)   # "stable"
print(state.persistence_score)         # 1.0 (initial state)
print(state.volatility_index)          # 0.0 (initial state)
print(state.memory_depth)              # 1

# With history
prior_states = [state]  # First state
state2 = compute_identity_resonance_memory(
    ucf_score=0.70,
    identity_harmonics_score=0.75,
    schema_stability=0.65,
    predicted_drift_score=0.35,
    prior_states=prior_states,
)

print(state2.memory_depth)             # 2
print(state2.persistence_score)        # Based on variance
print(state2.volatility_index)         # Based on delta
```

---

## Implementation Notes

- This phase **remembers** identity resonance, it does **NOT** react to it
- All computation is deterministic with no LLM calls
- Historical snapshots missing -> graceful fallback (return neutral state)
- Output is read-only and immutable (frozen dataclass)
- No decay heuristics beyond the locked formulas
- No interpretation or inference of what the memory means

---

## Integration with CoherenceState

Phase 36 fields in CoherenceState:

```python
# Phase 36: Identity Resonance Memory (observation only)
identity_resonance_memory_snapshot: Optional[Any] = None
identity_resonance_memory_history: List[Optional[Any]] = field(default_factory=list)
current_ims: Optional[float] = None  # Identity Memory Strength [0.0, 1.0]
current_iep: Optional[float] = None  # Identity Echo Persistence [0.0, 1.0]
current_ida: Optional[float] = None  # Identity Drift Anchoring [0.0, 1.0]
current_irm_memory_band: Optional[str] = None
current_irm_tags: List[str] = field(default_factory=list)
ims_history: List[Optional[float]] = field(default_factory=list)
iep_history: List[Optional[float]] = field(default_factory=list)
ida_history: List[Optional[float]] = field(default_factory=list)
irm_memory_band_history: List[Optional[str]] = field(default_factory=list)
```

---

## Test Requirements

45+ tests across 6 groups:

- **Group A**: Formula Math (weight application, clamp enforcement)
- **Group B**: Memory Accumulation (append-only, depth correctness)
- **Group C**: Volatility & Persistence (stable vs fragile, noise smoothing)
- **Group D**: Read-Only Proof (no downstream phase sees altered inputs)
- **Group E**: Determinism (same history + inputs = same output)
- **Group F**: Import Safety (no observer/governance/renderer imports)
