# SymbolU v2.7 — Deterministic Evaluation & State Evolution Layer

**Symbol-U v2.7.1 — Deterministic, Operator-Configurable, Non-Learning System**

**Date:** 2025-12-22
**Version:** 2.7.1 (with operator-configurable coefficients)
**Status:** Specification Complete
**Classification:** Enterprise-Safe, Patent-Aligned
**Prerequisite:** v2.6.1 (Guna Entropy Modulation + Signal Wiring)

---

## 1. Overview

SymbolU v2.7 introduces a **Deterministic Evaluation & State Evolution Layer** that:
- Evaluates each completed run using explicit formulas
- Computes policy-aligned utility (not morality)
- Produces target state vectors
- Updates internal state using bounded deterministic rules
- Emits machine-auditable explanations

**Critical Invariant:** v2.7 does NOT modify semantic truth. STL and C × R × S remain untouched.

---

## 2. Architectural Invariant

```
STL Truth (10D)
 → Canonical Matching (C × R × S)
 → Routing / Cascade
 → Candidate Selection (Stitching + Fusion)
 → Evaluation Layer (NEW in v2.7)
 → State Register Update (NEW in v2.7)
 → Guna Modulation (v2.6)
 → Delivery (DHA + Renderer)
```

Evaluation and State:
- **MUST NOT** alter truth
- **ONLY** influence future thresholds, routing, and delivery modulation

---

## 3. State Register (θ_t)

### 3.1 State Vector Definition

```
θ_t = [τ^768_t, τ^175_t, w^tone_t, w^guna_t, b^policy_t]
```

| Component | Type | Range | Description |
|-----------|------|-------|-------------|
| `τ^768_t` | float | [0, 1] | Threshold for skipping 768-D embeddings |
| `τ^175_t` | float | [0, 1] | Threshold for escalating to 175B model |
| `w^tone_t` | [3] floats | Σ = 1 | Delivery tone weights [sweet, jolt, metaphor] |
| `w^guna_t` | [3] floats | Σ = 1 | Guna preference weights [S, R, T] |
| `b^policy_t` | float | [-B, +B] | Bounded bias for tie-breaks (B = 0.1) |

### 3.2 Default State (θ_0)

```python
DEFAULT_STATE = StateRegister(
    tau_768=0.5,
    tau_175=0.7,
    w_tone=(0.4, 0.3, 0.3),      # [sweet, jolt, metaphor]
    w_guna=(0.33, 0.34, 0.33),   # [S, R, T]
    b_policy=0.0,
)
```

### 3.3 Hard Bounds

```python
BOUNDS = StateBounds(
    tau_768_min=0.1,  tau_768_max=0.9,
    tau_175_min=0.3,  tau_175_max=0.95,
    b_policy_max=0.1,
)
```

---

## 4. Required Observables (Evaluation Inputs)

All signals are passed in from upstream pipeline stages:

### 4.1 Guna Distribution

```
g_t = [s_t, r_t, t_t],  where s_t + r_t + t_t = 1
```

Source: `GunaVector` from v2.6 Guna derivation

### 4.2 Guna Entropy (Normalized)

```
H_t = -Σ_{i∈{S,R,T}} g_{t,i} × ln(g_{t,i} + ε) / ln(3)
```

Range: [0, 1]
Source: Signal wiring (v2.6.1)

### 4.3 Semantic Motion

```
Δ^sem_t ∈ [0, 1]
```

Source: Signal wiring (v2.6.1)

### 4.4 Contradiction Metric

```
C^contr_t ∈ [0, 1]
```

Measures semantic contradiction detected in candidate selection.

### 4.5 Failure Metric

```
F^fail_t ∈ [0, 1]
```

Measures routing/delivery failure signals.

---

## 5. Policy Utility Function

### 5.1 Formula (Mandatory)

```
U_t = (c_S × w_S × s_t + c_R × w_R × r_t + c_T × w_T × t_t)
      + λ_H × H_t
      + λ_C × C^contr_t
      + λ_F × F^fail_t
```

### 5.2 Operator-Configurable Coefficients (Fix #1)

All utility coefficients are operator-configurable via `UtilityCoefficients`:

