# Guna Entropy Modulation — Formal Engineering Specification

**Symbol-U v2.6.1 — Deterministic, Zero-Parameter, Non-Learning System**

**Date:** 2025-12-22
**Status:** Implementation Complete (Core + Signal Wiring + Pipeline Adapter)
**Classification:** Enterprise-Safe, Patent-Aligned

---

## 1. Overview

This document specifies a Guna-aware entropy modulation layer for SymbolU v2.6.

The layer operates **after truth is computed**, controlling only **delivery intensity**, not **meaning**.

---

## 2. System Context

### 2.1 Non-Negotiable Constraints

This system:
- Is **Augmented General Intelligence**, not AGI
- **Prohibits** learning, adaptation, preference formation, evaluation, or memory
- Requires all behavior to be expressed as **closed-form formulas**
- Treats configuration as **operator-supplied constants**, not intelligence
- Preserves **C × R × S semantic truth computation unchanged**

### 2.2 Explicit Non-Capabilities

This layer:
- **No learning**
- **No adaptation**
- **No state memory**
- **No evaluation of "better" or "worse"**
- **No psychology**
- **No morality**
- **No feedback loops**
- **No preference formation**

This layer is **scalar modulation only**.

---

## 3. Canonical Output Equation

```
OUTPUT_intensity = BASE_intensity × E
```

Where:
- `BASE_intensity` is already computed by STL + routing + (optional) AGI
- `E` is a scalar entropy modulation factor
- **`BASE_intensity` MUST NOT be altered** (only scaled)

---

## 4. Entropy Modulation Factor

```
E = G × P × T
```

No additional terms are permitted.

---

## 5. Guna Derivation (Mandatory Formulas)

### 5.1 Inputs (Wired from Pipeline — See Section 5A)

All inputs are deterministic and wired from existing pipeline signals:

| Symbol | Meaning                          | Range   | Source |
|--------|----------------------------------|---------|--------|
| C_s    | Structural coherence             | [0, 1]  | Coherence engine |
| M      | Motion / transformation magnitude| [0, 1]  | Signal wiring (§5A) |
| H      | Entropy                          | [0, 1]  | Signal wiring (§5A) |

### 5.2 Constants (Fixed)

```
H_mid = 0.5
ε = 10⁻⁹
```

### 5.3 Raw Guna Components

```
S_raw = C_s × (1 - H)
R_raw = M × (1 - |H - H_mid|)
T_raw = H × (1 - C_s)
```

### 5.4 Normalization

```
Z = S_raw + R_raw + T_raw + ε

S = S_raw / Z
R = R_raw / Z
T = T_raw / Z
```

**Constraint:** `S + R + T = 1`

### 5.5 Guna Vector

```
g = [S, R, T]
```

This vector:
- Is **descriptive only**
- Is **not evaluative**
- Carries **no moral meaning**
- Is **not learned**
- Is **not stored**
- Is **not fed back**

---

## 5A. Signal Wiring (v2.6.1)

This section specifies how **H** (entropy) and **M** (motion) are wired from existing pipeline signals.

### 5A.1 Entropy (H) Computation

H is computed from **operator-selectable** entropy sources:

| Mode | Formula | Source Signal | Max Value |
|------|---------|---------------|-----------|
| **GUNA** (default) | `H = H_G / ln(3)` | `RouterContext.H_G` | ln(3) ≈ 1.099 |
| DIMENSIONAL | `H = H_D / ln(10)` | `RouterContext.H_D` | ln(10) ≈ 2.303 |
| KOSHA | `H = H_K / ln(5)` | `RouterContext.H_K` | ln(5) ≈ 1.609 |

**Normalization:** Result is clamped to [0, 1].

**Determinism:** Mode is operator-configured, not inferred.

### 5A.2 Motion (M) Computation

M is computed from **operator-selectable** motion modes:

| Mode | Formula | Description |
|------|---------|-------------|
| **SEMANTIC** (default) | `M = Δ_sem` | Semantic distance between vectors |
| STRUCTURAL | `M = Δ_str_norm` | Normalized structural jumps |
| EXPERIENTIAL | `M = Δ_exp` | Intent-based (0 or 1) |
| COMPOSITE | `M = Σ(w_i × Δ_i) / Σw_i` | Weighted average |

