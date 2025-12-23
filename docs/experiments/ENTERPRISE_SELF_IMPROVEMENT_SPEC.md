# Enterprise Self-Improvement Module Specification

**Version:** 2.7.4
**Date:** 2025-12-23
**Status:** EXPERIMENTAL
**Location:** `symbolu/guna_modulation/recursive_self_improvement.py`

## Overview

The Enterprise Self-Improvement Module enables SymbolU v2.7 to observe its own performance, identify patterns of low utility, and autonomously adjust its operational parameters to improve future outcomes. This is an experimental AGI-adjacent capability that operates within strict safety bounds.

**Key Principle:** This is NOT ethics or value learning. It is policy-aligned operational self-optimization using existing signals.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  EnterpriseSelfImprover                         │
│  (Orchestrator)                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │  SelfEvaluator  │───▶│   MetaReasoner  │───▶│  Improvement│ │
│  │                 │    │                 │    │   Engine    │ │
│  └────────┬────────┘    └────────┬────────┘    └─────────────┘ │
│           │                      │                              │
│           ▼                      ▼                              │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │               EnterpriseKnowledgeBase                       ││
│  │  (Beliefs, Coefficient Adjustments, Learning State)         ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
└───────────────────────────────────────────────────────────────┬─┘
                                                                │
                        ┌───────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Existing Guna Modulation Layer                  │
├─────────────────────────────────────────────────────────────────┤
│  Observables (s, r, t, H, M, C_contr, F_fail)                  │
│  UtilityCoefficients (c_S, c_R, c_T, λ_H, λ_C, λ_F)           │
│  StateRegister (τ^768, τ^175, w_tone, w_guna, b_policy)       │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Belief System

**Class:** `Belief`

Represents a belief about system behavior or optimal configuration using Bayesian confidence.

```python
@dataclass
class Belief:
    id: str
    content: str
    belief_type: BeliefType  # PRIOR, LEARNED, HYPOTHESIS, VERIFIED, DEPRECATED
    confidence: float        # P(belief is true) in [0, 1]

    # Evidence tracking (Bayesian updating)
    evidence_count: int = 0
    supporting_evidence: int = 0
    contradicting_evidence: int = 0
```

**Belief Types:**

| Type | Description |
|------|-------------|
| `PRIOR` | Initial assumptions from system design |
| `LEARNED` | Learned from observation |
| `HYPOTHESIS` | Proposed but unverified |
| `VERIFIED` | Tested and confirmed (confidence > 0.8, evidence >= 20) |
| `DEPRECATED` | Previously held, now rejected (confidence < 0.2, evidence >= 10) |

**Bayesian Update Formula:**

```
α = supporting_evidence + 1  (Beta prior α)
β = contradicting_evidence + 1  (Beta prior β)
confidence = α / (α + β)  (Posterior mean)
```

### 2. SelfEvaluator

Tracks utility outcomes and identifies performance patterns.

**Tracked Metrics:**
- Utility by dominant Guna (Sattva, Rajas, Tamas)
- Utility by motion level (low, medium, high)
- Utility by entropy level (low, medium, high)
- Low utility streaks

**Failure Pattern Detection:**

```python
def identify_failure_patterns(self) -> List[Dict]:
    """
    Identifies patterns where average utility in a context
    is more than 0.1 below the overall average.

    Pattern types:
    - guna_failure: Low utility when specific Guna dominant
    - motion_failure: Low utility during specific motion level
    - entropy_failure: Low utility during specific entropy level
    """
```

### 3. EnterpriseKnowledgeBase

Self-modifiable knowledge store for beliefs and coefficient adjustments.

**Initial Prior Beliefs:**

| Belief ID | Content | Initial Confidence |
|-----------|---------|-------------------|
| `sattva_positive` | High Sattva leads to high utility | 0.7 |
| `rajas_moderate` | Moderate Rajas is optimal | 0.6 |
| `tamas_caution` | High Tamas requires careful handling | 0.7 |
| `low_entropy_stable` | Low entropy indicates stable state | 0.8 |
| `high_motion_opportunity` | High motion signals transformation opportunity | 0.6 |
| `contradiction_penalize` | High contradiction should penalize utility | 0.8 |
| `failure_penalize` | High failure should penalize utility | 0.9 |
| `coefficients_balanced` | Default coefficients are well-balanced | 0.6 |

