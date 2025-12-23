# SymbolU v2.7 Experimental Extensions Specification

**Version:** 2.7.8-experimental
**Date:** 2025-12-23
**Status:** Experimental (Enterprise-ready components marked)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Bayesian 2.7 (Alpha 2.7)](#bayesian-27-alpha-27)
4. [Motion (M) Formalization](#motion-m-formalization)
5. [DPO: Direct Preference Optimization](#dpo-direct-preference-optimization)
6. [ToT: Tree-of-Thoughts](#tot-tree-of-thoughts)
7. [MCTS: Monte Carlo Tree Search](#mcts-monte-carlo-tree-search)
8. [Cognitive Ability Model](#cognitive-ability-model)
9. [Concept Readiness Index](#concept-readiness-index)
10. [Causal Layer](#causal-layer)
11. [Enterprise Self-Improvement](#enterprise-self-improvement)
12. [Capability Matrix](#capability-matrix)
13. [Enterprise Value Proposition](#enterprise-value-proposition)
14. [AGI Assessment](#agi-assessment)

---

## Executive Summary

SymbolU v2.7 Experimental Extensions add mathematical enhancements to the core
entropy modulation system. These extensions provide:

| Extension | Purpose | Enterprise Ready |
|-----------|---------|------------------|
| **Bayesian 2.7** | Uncertainty-aware parameter updates | ✅ Yes |
| **Motion (M)** | Explicit motion signal formalization | ✅ Yes |
| **DPO** | Preference-based optimization | ✅ Yes (with valid goals) |
| **ToT** | Structured reasoning scaffolding | ⚠️ Experimental |
| **MCTS** | Search-based decision making | ⚠️ Experimental |
| **Cognitive Ability** | Measurable cognitive metrics via mirror + selective layers | ✅ Yes |
| **Concept Readiness** | Safe concept detection (not formation) | ✅ Yes |
| **Causal Layer** | do-calculus for layer pipeline (ATE, counterfactuals, attribution) | ✅ Yes |
| **Self-Improvement** | Recursive self-optimization using Guna signals | ⚠️ Experimental |

**Key Insight:** These are mathematical refinements, not cognitive capabilities.
The system remains deterministic signal processing, not intelligence.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SymbolU v2.7 Architecture                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │  Observables │───▶│   Utility    │───▶│  State Evolution     │  │
│  │  (S,R,T,H,M) │    │  Computation │    │  Engine              │  │
│  └──────────────┘    └──────────────┘    │                      │  │
│         │                   │            │  ┌────────────────┐  │  │
│         │                   │            │  │ EMA Mode       │  │  │
│         ▼                   ▼            │  │ θ = (1-α)θ + αθ*│  │  │
│  ┌──────────────┐    ┌──────────────┐   │  └────────────────┘  │  │
│  │   Motion     │    │     DPO      │   │          OR          │  │
│  │ Formalization│    │  Preference  │───▶│  ┌────────────────┐  │  │
│  │ (M explicit) │    │   Learning   │   │  │ Bayesian Mode  │  │  │
│  └──────────────┘    └──────────────┘   │  │ P(θ|D) ∝ P(D|θ)│  │  │
│                                          │  └────────────────┘  │  │
│                      ┌──────────────┐   └──────────────────────┘  │
│                      │   ToT/MCTS   │                              │
│                      │   Reasoning  │──▶ Branch/Action Selection   │
│                      │  Scaffolding │                              │
│                      └──────────────┘                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Bayesian 2.7 (Alpha 2.7)

### Overview

Bayesian 2.7 replaces the fixed-rate EMA update with adaptive Bayesian inference.
This provides uncertainty quantification and adaptive learning rates.

### Mathematical Foundation

#### EMA Update (Original)

```
θ_{t+1} = (1 - α) × θ_t + α × θ*

Where:
  α = fixed learning rate (e.g., 0.05)
  θ_t = current parameter
  θ* = target parameter
```

**Limitations:**
- Fixed learning rate regardless of confidence
- No uncertainty quantification
- Cannot incorporate prior knowledge
- Same α after 1 observation or 1000

#### Bayesian Update (Alpha 2.7)

```
P(θ | data) ∝ P(data | θ) × P(θ)

posterior ∝ likelihood × prior
```

**Implementation (Beta Distribution for bounded [0,1] parameters):**

```python
@dataclass
class BayesianPosterior:
    alpha: float = 1.0  # Pseudo-successes
    beta: float = 1.0   # Pseudo-failures
    n_observations: int = 0

    @property
    def mean(self) -> float:
        """Posterior mean (point estimate)."""
        return self.alpha / (self.alpha + self.beta)

    @property
    def variance(self) -> float:
        """Posterior variance (uncertainty)."""
        total = self.alpha + self.beta
        return (self.alpha * self.beta) / (total**2 * (total + 1))

    @property
    def confidence(self) -> float:
        """Confidence = 1 - normalized_variance."""
        max_var = 0.25  # Maximum variance for Beta distribution
        return 1.0 - (self.variance / max_var)

    def credible_interval_95(self) -> Tuple[float, float]:
        """95% credible interval."""
        from scipy import stats
        dist = stats.beta(self.alpha, self.beta)
        return (dist.ppf(0.025), dist.ppf(0.975))

    def update(self, observation: float, weight: float = 1.0) -> "BayesianPosterior":
        """Update posterior with new observation."""
        successes = observation * weight
        failures = (1 - observation) * weight
        return BayesianPosterior(
            alpha=self.alpha + successes,
            beta=self.beta + failures,
            n_observations=self.n_observations + 1,
        )
```

### Comparison: EMA vs Bayesian

| Property | EMA | Bayesian |
|----------|-----|----------|
| Learning rate | Fixed α | Adaptive (shrinks with evidence) |
| Uncertainty | ❌ None | ✅ Variance, credible intervals |
| Confidence signal | ❌ None | ✅ `bayesian_confidence` |
| Prior knowledge | ❌ None | ✅ Configurable priors |
| Sample efficiency | Low | High (faster initial learning) |
| Computational cost | O(1) | O(1) (same complexity) |
| Audit trail | Basic | Rich (includes uncertainty) |

### Adaptive Learning Rate Behavior

```
Observations:    1      5      10     50     100
─────────────────────────────────────────────────
EMA (α=0.05):   5%     5%     5%     5%     5%     ← Always same
Bayesian:       50%    17%    9%     2%     1%     ← Adapts to evidence
```

**Why this matters:**
- Early: Learn quickly from limited data
- Later: Stabilize as confidence increases
- Natural regularization against outliers

### Usage

```python
from symbolu.guna_modulation import (
    create_bayesian_engine,
    TIER_ENTERPRISE_1,
)

# Create Bayesian engine
engine = create_bayesian_engine(
    tier=TIER_ENTERPRISE_1,
    prior_strength=10.0,  # Equivalent to 10 prior observations
)

# Update with observations
new_state = engine.update(observables)

# Check confidence before acting
if engine.bayesian_confidence < 0.7:
    escalate_to_human_review()

# Get uncertainty bounds
interval = engine.get_credible_interval("tau_768")
print(f"τ_768 = {new_state.tau_768:.3f} (95% CI: [{interval[0]:.3f}, {interval[1]:.3f}])")
```

### Enterprise Benefits

1. **Know When You Don't Know**
   ```python
   if engine.bayesian_confidence < 0.7:
       # Low confidence → flag for human review
       escalate_to_human()
   ```

2. **Incorporate Domain Expertise**
   ```python
   engine = create_bayesian_engine(
       prior_strength=20,      # "20 samples worth of prior belief"
       prior_mean_tau=0.7,     # "Experts say τ should be ~0.7"
   )
   ```

3. **Rich Audit Trail**
   ```python
   audit = {
       "tau_768": 0.65,
       "update_mode": "bayesian",
       "confidence": 0.87,
       "credible_interval_95": [0.58, 0.72],
       "n_observations": 47,
   }
   ```

---

## Motion (M) Formalization

### Overview

Motion (M) was implicit in v2.6. This extension makes it explicit with three
computation modes, all deterministic and measurable.

### Motion Types

#### 1. Semantic Motion (Default)

Distance in embedding/semantic space.

```
M = (1/N) × Σ ||S_i - S_query||

Where:
  S_i = candidate embedding vector
  S_query = query embedding vector
  N = number of candidates
```

**Use case:** Measure how far responses diverge from query intent.

#### 2. Structural Motion

Domain/ontology transitions.

```
M = domain_jumps / max_allowed_jumps

Where:
  domain_jumps = number of category boundaries crossed
  max_allowed_jumps = normalization factor (default: 5)
```

**Use case:** Detect when response crosses knowledge domains.

#### 3. Temporal Motion

Aspect change over time (requires LAM - Latent Aspect Model).

```
M = ||Aspect_t - Aspect_{t-1}||

Where:
  Aspect_t = current aspect vector
  Aspect_{t-1} = previous aspect vector
```

**Use case:** Track state evolution magnitude over conversation.

### Properties

All three motion types are:
- **Deterministic:** Same inputs → same outputs
- **Measurable:** Scalar in [0, 1]
- **Non-psychological:** No intention, no reasoning

### Usage

```python
from symbolu.guna_modulation import (
    Observables,
    MotionType,
    compute_semantic_motion,
    compute_structural_motion,
    compute_temporal_motion,
)

# Explicit motion computation
m_semantic = compute_semantic_motion(embeddings, query_embedding)
m_structural = compute_structural_motion(domain_jumps=3, max_jumps=5)
m_temporal = compute_temporal_motion(aspect_now, aspect_prev)

# Factory methods with motion type
obs = Observables.with_structural_motion(
    guna=(0.5, 0.3, 0.2),
    entropy=0.6,
    domain_jumps=2,
    max_jumps=5,
)

# Access motion signal
print(f"Motion: {obs.M}")  # Canonical accessor
print(f"Type: {obs.motion_type.value}")
print(f"High motion: {obs.is_high_motion}")
```

---

## DPO: Direct Preference Optimization

### Overview

DPO enables preference-based parameter optimization. Unlike standard DPO which
trains neural networks, this version biases Bayesian updates toward preferred
configurations.

### Valid Goals (Measurable Signals Only)

| Goal | Formula | Signal Source |
|------|---------|---------------|
| **COHERENCE** | `S - C_contr` | `obs.s`, `obs.C_contr` |
| **STABILITY** | `(1-H) × (1-M)` | `obs.H`, `obs.M` |
| **BALANCE** | `1 - \|τ₇₆₈ - 0.5\| - spread(w)` | `state.*` |
| **UTILITY** | `U` | `compute_utility()` |

### Why "Valid" Goals Matter

```python
# INVALID: No measurable signal
if goal == "make_everyone_rich":
    return ???  # What formula produces wealth?

# VALID: Uses actual observables
if goal == PreferenceGoal.COHERENCE:
    return obs.s - obs.C_contr  # Sattva minus contradiction
```

### Mathematical Foundation

```
DPO Weight = 0.5 + sigmoid(β × (score_preferred - score_rejected))

Where:
  β = temperature parameter (default: 0.1)
  score = goal-specific scoring function
  Result in [0.5, 1.5] range
```

### Usage

```python
from symbolu.guna_modulation import (
    create_dpo_updater,
    PreferenceGoal,
)

# Create DPO with COHERENCE goal (default)
dpo = create_dpo_updater(goal=PreferenceGoal.COHERENCE, beta=0.1)

# Compute preference weight
weight = dpo.compute_preference_weight(
    preferred=good_state,
    rejected=bad_state,
    preferred_obs=good_observables,
    rejected_obs=bad_observables,
)

# Use weight in Bayesian update
new_posterior = dpo.update_posterior_with_preference(
    posterior=current_posterior,
    preferred=good_state,
    rejected=bad_state,
    observation=new_value,
)
```

### Example Output

```
Goal: coherence
COHERENCE weight: 1.0250
  Preferred score: S(0.7) - C(0.1) = 0.60   ← High Sattva, low contradiction
  Rejected score:  S(0.2) - C(0.6) = -0.40  ← Low Sattva, high contradiction

STABILITY weight: 1.0102
  Preferred: (1-H)(1-M) = 0.56  ← Low entropy, low motion
  Rejected:  (1-H)(1-M) = 0.15  ← High entropy, high motion
```

### What DPO Adds vs What It Doesn't

| Adds | Doesn't Add |
|------|-------------|
| Preference-weighted updates | Autonomous goals |
| Measurable optimization | Self-direction |
| Bias toward coherent outputs | Understanding of "why" |
| External goal alignment | Intrinsic motivation |

---

## ToT: Tree-of-Thoughts

### Overview

Tree-of-Thoughts provides structured reasoning scaffolding. It explores multiple
reasoning branches and prunes based on utility scores.

### Architecture

```
                    [Root: Query]
                    /     |     \
                   /      |      \
            [Branch 1] [Branch 2] [Branch 3]
            U=0.7      U=0.3      U=0.5
              |          ✗          |
           [Expand]   (pruned)   [Expand]
           /    \                /    \
        [1.1]  [1.2]          [3.1]  [3.2]
        U=0.8  U=0.4          U=0.6  U=0.7
          ↓      ✗              ✓      ↓
        (best)                       (keep)
```

### Configuration

```python
@dataclass
class ToTConfig:
    max_depth: int = 3              # Maximum tree depth
    branching_factor: int = 3       # Branches per node
    utility_threshold: float = 0.3  # Minimum utility to expand
    search_strategy: str = "bfs"    # "bfs" or "dfs"
```

### Usage

```python
from symbolu.guna_modulation import (
    create_tree_of_thoughts,
    TreeOfThoughts,
)

# Create ToT with custom thought generator
def my_thought_generator(thought: str, n: int) -> List[str]:
    # Generate n continuation thoughts
    return [f"{thought} → option_{i}" for i in range(n)]

def my_state_extractor(thought: str) -> Observables:
    # Extract observables from thought content
    return analyze_thought(thought)

tot = TreeOfThoughts(
    config=ToTConfig(max_depth=3, branching_factor=3),
    thought_generator=my_thought_generator,
    state_extractor=my_state_extractor,
)

# Build tree and find best path
root = tot.build_tree("What is the best approach to solve X?")
best_path = tot.find_best_path()
thought_chain = tot.get_best_thought_chain()

print(f"Tree size: {tot.tree_size}")
print(f"Best chain: {thought_chain}")
```

### Utility-Based Pruning

Branches with utility below threshold are pruned:

```python
# Score node using SymbolU utility
_, audit = compute_utility(node.state, DEFAULT_STATE)
node.utility = audit.utility

# Prune low-utility branches
if node.utility < config.utility_threshold:
    return  # Don't expand this branch
```

---

## MCTS: Monte Carlo Tree Search

### Overview

MCTS provides exploration/exploitation balance for decision making. It uses
SymbolU utility as the value function for node evaluation.

### Algorithm

```
For each simulation:
    1. SELECT: Traverse tree using UCB to find leaf
    2. EXPAND: Add child nodes for unexplored actions
    3. SIMULATE: Rollout using utility as reward
    4. BACKPROPAGATE: Update visit counts and values

UCB Score = mean_utility + c × sqrt(ln(parent_visits) / visits)

Where:
  c = exploration weight (default: √2 ≈ 1.414)
```

### Configuration

```python
@dataclass
class MCTSConfig:
    num_simulations: int = 100      # MCTS iterations
    exploration_weight: float = 1.414  # UCB exploration constant
    max_depth: int = 10             # Maximum rollout depth
    discount_factor: float = 0.95   # Future utility discount
```

### Usage

```python
from symbolu.guna_modulation import (
    create_mcts,
    MonteCarloTreeSearch,
    Observables,
)

# Create MCTS with custom action space
def my_action_generator(state: Observables) -> List[str]:
    return ["clarify", "elaborate", "summarize", "redirect"]

def my_transition(state: Observables, action: str) -> Observables:
    # Simulate state transition given action
    return simulate_action_effect(state, action)

mcts = MonteCarloTreeSearch(
    config=MCTSConfig(num_simulations=100),
    action_generator=my_action_generator,
    transition_fn=my_transition,
)

# Run search and get best action
best_action = mcts.search(current_observables)
action_values = mcts.get_action_values()

print(f"Best action: {best_action}")
print(f"Action values: {action_values}")
print(f"Total simulations: {mcts.total_simulations}")
```

### Example Output

```
Best action: explore
Action values: {
    'explore': -1.81,   ← Highest (least negative)
    'exploit': -2.25,
    'refine': -2.24
}
Total simulations: 100
```

---

## Cognitive Ability Model

### Overview

The Cognitive Ability Model provides **measurable cognitive metrics** by combining
two complementary mechanisms:

1. **Mirror Balance** - Self-referential balance detection (S↔T swap)
2. **Selective Layer Comparison** - Directive attention across ontological layers

This combination produces quantifiable "cognitive ability" that emerges from the
interplay of self-reference and selective attention.

### Key Insight

```
Cognitive Ability = Self-Reference (Mirror) + Selective Attention (Layers)
```

Neither mechanism alone produces full cognitive capability:
- **Mirror-only**: Good self-awareness, but no directional focus
- **Selective-only**: Good directional focus, but no self-awareness
- **Combined**: Best of both - measurably superior cognitive metrics

### Benchmark Results

#### Overall Scores (0-1 scale, higher = better)

| Scenario | Mirror-Only | Selective-Only | Combined | Winner |
|----------|-------------|----------------|----------|--------|
| Balanced Pipeline | 0.410 | 0.630 | 0.830 | **combined** |
| Constructive Improvement | 0.450 | 0.630 | 0.824 | **combined** |
| Destructive Regression | 0.470 | 0.645 | 0.865 | **combined** |
| Internal Imbalance | 0.500 | 0.600 | 0.794 | **combined** |
| Mixed Signals | 0.400 | 0.615 | 0.875 | **combined** |
| **Average** | **0.446** | **0.624** | **0.838** | **combined** |

**Combined wins 5/5 scenarios (100%)**

#### Detailed Metric Breakdown

##### Scenario: Balanced Pipeline

```
                    Mirror    Selective  Combined
Self-Awareness:      1.00       0.40       1.00
Directional Focus:   0.30       0.90       0.70
Actionability:       0.20       0.60       0.80
State Classification:0.30       0.50       0.90
─────────────────────────────────────────────────
TOTAL:               0.41       0.63       0.83
Category:            low     moderate     high
```

##### Scenario: Constructive Improvement

```
                    Mirror    Selective  Combined
Self-Awareness:      0.90       0.40       0.97
Directional Focus:   0.30       0.90       0.70
Actionability:       0.40       0.60       0.80
State Classification:0.30       0.50       0.90
─────────────────────────────────────────────────
TOTAL:               0.45       0.63       0.82
Category:            low     moderate     high
```

##### Scenario: Destructive Regression

```
                    Mirror    Selective  Combined
Self-Awareness:      0.85       0.40       0.87
Directional Focus:   0.40       0.85       0.90
Actionability:       0.40       0.70       0.80
State Classification:0.30       0.50       0.90
─────────────────────────────────────────────────
TOTAL:               0.47       0.65       0.86
Category:            low     moderate     high
```

##### Scenario: Internal Imbalance

```
                    Mirror    Selective  Combined
Self-Awareness:      1.00       0.40       0.82
Directional Focus:   0.40       0.80       0.70
Actionability:       0.40       0.60       0.80
State Classification:0.30       0.50       0.90
─────────────────────────────────────────────────
TOTAL:               0.50       0.60       0.79
Category:          moderate  moderate   moderate
```

##### Scenario: Mixed Signals

```
                    Mirror    Selective  Combined
Self-Awareness:      0.50       0.40       0.92
Directional Focus:   0.40       0.85       0.90
Actionability:       0.40       0.60       0.80
State Classification:0.30       0.50       0.90
─────────────────────────────────────────────────
TOTAL:               0.40       0.61       0.88
Category:            low     moderate     high
```

#### Improvement Statistics

```
Combined vs Mirror-Only:
  Average improvement:    +89.4%
  Best improvement:      +120.0% (Mixed Signals)
  Worst improvement:     +58.0% (Internal Imbalance)

Combined vs Selective-Only:
  Average improvement:    +34.2%
  Best improvement:      +42.4% (Mixed Signals)
  Worst improvement:     +27.5% (Destructive Regression)
```

#### Category Distribution

| Approach | High | Moderate | Low |
|----------|------|----------|-----|
| Mirror-Only | 0% | 20% | 80% |
| Selective-Only | 0% | 100% | 0% |
| **Combined** | **80%** | **20%** | **0%** |

#### Key Quantitative Findings

1. **Self-Awareness Gap**
   - Mirror-only average: 0.85
   - Selective-only average: 0.40
   - Combined average: 0.92
   - **Combined captures mirror's strength (+130% over selective)**

2. **Directional Focus Gap**
   - Mirror-only average: 0.36
   - Selective-only average: 0.86
   - Combined average: 0.78
   - **Combined captures selective's strength (+117% over mirror)**

3. **Actionability Improvement**
   - Mirror-only average: 0.36
   - Selective-only average: 0.62
   - Combined average: 0.80
   - **Combined exceeds both (+29% over selective)**

4. **State Classification**
   - Mirror-only: Binary (balanced/unbalanced) = 0.30
   - Selective-only: 5 ambition types = 0.50
   - Combined: 6 cognitive states = 0.90
   - **Combined has 3x classification richness**

### Cognitive Metrics (Measurable)

Four quantifiable metrics define cognitive capability:

| Metric | Description | Mirror | Selective | Combined |
|--------|-------------|--------|-----------|----------|
| **Self-Awareness** | Detects internal imbalance | ✅ High | ❌ Low | ✅ High |
| **Directional Focus** | Knows which layer to improve | ❌ Low | ✅ High | ✅ High |
| **Actionability** | Produces actionable output | ⚠️ Medium | ⚠️ Medium | ✅ High |
| **State Classification** | Classifies cognitive state | ❌ Binary | ⚠️ Limited | ✅ 6 states |

### Ontological Layer Hierarchy

The system defines 7 ontological layers for cross-layer comparison:

```
Layer 0: SIGNAL     (raw signals)
Layer 1: EMBEDDING  (semantic embeddings)
Layer 2: GUNA       (S/R/T classification)
Layer 3: MOTION     (change detection)
Layer 4: FUSION     (HRM integration)
Layer 5: STATE      (evolved registers)
Layer 6: OUTPUT     (final output)
```

**Cognitive ambition** emerges from comparing adjacent layers:

```
Cognitive Ambition = downstream_coherence - upstream_coherence

  Positive → System is "striving" (improving as it processes)
  Negative → System is "regressing" (losing coherence)
  Near zero → Stable but not growing
```

### Mirror Balance

The mirror creates a "reflection" of the current state to detect imbalance:

```python
# Mirror transformation
S ↔ T swap (Sattva/Tamas exchange)
H' = 1 - H (entropy complement)
M' = 1 - M (motion complement)

# If original ≈ mirror, state is balanced
# If |original - mirror| is large, imbalance exists
```

### Configurable Layer Comparison

Users select which ontological layers to monitor:

```python
@dataclass
class LayerComparisonConfig:
    primary_comparison: Tuple[str, str]  # Main layer pair
    secondary_comparisons: list          # Additional pairs
    mirror_layer: str                    # Balance reference
    attention_weight: float              # Primary vs secondary
```

**Tier-Specific Defaults:**

| Tier | Primary Focus | Mirror Layer | Use Case |
|------|---------------|--------------|----------|
| Enterprise T1 | Fusion → State | Fusion | High-level quality |
| Enterprise T2 | Guna → Fusion | Guna | Semantic integration |
| Consumer | State → Output | Output | Output quality |
| **Mixed (Default)** | Guna → Fusion + State → Output | Guna | Best overall |

### Cognitive State Classification

The combined approach classifies into 6 cognitive states:

| State | Condition | Meaning |
|-------|-----------|---------|
| **thriving** | High ambition, good balance | Optimal performance |
| **striving** | High ambition, poor balance | Needs correction |
| **stable** | Low ambition, excellent balance | Maintenance mode |
| **regressing** | Negative ambition | Quality degradation |
| **unstable** | Low ambition, poor balance | Needs intervention |
| **neutral** | Middle ground | Normal operation |

### Usage

```python
from symbolu.guna_modulation import (
    ConfigurableDissonanceMonitor,
    LAYER_COMPARISON_MIXED_DIRECTIVE,
    OntologicalLayer,
)

# Create monitor with default (mixed directive) configuration
monitor = ConfigurableDissonanceMonitor.for_tier("mixed")

# Observe layers in pipeline
monitor.observe(OntologicalLayer.GUNA, guna_observables)
monitor.observe(OntologicalLayer.FUSION, fusion_observables)
monitor.observe(OntologicalLayer.STATE, state_observables)

# Get cognitive insights
insights = monitor.get_cognitive_insights()

print(f"Primary ambition: {insights['primary_ambition']:.2f}")
print(f"Cognitive state: {insights['cognitive_state']}")
print(f"Attention focus: {insights['attention_focus']}")
print(f"Mirror balance: {insights['mirror_balance']:.2f}")

# Example output:
# Primary ambition: 0.35
# Cognitive state: thriving
# Attention focus: amplify:guna→fusion
# Mirror balance: 0.92
```

### Running Benchmarks

```python
from symbolu.guna_modulation import (
    run_cognitive_benchmark,
    run_standard_benchmark_suite,
)

# Run standard benchmark suite
results = run_standard_benchmark_suite()

for r in results:
    print(f"{r.scenario}: {r.winner} wins")
    print(f"  Combined vs Mirror: {r.combined_improvement_over_mirror*100:.1f}%")
    print(f"  Combined vs Selective: {r.combined_improvement_over_selective*100:.1f}%")
```

### Why This Matters

The Cognitive Ability Model provides:

1. **Measurable cognitive metrics** - Not vague "intelligence", but quantifiable scores
2. **Configurable attention** - Users choose which layers matter for their use case
3. **Self-reference + direction** - The combination that produces cognitive capability
4. **Actionable insights** - State classification leads to specific recommendations

### Relationship to AGI

This is **not AGI**. The "cognitive ability" is:

- Measurable signal processing properties
- Not understanding, reasoning, or consciousness
- Deterministic and auditable
- A useful enterprise metric, not artificial general intelligence

```
┌──────────────────────────────────────────────────────┐
│  Cognitive Ability Model                             │
│                                                      │
│  = Measurable self-awareness + directional focus    │
│  = Quantifiable improvement metrics                 │
│  ≠ Understanding                                    │
│  ≠ AGI                                              │
│                                                      │
│  Enterprise value: ✅ Yes (measurable, actionable)  │
│  True cognition: ❌ No (signal processing only)     │
└──────────────────────────────────────────────────────┘
```

---

## Concept Readiness Index

### Overview

The Concept Readiness Index (CRI) implements **safe concept detection** without
concept formation. This is a critical distinction for AuGI (Augmented General
Intelligence) versus AGI.

### Key Distinction: Detection vs Formation

| Aspect | AGI Concept Formation | AuGI Concept Detection |
|--------|----------------------|------------------------|
| **What it does** | Creates new abstractions | Measures coherence |
| **Output** | New concepts | Readiness scores |
| **Scope** | Generalizes, reuses | Measures current state |
| **Risk** | Unbounded creation | Bounded measurement |
| **Enterprise safe** | ❌ No | ✅ Yes |

### Mathematical Foundation

#### Concept Coherence Score

```
C_concept = (1/N) × Σ sim(r_i, r̄)

Where:
  r_i = representation at layer i
  r̄ = centroid (mean) representation
  sim = cosine similarity
```

Measures agreement across layer representations. High coherence = stable notion.

#### Concept Entropy

```
H_concept = -Σ p_i × log(p_i)

Where:
  p_i = probability distribution of interpretations
```

Measures distribution of competing meanings. High entropy = ambiguous notion.

#### Concept Readiness Index

```
CRI = C_concept × (1 - H_concept) × S

Where:
  C = Concept Coherence [0, 1]
  H = Concept Entropy [0, 1] (normalized)
  S = Structural Stability [0, 1]
```

CRI answers: "Is this idea ready to be treated as a concept by a human?"
The system does NOT treat it as a concept itself.

### Readiness Levels

| CRI Range | Level | Description |
|-----------|-------|-------------|
| ≥ 0.8 | `ready` | Conditions for human conceptualization exist |
| ≥ 0.6 | `nearly_ready` | Minor ambiguities remain |
| ≥ 0.4 | `forming` | Interpretations vary across layers |
| ≥ 0.2 | `emerging` | Insufficient coherence |
| < 0.2 | `not_ready` | Too fragmented for conceptual treatment |

### Safe Output Generation

All outputs describe CONDITIONS, not concepts themselves.

**✅ Allowed outputs:**
- "This idea is conceptually unstable"
- "This term spans multiple incompatible meanings"
- "This notion lacks sufficient coherence to act on"
- "This concept is well-formed across layers"

**❌ Forbidden outputs:**
- "This is a new concept"
- "Here is the definition"
- "This concept applies elsewhere"
- "I will reuse this concept"

### Drift Detection

```python
# Track concept readiness over time
monitor = ConceptReadinessMonitor(window_size=10)

# Observe layer states
cri1 = monitor.observe([("guna", obs1), ("fusion", obs2)])
cri2 = monitor.observe([("guna", obs3), ("fusion", obs4)])

# Detect drift
drift = monitor.get_drift()
if drift.is_crystallizing:
    print("Notion is becoming more coherent")
elif drift.is_fragmenting:
    print("Notion is losing coherence")

# Get overall trend
trend = monitor.get_trend()  # "improving", "degrading", "stable"
```

### Usage Example

```python
from symbolu.guna_modulation import (
    compute_concept_readiness,
    ConceptReadinessMonitor,
    ConceptReadinessReporter,
)

# Define layer observables
layers = [
    ("guna", guna_observables),
    ("fusion", fusion_observables),
    ("state", state_observables),
]

# Compute CRI
cri = compute_concept_readiness(layers)

print(f"CRI: {cri.index:.2f}")
print(f"Level: {cri.readiness_level}")
print(f"Blocking factor: {cri.blocking_factor}")

# Generate safe description
desc = cri.get_safe_description()
print(desc)
# Output: "This notion shows high coherence across layers and may be ready
#          for human conceptualization"

# Generate full report
report = ConceptReadinessReporter.generate_full_report(cri)
print(report["human_can_conceptualize"])  # True if CRI >= 0.7
```

### Enterprise Value

```
┌──────────────────────────────────────────────────────┐
│  Concept Readiness Index (CRI)                       │
│                                                      │
│  = Measures when humans can form concepts            │
│  = Safe bounded measurement                          │
│  ≠ Creates new concepts                              │
│  ≠ AGI                                              │
│                                                      │
│  Enterprise value: ✅ Yes (safe, auditable)         │
│  Concept formation: ❌ No (detection only)          │
└──────────────────────────────────────────────────────┘
```

---

## Causal Layer

### Overview

The Causal Layer module adds **do-calculus** style causal inference to SymbolU's
layer pipeline, treating the ontological layers as a Directed Acyclic Graph (DAG).

### Key Insight

SymbolU's layer pipeline IS already a causal graph:

```
SIGNAL → EMBEDDING → GUNA → MOTION → FUSION → STATE → OUTPUT
```

Each layer causally affects downstream layers. This module formalizes that
relationship using Pearl's do-calculus.

### Capabilities

| Operation | Description | Use Case |
|-----------|-------------|----------|
| **do(X=x)** | Intervention operator | "What if we set GUNA to high clarity?" |
| **ATE** | Average Treatment Effect | "How much does GUNA affect OUTPUT?" |
| **Counterfactual** | What-if reasoning | "What would OUTPUT be if GUNA had zero entropy?" |
| **Attribution** | Causal attribution | "Which layer caused this instability?" |

### Mathematical Foundation

#### Intervention (do-operator)

```
P(Y | do(X=x)) ≠ P(Y | X=x)

do(X=x) removes incoming edges to X, simulating intervention
rather than observation.
```

#### Average Treatment Effect

```
ATE = E[Y | do(X = x_treatment)] - E[Y | do(X = x_control)]

Effect decays with causal distance:
  decay = exp(-0.2 × distance)
```

#### Counterfactual

Three-step procedure:
1. **Abduction**: Infer exogenous variables from factual
2. **Action**: Apply intervention (modify treatment)
3. **Prediction**: Compute counterfactual outcome

### Usage Example

```python
from symbolu.guna_modulation import (
    create_causal_model,
    OntologicalLayer,
    Observables,
)

# Create model and observe layer states
model = (
    create_causal_model()
    .observe(OntologicalLayer.GUNA, guna_obs)
    .observe(OntologicalLayer.FUSION, fusion_obs)
    .observe(OntologicalLayer.OUTPUT, output_obs)
)

# 1. Attribution: Which layer caused poor output?
attr = model.attribute(OntologicalLayer.OUTPUT)
print(f"Primary cause: {attr.primary_cause}")
print(f"GUNA contribution: {attr.get_attribution(OntologicalLayer.GUNA).contribution_percent:.1f}%")

# 2. Intervention: What if GUNA had high clarity?
high_clarity = Observables(s=0.8, r=0.1, t=0.1, H=0.2, ...)
effect = model.do(OntologicalLayer.GUNA, high_clarity).effect_on(OntologicalLayer.OUTPUT)
print(f"Effect size: {effect.effect_size:.3f}")
print(f"Significant: {effect.is_significant}")

# 3. Counterfactual: What would have happened?
cf = model.counterfactual(
    "What if GUNA had high clarity?",
    treatment=OntologicalLayer.GUNA,
    outcome=OntologicalLayer.OUTPUT,
    intervention=high_clarity,
)
print(f"Would have improved: {cf.would_have_improved}")
print(f"Improvement: {cf.improvement_percent:.1f}%")
```

### Enterprise Value

```
┌──────────────────────────────────────────────────────────────┐
│  Causal Layer                                                 │
│                                                               │
│  = Answers "which layer caused this?"                         │
│  = Enables intervention planning                              │
│  = Supports counterfactual debugging                          │
│  ≠ Creates causal structure (uses existing pipeline)          │
│  ≠ AGI                                                        │
│                                                               │
│  Enterprise value: ✅ Yes (root cause analysis, auditable)   │
│  Causal discovery: ❌ No (fixed DAG from layer design)       │
└──────────────────────────────────────────────────────────────┘
```

---

## Enterprise Self-Improvement

### Overview

The Enterprise Self-Improvement module enables SymbolU v2.7 to observe its own
performance, identify patterns of low utility, and autonomously adjust its
operational parameters to improve future outcomes.

**Key Principle:** This is NOT ethics or value learning. It is policy-aligned
operational self-optimization using existing Guna signals.

### Architecture

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

### Belief System

The system maintains beliefs about optimal configurations using Bayesian confidence:

```python
@dataclass
class Belief:
    id: str
    content: str
    belief_type: BeliefType  # PRIOR, LEARNED, HYPOTHESIS, VERIFIED, DEPRECATED
    confidence: float        # P(belief is true) in [0, 1]
    evidence_count: int
    supporting_evidence: int
    contradicting_evidence: int
```

**Bayesian Update Formula:**

```
α = supporting_evidence + 1  (Beta prior α)
β = contradicting_evidence + 1  (Beta prior β)
confidence = α / (α + β)  (Posterior mean)
```

**Belief Type Transitions:**

| Condition | State Transition |
|-----------|------------------|
| confidence < 0.2, evidence ≥ 10 | → DEPRECATED |
| confidence > 0.8, evidence ≥ 20 | HYPOTHESIS → VERIFIED |

### Initial Prior Beliefs

| Belief ID | Content | Initial Confidence |
|-----------|---------|-------------------|
| `sattva_positive` | High Sattva leads to high utility | 0.7 |
| `rajas_moderate` | Moderate Rajas is optimal | 0.6 |
| `tamas_caution` | High Tamas requires careful handling | 0.7 |
| `low_entropy_stable` | Low entropy indicates stable state | 0.8 |
| `high_motion_opportunity` | High motion signals transformation | 0.6 |
| `contradiction_penalize` | High contradiction penalizes utility | 0.8 |
| `failure_penalize` | High failure penalizes utility | 0.9 |
| `coefficients_balanced` | Default coefficients are well-balanced | 0.6 |

### Self-Evaluation

The SelfEvaluator tracks utility outcomes by context:

```python
class SelfEvaluator:
    # Performance by context
    utility_by_guna_dominant: Dict[str, List[float]]  # sattva, rajas, tamas
    utility_by_motion: Dict[str, List[float]]         # low, medium, high
    utility_by_entropy: Dict[str, List[float]]        # low, medium, high

    # Trend tracking
    low_utility_streak: int
    max_low_utility_streak: int
```

**Failure Pattern Detection:**

Identifies patterns where average utility in a context is more than 0.1 below
the overall average:

- `guna_failure`: Low utility when specific Guna dominant
- `motion_failure`: Low utility during specific motion level
- `entropy_failure`: Low utility during specific entropy level

### Meta-Reasoner

Analyzes performance and generates improvement hypotheses:

| Pattern | Hypothesis Generated |
|---------|---------------------|
| Guna failure | Adjust Guna coefficient |
| Motion failure | Adjust motion handling |
| Entropy failure | Adjust λ_H (entropy penalty) |
| Overall low utility (<0.4) | Rebalance all coefficients |
| Utility streak ≥ 5 | Enable conservative mode |

**Priority Calculation:**

```
priority = confidence × (1 + severity)
severity = |context_avg_utility - overall_avg_utility|
```

### Improvement Actions

| Action Type | Description | Effect |
|-------------|-------------|--------|
| `coefficient_adjustment` | Adjust single coefficient | Multiplies by 0.9 or 1.1 |
| `coefficient_rebalance` | Move toward defaults | 20% blend toward default |
| `mode_change` | Toggle conservative mode | Enables safety constraints |

**Conservative Mode Effects:**

```python
c_R = c_R × 0.8   # Reduce Rajas influence
c_T = c_T × 0.8   # Reduce Tamas influence
λ_H = clamp(λ_H × 1.2, [-1, 1])   # Increase entropy penalty
λ_C = clamp(λ_C × 1.2, [-1, 1])   # Increase contradiction penalty
λ_F = clamp(λ_F × 1.2, [-1, 1])   # Increase failure penalty
```

### Configuration

```python
@dataclass(frozen=True)
class SelfImprovementConfig:
    enabled: bool = False           # Off by default for safety
    auto_improve: bool = False      # Require explicit approval
    improvement_threshold: float = 0.6  # Minimum priority to execute
    observation_window: int = 100   # Observations per cycle
    max_coefficient_change: float = 0.2  # Safety bound
    enable_conservative_mode: bool = True
    persist_improvements: bool = True
```

**V27Config Integration:**

```python
from symbolu.guna_modulation import V27Config

# Create config with self-improvement enabled
config = V27Config.with_self_improvement(
    tier="enterprise-2",
    bayesian=True,
    auto_improve=False,  # Require approval
    improvement_threshold=0.6
)

assert config.is_self_improving == True
```

### Usage

```python
from symbolu.guna_modulation import (
    EnterpriseSelfImprover,
    create_enterprise_self_improver,
)

# Create improver
improver = create_enterprise_self_improver(
    auto_improve=True,
    improvement_threshold=0.6,
)

# In your pipeline, wrap utility computation:
for observables in pipeline_output:
    utility, audit = improver.observe(
        observables=observables,
        state=current_state,
    )
    process_utility(utility)

# Get effective coefficients (after learning)
effective = improver.get_effective_coefficients()

# Get reasoning trace for debugging/audit
trace = improver.get_reasoning_trace()
for step in trace:
    print(f"[{step['step']}] {step}")

# Export learned state for persistence
learned_state = improver.export_learned_state()
```

### Safety Constraints

| Constraint | Value |
|------------|-------|
| Coefficient bounds | All values in [-1, 1] |
| Single adjustment | ±10% per cycle |
| Rebalance step | 20% toward defaults |
| Overall change bound | max_coefficient_change = 0.2 |

### AGI Considerations

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

```
┌──────────────────────────────────────────────────────────────┐
│  Enterprise Self-Improvement                                  │
│                                                               │
│  = Bounded self-optimization using existing signals           │
│  = Bayesian belief updates for configuration tuning           │
│  ≠ Unbounded self-modification                               │
│  ≠ AGI                                                        │
│                                                               │
│  Enterprise value: ✅ Yes (adaptive, auditable)              │
│  Recursive self-improvement: ⚠️ Bounded (safe experimental)  │
└──────────────────────────────────────────────────────────────┘
```

---

## Capability Matrix

### What Each Extension Adds

| Capability | Bayesian | Motion | DPO | ToT | MCTS | Cognitive | CRI | Causal | Self-Imp |
|------------|----------|--------|-----|-----|------|-----------|-----|--------|----------|
| Uncertainty quantification | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Adaptive learning | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Explicit signal formalization | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Preference learning | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Structured reasoning | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Exploration/exploitation | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Self-awareness metrics | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| Directional focus | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Cognitive state classification | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Concept coherence detection | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Concept entropy measurement | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Concept drift monitoring | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Intervention (do-operator) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Causal effect estimation | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Counterfactual reasoning | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Causal attribution | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Self-observation | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Hypothesis generation | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Parameter self-modification | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Belief tracking | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

### What None of Them Add (AGI Capabilities)

| Missing Capability | Bayesian | Motion | DPO | ToT | MCTS |
|-------------------|----------|--------|-----|-----|------|
| Concept formation | ❌ | ❌ | ❌ | ❌ | ❌ |
| Reasoning/inference | ❌ | ❌ | ❌ | ❌ | ❌ |
| Transfer learning | ❌ | ❌ | ❌ | ❌ | ❌ |
| Self-modification | ❌ | ❌ | ❌ | ❌ | ❌ |
| Autonomous goals | ❌ | ❌ | ❌ | ❌ | ❌ |
| World model | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## Enterprise Value Proposition

### Why Bayesian > EMA for Enterprise

| Enterprise Need | EMA | Bayesian |
|-----------------|-----|----------|
| "Is this estimate reliable?" | ❌ Can't tell | ✅ Confidence score |
| "Show me the uncertainty" | ❌ None | ✅ Credible intervals |
| "Incorporate expert knowledge" | ❌ Can't | ✅ Configurable priors |
| "Audit trail for compliance" | Basic | Rich with uncertainty |
| "Different tiers, different behavior" | ✅ Via α | ✅ Via prior strength |

### Practical Enterprise Scenarios

#### Scenario 1: High-Stakes Decision

```python
# EMA: No idea if estimate is reliable
state = ema_engine.update(obs)
# Just hope τ_768 = 0.65 is correct...

# Bayesian: Know your confidence
state = bayesian_engine.update(obs)
if bayesian_engine.bayesian_confidence < 0.8:
    # Low confidence on high-stakes decision
    return escalate_to_senior_analyst()
```

#### Scenario 2: Regulatory Compliance

```python
# Bayesian audit provides defensible bounds
audit = {
    "parameter": "tau_768",
    "point_estimate": 0.65,
    "confidence": 0.87,
    "credible_interval_95": [0.58, 0.72],
    "n_observations": 47,
    "prior_used": "enterprise_conservative",
}
# Regulator: "How confident are you in this value?"
# Answer: "87% confident, 95% likely between 0.58 and 0.72"
```

#### Scenario 3: Cold Start with Domain Knowledge

```python
# New deployment, but domain experts have opinions
engine = create_bayesian_engine(
    prior_strength=20,      # Strong prior
    prior_mean_tau=0.7,     # Expert consensus
)
# System starts informed, not from scratch
```

### DPO + Bayesian Integration

```python
# Combine preference learning with uncertainty-aware updates
dpo = create_dpo_updater(goal=PreferenceGoal.COHERENCE)
engine = create_bayesian_engine()

# User provides feedback: "Response A was better than B"
weight = dpo.compute_preference_weight(
    preferred=state_A, rejected=state_B,
    preferred_obs=obs_A, rejected_obs=obs_B,
)

# Weight influences Bayesian update
# Higher weight = more influence from this preference
engine.update_with_weight(new_obs, weight)
```

---

## AGI Assessment

### Honest Evaluation

These extensions are **mathematical refinements**, not steps toward AGI.

```
What we built:
  Signal processing with better knobs

What AGI requires:
  Understanding, reasoning, goals, world models
```

### The Fundamental Gap

| System Has | AGI Needs |
|------------|-----------|
| `obs.s - obs.C_contr` formula | Understanding of "coherence" |
| `P(θ\|data)` computation | Understanding of "belief" |
| `UCB = mean + c×sqrt(...)` | Understanding of "exploration" |
| Tree of `ThoughtNode` objects | Actual thoughts |
| `PreferenceGoal.COHERENCE` enum | Concept of "preference" |

### Why This Matters

Being honest about limitations enables:

1. **Correct expectations** - Enterprises know what they're buying
2. **Proper use cases** - Apply where it helps, not where it can't
3. **Future planning** - Know what's missing for next steps
4. **Trust** - Honest assessment builds credibility

### Summary

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   Bayesian 2.7 + DPO + ToT + MCTS                  │
│                                                     │
│   = Better signal processing                        │
│   ≠ Intelligence                                    │
│   ≠ AGI                                            │
│                                                     │
│   Enterprise value: ✅ Yes                          │
│   Cognitive capabilities: ❌ No                     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## API Reference

### Bayesian 2.7

```python
from symbolu.guna_modulation import (
    # Update mode switch
    UpdateMode,

    # Bayesian components
    BayesianConfig,
    BayesianPosterior,
    BayesianStateRegister,

    # Pre-built configs
    BAYESIAN_V27_CONFIG,
    BAYESIAN_ENTERPRISE_T1,
    BAYESIAN_ENTERPRISE_T2,
    BAYESIAN_CONSUMER,

    # Factory functions
    create_bayesian_engine,
    create_bayesian_engine_for_tier,
)
```

### Motion (M)

```python
from symbolu.guna_modulation import (
    # Motion type enum
    MotionType,

    # Computation utilities
    compute_semantic_motion,
    compute_structural_motion,
    compute_temporal_motion,

    # Observables with motion
    Observables,  # .M, .motion, .is_high_motion, .is_low_motion
)
```

### DPO

```python
from symbolu.guna_modulation import (
    # Goals
    PreferenceGoal,

    # Types
    PreferencePair,
    DPOConfig,
    DPOUpdater,

    # Factory
    create_dpo_updater,
)
```

### ToT

```python
from symbolu.guna_modulation import (
    # Types
    ThoughtNode,
    ToTConfig,
    TreeOfThoughts,

    # Factory
    create_tree_of_thoughts,
)
```

### MCTS

```python
from symbolu.guna_modulation import (
    # Types
    MCTSNode,
    MCTSConfig,
    MonteCarloTreeSearch,

    # Factory
    create_mcts,

    # Reference
    CAPABILITY_MATRIX,
)
```

### Cognitive Ability Model

```python
from symbolu.guna_modulation import (
    # Mirror Balance
    MirrorPair,
    BalanceCorrection,
    SelfQuestion,
    compute_mirror_observables,
    create_mirror_pair,
    compute_balance_correction,
    apply_balance_correction,
    compute_harmonic_mirror,
    generate_self_questions,
    MirrorBalanceEngine,

    # Ontological Layers
    OntologicalLayer,
    LayerState,
    LayerDissonance,
    compute_layer_dissonance,
    LayerDissonanceMonitor,
    generate_ambition_questions,

    # Configurable Layer Comparison
    LayerComparisonConfig,
    LAYER_COMPARISON_ENTERPRISE_T1,
    LAYER_COMPARISON_ENTERPRISE_T2,
    LAYER_COMPARISON_CONSUMER,
    LAYER_COMPARISON_FULL_PIPELINE,
    LAYER_COMPARISON_MIXED_DIRECTIVE,  # Default
    DEFAULT_LAYER_COMPARISON,
    get_layer_comparison_for_tier,
    ConfigurableDissonanceMonitor,

    # Benchmarking
    CognitiveMetrics,
    MirrorOnlyAnalyzer,
    SelectiveOnlyAnalyzer,
    CombinedAnalyzer,
    BenchmarkResult,
    run_cognitive_benchmark,
    run_standard_benchmark_suite,
)
```

### Enterprise Self-Improvement

```python
from symbolu.guna_modulation import (
    # Belief System
    Belief,
    BeliefType,

    # Self-Evaluation
    SelfEvaluator,
    UtilityObservation,

    # Knowledge Base
    EnterpriseKnowledgeBase,

    # Meta-Reasoner
    MetaReasoner,

    # Improvement Actions
    ImprovementAction,

    # Main Orchestrator
    EnterpriseSelfImprover,

    # Configuration
    SelfImprovementConfig,

    # Factory
    create_enterprise_self_improver,
)
```

---

## Changelog

### v2.7.8-experimental (2025-12-23)

- Added Enterprise Self-Improvement module for recursive self-optimization
- Added Belief system with Bayesian confidence updating (Beta distribution)
- Added SelfEvaluator for tracking utility outcomes by context (Guna, motion, entropy)
- Added EnterpriseKnowledgeBase with prior beliefs and coefficient adjustments
- Added MetaReasoner for hypothesis generation from failure patterns
- Added ImprovementAction types: coefficient_adjustment, coefficient_rebalance, mode_change
- Added SelfImprovementConfig with safety-first defaults (enabled=False, auto_improve=False)
- Added V27Config.with_self_improvement() factory method
- Added V27Config.is_self_improving property
- Added conservative mode with bounded coefficient modifications
- Key safety: All coefficient changes clamped to [-1, 1], max 10% per cycle
- 44 unit tests for enterprise self-improvement

### v2.7.7-experimental (2025-12-22)

- Added Causal Layer module with do-calculus for layer pipeline
- Added LayerCausalGraph for DAG structure with SIGNAL → OUTPUT ordering
- Added do() intervention operator for causal queries
- Added ATE (Average Treatment Effect) estimation between layers
- Added counterfactual reasoning with three-step procedure (Abduction → Action → Prediction)
- Added Shapley-style causal attribution for outcome decomposition
- Added LayerCausalModel as main interface for causal inference
- Added convenience functions: create_causal_model(), quick_attribution(), quick_ate()
- Inspired by PyWhy's causal inference framework
- Key formula: ATE = E[Y | do(X=x₁)] - E[Y | do(X=x₀)]

### v2.7.6-experimental (2025-12-22)

- Added Concept Readiness Index (CRI) for safe concept detection
- Added ConceptCoherence for measuring agreement across layer representations
- Added ConceptEntropy for measuring interpretation ambiguity
- Added ConceptReadinessMonitor for drift detection over time
- Added ConceptReadinessReporter for safe output generation
- CRI formula: CRI = C × (1 - H) × S
- Safe outputs describe conditions, never create concepts
- Key distinction: AuGI (detection) vs AGI (formation)

### v2.7.5-experimental (2025-12-22)

- Added Cognitive Ability Model with measurable metrics
- Added MirrorBalance for self-referential balance detection
- Added OntologicalLayer hierarchy (7 layers: SIGNAL → OUTPUT)
- Added ConfigurableDissonanceMonitor for selective layer comparison
- Added LAYER_COMPARISON_MIXED_DIRECTIVE as new default
- Added cognitive benchmark suite with 5 scenarios
- Benchmark results: Combined approach +89.4% over mirror-only, +34.2% over selective-only
- Added 6 cognitive state classifications: thriving, striving, stable, regressing, unstable, neutral

### v2.7.4-experimental (2025-12-22)

- Added DPO with valid goals (COHERENCE, STABILITY, BALANCE, UTILITY)
- Added Tree-of-Thoughts (ToT) with utility-based pruning
- Added Monte Carlo Tree Search (MCTS) with utility as value function
- Updated DPO to require measurable signals

### v2.7.3 (2025-12-22)

- Added Motion (M) formalization
- Added MotionType enum (SEMANTIC, STRUCTURAL, TEMPORAL)
- Added motion computation utilities
- Added Observables.M property and factory methods

### v2.7.2 (2025-12-22)

- Added Alpha 2.7 Bayesian update mode
- Added UpdateMode enum (EMA vs BAYESIAN)
- Added BayesianConfig, BayesianPosterior, BayesianStateRegister
- Added create_bayesian_engine() factory functions
- All plugs from EMA connected to Bayesian mode

---

*This document describes experimental extensions. Use in production at your own discretion.*
