# P18: Temporal Entropy Differential

## Overview

P18 is a **deterministic, observation-only** governance phase that computes temporal entropy metrics to track pipeline state stability over time. It measures system instability and trends without modifying any upstream state or decisions.

## Purpose

P18 provides:
- **Entropy measurement**: Quantifies current system instability
- **Trend detection**: Identifies whether entropy is increasing, decreasing, or stable
- **Volatility tracking**: Measures how much entropy fluctuates over recent turns

This information is useful for:
- Observability and debugging
- Understanding session stability patterns
- Future gating decisions (observation-only for now)

## Outputs

### P18TemporalEntropyReport

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `entropy_now` | `float` | [0.0, 1.0] | Current entropy level (higher = more instability) |
| `entropy_prev` | `Optional[float]` | [0.0, 1.0] | Previous turn's entropy (None if no history) |
| `delta_entropy` | `Optional[float]` | [-1.0, 1.0] | Change in entropy (None if no history) |
| `trend` | `EntropyTrend` | enum | INCREASING, DECREASING, STABLE, INSUFFICIENT_HISTORY |
| `volatility_band` | `VolatilityBand` | enum | LOW, MED, HIGH, UNKNOWN |
| `window_size_used` | `int` | >= 0 | Number of historical deltas used for volatility |
| `debug` | `dict` | - | Trace information for debugging |

## Entropy Formula

P18 computes entropy using a **fixed weighted blend** of instability sources:

```
entropy_now = W_COHERENCE * (1 - coherence_score) +
              W_QUALITY * (1 - coherence_quality) +
              W_INTEGRITY * (1 - integrity_score) +
              W_TENSION * tension_index +
              W_VOLATILITY * historical_volatility +
              missing_count * EVIDENCE_MISSING_PENALTY
```

### Weights (Fixed Constants)

| Weight | Value | Source |
|--------|-------|--------|
| `W_COHERENCE` | 0.30 | `ctx.coherence_state.coherence_score` (v1/v2/v3) |
| `W_QUALITY` | 0.20 | `ctx.coherence_state.coherence_v3_quality` or `coherence_fused` |
| `W_INTEGRITY` | 0.25 | `ctx.p17.integrity_score` |
| `W_TENSION` | 0.15 | `ctx.coherence_state.tension_index` |
| `W_VOLATILITY` | 0.10 | Historical volatility from delta history |
| `EVIDENCE_MISSING_PENALTY` | 0.05 | Per missing input |

### Input Sources

P18 reads from these upstream signals:

1. **Coherence Score** (priority order):
   - `ctx.coherence_state.coherence_score_v3`
   - `ctx.coherence_state.coherence_score_v2`
   - `ctx.coherence_state.coherence_score`

2. **Coherence Quality**:
   - `ctx.coherence_state.coherence_v3_quality`
   - `ctx.coherence_state.coherence_fused`

3. **Integrity Score**:
   - `ctx.p17.integrity_score`
   - `ctx.coherence_state.semantic_integrity_score`

4. **Tension Index**:
   - `ctx.coherence_state.tension_index`
   - `ctx.tension_corridor`

### Missing Inputs

When inputs are missing:
- Neutral default value (0.5) is used
- `EVIDENCE_MISSING_PENALTY` (0.05) is added per missing input
- Missing inputs are tracked in `debug.missing_inputs`

## Trend Classification

```
if entropy_prev is None:
    trend = INSUFFICIENT_HISTORY
elif delta > TREND_EPSILON (0.05):
    trend = INCREASING
elif delta < -TREND_EPSILON:
    trend = DECREASING
else:
    trend = STABLE
```

## Volatility Classification

Volatility is computed from the last N deltas (N=5 by default):

```
volatility = (std_dev + mean_abs) / 2.0

if volatility <= 0.10:
    band = LOW
elif volatility >= 0.30:
    band = HIGH
else:
    band = MED
```

If insufficient history:
- Single delta: classify based on |delta| alone
- No deltas: `UNKNOWN`

## Usage

### In Pipeline

```python
from symbolu.mechanical.pipeline.p18_temporal_entropy import maybe_run_p18

# Run P18 after P17 and coherence computation
maybe_run_p18(ctx)

# Access results
if ctx.p18 is not None:
    print(f"Entropy: {ctx.p18.entropy_now:.3f}")
    print(f"Delta: {ctx.p18.delta_entropy}")
    print(f"Trend: {ctx.p18.trend.value}")
    print(f"Volatility: {ctx.p18.volatility_band.value}")
```

### Direct Testing

```python
from symbolu.mechanical.pipeline.p18_temporal_entropy import run_p18_directly

# Create mock coherence state
class MockCoherenceState:
    coherence_score = 0.8
    coherence_v3_quality = 0.7
    tension_index = 0.3
    temporal_entropy_diff = 0.2  # Previous entropy
    temporal_entropy_diff_history = [0.01, -0.02, 0.03]

# Create mock P17 report
class MockP17:
    integrity_score = 0.9

# Run directly
report = run_p18_directly(
    coherence_state=MockCoherenceState(),
    p17=MockP17(),
)

print(f"Entropy: {report.entropy_now}")
```

### Helper Functions

```python
from symbolu.mechanical.pipeline.p18_temporal_entropy import (
    get_entropy_now,
    get_entropy_trend,
    get_volatility_band,
    is_entropy_increasing,
    is_entropy_stable,
    is_high_volatility,
)

# Get current entropy (returns 0.5 if no report)
entropy = get_entropy_now(ctx)

# Check trend
if is_entropy_increasing(ctx):
    print("System instability rising")
elif is_entropy_stable(ctx):
    print("System stable")

# Check volatility
if is_high_volatility(ctx):
    print("High entropy fluctuation")
```

## Interpretation

### Entropy Levels

| Range | Interpretation |
|-------|----------------|
| 0.0 - 0.2 | Very stable, high coherence |
| 0.2 - 0.4 | Normal operation |
| 0.4 - 0.6 | Moderate instability |
| 0.6 - 0.8 | High instability, review session |
| 0.8 - 1.0 | Critical instability |

### Trends

| Trend | Meaning |
|-------|---------|
| INCREASING | System becoming less stable |
| DECREASING | System stabilizing |
| STABLE | Entropy holding steady |
| INSUFFICIENT_HISTORY | First turn, no comparison possible |

### Volatility Bands

| Band | Meaning |
|------|---------|
| LOW | Consistent entropy, predictable |
| MED | Normal fluctuation |
| HIGH | Erratic entropy, session may be unstable |
| UNKNOWN | Insufficient data |

## History Tracking

P18 updates `CoherenceState` with:
- `temporal_entropy_snapshot`: Full P18 report
- `temporal_entropy_diff`: Current entropy value
- `temporal_entropy_volatility`: Numeric volatility (0.1/0.5/0.9)
- `temporal_entropy_diff_history`: List of delta values
- `temporal_entropy_volatility_history`: List of volatility values

## Design Principles

1. **Observation-Only**: Never modifies upstream state or decisions
2. **Deterministic**: Same inputs always produce same outputs
3. **Fixed Formula**: Weights are constants, not configurable
4. **Graceful Degradation**: Missing inputs use neutral defaults
5. **No LLM Calls**: Pure computation, no probabilistic behavior

## Authority Model

- P18 runs **after** P17 and coherence computation
- P18 receives **read-only** signals from upstream
- P18 produces advisory report only
- P18 **never** blocks or gates pipeline execution