| Coefficient | Default | Range | Purpose |
|-------------|---------|-------|---------|
| `c_S` | +1.0 | [-3, +3] | Sattva contribution sign (+1 = reward) |
| `c_R` | -1.0 | [-3, +3] | Rajas contribution sign (-1 = penalty) |
| `c_T` | -1.0 | [-3, +3] | Tamas contribution sign (-1 = penalty) |
| `λ_H` | -0.3 | [-1, +1] | Entropy penalty (negative = penalize) |
| `λ_C` | -0.5 | [-1, +1] | Contradiction penalty |
| `λ_F` | -0.4 | [-1, +1] | Failure penalty |

**Validation:** `|c_S| + |c_R| + |c_T| ≤ 3` and `|λ_*| ≤ 1`

### 5.3 Configuration Example

```python
from symbolu.guna_modulation import UtilityCoefficients

# Default: Sattva positive, Rajas/Tamas negative
default = UtilityCoefficients()  # c_S=+1, c_R=-1, c_T=-1

# Custom: Neutral (all terms contribute equally)
neutral = UtilityCoefficients(c_S=1.0, c_R=1.0, c_T=1.0,
                               lambda_H=0.0, lambda_C=0.0, lambda_F=0.0)

# Custom: Rajas-positive for action-oriented deployments
action_oriented = UtilityCoefficients(c_S=0.5, c_R=0.8, c_T=-1.0)
```

### 5.4 Properties

- `U_t` is **not ethics** — it is policy-aligned operational utility
- All terms are logged for audit
- Range: approximately [-2, 1] depending on configuration
- **Operators can flip signs** to change the optimization objective

---

## 6. Deterministic Target State Computation

### 6.1 Target for 768-Skip Threshold

```
τ^768*_t = clip(τ^768_0 + a₁ × U_t - a₂ × H_t, [τ^768_min, τ^768_max])
```

| Constant | Value | Meaning |
|----------|-------|---------|
| `a₁` | 0.1 | Utility influence on skip threshold |
| `a₂` | 0.05 | Entropy influence on skip threshold |

**Interpretation:** Higher utility → more aggressive skipping; higher entropy → more conservative.

### 6.2 Target for 175B Escalation Threshold

```
τ^175*_t = clip(τ^175_0 - b₁ × (1 - U_t) - b₂ × C^contr_t, [τ^175_min, τ^175_max])
```

| Constant | Value | Meaning |
|----------|-------|---------|
| `b₁` | 0.08 | Low utility triggers easier escalation |
| `b₂` | 0.1 | Contradiction triggers easier escalation |

**Interpretation:** Lower utility or higher contradiction → lower threshold → more likely to escalate.

### 6.3 Target Tone Weights — Named Coefficients (Fix #3)

```
ℓ_sweet = k_sweet_sattva × s_t - k_sweet_tamas × t_t
ℓ_jolt = k_jolt_rajas × r_t + k_jolt_contr × C^contr_t
ℓ_metaphor = k_metaphor_entropy × H_t + k_metaphor_rajas × r_t

w^tone*_t = softmax([ℓ_sweet, ℓ_jolt, ℓ_metaphor])
```

All tone logit coefficients are named, bounded, and validated via `ToneLogitConfig`:

| Coefficient | Default | Range | Meaning |
|-------------|---------|-------|---------|
| `k_sweet_sattva` | 1.0 | [0, 2] | Sattva promotes calm delivery |
| `k_sweet_tamas` | 0.5 | [0, 2] | Tamas reduces calm delivery |
| `k_jolt_rajas` | 0.8 | [0, 2] | Rajas promotes energetic delivery |
| `k_jolt_contr` | 0.3 | [0, 2] | Contradiction promotes corrective energy |
| `k_metaphor_entropy` | 0.6 | [0, 2] | Entropy promotes abstract/poetic tone |
| `k_metaphor_rajas` | 0.4 | [0, 2] | Rajas also promotes metaphor |

**Validation:** All coefficients must be in [0, 2] to prevent extreme softmax outputs.

### 6.4 Tone Configuration Example

```python
from symbolu.guna_modulation import ToneLogitConfig

# Default configuration
default_tone = ToneLogitConfig()

# Custom: More responsive to contradictions
responsive = ToneLogitConfig(
    k_jolt_contr=0.8,      # Higher contradiction → jolt
    k_metaphor_entropy=0.9  # Higher entropy → metaphor
)
```

