# Phase 35 — Predictive Persona Drift Model

## Purpose

Phase 35 answers one question only:

> "Given current trajectories, is the user's expressed identity likely to drift in the near future?"

It does **NOT**:
- Predict behavior
- Infer intent
- Trigger interventions
- Modify persona delivery
- Influence regime or discourse
- Change semantics or lexical selection

It produces a **forecast signal**, not a decision.

---

## Authority Boundaries

### ❌ MUST NOT:
- Change regime (P6)
- Change discourse (P7)
- Change semantics or lexical selection (P8–P9)
- Influence DHA, Persona Engine, Renderer
- Influence insight gating (P32)

### ✅ MAY:
- Produce numeric drift forecasts
- Label drift risk bands
- Emit explanatory tags

---

## Inputs (Read-Only)

From PipelineContext:
- `drift_fusion_index` (P19)
- `temporal_entropy_diff` (P18)
- `schema_drift` (P33)
- `identity_harmonics_score` (P34, if present)
- `coherence_v3_quality` (P12)
- `ucf_score` (P26)

Historical (read-only):
- Last N (configurable, default = 3) snapshots of the above metrics

**❌ Acoustic observers (P22–P24) are forbidden as direct inputs.**

---

## Output

`PredictivePersonaDriftReport` (immutable dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `predicted_drift_score` | float ∈ [0.0, 1.0] | Predicted drift magnitude |
| `drift_risk_band` | "low" \| "moderate" \| "high" | Risk classification |
| `trend_direction` | "stable" \| "worsening" \| "improving" | Trend direction |
| `forecast_horizon` | "short" | Always "short" for P35 |
| `contributing_factors` | List[str] | Explanatory tags |
| `confidence` | float ∈ [0.0, 1.0] | Forecast confidence |

This report is **observer-only**.

---

## Core Formula (Locked)

### Step 1 — Base Predictive Drift Score

```
predicted_drift_score =
    0.35 * drift_fusion_index
  + 0.25 * schema_drift
  + 0.20 * temporal_entropy_diff
  + 0.10 * (1 - coherence_v3_quality)
  + 0.10 * (1 - ucf_score)
```

Clamped to [0.0, 1.0].

---

### Step 2 — Trend Direction (Rule-Based)

Using last N snapshots:
- **"worsening"** if ≥2 signals increased > +0.05
- **"improving"** if ≥2 signals decreased > −0.05
- Else **"stable"**

No regression, no extrapolation beyond linear deltas.

---

### Step 3 — Risk Band

| Band | Condition |
|------|-----------|
| low | score < 0.35 |
| moderate | 0.35 ≤ score < 0.65 |
| high | score ≥ 0.65 |

---

### Step 4 — Confidence Score

```
confidence = 1.0 - variance(predicted_drift_score over last N snapshots)
```

Clamped to [0.0, 1.0].

---

## Contributing Factors (Ruled)

Include tags when thresholds exceeded:

| Tag | Condition |
|-----|-----------|
| `SCHEMA_INSTABILITY` | schema_drift ≥ 0.50 |
| `TEMPORAL_ENTROPY_RISING` | temporal_entropy_diff ≥ 0.55 |
| `COHERENCE_DECAY` | coherence_v3_quality < 0.45 |
| `IDENTITY_HARMONICS_WEAKENING` | identity_harmonics_score < 0.45 |
| `CROSS_SIGNAL_VOLATILITY` | signal_variance > 0.10 |

Tags explain **why**, never prescribe **what to do**.

---

## Module Structure

```
symbolu/core/predictive/persona_drift/
├── __init__.py              # Public API exports
├── drift_report.py          # PredictivePersonaDriftReport dataclass
├── drift_formula.py         # Formula computation
├── drift_trend_analyzer.py  # Trend analysis
└── README.md                # This file
```

---

## Required Invariants

| Invariant | Description |
|-----------|-------------|
| **INV-P35-1** | Forecast never influences current decisions |
| **INV-P35-2** | Prediction never escalates authority |
| **INV-P35-3** | Observer-only behavior enforced |
| **INV-P35-4** | Deterministic math only |
| **INV-P35-5** | No acoustic dependency |

---

## Usage

```python
from symbolu.core.predictive.persona_drift import (
    PredictivePersonaDriftReport,
    create_report,
    compute_base_drift_score,
    risk_band_from_score,
    classify_trend_direction,
    compute_contributing_factors,
    compute_confidence,
)

# Compute drift score
score = compute_base_drift_score(
    drift_fusion_index=0.5,
    schema_drift=0.3,
    temporal_entropy_diff=0.4,
    coherence_v3_quality=0.7,
    ucf_score=0.8,
)

# Classify risk band
band = risk_band_from_score(score)

# Create report
report = create_report(
    predicted_drift_score=score,
    drift_risk_band=band,
    trend_direction="stable",
    contributing_factors=["SCHEMA_INSTABILITY"],
    confidence=0.8,
)
```

---

## Implementation Notes

- This phase forecasts identity drift, it does **NOT** react to it
- All computation is deterministic with no LLM calls
- Historical snapshots missing → graceful fallback (return stable/neutral)
- Output is read-only and immutable (frozen dataclass)
