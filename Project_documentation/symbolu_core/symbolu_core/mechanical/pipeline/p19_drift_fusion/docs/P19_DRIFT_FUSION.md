# Phase 19: Drift Fusion

## Overview

Phase 19 (P19) is a **deterministic, read-only diagnostic synthesis phase** that fuses symbolic, semantic, and temporal drift signals into a unified drift profile.

### Critical Constraints

P19 is **observation-only**. It:

- ✅ Computes drift metrics deterministically
- ✅ Provides diagnostic signals for analytics/dashboards
- ✅ Stores history for trend analysis

P19 must **NOT**:

- ❌ Infer intent
- ❌ Infer emotion
- ❌ Select regime
- ❌ Gate actions
- ❌ Trigger any side effects
- ❌ Modify routing, TTOR, MLCR, Fusion, DHA, or Renderer

## Input Signals

P19 fuses signals from upstream phases:

| Signal | Source | Range | Description |
|--------|--------|-------|-------------|
| `semantic_integrity_score` | P17 | [0.0, 1.0] | Semantic coherence/self-consistency |
| `cognitive_drift_v3` | P17 | [0.0, 1.0] | Semantic center-of-gravity drift |
| `temporal_entropy_diff` | P18 | [0.0, 1.0] | Normalized entropy differential (0.5 = neutral) |
| `temporal_entropy_volatility` | P18 | [0.0, 1.0] | Entropy volatility measure |
| `coherence_fused` | P16 | [0.0, 1.0] | Fused coherence score |

## Output Metrics

### Drift Fusion Index

**Formula:**

```
drift_fusion_index =
    0.35 × cognitive_drift_v3 +
    0.25 × (1 - semantic_integrity_score) +
    0.20 × temporal_entropy_volatility +
    0.15 × |temporal_entropy_diff - 0.5| +
    0.05 × (1 - coherence_fused)
```

**Interpretation:**

| Index Range | Meaning |
|-------------|---------|
| 0.00 - 0.30 | Low drift - stable conversation |
| 0.30 - 0.65 | Moderate drift - some instability |
| 0.65 - 1.00 | High drift - significant instability |

### Drift Risk Band

| Band | Threshold | Description |
|------|-----------|-------------|
| `low` | index < 0.30 | Minimal drift detected |
| `moderate` | 0.30 ≤ index < 0.65 | Moderate drift present |
| `high` | index ≥ 0.65 | High drift detected |

### Drift Pattern Tags

Rule-based tags assigned when individual signals cross thresholds:

| Tag | Condition | Meaning |
|-----|-----------|---------|
| `semantic_drift` | `semantic_integrity_score < 0.55` | Low semantic integrity detected |
| `cognitive_drift` | `cognitive_drift_v3 > 0.55` | High cognitive drift detected |
| `temporal_instability` | `temporal_entropy_volatility > 0.55` | High entropy volatility |
| `entropy_shift` | `\|temporal_entropy_diff - 0.5\| > 0.25` | Significant entropy deviation |
| `low_coherence_context` | `coherence_fused < 0.45` | Low coherence context |

## Usage

### Pipeline Integration

```python
from symbolu.mechanical.pipeline.p19_drift_fusion import maybe_run_p19

# Run after P17 and P18
maybe_run_p19(ctx)

# Access results
if ctx.p19 is not None:
    print(f"Drift index: {ctx.p19.drift_fusion_index}")
    print(f"Risk band: {ctx.p19.drift_risk_band}")
    print(f"Tags: {ctx.p19.drift_pattern_tags}")
```

### Direct Testing

```python
from symbolu.mechanical.pipeline.p19_drift_fusion import run_p19_directly

report = run_p19_directly(
    semantic_integrity_score=0.6,
    cognitive_drift_v3=0.4,
    temporal_entropy_diff=0.55,
    temporal_entropy_volatility=0.3,
    coherence_fused=0.7,
)

print(f"Index: {report.drift_fusion_index}")
print(f"Band: {report.drift_risk_band}")
print(f"Tags: {report.drift_pattern_tags}")
```

### Convenience Functions

