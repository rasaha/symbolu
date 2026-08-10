# Coherence v3 Formula Draft

**Phase 10: Formula-Layer Megafusion v1.0**

## Overview

Coherence v3 is the first formula-layer megafusion in Symbol-U v3.0, integrating all prior formula phases into a unified coherence metric. This experimental score combines temporal dynamics, resonance patterns, and modulation biases to provide a holistic measure of conversation coherence.

**Status:** EXPERIMENTAL - Disabled by default across all domains

**Version:** v3.0 Draft 1.0
**Release:** Phase 10
**Date:** 2025-12-10

---

## Design Philosophy

### Core Principles

1. **Non-Invasive Integration**
   - v3 is purely observational and does not affect pipeline behavior unless explicitly enabled
   - All existing coherence v1 and v2 logic remains unchanged
   - v3 calculations run in parallel without modifying routing, mappers, or rendering

2. **Graceful Degradation**
   - Returns `None` if any required metric is missing
   - Never blocks or throws errors if formulas are unavailable
   - Maintains JSON-safety throughout the pipeline

3. **Feature-Flag Gated**
   - Controlled by `use_coherence_v3` flag in domain profiles
   - Defaults to `False` for all domains (trading, therapy, identity, generic)
   - Enables safe experimentation without affecting production behavior

4. **Deterministic & Zero-LLM**
   - Pure mathematical formula with no LLM dependencies
   - Produces identical results for identical inputs
   - Fully testable and reproducible

---

## Formula Composition

### Canonical v3 Formula

```python
coherence_score_v3 = clamp(
    0.35 * base                           # v1 canonical coherence (foundational)
  + 0.15 * resonance_index                # Phase 3: stabilizing signal
  + 0.10 * arc_alignment_index            # Phase 3: temporal pattern alignment
  + 0.10 * (1 - tension_index)            # Phase 3: tension penalty
  + 0.10 * guna_resonance_index           # Phase 8: Guna balance measure
  + 0.10 * kosha_resonance_index          # Phase 8: Kosha coherence measure
  + 0.05 * bias_synergy                   # Phase 9: bias synergy from modulation
  + 0.05 * harmonics_coherence,           # Phase 9: expression harmonics coherence
  0.0, 1.0
)
```

**Weight Distribution:**
- **35%** - Base coherence v1 (foundational layer)
- **35%** - Phase 3 derived metrics (resonance + arc + tension)
- **20%** - Phase 8 Guna/Kosha resonance
- **10%** - Phase 9 modulation biases and harmonics

**Output Range:** `[0.0, 1.0]` (clamped)

---

## Input Dependencies

### Required Inputs (Missing → Returns None)

1. **Phase 1: Temporal Formulas** (indirect via Phase 3)
   - `smi` - Symbolic Mental Index
   - `delta_smi` - SMI momentum
   - `bhava_gap` - Bhava circular distance
   - `tension_corridor` - Tension dynamics signal

2. **Phase 3: Derived Metrics** (direct inputs)
   - `resonance_index` - Overall stabilizing signal [0.0, 1.0]
   - `tension_index` - Session tension measure [0.0, 1.0]
   - `arc_alignment_index` - Temporal pattern alignment [0.0, 1.0]

3. **Phase 8: Resonance Metrics** (direct inputs)
   - `guna_resonance_index` - Guna balance/distortion measure [0.0, 1.0]
   - `kosha_resonance_index` - Kosha coherence measure [0.0, 1.0]

### Optional Inputs (Defaults applied)

4. **Phase 9: Modulation Biases**
   - `guna_resonance_bias` - Guna bias from mapper [-0.10, +0.10] (default: 0.0)
   - `kosha_resonance_bias` - Kosha bias from mapper [-0.10, +0.10] (default: 0.0)
   - `expression_harmonics` - List of kosha activation values (default: None)

5. **Base Coherence**
   - `coherence_score` (v1) - Always available, default: 1.0

---

## Support Functions

### Bias Synergy

Combines guna and kosha resonance biases into a normalized synergy score.

