# Phase 26: Unified Consciousness Formula (UCF)

## Purpose

Phase 26 computes a **single scalar**: **UCF** (Unified Consciousness Formula).

UCF answers one question only:

> "How internally coherent and stable is the system's cognitive state right now?"

## Characteristics

UCF is:
- **Numeric**: Float in [0.0, 1.0]
- **Deterministic**: Same inputs → identical UCF (bitwise)
- **Authoritative as a metric**: UCF is the canonical stability scalar
- **NOT authoritative as a decision**: UCF never makes decisions

UCF is later consumed by downstream phases (P32, P35+), but **never performs gating itself**.

## Formula (Canonical v1.0)

```
UCF = clamp(
    0.30 * coherence_v3_quality +
    0.25 * (1 - drift_fusion_index) +
    0.20 * (1 - entropy_volatility) +
    0.15 * schema_stability +
    0.10 * identity_harmonics_stability
)
```

### Weights

| Factor | Weight | Source | Description |
|--------|--------|--------|-------------|
| coherence_v3_quality | 0.30 | P10/P12 | Primary coherence quality signal |
| drift_fusion_stability | 0.25 | P19 | Inverted drift fusion index (1 - drift) |
| entropy_stability | 0.20 | P18 | Inverted entropy volatility (1 - volatility) |
| schema_stability | 0.15 | P33 | Schema stability from adaptive routing |
| identity_harmonics | 0.10 | Optional | Identity harmonics stability |

**Total: 1.00**

### Rules

- Missing optional inputs → neutral contribution (0.5, no penalty)
- All intermediate values clamped to [0.0, 1.0]
- Final UCF clamped to [0.0, 1.0]

## Stability Bands (Deterministic)

```
ucf >= 0.75 → "stable"
0.45 ≤ ucf < 0.75 → "transitional"
ucf < 0.45 → "unstable"
```

**No exceptions. No heuristics.**

## Output Structure

```python
@dataclass(frozen=True)
class UnifiedConsciousnessState:
    ucf_score: float  # [0.0, 1.0]
    stability_band: StabilityBand  # stable | transitional | unstable
    contributing_factors: Dict[str, float]  # breakdown
    confidence: float  # [0.0, 1.0] based on input availability
```

## Invariants

### INV-P26-1: UCF is read-only truth, not a decision

UCF computes a metric. It never decides regime, discourse, semantics, lexical choice, or delivery mode.

### INV-P26-2: Observer data cannot affect UCF

UCF MUST NOT import or use data from observer-only phases (P22, P23, P24).

### INV-P26-3: UCF monotonic with respect to instability

Higher instability inputs → lower UCF score. The formula is monotonically decreasing with respect to drift, volatility, and other instability signals.

### INV-P26-4: UCF never opens gates directly

UCF is consumed by downstream phases for observation. It never triggers actions, opens gates, or modifies pipeline behavior.

### INV-P26-5: Absence of optional inputs never destabilizes output

Missing inputs use neutral defaults (0.5). The formula produces valid output even with zero inputs available.

## Hard Constraints (Non-Negotiable)

### Authority Rules

#### MUST NOT:
- Decide regime
- Gate insight
- Select discourse
- Influence lexical choice
- Trigger actions

#### MUST NOT import:
- P6-P9 (regime, discourse, semantics, lexical)
- P21 delivery logic
- Renderer, DHA, Persona
- Observer-only phases (P22-P24)

#### MAY import (read-only):
- CoherenceState (P10/P12 outputs)
- Temporal metrics (P18, P19)
- Identity harmonics (if present)
- Schema stability metrics (P33)

### Determinism

- Same inputs → identical UCF (bitwise)
- No randomness
- No LLM calls
- No time-based behavior

## File Structure

```
symbolu/core/consciousness/
├── __init__.py          # Module exports
├── ucf_schema.py        # Dataclasses + enums
├── ucf_formula.py       # Pure computation
├── ucf_resolver.py      # Orchestration
└── README.md            # This file

symbolu/mechanical/pipeline/p26_ucf/
├── __init__.py          # Pipeline exports
└── p26_integration.py   # Pipeline integration
```

## Usage

### In Pipeline

```python
from symbolu.mechanical.pipeline.p26_ucf import maybe_run_p26

# Run P26 after P18/P19/P33
maybe_run_p26(ctx)

# Access UCF state
if ctx.p26 is not None:
    print(f"UCF Score: {ctx.p26.ucf_score}")
    print(f"Stability: {ctx.p26.stability_band.value}")
    print(f"Confidence: {ctx.p26.confidence}")
```

### Direct Computation (Testing)

```python
from symbolu.mechanical.pipeline.p26_ucf import run_p26_directly

state = run_p26_directly(
    coherence_v3_quality=0.8,
    drift_fusion_index=0.2,
    entropy_volatility=0.3,
    schema_stability=0.7,
    identity_harmonics_stability=0.6,
)

print(f"UCF: {state.ucf_score}")  # ~0.72
print(f"Band: {state.stability_band.value}")  # "transitional"
```

## Test Requirements

50+ tests required, grouped as:

### Group A: Formula Math
- Exact numeric verification
- Weight sensitivity tests
- Determinism verification

### Group B: Boundary Conditions
- 0.0 / 1.0 clamps
- Missing optional inputs
- All inputs missing

### Group C: Determinism
- Same ctx → same hash
- Multiple iterations identical

### Group D: Authority Proof
- Modifying UCF MUST NOT alter regime
- Modifying UCF MUST NOT alter discourse
- Modifying UCF MUST NOT alter semantics
- Modifying UCF MUST NOT alter lexical output

### Group E: Import Safety
- Static import graph test
- Forbidden imports cause failure

### Group F: Regression Lock
- Existing pipelines unchanged when P26 is enabled

## Rationale

UCF provides a single, authoritative metric for cognitive stability that:

1. **Unifies** multiple stability signals into one scalar
2. **Simplifies** downstream consumption (single number vs multiple metrics)
3. **Preserves** observation-only semantics (no behavioral impact)
4. **Enables** future reasoning-layer integration (P32, P35+)

The weighted formula balances:
- Coherence quality (30%): Primary signal of system coherence
- Drift stability (25%): Resistance to semantic/temporal drift
- Entropy stability (20%): Temporal consistency
- Schema stability (15%): Schema-level coherence
- Identity harmonics (10%): Optional identity signal

This weighting reflects the relative importance of each signal in determining overall cognitive stability, with coherence quality as the dominant factor.

## Version History

- **v1.0.0**: Initial implementation with canonical formula
