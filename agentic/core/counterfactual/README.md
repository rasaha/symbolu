# Phase 25: Counterfactual Sandbox

## Purpose

Phase 25 provides a **counterfactual simulation sandbox** for bounded perturbation analysis. It answers one question only:

> "If certain cognitive inputs were different, how would coherence and stability respond - hypothetically?"

This phase:
- Simulates alternative internal states
- Computes delta-effects on existing truth metrics
- **Never** selects, recommends, or predicts outcomes

**It is a sandbox, not a planner.**

## Architecture

```
symbolu/core/counterfactual/
├── __init__.py         # Public API exports
├── cf_schema.py        # Data models (CounterfactualScenario, CounterfactualResult, CounterfactualSandboxReport)
├── cf_engine.py        # Core computation engine (run_sandbox, simulate_scenario)
├── cf_analyzer.py      # Analysis utilities (summarize_report, analyze_ucf_sensitivity)
└── README.md           # This file

symbolu/mechanical/pipeline/p25_counterfactual/
├── __init__.py         # Pipeline integration exports
└── p25_integration.py  # Pipeline entry points (maybe_run_p25, run_p25_directly)
```

## Usage

### Basic Usage

```python
from symbolu.core.counterfactual import (
    CounterfactualScenario,
    run_sandbox,
    summarize_report,
)

# Define scenarios
scenarios = [
    CounterfactualScenario(
        scenario_id="coherence_drop",
        delta_coherence=-0.2,  # What if coherence dropped by 20%?
    ),
    CounterfactualScenario(
        scenario_id="drift_spike",
        delta_drift=0.3,  # What if drift increased by 30%?
    ),
    CounterfactualScenario(
        scenario_id="entropy_increase",
        delta_entropy=0.25,  # What if entropy increased by 25%?
    ),
]

# Run sandbox with baseline values
report = run_sandbox(
    scenarios=scenarios,
    baseline_coherence=0.7,
    baseline_drift=0.3,
    baseline_entropy=0.2,
    baseline_schema_stability=0.6,
)

# Analyze results
print(f"Baseline UCF: {report.baseline_ucf}")
print(f"Max negative impact: {report.max_negative_delta}")
print(f"Max positive impact: {report.max_positive_delta}")

# Get full summary
summary = summarize_report(report)
```

### Pipeline Integration

```python
from symbolu.mechanical.pipeline.p25_counterfactual import (
    maybe_run_p25,
    CounterfactualScenario,
    has_any_risk_flags,
)

# In pipeline (ctx is PipelineContext)
scenarios = [
    CounterfactualScenario(scenario_id="test", delta_coherence=-0.1),
]
maybe_run_p25(ctx, scenarios)

# Access results
if ctx.p25 is not None:
    print(f"Scenarios tested: {ctx.p25.scenario_count()}")
    if has_any_risk_flags(ctx):
        print("Warning: Risk flags detected")
```

## Data Models

### CounterfactualScenario (Input)

```python
@dataclass(frozen=True)
class CounterfactualScenario:
    scenario_id: str              # Unique identifier
    delta_coherence: float = 0.0  # Change to coherence [-1.0, +1.0]
    delta_entropy: float = 0.0    # Change to entropy [-1.0, +1.0]
    delta_drift: float = 0.0      # Change to drift [-1.0, +1.0]
    delta_schema_stability: Optional[float] = None  # Optional [-1.0, +1.0]
```

### CounterfactualResult (Output per Scenario)

```python
@dataclass(frozen=True)
class CounterfactualResult:
    scenario_id: str
    ucf_delta: float              # Change in UCF score
    coherence_delta: float        # Change in adjusted coherence
    stability_band_before: str    # "stable" | "transitional" | "unstable"
    stability_band_after: str     # "stable" | "transitional" | "unstable"
    risk_flags: Tuple[str, ...]   # e.g., ("STABILITY_DROP", "UCF_THRESHOLD_CROSS")
```

### CounterfactualSandboxReport (Full Report)

```python
@dataclass(frozen=True)
class CounterfactualSandboxReport:
    baseline_ucf: float
    baseline_stability_band: str
    results: Tuple[CounterfactualResult, ...]
    max_negative_delta: float
    max_positive_delta: float
    notes: Optional[str] = None
```

