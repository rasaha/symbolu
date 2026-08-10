# Phase 33: Schema Adaptive Routing (Observation-Only)

## Purpose

Phase 33 computes schema-level stability and alignment metrics **ONLY**.

It answers: **"Which internal cognitive schema is currently most stable and aligned — without influencing behavior?"**

This phase is **observation-only** and **read-only**.

## Outputs

### SchemaAdaptiveRoutingSnapshot

An immutable dataclass containing:

| Field | Type | Description |
|-------|------|-------------|
| `schema_alignment_scores` | `Dict[str, float]` | Per-schema alignment scores [0.0, 1.0] |
| `schema_stability_scores` | `Dict[str, float]` | Per-schema stability scores [0.0, 1.0] |
| `schema_drift_scores` | `Dict[str, float]` | Per-schema drift scores [0.0, 1.0] |
| `dominant_schema` | `Optional[str]` | Most stable/aligned schema, or None |
| `confidence` | `float` | Overall confidence in assessment [0.0, 1.0] |
| `stability_band` | `SchemaStabilityBand` | HIGH / MODERATE / LOW / UNKNOWN |
| `confidence_band` | `SchemaConfidenceBand` | HIGH / MODERATE / LOW / INSUFFICIENT |
| `diagnostic_tags` | `FrozenSet[str]` | Diagnostic tags (allow-listed only) |
| `observer_only` | `bool` | Always `True` - marks as non-authoritative |

**Critical Rule**: These values are **diagnostic only**. They are **never used for routing**.

## Inputs (Read-Only)

P33 may read from PipelineContext:

| Source | Field | Used For |
|--------|-------|----------|
| `ctx.coherence_state` | `coherence_score_v3` | Stability & alignment computation |
| `ctx.coherence_state` | `coherence_v3_quality` | Quality weighting |
| `ctx.coherence_state` | `drift_fusion_index` | Drift & stability computation |
| `ctx.coherence_state` | `temporal_entropy_volatility` | Entropy penalty |
| `ctx.coherence_state` | `current_identity_harmonics_index` | Alignment computation |
| `ctx.persona_schema_metadata` | (static definitions) | Schema IDs |

### Forbidden Inputs

**Observer acoustic data is NOT ALLOWED as input.**

## Formulas

### Stability Score

```
stability = W_COHERENCE_V3 * coherence_v3 +
            W_COHERENCE_QUALITY * coherence_v3_quality +
            W_DRIFT_INVERSE * (1 - drift_fusion_index) +
            W_ENTROPY_INVERSE * (1 - temporal_entropy_volatility)
```

Weights:
- `W_COHERENCE_V3 = 0.35`
- `W_COHERENCE_QUALITY = 0.25`
- `W_DRIFT_INVERSE = 0.25`
- `W_ENTROPY_INVERSE = 0.15`

### Alignment Score

```
alignment = W_ALIGN_COHERENCE * coherence_v3 +
            W_ALIGN_QUALITY * coherence_v3_quality +
            W_ALIGN_IDENTITY * identity_harmonics_index
```

Weights:
- `W_ALIGN_COHERENCE = 0.40`
- `W_ALIGN_QUALITY = 0.35`
- `W_ALIGN_IDENTITY = 0.25`

### Drift Score

```
drift = W_DRIFT_FUSION * drift_fusion_index +
        W_DRIFT_ENTROPY * temporal_entropy_volatility
```

Weights:
- `W_DRIFT_FUSION = 0.70`
- `W_DRIFT_ENTROPY = 0.30`

### Confidence

```
confidence = W_CONF_DATA_PRESENCE * data_presence_score +
             W_CONF_STABILITY * avg_stability +
             W_CONF_HISTORY * history_score
```

Weights:
- `W_CONF_DATA_PRESENCE = 0.50`
- `W_CONF_STABILITY = 0.30`
- `W_CONF_HISTORY = 0.20`

All outputs are clamped to [0.0, 1.0].

## Hard Constraints (Non-Negotiable)

### Authority & Safety

| Constraint | Description |
|------------|-------------|
| ❌ MUST NOT affect | Regime (P6), Discourse (P7), Semantics (P8), Lexical (P9), Delivery (P21) |
| ❌ MUST NOT | Gate, block, or route anything |
| ❌ MUST NOT | Influence Phase 10/12 results |

### Imports

| Constraint | Description |
|------------|-------------|
| ❌ MUST NOT import | P6, P7, P8, P9 |
| ❌ MUST NOT import | Policy, Planner, Renderer |
| ❌ MUST NOT import | Observer modules (P22–P24) |
| ✅ MAY import | Core formulas, CoherenceState, Drift/entropy metrics, Schema metadata definitions |

### Determinism

- Same inputs → same outputs (bitwise)
- No randomness
- No LLM calls

## Invariants

| ID | Invariant |
|----|-----------|
| INV-P33-1 | Phase 33 cannot influence any decision |
| INV-P33-2 | Schema scores are observational only |
| INV-P33-3 | Dominant schema selection has zero side effects |
| INV-P33-4 | Observer data (P22-P24) cannot enter Phase 33 |
| INV-P33-5 | Absence of schema metadata does not break pipeline |

## Usage

```python
from symbolu.mechanical.pipeline.p33_schema_adaptive import maybe_run_p33

# In pipeline after coherence computation:
maybe_run_p33(ctx)

# Access snapshot (observation only):
if ctx.p33 is not None:
    print(f"Dominant schema: {ctx.p33.dominant_schema}")
    print(f"Confidence: {ctx.p33.confidence}")
    print(f"Stability: {ctx.p33.stability_band.value}")
```

## File Structure

```
p33_schema_adaptive/
├── __init__.py           # Public exports
├── p33_schema_snapshot.py # Frozen dataclasses (SchemaAdaptiveRoutingSnapshot)
├── p33_schema_resolver.py # Deterministic logic (P33SchemaAdaptiveResolver)
├── p33_integration.py    # maybe_run_p33(ctx) entry point
└── README.md             # This file - spec & invariants
```

## Test Requirements

Tests are organized into 5 groups (40+ tests total):

### Group A — Formula Correctness
- Known inputs → expected numeric outputs
- Boundary conditions (0.0 / 1.0)

### Group B — Non-Authority Proof
- Modifying P33 output MUST NOT change:
  - Regime
  - Discourse
  - Semantics
  - Lexical selection

### Group C — Determinism
- Same context → identical snapshot hash

### Group D — Import Safety
- Static test proving no forbidden imports

### Group E — Regression Lock
- Existing pipelines produce identical outputs when P33 is enabled

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-14 | Initial implementation |
