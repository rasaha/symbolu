# SymbolU v2.7 — Deterministic Evaluation & State Evolution Layer

**Symbol-U v2.7 — Deterministic, Zero-Parameter, Non-Learning System**

**Date:** 2025-12-22
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
U_t = w_S × s_t - w_R × r_t - w_T × t_t
      - λ_H × H_t
      - λ_C × C^contr_t
      - λ_F × F^fail_t
```

### 5.2 Fixed Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `λ_H` | 0.3 | Entropy penalty coefficient |
| `λ_C` | 0.5 | Contradiction penalty coefficient |
| `λ_F` | 0.4 | Failure penalty coefficient |

### 5.3 Properties

- `U_t` is **not ethics** — it is policy-aligned operational utility
- All terms are logged for audit
- Range: approximately [-2, 1] depending on configuration

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

### 6.3 Target Tone Weights (Softmax)

```
ℓ_sweet = k₁ × s_t - k₂ × t_t
ℓ_jolt = k₃ × r_t + k₄ × C^contr_t
ℓ_metaphor = k₅ × H_t + k₆ × r_t

w^tone*_t = softmax([ℓ_sweet, ℓ_jolt, ℓ_metaphor])
```

| Constant | Value | Meaning |
|----------|-------|---------|
| `k₁` | 1.0 | Sattva promotes sweetness |
| `k₂` | 0.5 | Tamas reduces sweetness |
| `k₃` | 0.8 | Rajas promotes jolt |
| `k₄` | 0.3 | Contradiction promotes jolt |
| `k₅` | 0.6 | Entropy promotes metaphor |
| `k₆` | 0.4 | Rajas also promotes metaphor |

---

## 7. State Update Rule (The v2.7 Boundary)

### 7.1 Core Equation

```
θ_{t+1} = clip((1 - α) × θ_t + α × θ*_t, bounds)
```

### 7.2 Properties

| Property | Value |
|----------|-------|
| `α` (learning rate) | 0.05 (fixed) |
| Randomness | None |
| Reversibility | Full (by decay toward θ_0) |
| Determinism | Guaranteed |

### 7.3 Component-wise Update

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

### 8.1 Configuration Flag

```python
class V27Config:
    v2_7_enabled: bool = False  # Default: behave like v2.6
    alpha: float = 0.05
    # ... other constants
```

### 8.2 Runtime Behavior

```python
if not config.v2_7_enabled:
    # v2.6 behavior: state remains constant
    theta_{t+1} = theta_t
    # Update equation does NOT execute
else:
    # v2.7 behavior: deterministic state evolution
    theta_{t+1} = update(theta_t, observables)
    # All updates logged and auditable
```

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

## 10. Explicit Non-Capabilities

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

## 11. Determinism Proof

### 11.1 Theorem

Given identical inputs `(θ_t, observables)`, the system produces identical `θ_{t+1}`.

### 11.2 Proof

1. All formulas are pure mathematical operations
2. No randomness in any computation path
3. `clip()` and `softmax()` are deterministic functions
4. State update equation has no stochastic terms
5. Same `α`, same bounds, same constants

### 11.3 Test Assertion

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

## 12. Implementation Files

| File | Purpose |
|------|---------|
| `state_types.py` | State register and bounds definitions |
| `observables.py` | Observable signals container |
| `utility.py` | Policy utility computation |
| `target_computation.py` | Target state formulas |
| `state_evolution_engine.py` | State update engine |
| `audit.py` | Audit trail generation |

---

## 13. Data Schemas

### 13.1 StateRegister

```python
@dataclass(frozen=True)
class StateRegister:
    tau_768: float      # [0.1, 0.9]
    tau_175: float      # [0.3, 0.95]
    w_tone: Tuple[float, float, float]   # Σ = 1
    w_guna: Tuple[float, float, float]   # Σ = 1
    b_policy: float     # [-0.1, 0.1]
```

### 13.2 Observables

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

### 13.3 V27Config

```python
@dataclass(frozen=True)
class V27Config:
    v2_7_enabled: bool = False
    alpha: float = 0.05
    lambda_H: float = 0.3
    lambda_C: float = 0.5
    lambda_F: float = 0.4
    # ... other constants
```

---

## 14. Layman Explanation

> "The system already knows the answer.
> v2.7 only adjusts its internal knobs using fixed rules, so next time it knows how strongly, how cautiously, and how deeply to act — and it can always explain why."

---

## 15. Final Constraint

If a behavior cannot be expressed as a **closed-form formula**, it must be **excluded**.

---

*End of v2.7 Specification*