### 4. MetaReasoner

Analyzes performance and generates improvement hypotheses.

**Hypothesis Generation Rules:**

| Pattern | Hypothesis Generated |
|---------|---------------------|
| Guna failure | Adjust Guna coefficient |
| Motion failure | Adjust motion handling |
| Entropy failure | Adjust λ_H (entropy penalty) |
| Overall low utility (<0.4) | Rebalance all coefficients |
| Utility streak >= 5 | Enable conservative mode |

**Priority Calculation:**

```
priority = confidence × (1 + severity)
severity = |context_avg_utility - overall_avg_utility|
```

### 5. EnterpriseSelfImprover

Orchestrates the complete self-improvement cycle.

**Improvement Actions:**

| Action Type | Description | Effect |
|-------------|-------------|--------|
| `coefficient_adjustment` | Adjust single coefficient | Multiplies coefficient by 0.9 or 1.1 |
| `coefficient_rebalance` | Move toward defaults | 20% blend toward default coefficients |
| `mode_change` | Toggle conservative mode | Enables safety constraints |

**Conservative Mode Effects:**

```python
c_R = c_R × 0.8   # Reduce Rajas influence
c_T = c_T × 0.8   # Reduce Tamas influence
λ_H = min(1.0, λ_H × 1.2)   # Increase entropy penalty (clamped)
λ_C = min(1.0, λ_C × 1.2)   # Increase contradiction penalty (clamped)
λ_F = min(1.0, λ_F × 1.2)   # Increase failure penalty (clamped)
```

## Configuration

### SelfImprovementConfig

Located in `symbolu/guna_modulation/v27_config.py`:

```python
@dataclass(frozen=True)
class SelfImprovementConfig:
    enabled: bool = False           # Off by default for safety
    auto_improve: bool = False      # Require explicit approval by default
    improvement_threshold: float = 0.6  # Minimum priority to execute
    observation_window: int = 100   # Observations per cycle
    max_coefficient_change: float = 0.2  # Safety bound
    enable_conservative_mode: bool = True
    persist_improvements: bool = True
```

### V27Config Integration

```python
# Check if self-improvement is enabled
config = V27Config.with_self_improvement(
    tier="enterprise-2",
    bayesian=True,
    auto_improve=False,  # Require approval
    improvement_threshold=0.6
)

assert config.is_self_improving == True
assert config.self_improvement_enabled == True
```

### Factory Function

```python
from symbolu.guna_modulation.recursive_self_improvement import (
    create_enterprise_self_improver,
)

improver = create_enterprise_self_improver(
    config=config,
    auto_improve=True,   # Enable automatic improvement
    improvement_threshold=0.6,
)
```

## Usage

### Basic Integration

```python
from symbolu.guna_modulation.recursive_self_improvement import EnterpriseSelfImprover
from symbolu.guna_modulation.observables import Observables
from symbolu.guna_modulation.state_types import StateRegister

# Create improver
improver = EnterpriseSelfImprover(auto_improve=False)

# In your pipeline, wrap utility computation:
for observables in pipeline_output:
    utility, audit = improver.observe(
        observables=observables,
        state=current_state,
    )

    # Use utility as normal
    process_utility(utility)

# Periodically run improvement (if auto_improve=False)
if should_improve:
    actions = improver.run_improvement_cycle()
    for action in actions:
        log(f"Improvement: {action.description}")
```

### Getting Effective Coefficients

```python
# Get currently active coefficients (after learning)
effective = improver.get_effective_coefficients()

# Use in utility computation
utility, audit = compute_utility(observables, state, effective)
```

### Reasoning Trace

```python
# Get reasoning trace for debugging/audit
trace = improver.get_reasoning_trace()
for step in trace:
    print(f"[{step['step']}] {step}")
```

### State Export

```python
# Export learned state for persistence
learned_state = improver.export_learned_state()

# Contains:
# - knowledge_base: All beliefs with confidence scores
# - coefficient_overrides: Learned coefficient adjustments
# - conservative_mode: Current safety mode
# - improvements: History of executed improvements
```

## Safety Constraints

### Coefficient Bounds

