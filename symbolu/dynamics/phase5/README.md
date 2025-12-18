# Phase-5 Dynamic Resolution Layer

## Overview

Phase-5 introduces dynamic behavior to the Varna-Ontological system. It operates on resolved ontology output from Phase-4A to distinguish:

- **True ontology defects** (structural issues in frozen data)
- **Flatness caused by static inspection** (lack of temporal dimension)
- **Intentional modeling boundaries** (design decisions, not bugs)

## Why Phase-5 Exists Before Ontology Revision

Phase-5 was created **before** any ontology revision to serve as a falsification tool. The Varna-Ontological Stress Validation identified several concerns:

1. **Flat gradients** in certain varnas (e.g., `ga` uniformly constructive, `ddha` uniformly degenerative)
2. **No reverse sublimation path** in ontology (upward-only movement)
3. **Potential inference patterns** in polarity assignments

**The critical question:** Are these issues structural (ontology defects) or dynamic (appearing flat only under static inspection)?

Phase-5 answers this by applying time-based dynamics. If a flat ontology pattern produces a non-flat trajectory under dynamics, the "flatness" was dynamic, not structural.

## What Phase-5 Is NOT

Phase-5 is **NOT**:
- An ontology fix
- A polarity reinterpretation layer
- A gradient smoother
- A meaning generator

Phase-5 **CANNOT**:
- Modify ontology files
- Invent semantic content
- Change polarity labels
- Artificially smooth flat patterns

## Critical Invariants

Phase-5 enforces four invariants in code:

| Invariant | Meaning |
|-----------|---------|
| `NO_ONTOLOGY_WRITE` | Never modifies ontology files |
| `NO_ONTOLOGY_INFERENCE` | Never invents meanings |
| `NO_POLARITY_REINTERPRETATION` | Never changes polarity labels |
| `NO_SMOOTHING_FLATNESS` | Never artificially smooths flat gradients |

Violations raise `Phase5InvariantViolation` exceptions.

## Downward Movement ≠ Reverse Sublimation

Phase-5 allows both **upward and downward** layer traversal:

```
O10_ABSOLVING
     ↑↓
O9_UNIFYING
     ↑↓
    ...
     ↑↓
O1_ACTING
```

**Important:** Downward movement in Phase-5 is **dynamic regression under load**, not "reverse sublimation" in the ontology sense.

- **Sublimation** (ontology): A structural vector indicating transcendence direction
- **Regression** (Phase-5): A dynamic phenomenon where high load causes layer descent

The ontology's `sublimate_vector` remains unchanged. Phase-5 adds a dynamic dimension.

## API Reference

### `resolve_dynamics()`

Primary Phase-5 API.

```python
from symbolu.dynamics.phase5 import resolve_dynamics

result = resolve_dynamics(
    varna="ka",                    # Varna token (validated via Phase-4A)
    start_layer="O1_ACTING",       # Starting layer (O1-O10)
    load=0.5,                      # External load (0.0-1.0)
    time_steps=10,                 # Simulation steps
    decay_constant=0.1,            # Momentum decay rate (0.0-1.0)
    amplification_factor=1.2,      # Momentum amplification (0.5-2.0)
    allow_regression=True,         # Enable downward movement
    regression_threshold=0.7,      # Load level for regression
    saturation_threshold=0.9,      # Momentum saturation level
    o8_damping_factor=0.5,         # O8 momentum damping
)
```

### Returns: `TrajectoryResult`

```python
result.varna              # Input varna
result.start_layer        # Starting layer
result.trajectory         # Tuple[DynamicState, ...] — full trajectory
result.final_layer        # Ending layer
result.peak_activation    # Maximum activation reached
result.peak_momentum      # Maximum momentum magnitude
result.total_distortion   # Accumulated distortion load
result.total_sublimation  # Accumulated sublimation load
result.terminated         # True if O10 termination occurred
result.regressed          # True if downward regression occurred
result.layers_visited     # All layers visited during trajectory
result.is_flat()          # Check if trajectory is flat
```

### `DynamicState`

A single state in the trajectory.

```python
state.time_step           # Discrete time step (0-indexed)
state.layer_id            # Current layer (e.g., "O1_ACTING")
state.layer_index         # Numeric index (1-10)
state.activation_level    # Current activation (0.0-1.0)
state.momentum            # Directional force (-1.0 to 1.0)
state.direction           # UP, DOWN, or LATERAL
state.distortion_load     # Accumulated distortion pressure
state.sublimation_load    # Accumulated sublimation pressure
state.termination_flag    # True if terminated at O10
state.regression_flag     # True if regressed due to load
```