---

## 7. State Update Rule (The v2.7 Boundary)

### 7.1 Core Equation

```
θ_{t+1} = clip((1 - α) × θ_t + α × θ*_t, bounds)
```

### 7.2 Tier-Specific Alpha with Half-Life (Fix #2)

The learning rate α is tier-specific with documented half-life:

| Tier | Alpha (α) | Half-Life (updates) | 90% Decay | Use Case |
|------|-----------|---------------------|-----------|----------|
| Enterprise T1 | 0.02 | ~35 updates | ~115 updates | Ultra-stable, regulated environments |
| Enterprise T2 | 0.05 | ~14 updates | ~45 updates | Balanced stability and responsiveness |
| Consumer | 0.10 | ~7 updates | ~22 updates | Faster adaptation to user patterns |

**Half-Life Formula:**
```
t_½ = ln(0.5) / ln(1 - α) ≈ 0.693 / α
```

This means after t_½ updates, 50% of the original state remains.

### 7.3 Alpha Configuration Example

```python
from symbolu.guna_modulation import (
    AlphaConfig,
    ALPHA_ENTERPRISE_T1,
    ALPHA_ENTERPRISE_T2,
    ALPHA_CONSUMER,
    V27Config,
)

# Pre-configured tiers
enterprise_t1 = ALPHA_ENTERPRISE_T1  # α=0.02, t_½≈35
enterprise_t2 = ALPHA_ENTERPRISE_T2  # α=0.05, t_½≈14
consumer = ALPHA_CONSUMER            # α=0.10, t_½≈7

# Check decay properties
print(f"Half-life: {enterprise_t2.half_life_updates:.1f} updates")
print(f"After 10 updates: {enterprise_t2.decay_after_n(10):.1%} remains")

# Create engine for tier
from symbolu.guna_modulation import create_engine_for_tier
engine = create_engine_for_tier("enterprise_tier_2")
```

### 7.4 Properties

| Property | Value |
|----------|-------|
| `α` (learning rate) | Tier-specific (0.02, 0.05, or 0.10) |
| Randomness | None |
| Reversibility | Full (by decay toward θ_0) |
| Determinism | Guaranteed |

### 7.5 Component-wise Update

```python
tau_768_{t+1} = clip((1-α) × tau_768_t + α × tau_768*_t, bounds)
tau_175_{t+1} = clip((1-α) × tau_175_t + α × tau_175*_t, bounds)
w_tone_{t+1} = normalize((1-α) × w_tone_t + α × w_tone*_t)
w_guna_{t+1} = (1-α) × w_guna_t + α × w_guna_t  # Only changes via config
b_policy_{t+1} = clip((1-α) × b_policy_t + α × δ_policy, bounds)
```

Where `δ_policy = sign(U_t) × min(|U_t|, 0.01)` for small tie-break adjustments.

---

## 8. Version Gating (Mandatory)

### 8.1 Master Configuration

```python
@dataclass(frozen=True)
class V27Config:
    v2_7_enabled: bool = False  # Master switch
    alpha_config: AlphaConfig   # Tier-specific alpha
    utility_coefficients: UtilityCoefficients  # Fix #1
    tone_config: ToneLogitConfig  # Fix #3
    persistence_config: StatePersistenceConfig  # Fix #4
```

### 8.2 Pre-Built Configurations

```python
from symbolu.guna_modulation import (
    DEFAULT_V27_CONFIG,      # v2.7 disabled (v2.6 behavior)
    ENABLED_V27_CONFIG,      # v2.7 enabled, Enterprise T2
    ENTERPRISE_T1_CONFIG,    # α=0.02, ultra-stable
    ENTERPRISE_T2_CONFIG,    # α=0.05, balanced
    CONSUMER_CONFIG,         # α=0.10, responsive
)
```

### 8.3 Runtime Behavior (Fix #5: v2.6 vs v2.7)

```python
if not config.v2_7_enabled:
    # v2.6 behavior: STATELESS
    # - No temporal memory
    # - State remains constant
    # - Each query processed independently
    theta_{t+1} = theta_t
else:
    # v2.7 behavior: BOUNDED TEMPORAL MEMORY
    # - State evolves via deterministic EMA
    # - Bounded by hard limits (cannot drift arbitrarily)
    # - Reversible by decay toward θ_0
    # - Full audit trail maintained
    theta_{t+1} = update(theta_t, observables)
```