```python
from symbolu.mechanical.pipeline.p19_drift_fusion import (
    has_p19_report,
    get_drift_fusion_index,
    get_drift_risk_band,
    get_drift_pattern_tags,
    is_low_risk,
    is_moderate_risk,
    is_high_risk,
    has_semantic_drift,
    has_cognitive_drift,
    has_temporal_instability,
)

# Check if report exists
if has_p19_report(ctx):
    # Get individual values
    index = get_drift_fusion_index(ctx)
    band = get_drift_risk_band(ctx)
    tags = get_drift_pattern_tags(ctx)

    # Risk level checks
    if is_high_risk(ctx):
        print("High drift detected")

    # Pattern checks
    if has_semantic_drift(ctx):
        print("Semantic drift pattern present")
```

## API Reference

### P19DriftFusionReport

```python
@dataclass(frozen=True)
class P19DriftFusionReport:
    """Immutable report of drift fusion computation."""

    # Core outputs
    drift_fusion_index: float          # [0.0, 1.0]
    drift_risk_band: str               # "low" | "moderate" | "high"
    drift_pattern_tags: tuple          # Tuple of tag strings

    # Input signals (for observability)
    semantic_integrity_score: Optional[float]
    cognitive_drift_v3: Optional[float]
    temporal_entropy_diff: Optional[float]
    temporal_entropy_volatility: Optional[float]
    coherence_fused: Optional[float]

    # Debug info
    debug: Dict[str, Any]

    # Convenience methods
    def is_low_risk(self) -> bool
    def is_moderate_risk(self) -> bool
    def is_high_risk(self) -> bool
    def has_semantic_drift(self) -> bool
    def has_cognitive_drift(self) -> bool
    def has_temporal_instability(self) -> bool
    def has_entropy_shift(self) -> bool
    def has_low_coherence_context(self) -> bool
    def tag_count(self) -> int
    def to_dict(self) -> Dict[str, Any]
```

### Constants

```python
# Formula weights (sum to 1.0)
W_COGNITIVE_DRIFT = 0.35
W_INTEGRITY = 0.25
W_VOLATILITY = 0.20
W_ENTROPY_SHIFT = 0.15
W_COHERENCE = 0.05

# Risk band thresholds
RISK_BAND_LOW_THRESHOLD = 0.30
RISK_BAND_HIGH_THRESHOLD = 0.65

# Pattern tag thresholds
TAG_SEMANTIC_DRIFT_THRESHOLD = 0.55
TAG_COGNITIVE_DRIFT_THRESHOLD = 0.55
TAG_TEMPORAL_INSTABILITY_THRESHOLD = 0.55
TAG_ENTROPY_SHIFT_THRESHOLD = 0.25
TAG_LOW_COHERENCE_THRESHOLD = 0.45
```

## CoherenceState Integration

P19 metrics are stored in `CoherenceState` for history tracking:

```python
# Current values
coherence_state.drift_fusion_index: Optional[float]
coherence_state.drift_risk_band: Optional[str]
coherence_state.drift_pattern_tags: List[str]

# Histories
coherence_state.drift_fusion_index_history: List[Optional[float]]
coherence_state.drift_risk_band_history: List[str]
coherence_state.drift_pattern_tags_history: List[List[str]]
```

## Observer/API Integration

P19 metrics are exposed through `CoherenceObserver.snapshot()`:

```json
{
    "drift_fusion": {
        "index": 0.45,
        "drift_fusion_index": 0.45,
        "risk_band": "moderate",
        "pattern_tags": ["semantic_drift", "entropy_shift"]
    }
}
```

## DILchat Hints

P19 generates hints based on drift risk level:

| Hint Code | Condition | Message |
|-----------|-----------|---------|
| `DRIFT_LOW_RISK` | index < 0.30 or band == "low" | "Semantic-temporal drift is low and stable." |
| `DRIFT_MODERATE_RISK` | 0.30 ≤ index < 0.65 or band == "moderate" | "Moderate semantic-temporal drift present." |
| `DRIFT_HIGH_RISK` | index ≥ 0.65 or band == "high" | "High semantic-temporal drift detected. Consider grounding strategies." |

## Design Principles

1. **Deterministic**: Same inputs always produce same outputs
2. **Non-Invasive**: Zero impact on routing, scoring, or behavior
3. **Observation-Only**: Never used for gating or blocking
4. **Backward-Compatible**: All existing tests remain passing
5. **Pure Math**: Weighted formulas + rule-based tagging only
6. **Immutable Outputs**: Frozen dataclasses for snapshots
7. **History Tracking**: CoherenceState maintains per-turn histories
8. **Graceful Degradation**: Works with partial/missing inputs

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024 | Initial release with mechanical pipeline structure |