### 5A.3 Delta Component Definitions

#### Semantic Delta (Δ_sem)

```
Δ_sem = 1 - cosine_similarity(query_aspect_probs, candidate_aspect_probs)
```

- Source: `RouterContext.aspect_probs` (query) vs candidate aspect probs
- Range: [0, 1]
- Identical vectors → 0 (no motion)
- Orthogonal vectors → 1 (max motion)

#### Structural Delta (Δ_str_norm)

```
Δ_str_norm = min(cross_domain_count, MAX_JUMPS) / MAX_JUMPS
```

- Source: `StitchingDecision.diagnostics["cross_domain_count"]`
- MAX_JUMPS = 5 (constant)
- Range: [0, 1]

#### Experiential Delta (Δ_exp)

```
Δ_exp = 1 if intent ∈ {COMMAND, SHOULD, REFLECTION} else 0
```

- Source: `ActivationPlan.intent` (IntentType enum)
- Binary: 0 or 1
- Experiential intents represent transformative delivery postures

### 5A.4 Signal Source Mapping (Pipeline Adapter)

The pipeline adapter wires to **existing** signals rather than recomputing:

| Signal | Pipeline Source | Component |
|--------|-----------------|-----------|
| H_G | `RouterContext.H_G` | TTOR |
| H_D | `RouterContext.H_D` | TTOR |
| H_K | `RouterContext.H_K` | TTOR |
| Δ_sem | `cosine_similarity()` from aspect_probs | similarity.py |
| Δ_str | `StitchingDecision.diagnostics["cross_domain_count"]` | Stitching |
| Δ_exp | `ActivationPlan.intent` (IntentType enum) | MLCR |

### 5A.5 Wiring Configuration

```python
SignalWiringConfig(
    entropy_mode=EntropyMode.GUNA,        # H source selection
    motion_mode=MotionMode.SEMANTIC,       # M computation mode
    composite_weights=(1.0, 1.0, 1.0),     # For COMPOSITE mode only
)
```

All configuration is **operator-supplied constants** — no inference, no learning.

---

## 6. Guna Coefficient (G)

```
G = w_S × S + w_R × R + w_T × T
```

Where:
- `w_S`, `w_R`, `w_T` are **operator-configured constants**
- No defaults imply good/bad
- No inference is allowed

**Example configuration (illustrative only):**
```
w_S = 0.9
w_R = 1.05
w_T = 0.6
```

---

## 7. Policy Scalar (P)

```
P = clamp(1 - r_risk - r_escalation, 0, 1)
```

Where:
- `r_risk`, `r_escalation` are **operator-supplied constants**
- No interpretation or judgment is allowed

---

## 8. Tier Scalar (T)

Fixed system constant:

| Tier               | T Value |
|--------------------|---------|
| Enterprise Tier 1  | 1.0     |
| Enterprise Tier 2  | 0.9     |
| Consumer Tier      | 0.85    |

---

## 9. Final Intensity Equation

```
OUTPUT_intensity = BASE_intensity × (w_S × S + w_R × R + w_T × T) × P × T
```

No additional logic is allowed.

---

## 10. Pipeline Placement

```
Input
 → STL (10D symbolic reasoning)
 → Canonical Matching (C × R × S)
 → Tier Routing (TTOR)
    └─→ Provides: H_G, H_D, H_K, aspect_probs
 → Stitching
    └─→ Provides: cross_domain_count
 → Fusion / MLCR
    └─→ Provides: IntentType
 → AGI Augmentation (optional)
 ─────────────────────────────────────
 → Signal Wiring (v2.6.1)
    ├─→ Compute H from RouterContext
    └─→ Compute M from pipeline signals
 → Guna Derivation (FORMULAS ABOVE)
 → Entropy Modulation (E = G × P × T)
 ─────────────────────────────────────
 → Renderer
 → Output
```

**Key Principle:** Signal wiring reads from existing pipeline stages; it does not modify upstream computation.

---

## 11. Determinism & Audit Requirements

### 11.1 Determinism Proof

Same inputs → same `S`, `R`, `T`, `G`, `E`, `OUTPUT`

The implementation guarantees:
- All formulas are pure mathematical operations
- No randomness, no stochastic elements
- No external state dependencies
- No time-dependent behavior

