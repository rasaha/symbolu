# DHA (Delivery Harmonization Algorithm)

## Overview

DHA is a **tier-safe, deterministic, zero-parameter, formula-only** module that computes delivery modulation parameters from upstream signals using closed-form formulas.

**Pipeline Position:** Fusion → **DHA** → Renderer

## Core Properties

- **Tier-safe:** Different configurations per tier (enterprise_tier_1, enterprise_tier_2, consumer)
- **Deterministic:** Same inputs always produce same outputs
- **Zero-parameter:** No learned/trained parameters
- **Formula-only:** Closed-form mathematical computations
- **Full audit:** Complete metadata trail for all computations

## Formulas

### Final Output Intensity

```
OUTPUT_final = BASE_output × D
```

Where D is the delivery modulation factor.

### Delivery Modulation Factor

```
D = T × I × R
```

Where:
- **T** = tone selection factor (represented as max of tone weights)
- **I** = intensity scalar
- **R** = restraint scalar

### Tone Weights (Deterministic Softmax)

Logit computation:
```
l_sweet = k1 × s - k2 × t
l_jolt  = k3 × r + k4 × C_contr
l_meta  = k5 × H + k6 × r
```

Softmax:
```
w_tone = softmax([l_sweet, l_jolt, l_meta])
```

**Invariant:** `sum(weights) = 1` (within floating tolerance)

### Intensity Scalar

```
I = clip(α₁ × C_s + α₂ × M - α₃ × H, I_min, I_max)
```

Where:
- **C_s** = structural coherence score [0, 1]
- **M** = motion/transformation magnitude [0, 1]
- **H** = normalized entropy [0, 1]

### Restraint Scalar

```
R = clamp(1 - risk_bias - escalation_bias, 0, 1)
```

### Entropy Normalization

**Option A (Default):**
```
H = H_G / ln(3)
```

**Option B:**
```
H = H_D / ln(10)
```

**Option C:**
```
H = H_K / ln(5)
```

## Input Signals

DHA reads only these pre-existing signals from the pipeline:

| Signal | Description | Default if Missing |
|--------|-------------|-------------------|
| C_s | Structural coherence score | 0.5 |
| M | Motion/transformation magnitude | 0.0 |
| H_G | Guna entropy | 0.0 |
| H_D | Dimensional entropy | 0.0 |
| H_K | Kosha entropy | 0.0 |
| C_contr | Contradiction metric | 0.0 |
| s | Sattva component | 0.333 |
| r | Rajas component | 0.333 |
| t | Tamas component | 0.334 |
| tier | Tier identifier | consumer |

## Output

### DHAResult

```python
@dataclass(frozen=True)
class DHAResult:
    tone_weights: ToneWeights  # {sweet, jolt, metaphor}
    I: float                   # Intensity scalar [I_min, I_max]
    R: float                   # Restraint scalar [0, 1]
    D: float                   # Delivery modulation factor
    suppressed: bool           # True if D < 0.1
    audit: dict                # Complete audit trail
```

### Audit Contents

The audit dict includes:
- `entropy_source` - which entropy option used
- `raw_entropy` - raw entropy value before normalization
- `normalized_H` - normalized H value
- `logits` - {l_sweet, l_jolt, l_meta}
- `weights` - {sweet, jolt, metaphor}
- `I`, `R`, `D` - computed scalars
- `tier` - tier identifier
- `enabled` - enabled flag
- `inputs` - all input signals
- `missing_signals` - list of signals that used defaults

## Configuration

### DHAConfig

```python
@dataclass(frozen=True)
class DHAConfig:
    enabled: bool = False                    # Disabled by default
    entropy_source: EntropySource = GUNA    # Default: Option A
    tone_logits: ToneLogitConfig
    intensity: IntensityConfig
    restraint: RestraintConfig
    numerics: NumericsConfig
```

### Tier Configurations

```python
# Enterprise Tier 1 - Minimal modulation
DHAConfig.for_tier("enterprise_tier_1")

# Enterprise Tier 2 - Moderate modulation
DHAConfig.for_tier("enterprise_tier_2")

# Consumer - Full modulation
DHAConfig.for_tier("consumer")
```

## Pipeline Integration

### Enable via Request Metadata

```python
request = UserRequest(
    text="Query text",
    metadata={"dha_formula_enabled": True}
)
```

### Direct Usage

```python
from symbolu.dha import DHAEngine, DHAConfig, DHAInputs

# Create engine
config = DHAConfig(enabled=True)
engine = DHAEngine(config)

# Create inputs
signals = DHAInputs.from_pipeline_signals(
    coherence_score=0.8,
    motion_magnitude=0.3,
    guna_entropy=0.5,
    tier="consumer"
)

# Apply
base_output = "Response text"
output, result = engine.apply(base_output, signals)

print(f"D = {result.D}")
print(f"Tone = {result.dominant_tone}")
```

### Pipeline Stage

```python
from symbolu.dha import DHAStage, DHAConfig

stage = DHAStage(DHAConfig(enabled=True))
ctx = stage.run(ctx)
```

## What DHA Does NOT Do

- **Change semantic meaning** of BASE_output
- **Psychology inference** - no user mental state modeling
- **Moral judgments** - no ethical evaluation
- **Learning** - no feedback loops or state updates
- **Randomness** - fully deterministic

## Testing

Run tests:
```bash
pytest tests/dha/ -v
```

Required test coverage:
1. **Determinism** - same inputs → same outputs
2. **Disable** - enabled=False → no-op
3. **Entropy Options** - A/B/C produce correct normalization
4. **Softmax Validity** - weights sum to 1, no NaNs
5. **Missing Signal Defaults** - defaults used, audit marks missing
6. **Bounds Enforcement** - I in [I_min, I_max], R in [0, 1]
7. **Audit Completeness** - all required fields present

## Version

- **Module Version:** 1.0.0
- **Date:** 2025-12-22