**Architectural Note:** v2.7 introduces bounded temporal memory. This is a deliberate departure from v2.6's stateless model. See Section 14 for detailed comparison.

**Constraint:** Flag is checked at **runtime**, not compile time.

---

## 9. Audit & Explainability

### 9.1 Required Emissions

Every update MUST emit:

```python
@dataclass(frozen=True)
class StateUpdateAudit:
    # Observed signals
    guna: GunaVector           # g_t = [s, r, t]
    entropy: float             # H_t
    semantic_motion: float     # Δ^sem_t
    contradiction: float       # C^contr_t
    failure: float             # F^fail_t

    # Computed values
    utility: float             # U_t
    target_state: StateRegister  # θ*_t

    # Applied changes
    delta_theta: StateDelta    # θ_{t+1} - θ_t
    rules_fired: List[str]     # Rule IDs

    # Timestamps
    timestamp: str
    run_id: str
```

### 9.2 Example Audit Output

```json
{
  "tau_175_delta": -0.04,
  "reason": "U_t = 0.31, C_contr = 0.62",
  "rule_id": "RULE_HIGH_CONTRADICTION_TIGHTEN_175B",
  "explanation": "tau_175 decreased by 0.04 because contradiction metric (0.62) exceeded threshold"
}
```

---

## 10. State Persistence (Fix #4)

### 10.1 Persistence Configuration

State persistence is explicit, scoped, and decay-governed via `StatePersistenceConfig`:

```python
@dataclass(frozen=True)
class StatePersistenceConfig:
    scope: str = "tenant"              # global | tenant | user | session
    decay_on_restart: bool = True       # Apply decay when system restarts
    restart_decay_factor: float = 0.5   # How much state to preserve (0=reset, 1=keep)
    max_state_age_hours: int = 168      # Reset stale state after 7 days
    storage_backend: str = "memory"     # memory | redis | postgres
```

### 10.2 Scope Semantics

| Scope | Meaning | Use Case |
|-------|---------|----------|
| `global` | Single state for entire system | Single-tenant deployments |
| `tenant` | Separate state per tenant | Multi-tenant SaaS |
| `user` | Separate state per user | Personalized responses |
| `session` | State per session only | Stateless-by-default |

### 10.3 Restart Decay

On system restart, state is decayed toward default:

```
θ_restart = factor × θ_saved + (1 - factor) × θ_0
```

| Factor | Effect |
|--------|--------|
| 0.0 | Full reset to θ_0 |
| 0.5 | 50% preserved, 50% reset (default) |
| 1.0 | No decay (full preservation) |

### 10.4 Persistence Configuration Example

```python
from symbolu.guna_modulation import (
    StatePersistenceConfig,
    PERSISTENCE_GLOBAL,
    PERSISTENCE_TENANT,
    PERSISTENCE_USER,
    PERSISTENCE_SESSION,
)

# Session-scoped (no persistence)
session_config = PERSISTENCE_SESSION  # decay_on_restart=False

# Tenant-scoped with Redis backend
production_config = StatePersistenceConfig(
    scope="tenant",
    decay_on_restart=True,
    restart_decay_factor=0.7,  # Preserve 70%
    max_state_age_hours=336,   # 2 weeks
    storage_backend="redis",
)
```

---

## 11. Explicit Non-Capabilities

This layer:

| Property | Status |
|----------|--------|
| Stochastic learning | **PROHIBITED** |
| Gradient updates | **PROHIBITED** |
| Reinforcement learning | **PROHIBITED** |
| Moral truth computation | **PROHIBITED** |
| Psychological belief modeling | **PROHIBITED** |
| User preference learning | **PROHIBITED** |
| Truth modification | **PROHIBITED** |
| Unbounded state drift | **PROHIBITED** |

All state changes are:
- Rule-bound
- Formula-driven
- Logged
- Reversible
- Bounded

---

## 12. Determinism Proof

### 12.1 Theorem

Given identical inputs `(θ_t, observables)`, the system produces identical `θ_{t+1}`.

### 12.2 Proof

1. All formulas are pure mathematical operations
2. No randomness in any computation path
3. `clip()` and `softmax()` are deterministic functions
4. State update equation has no stochastic terms
5. Same `α`, same bounds, same constants