```python
def _bias_synergy(guna_bias: float, kosha_bias: float) -> float:
    """
    Compute bias synergy from guna and kosha resonance biases.

    Args:
        guna_bias: Guna resonance bias [-0.10, +0.10]
        kosha_bias: Kosha resonance bias [-0.10, +0.10]

    Returns:
        Normalized synergy score [0.0, 1.0]
    """
    synergy = (guna_bias + kosha_bias) / 2.0
    synergy = clamp(synergy, -0.10, 0.10)
    return 0.5 + synergy  # Normalize to [0, 1]
```

**Interpretation:**
- `0.5` = neutral (no bias)
- `> 0.5` = positive synergy (biases align constructively)
- `< 0.5` = negative synergy (biases create tension)

### Harmonics Coherence

Measures coherence as the inverse of standard deviation of expression harmonics.

```python
def _harmonics_coherence(expression_harmonics: Optional[List[float]]) -> float:
    """
    Compute coherence from expression harmonics.

    Lower variance = higher coherence

    Args:
        expression_harmonics: List of harmonic values from kosha activation

    Returns:
        Harmonics coherence score [0.0, 1.0]
        Returns 1.0 if harmonics is None or empty (neutral default)
    """
    if expression_harmonics is None or len(expression_harmonics) == 0:
        return 1.0  # Neutral = perfect coherence

    if len(expression_harmonics) == 1:
        return 1.0  # No variance = perfect coherence

    # Compute standard deviation
    mean = sum(expression_harmonics) / len(expression_harmonics)
    variance = sum((x - mean) ** 2 for x in expression_harmonics) / len(expression_harmonics)
    stddev = variance ** 0.5

    # Coherence = 1 - stddev
    return clamp(1.0 - stddev, 0.0, 1.0)
```

**Interpretation:**
- `1.0` = perfect harmonic coherence (no variance)
- `> 0.9` = very coherent (low variance)
- `< 0.6` = incoherent (high variance)

---

## Domain Gating Rules

### Default Behavior (All Domains)

```python
# domain_profiles.py
"trading": {
    "use_coherence_v3": False,  # Disabled by default
    ...
}

"therapy": {
    "use_coherence_v3": False,  # Disabled by default
    ...
}

"identity": {
    "use_coherence_v3": False,  # Disabled by default
    ...
}

"generic": {
    "use_coherence_v3": False,  # Disabled by default
    ...
}
```

### Activation Rules

v3 is used for policy decisions ONLY when:
1. Domain profile has `use_coherence_v3 = True`
2. AND v3 score is successfully computed (not `None`)

### Fallback Cascade

```python
Priority:
  1. v3 (if use_coherence_v3=True AND v3 available)
  2. v2 (if use_coherence_v2=True AND v2 available)
  3. v1 (always fallback)
```

This ensures backward compatibility and graceful degradation.

---

## Missing Data Behavior

### Strict Missing-Data Rule

**If ANY required Phase 3 or Phase 8 metric is missing → return `None`**

Required metrics:
- `resonance_index`
- `tension_index`
- `arc_alignment_index`
- `guna_resonance_index`
- `kosha_resonance_index`

Optional metrics (defaults applied):
- `guna_resonance_bias` → 0.0
- `kosha_resonance_bias` → 0.0
- `expression_harmonics` → `None` (harmonics_coherence returns 1.0)

### Example

```python
# Scenario: Missing guna_resonance_index
state = CoherenceState(...)
state.resonance_index = 0.70
state.tension_index = 0.40
state.arc_alignment_index = 0.65
state.guna_resonance_index = None  # MISSING
state.kosha_resonance_index = 0.72

v3 = engine._compute_coherence_score_v3(state, mapper_profile)
assert v3 is None  # Missing data → None
```

---

## Safety and Invariance Rules

### Hard Invariants

1. **v1 remains primary**
   - `coherence_score` (v1) is always used unless explicitly overridden
   - v1 score is never modified or replaced automatically

2. **v2 remains secondary**
   - `coherence_score_v2` is used only when `use_coherence_v2=True`
   - v2 behavior is unchanged by v3 introduction

3. **v3 is experimental only**
   - `coherence_score_v3` is observation-only by default
   - Never used in routing, mapping, rendering, or policy unless flag is enabled

4. **No pipeline modification**
   - TTOR routing logic unchanged
   - MLCR mapper activation unchanged
   - Fusion candidate selection unchanged
   - DHA delivery harmonization unchanged
   - Renderer output unchanged

