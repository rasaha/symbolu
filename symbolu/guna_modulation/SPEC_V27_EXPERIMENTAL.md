# SymbolU v2.7 Experimental Extensions Specification

**Version:** 2.7.4-experimental
**Date:** 2025-12-22
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
8. [Capability Matrix](#capability-matrix)
9. [Enterprise Value Proposition](#enterprise-value-proposition)
10. [AGI Assessment](#agi-assessment)

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

## Capability Matrix

### What Each Extension Adds

| Capability | Bayesian | Motion | DPO | ToT | MCTS |
|------------|----------|--------|-----|-----|------|
| Uncertainty quantification | ✅ | ❌ | ❌ | ❌ | ❌ |
| Adaptive learning | ✅ | ❌ | ✅ | ❌ | ❌ |
| Explicit signal formalization | ❌ | ✅ | ❌ | ❌ | ❌ |
| Preference learning | ❌ | ❌ | ✅ | ❌ | ❌ |
| Structured reasoning | ❌ | ❌ | ❌ | ✅ | ✅ |
| Exploration/exploitation | ❌ | ❌ | ❌ | ❌ | ✅ |

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

---

## Changelog

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