### 12.3 Test Assertion

```python
def test_determinism():
    state = DEFAULT_STATE
    observables = Observables(s=0.5, r=0.3, t=0.2, H=0.4, ...)

    result1 = update_state(state, observables, config)
    result2 = update_state(state, observables, config)

    assert result1 == result2  # Must be identical

    for _ in range(1000):
        result_n = update_state(state, observables, config)
        assert result_n == result1
```

---

## 13. Implementation Files

| File | Purpose |
|------|---------|
| `state_types.py` | State register and bounds definitions |
| `observables.py` | Observable signals container |
| `utility.py` | Policy utility computation |
| `v27_config.py` | Configuration (coefficients, tiers, persistence) |
| `state_evolution_engine.py` | State update engine |

---

## 14. Data Schemas

### 14.1 StateRegister

```python
@dataclass(frozen=True)
class StateRegister:
    tau_768: float      # [0.1, 0.9]
    tau_175: float      # [0.3, 0.95]
    w_tone: Tuple[float, float, float]   # Σ = 1
    w_guna: Tuple[float, float, float]   # Σ = 1
    b_policy: float     # [-0.1, 0.1]
```

### 14.2 Observables

```python
@dataclass(frozen=True)
class Observables:
    s: float            # Sattva [0, 1]
    r: float            # Rajas [0, 1]
    t: float            # Tamas [0, 1]
    H: float            # Entropy [0, 1]
    delta_sem: float    # Semantic motion [0, 1]
    C_contr: float      # Contradiction [0, 1]
    F_fail: float       # Failure [0, 1]
```

### 14.3 V27Config (Updated with Fixes #1-4)

```python
@dataclass(frozen=True)
class V27Config:
    v2_7_enabled: bool = False
    alpha_config: AlphaConfig           # Fix #2: Tier-specific alpha
    utility_coefficients: UtilityCoefficients  # Fix #1: Operator-configurable signs
    tone_config: ToneLogitConfig        # Fix #3: Named, bounded coefficients
    persistence_config: StatePersistenceConfig  # Fix #4: Scoped persistence

    @property
    def alpha(self) -> float: ...
    @property
    def tier(self) -> str: ...
    @property
    def half_life(self) -> float: ...
```

---

## 15. v2.6 vs v2.7 Comparison (Fix #5)

### 15.1 Architectural Difference

| Aspect | v2.6 | v2.7 |
|--------|------|------|
| **State** | Stateless | Bounded temporal memory |
| **Query Processing** | Independent | Context-influenced |
| **Memory** | None | Low-pass filter over observables |
| **Drift** | Impossible | Bounded by hard limits |
| **Audit** | Input/output only | Full state history |

### 15.2 What v2.7 Temporal State IS

- A **low-pass filter** over observable signals
- **Bounded** by hard limits (cannot drift arbitrarily)
- **Reversible** by decay toward θ_0
- **Deterministic** given the same history
- Aggregate statistics only (no memory of specific queries)

### 15.3 What v2.7 Temporal State is NOT

- ❌ Stochastic learning (no gradient updates)
- ❌ Preference formation (no evaluation of "good" outcomes)
- ❌ Memory of specific queries
- ❌ Psychology or user modeling
- ❌ Unbounded adaptation

### 15.4 Enterprise Implication

If `v2_7_enabled=True`, the system's behavior at time t depends on prior observations:

```python
# v2.6: Each query processed identically
result_1 = process_query(query, config)  # Uses DEFAULT_STATE
result_2 = process_query(query, config)  # Uses DEFAULT_STATE (same)

# v2.7: State evolves based on observations
engine = StateEvolutionEngine(ENABLED_V27_CONFIG)
result_1 = engine.update(observables_1)  # Updates state
result_2 = engine.update(observables_2)  # Uses evolved state
```

Audit trails include full state history for reproducibility.

---

## 16. Layman Explanation

> "The system already knows the answer.
> v2.7 only adjusts its internal knobs using fixed rules, so next time it knows how strongly, how cautiously, and how deeply to act — and it can always explain why."

---

## 17. Final Constraint

If a behavior cannot be expressed as a **closed-form formula**, it must be **excluded**.

---

*End of v2.7.1 Specification*