5. **JSON-safe everywhere**
   - v3 is `Optional[float]` and serializes to `null` when `None`
   - No breaking changes to API contracts

### Behavioral Guarantees

1. **Backward compatibility**
   - Existing v1/v2 behavior is preserved exactly
   - Old code expecting only v1/v2 continues to work

2. **Determinism**
   - Same inputs always produce same v3 score
   - No randomness or non-deterministic behavior

3. **Graceful degradation**
   - Missing data returns `None`, not errors
   - Partial data doesn't corrupt v1/v2 scores

4. **CI-safe**
   - All existing tests pass without modification
   - v3 tests run in parallel without interference

---

## Migration Plan

### Phase 10 → Phase 11 (Domain Experimentation)

**Phase 11 Goals:**
- Enable v3 for therapy domain (`use_coherence_v3=True`)
- Enable v3 for identity domain (`use_coherence_v3=True`)
- Keep trading and generic on v1 (ultra-conservative)

**Phase 11 Actions:**
1. Update `domain_profiles.py`:
   ```python
   "therapy": {
       "use_coherence_v3": True,  # Enable for Phase 11
       ...
   }

   "identity": {
       "use_coherence_v3": True,  # Enable for Phase 11
       ...
   }
   ```

2. Monitor v3 behavior in therapy/identity sessions
3. Compare v3 vs v2 vs v1 across multiple sessions
4. Collect metrics on v3 performance and drift patterns

### Phase 11 → Phase 12 (Formula Refinement)

**Phase 12 Goals:**
- Refine v3 formula weights based on Phase 11 data
- Potentially introduce v3.1 with updated coefficients
- Decide on broader domain rollout

**Phase 12 Actions:**
1. Analyze therapy/identity session data
2. Identify formula weight adjustments
3. Implement v3.1 with new weights (if needed)
4. Expand to generic domain if stable

### Phase 12+ (Production Consideration)

**Long-term Goals:**
- Determine if v3 should replace v2 as secondary score
- Consider deprecating v1/v2 if v3 proves superior
- Potentially make v3 the new canonical coherence

**Prerequisites:**
- Multi-month production data collection
- Statistical validation of v3 superiority
- Domain-specific tuning and validation

---

## Implementation Details

### File Modifications

**Core:**
- `symbolu/core/coherence/coherence_state.py`
  - Added `coherence_score_v3: Optional[float]` field

- `symbolu/core/coherence/coherence_engine.py`
  - Added `_compute_coherence_score_v3()` method
  - Added `_bias_synergy()` support function
  - Added `_harmonics_coherence()` support function

**Policy:**
- `symbolu/policy/domain_profiles.py`
  - Added `use_coherence_v3: False` flag to all domains

- `symbolu/policy/policy_engine.py`
  - Updated `_get_active_coherence_score()` to support v3 cascade

**Pipeline:**
- `symbolu/mechanical/pipeline/coherence_observer.py`
  - Added `coherence_score_v3` to `CoherenceObservation` dataclass
  - Updated `observe()` to extract v3 from state

**API:**
- `symbolu/api/unified_api.py`
  - v3 automatically included via `CoherenceObserver` serialization

**Tests:**
- `symbolu/mechanical/pipeline/integration_tests/test_phase10_coherence_v3_formula_fusion.py`
  - 26 comprehensive tests (formula math, observer, policy, invariance)

**CI:**
- `.github/workflows/pipeline-ci.yml`
  - Added Phase 10 test step
  - Updated artifact upload

### Test Coverage

**Group A: Formula Math (8 tests)**
- v3 > v2 when resonance strong
- v3 < v2 when tension high
- v3 clamps correctly to [0.0, 1.0]
- Missing data returns None
- Bias synergy computation
- Harmonics coherence computation
- Full fusion determinism
- Base-only scenario

**Group B: Observer + Unified API (7 tests)**
- v3 included in observer
- v3 included in unified output
- v3 is None when missing
- JSON serialization safety
- Multi-turn consistency
- Snapshot invariance
- Backward compatibility

**Group C: Policy Integration (6 tests)**
- v3 ignored for all domains by default
- Enabling flag uses v3
- v3 fallback to v2/v1 cascade
- Policy determinism with v3
- Invariance for trading/generic
- Invariance for mapper rules