All coefficient adjustments are bounded to prevent extreme behavior:

```python
# Coefficient clamp (in _apply_conservative_mode)
def clamp(val: float) -> float:
    return max(-1.0, min(1.0, val))
```

### Adjustment Limits

- Single adjustment: ±10% per cycle
- Rebalance: 20% toward defaults
- Overall change bound: `max_coefficient_change = 0.2`

### Mode Transitions

Conservative mode is triggered when:
- Low utility streak >= 5 observations
- Manual activation via hypothesis

Conservative mode increases penalties and reduces Guna influence.

## Signal Mappings

The self-improvement module uses existing Observables:

| Observable | Usage in Self-Improvement |
|------------|---------------------------|
| `s` (Sattva) | Categorizes dominant Guna, updates `sattva_positive` belief |
| `r` (Rajas) | Categorizes dominant Guna, updates `rajas_moderate` belief |
| `t` (Tamas) | Categorizes dominant Guna, updates `tamas_caution` belief |
| `H` (Entropy) | Categorizes entropy level, updates `low_entropy_stable` belief |
| `M` (Motion) | Categorizes motion level, updates `high_motion_opportunity` belief |
| `C_contr` | Tracks contradiction-related failures |
| `F_fail` | Tracks failure-related patterns |

## Testing

**Test File:** `tests/unit/symbolu/test_recursive_self_improvement.py`

**Test Coverage:** 44 tests across 7 test classes:

| Test Class | Description | Tests |
|------------|-------------|-------|
| `TestBelief` | Belief creation and Bayesian updates | 7 |
| `TestSelfEvaluator` | Observation tracking and pattern detection | 7 |
| `TestEnterpriseKnowledgeBase` | Knowledge base operations | 6 |
| `TestMetaReasoner` | Hypothesis generation and prioritization | 5 |
| `TestEnterpriseSelfImprover` | Core improvement functionality | 10 |
| `TestSelfImprovementConfig` | Configuration switches | 5 |
| `TestIntegration` | End-to-end integration | 4 |

**Running Tests:**

```bash
pytest tests/unit/symbolu/test_recursive_self_improvement.py -v
```

## Invariants

### Hard Invariants (NEVER violated)

1. **Bounded Coefficients:** All coefficients remain in `[-1, 1]`
2. **Non-destructive:** Original Observables and State are never modified
3. **Deterministic:** Same observation sequence produces same improvements
4. **Audit Trail:** All improvements are logged with reasoning

### Soft Invariants (Configurable)

1. **Approval Required:** With `auto_improve=False`, improvements need explicit trigger
2. **Conservative by Default:** `enabled=False` in default config
3. **Threshold Gate:** Only improvements with `priority >= threshold` execute

## Relationship to Other Modules

### Upstream Dependencies

- `symbolu.guna_modulation.observables` → Signal source
- `symbolu.guna_modulation.utility` → `compute_utility()` function
- `symbolu.guna_modulation.state_types` → `StateRegister`, `DEFAULT_STATE`
- `symbolu.guna_modulation.v27_config` → Coefficients and configuration

### Downstream Integration

The self-improver wraps utility computation and can be integrated with:
- Evolution Engine (for state updates)
- Causal Layer (for failure reasoning)
- Persistent storage (for learning across sessions)

## Experimental Status

This module is **EXPERIMENTAL** and:

- OFF by default (`enabled=False`)
- Requires explicit opt-in
- Has bounded coefficient changes
- Maintains full audit trail
- Can be reverted via `rebalance_coefficients`

## AGI Considerations

This module exhibits characteristics associated with recursive self-improvement:

1. **Self-Observation:** Tracks its own utility outcomes
2. **Pattern Recognition:** Identifies systematic failures
3. **Hypothesis Generation:** Proposes improvements
4. **Self-Modification:** Adjusts its own parameters
5. **Learning:** Beliefs update via Bayesian inference

However, it operates within strict safety bounds and does NOT:
- Modify its own code
- Expand its action space
- Bypass safety constraints
- Learn new objectives

## Changelog

### v2.7.4 (2025-12-23)
- Initial implementation
- Integrated with existing Guna modulation signals
- Added configuration switch in V27Config
- 44 unit tests passing
- Conservative mode coefficient clamping fix