### 11.2 Disable Proof

If `w_S = w_R = w_T = 1` and `P = T = 1`, output is unchanged.

**Proof:**
1. With neutral weights: `G = 1×S + 1×R + 1×T = S + R + T = 1` (normalized)
2. With zero policy risk: `P = clamp(1 - 0 - 0, 0, 1) = 1`
3. With Tier 1 scalar override: `T = 1`
4. Therefore: `E = G × P × T = 1 × 1 × 1 = 1`
5. Therefore: `OUTPUT_intensity = BASE_intensity × 1 = BASE_intensity`

### 11.3 Audit Trace Example

**Raw Pipeline Inputs:**
```
H_G = 0.33 (from RouterContext)
H_D = 1.15 (from RouterContext)
H_K = 0.80 (from RouterContext)
query_aspect_probs = {"clarity": 0.8, "depth": 0.6}
candidate_aspect_probs = {"clarity": 0.7, "depth": 0.5}
cross_domain_count = 1
intent_type = "WHAT"
C_s = 0.7
BASE_intensity = 0.8
```

**Step 0: Signal Wiring (GUNA + SEMANTIC modes)**
```
# Entropy (H)
H = H_G / ln(3) = 0.33 / 1.099 ≈ 0.30

# Motion (M) - Semantic Delta
cosine_sim = dot(query, cand) / (|query| × |cand|)
           = (0.8×0.7 + 0.6×0.5) / (1.0 × 0.86) ≈ 0.997
Δ_sem = 1 - 0.997 ≈ 0.003
M = Δ_sem ≈ 0.003 (very similar vectors → low motion)
```

**Wired Values:**
```
H = 0.30
M = 0.003
C_s = 0.7
```

**Step 1: Raw Guna Components**
```
S_raw = C_s × (1 - H) = 0.7 × (1 - 0.30) = 0.7 × 0.70 = 0.490
R_raw = M × (1 - |H - 0.5|) = 0.003 × (1 - 0.20) = 0.003 × 0.80 = 0.0024
T_raw = H × (1 - C_s) = 0.30 × (1 - 0.7) = 0.30 × 0.30 = 0.090
```

**Step 2: Normalization**
```
Z = 0.490 + 0.0024 + 0.090 + 10⁻⁹ ≈ 0.5824
S = 0.490 / 0.5824 ≈ 0.841
R = 0.0024 / 0.5824 ≈ 0.004
T = 0.090 / 0.5824 ≈ 0.155
```

Note: Low motion (M ≈ 0) suppresses Rajas, increasing Sattva dominance.

**Step 3: Guna Coefficient (with default weights)**
```
G = 0.9 × 0.841 + 1.05 × 0.004 + 0.6 × 0.155
G = 0.757 + 0.004 + 0.093 = 0.854
```

**Step 4: Policy Scalar (with zero risk)**
```
P = clamp(1 - 0 - 0, 0, 1) = 1.0
```

**Step 5: Tier Scalar (Enterprise Tier 1)**
```
T_tier = 1.0
```

**Step 6: Entropy Modulation Factor**
```
E = G × P × T_tier = 0.854 × 1.0 × 1.0 = 0.854
```

**Step 7: Output Intensity**
```
OUTPUT_intensity = 0.8 × 0.854 = 0.683
```

**Interpretation:** High coherence + low motion + moderate entropy → Sattva-dominant response with slightly reduced intensity.

---

## 12. Layman Explanation

> "The system already knows the answer.
> This layer only controls how strongly it speaks, using fixed mathematical knobs — like a volume control, not thinking."

---

## 13. Implementation Files

### 13.1 Core Modulation

| File | Purpose |
|------|---------|
| `types.py` | Type definitions (frozen dataclasses) |
| `config.py` | Tier configurations and constants |
| `guna_derivation.py` | Guna vector derivation formulas |
| `entropy_modulation_engine.py` | Main engine implementation |

### 13.2 Signal Wiring (v2.6.1)

| File | Purpose |
|------|---------|
| `signal_wiring.py` | H and M computation with operator-selectable modes |
| `pipeline_integration.py` | Integration layer connecting wiring to engine |
| `pipeline_signal_adapter.py` | Adapter wiring to existing pipeline signals |