## Risk Flags

Risk flags are **descriptive, not actionable**. They indicate conditions detected, not recommendations.

| Flag | Condition |
|------|-----------|
| `STABILITY_DROP` | UCF dropped by more than 15% |
| `ENTROPY_SPIKE` | Entropy increased by more than 20% |
| `DRIFT_ACCELERATION` | Drift increased by more than 20% |
| `UCF_THRESHOLD_CROSS` | UCF crossed a stability band boundary (0.75 or 0.45) |

## Invariants

### Hard Invariants (Non-Negotiable)

| ID | Invariant |
|----|-----------|
| INV-P25-1 | Sandbox outputs are observational only |
| INV-P25-2 | No mutation of PipelineContext (except p25 attachment) |
| INV-P25-3 | Counterfactuals never imply recommendations |
| INV-P25-4 | UCF is recomputed via P26 formula, never overridden |
| INV-P25-5 | No forward prediction allowed |

### Authority Constraints

**MUST NOT:**
- Trigger regime changes
- Open insight windows
- Select discourse acts
- Influence semantics or lexical choice
- Predict futures
- Decide actions

**MUST NOT Import:**
- P6-P9 (regime, discourse, semantics, lexical)
- P21 delivery logic
- Renderer, DHA, Persona
- Acoustic/phonetic observers

**MAY Import:**
- P10 coherence outputs
- P12 coherence quality
- P18 temporal entropy
- P19 drift fusion
- P26 UCF formula
- Core formula utilities

### Determinism

- No randomness
- No sampling
- No Monte-Carlo
- Same inputs → same outputs (bitwise identical)

## Computation Rules

For each scenario:

1. **Apply deltas virtually** (no mutation of baseline)
   - `adjusted_value = clamp(baseline + delta, 0.0, 1.0)`

2. **Recompute adjusted metrics**
   - adjusted coherence
   - adjusted entropy
   - adjusted drift

3. **Recompute UCF** using P26 formula with adjusted values

4. **Compare before vs after**
   - Compute deltas
   - Detect risk flags
   - Record band transitions

## Analysis Functions

```python
from symbolu.core.counterfactual import (
    analyze_ucf_sensitivity,
    analyze_stability_transitions,
    analyze_risk_flags,
    summarize_report,
    find_boundary_scenarios,
    compute_delta_distribution,
    filter_results_by_flag,
    filter_results_by_band_change,
)

# Get UCF sensitivity analysis
sensitivity = analyze_ucf_sensitivity(report)
# -> {"max_negative_impact": -0.15, "most_sensitive_scenario": "drift_spike", ...}

# Get stability transition analysis
transitions = analyze_stability_transitions(report)
# -> {"transitions_count": 2, "stable_to_transitional": 1, ...}

# Get risk flag distribution
flags = analyze_risk_flags(report)
# -> {"total_flagged_scenarios": 3, "most_common_flag": "STABILITY_DROP", ...}

# Get full summary
summary = summarize_report(report)

# Find scenarios crossing stability boundaries
boundaries = find_boundary_scenarios(report)
# -> {"crossing_to_unstable": ["drift_spike"], ...}

# Filter results
stability_drops = filter_results_by_flag(report, "STABILITY_DROP")
band_changes = filter_results_by_band_change(report, from_band="stable", to_band="transitional")
```

## Testing

The test suite covers 6 groups with 60+ tests:

| Group | Description | Tests |
|-------|-------------|-------|
| A | Formula Correctness | Delta application math, clamp behavior |
| B | Determinism | Same scenario → same result |
| C | Non-Authority Proof | No impact on regime/discourse/semantics/lexical |
| D | Boundary Safety | Extreme deltas, zero deltas |
| E | Import Safety | Forbidden imports fail build |
| F | Regression Lock | Pipeline identical when P25 unused |

## Version

Current version: `1.0.0`

## Dependencies

- P26 UCF formula (for recomputation)
- Core formula utilities

## Notes

- This phase is a **numerical mirror**, not intelligence
- No heuristics, no AI logic, no scenario selection
- No future reasoning or recommendation generation
- Outputs are purely descriptive observations