## Dynamic Behaviors

### Momentum Accumulation

- Repeated distortion increases **downward** momentum
- Repeated sublimation increases **upward** momentum
- Momentum decays over time based on `decay_constant`
- Momentum amplified based on `amplification_factor`

### Regression Under Load

When `allow_regression=True` and `load >= regression_threshold`:
- Downward traversal becomes possible
- Represents layer descent under stress
- Does NOT alter ontology

### Saturation

At O9/O10, excess momentum triggers saturation:
- Momentum collapses or dampens
- Prevents runaway accumulation
- Models natural limits at transcendence layers

### O8 Handling

O8_META_OBSERVING has special behavior:
- Dampens momentum by `o8_damping_factor`
- May pause traversal
- Does NOT alter polarity
- Models "witnessing without modifying"

### Termination

At O10_ABSOLVING:
- If `sublimate_vector == "terminating"`, trajectory ends
- No implicit rebirth
- Must explicitly restart with new `resolve_dynamics()` call

## Usage Examples

### Basic Trajectory

```python
result = resolve_dynamics(
    varna="ka",
    start_layer="O1_ACTING",
    load=0.3,
    time_steps=15,
    decay_constant=0.1,
    amplification_factor=1.2,
    allow_regression=False,
)

for state in result.trajectory:
    print(f"t={state.time_step}: {state.layer_id} (activation={state.activation_level:.3f})")
```

### Stress Testing Flat Ontology

```python
# 'ga' has flat constructive pattern in ontology
result = resolve_dynamics(
    varna="ga",
    start_layer="O1_ACTING",
    load=0.5,
    time_steps=20,
    decay_constant=0.1,
    amplification_factor=1.3,
    allow_regression=True,
)

if result.is_flat():
    print("Flatness is structural (persists under dynamics)")
else:
    print("Flatness was dynamic (resolved under dynamics)")
```

### Regression Under High Load

```python
result = resolve_dynamics(
    varna="kha",  # Degenerative tendency
    start_layer="O7_PURPOSING",
    load=0.9,
    time_steps=25,
    decay_constant=0.05,
    amplification_factor=1.5,
    allow_regression=True,
    regression_threshold=0.7,
)

if result.regressed:
    print(f"Regressed from O7 to {result.final_layer}")
```

## Test Categories

The test suite (`tests/dynamics/test_phase5_dynamics.py`) covers:

1. **Flat-Gradient Stress Test**: Proves flat ontology can produce non-flat trajectories
2. **Regression Test**: Verifies downward traversal without ontology modification
3. **Ontology Isolation Test**: Asserts no direct JSON access
4. **Determinism Test**: Same input → identical output (bitwise)
5. **Failure Mode Test**: Invalid inputs fail fast, no inference

Run tests:

```bash
pytest tests/dynamics/test_phase5_dynamics.py -v
```

## Architecture

```
symbolu/dynamics/phase5/
├── __init__.py              # Public API exports
├── phase5_dynamics_engine.py # Core engine
├── models.py                # Data models (DynamicState, etc.)
├── errors.py                # Exception types
└── README.md                # This file
```

### Dependency Graph

```
Phase-5 (dynamics)
    │
    └── reads from ──→ Phase-4A (ontology lookup)
                           │
                           └── reads from ──→ Frozen Ontology Files (v1.json)
```

Phase-5 **ONLY** accesses ontology through Phase-4A. No direct file access.

## Re-Classifying Stress Test Findings

After Phase-5, the original stress test findings can be re-classified:

| Finding | Phase-5 Result | Classification |
|---------|----------------|----------------|
| Flat gradient (`ga`) | Trajectory shows variation | **Dynamic** — not structural |
| Flat gradient (`ddha`) | Trajectory remains flat | **Structural** — true flatness |
| No reverse sublimation | Regression possible under load | **Dynamic** — Phase-5 adds downward path |
| O8 uniformly neutral | O8 dampens but doesn't alter | **Intentional** — by design |

Phase-5 does not "fix" issues. It **reveals** their nature.

## Version History

- **v1.0** (2024-12-18): Initial implementation
  - Core dynamics engine
  - Full test suite
  - Invariant enforcement