**Group D: Behavioral Invariance (5 tests)**
- TTOR unchanged
- MLCR unchanged
- Mapper activation unchanged
- Renderer output unaffected
- Policy flags unchanged unless enabled

**Total:** 26 tests ensuring complete safety and correctness

---

## Example Usage

### Computing v3 (Internal)

```python
from symbolu.core.coherence.coherence_engine import CoherenceEngine
from symbolu.core.coherence.coherence_state import CoherenceState

engine = CoherenceEngine()

# Create state with all required metrics
state = CoherenceState(convo_id="user123", turn_index=5, coherence_score=0.70)

# Set Phase 3 metrics
state.resonance_index = 0.75
state.tension_index = 0.35
state.arc_alignment_index = 0.68

# Set Phase 8 metrics
state.guna_resonance_index = 0.72
state.kosha_resonance_index = 0.78

# Set Phase 9 biases (from mapper profile)
mapper_profile = {
    "guna_resonance_bias": 0.05,
    "kosha_resonance_bias": 0.04,
    "expression_harmonics": [0.70, 0.72, 0.71, 0.73],
}

# Compute v3
v3 = engine._compute_coherence_score_v3(state, mapper_profile)
print(f"Coherence v3: {v3:.3f}")  # Example: 0.745
```

### Enabling v3 for a Domain (Future)

```python
# domain_profiles.py
"therapy": {
    "use_coherence_v3": True,  # Enable v3 for therapy domain
    ...
}
```

### Policy Integration

```python
from symbolu.policy.policy_engine import compute_policy_flags

unified_output = {
    "coherence": {
        "coherence_score": 0.60,     # v1
        "coherence_score_v2": 0.70,  # v2
        "coherence_score_v3": 0.78,  # v3
        ...
    },
    ...
}

# With v3 disabled (default)
flags = compute_policy_flags(unified_output, "therapy")
# Uses v2 (therapy has use_coherence_v2=True)

# If v3 were enabled for therapy:
# flags would use v3 (0.78) instead of v2 (0.70)
```

---

## Observability

### Unified API Output

```json
{
  "coherence": {
    "coherence_score": 0.68,
    "coherence_score_v2": 0.72,
    "coherence_score_v3": 0.76,
    "persona_drift_score": 0.28,
    "semantic_stability_score": 0.82,
    "temporal_arc_score": 0.74,
    "mapper_volatility_score": 0.20,
    "resonance_index": 0.75,
    "tension_index": 0.35,
    "arc_alignment_index": 0.68,
    "guna_resonance_index": 0.72,
    "kosha_resonance_index": 0.78
  }
}
```

### Observer Snapshot

```python
observer = CoherenceObserver()
snapshot = observer.snapshot()

# snapshot contains v3 if available
{
  "coherence": 0.68,  # Still v1 (primary)
  "formulas": {
    ...
    "guna_resonance_index": 0.72,
    "kosha_resonance_index": 0.78
  }
}
```

---

## Known Limitations

1. **Requires Complete Metric Stack**
   - v3 needs all of Phase 1, 3, 8, and 9 to be active
   - Cannot compute v3 on first turn (no delta_smi yet)
   - Gracefully returns `None` when data unavailable

2. **Experimental Weight Distribution**
   - Current weights (35% base, 35% Phase 3, 20% Phase 8, 10% Phase 9) are draft
   - May need tuning based on real-world data
   - Phase 11/12 will refine weights

3. **No Historical Smoothing**
   - v3 is computed per-turn, no temporal smoothing
   - Future versions may add moving averages or trend analysis

4. **Limited Domain Testing**
   - Phase 10 has v3 disabled for all domains
   - Real-world validation begins in Phase 11 (therapy/identity)

---

## References

- **Phase 1:** Temporal Formulas (SMI, ΔSMI, Bhava Gap, Tension Corridor)
- **Phase 3:** Derived Formula Metrics (Resonance, Tension, Arc Alignment)
- **Phase 4:** Coherence v2 Integration (formula-aware coherence)
- **Phase 8:** Guna/Kosha Resonance Engine
- **Phase 9:** Guna/Kosha Mapper Modulation (biases and harmonics)
- **Phase 10:** Coherence v3 Formula Fusion (this document)

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| v3.0 Draft 1.0 | 2025-12-10 | Initial Phase 10 implementation |

---

**End of Coherence v3 Formula Draft**