### 13.3 Module Interface

| File | Purpose |
|------|---------|
| `__init__.py` | Module exports and convenience aliases |
| `SPEC.md` | This specification document |

### 13.4 Test Coverage

| Test File | Count | Purpose |
|-----------|-------|---------|
| `test_guna_derivation.py` | 21 | Guna formula verification |
| `test_entropy_modulation_engine.py` | 34 | Engine and E computation |
| `test_signal_wiring.py` | 66 | H/M wiring and modes |
| `test_pipeline_signal_adapter.py` | 50 | Pipeline adapter functions |
| `test_signal_wiring_integration.py` | 37 | End-to-end integration |
| **Total** | **208** | All determinism verified |

---

## 14. Usage Examples

### 14.1 Direct Modulation (Pre-computed H, M)

```python
from symbolu.guna_modulation import (
    EntropyModulationEngine,
    TIER_1_MODULATION_CONFIG,
    modulate_intensity,
)

# Using the engine
engine = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)
result = engine.modulate(
    base_intensity=0.8,
    C_s=0.7,  # Structural coherence
    M=0.5,    # Motion magnitude
    H=0.3,    # Entropy
)
print(f"Output Intensity: {result.output_intensity}")
print(f"Modulation Factor E: {result.E}")

# Using the standalone function
result = modulate_intensity(
    base_intensity=0.8,
    C_s=0.7,
    M=0.5,
    H=0.3,
)
```

### 14.2 Pipeline Integration (Wired H, M)

```python
from symbolu.guna_modulation import (
    PipelineModulationEngine,
    EntropyMode,
    MotionMode,
    SignalWiringConfig,
)

# Create engine with signal wiring configuration
engine = PipelineModulationEngine(
    wiring_config=SignalWiringConfig(
        entropy_mode=EntropyMode.GUNA,      # H = H_G / ln(3)
        motion_mode=MotionMode.SEMANTIC,    # M = Δ_sem
    ),
)

# Modulate with pipeline signals
result = engine.modulate_from_pipeline(
    base_intensity=0.8,
    C_s=0.7,
    # Entropy sources (from RouterContext)
    H_G=0.5, H_D=1.0, H_K=0.3,
    # Motion sources
    candidate_aspect_vector={"clarity": 0.8, "depth": 0.6},
    context_aspect_vector={"clarity": 0.7, "depth": 0.7},
    domain_jump_count=2,
    intent="informative",
)

print(f"Wired H: {result.H}")
print(f"Wired M: {result.M}")
print(f"Output: {result.output_intensity}")
```

### 14.3 Pipeline Adapter (From Existing Signals)

```python
from symbolu.guna_modulation import (
    PipelineSignalContext,
    wire_from_pipeline_context,
    modulate_from_pipeline_context,
    SignalWiringConfig,
)

# Aggregate signals from pipeline stages
context = PipelineSignalContext(
    # From RouterContext (TTOR)
    H_G=0.8, H_D=1.5, H_K=1.0,
    query_aspect_probs={"clarity": 0.7, "depth": 0.5},
    # From ActivationPlan (MLCR)
    intent_type="COMMAND",
    # From StitchingDecision
    cross_domain_count=2,
    # From Candidate
    candidate_aspect_probs={"clarity": 0.8, "depth": 0.4},
    # From Coherence
    C_s=0.75,
)

# Wire signals
wired = wire_from_pipeline_context(context, SignalWiringConfig())
print(f"H: {wired.H}, M: {wired.M}")

# Or complete modulation in one step
result = modulate_from_pipeline_context(
    base_intensity=0.8,
    context=context,
)
print(f"Output: {result.output_intensity}")
```

### 14.4 Audit Trail Access

```python
# All results include complete audit trails
print(result.wired_signals.audit.entropy_audit.entropy_mode)  # "guna"
print(result.wired_signals.audit.motion_audit.motion_mode)    # "semantic"
print(result.modulation_result.trace)  # Full computation trace
```

---

## 15. Classification

This implementation is:
- **SymbolU v2.6**
- **Deterministic**
- **Non-normative**
- **Enterprise-safe**
- **Patent-aligned**

---

## 16. Final Constraint

If a behavior cannot be expressed as a **closed-form formula**, it must be **excluded**.

---

*End of Specification*
