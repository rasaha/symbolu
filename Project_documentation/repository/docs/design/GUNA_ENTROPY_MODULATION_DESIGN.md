# Guna Entropy Modulation — Comprehensive Design Document

**Symbol-U v2.6 — Deterministic, Zero-Parameter, Non-Learning System**

| Attribute | Value |
|-----------|-------|
| Version | 2.6.0 |
| Date | 2025-12-22 |
| Status | Implementation Complete |
| Classification | Enterprise-Safe, Patent-Aligned |
| Author | Symbol-U Engineering |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Design Goals](#3-design-goals)
4. [System Context](#4-system-context)
5. [Architecture Overview](#5-architecture-overview)
6. [Detailed Design](#6-detailed-design)
7. [Mathematical Specification](#7-mathematical-specification)
8. [Implementation Architecture](#8-implementation-architecture)
9. [Configuration System](#9-configuration-system)
10. [Audit & Observability](#10-audit--observability)
11. [Testing Strategy](#11-testing-strategy)
12. [Security Considerations](#12-security-considerations)
13. [Performance Analysis](#13-performance-analysis)
14. [Deployment Guide](#14-deployment-guide)
15. [Future Considerations](#15-future-considerations)
16. [Appendices](#16-appendices)

---

## 1. Executive Summary

### 1.1 Purpose

This document describes the design and implementation of a **Guna-aware entropy modulation layer** for Symbol-U v2.6. The layer provides deterministic, formula-driven control over delivery intensity without affecting semantic content or truth computation.

### 1.2 Key Characteristics

| Characteristic | Description |
|----------------|-------------|
| **Deterministic** | Same inputs always produce same outputs |
| **Zero-Parameter** | No learned weights or adaptive parameters |
| **Non-Learning** | No training, adaptation, or memory |
| **Formula-Driven** | All behavior expressed as closed-form equations |
| **Enterprise-Safe** | Auditable, predictable, compliant |

### 1.3 Core Equation

```
OUTPUT_intensity = BASE_intensity × E

Where: E = G × P × T
```

### 1.4 Layman Explanation

> "The system already knows the answer. This layer only controls how strongly it speaks, using fixed mathematical knobs — like a volume control, not thinking."

---

## 2. Problem Statement

### 2.1 Business Need

Enterprise and consumer applications require controlled delivery intensity that:

1. **Varies by tier** — Enterprise customers need full-intensity responses; consumer tier may need moderated delivery
2. **Responds to context** — High-entropy or high-risk contexts warrant intensity adjustment
3. **Remains auditable** — Every intensity decision must be traceable and explainable
4. **Preserves truth** — Intensity modulation must never alter semantic meaning

### 2.2 Technical Requirements

| Requirement | Rationale |
|-------------|-----------|
| Closed-form formulas only | Ensures reproducibility and auditability |
| No learned parameters | Eliminates training drift and non-determinism |
| No state memory | Prevents context leakage between requests |
| Operator-configurable | Allows tier-specific and policy-specific tuning |
| Full audit trail | Regulatory compliance and debugging |

### 2.3 Constraints

The system explicitly **prohibits**:

- Learning or adaptation
- Preference formation
- Psychological inference
- Moral judgment
- Evaluation of "better" or "worse"
- Feedback loops
- State memory across requests

---

## 3. Design Goals

### 3.1 Primary Goals

| Goal | Priority | Metric |
|------|----------|--------|
| **Determinism** | Critical | 100% reproducibility |
| **Auditability** | Critical | Complete trace for every computation |
| **Disable-ability** | Critical | Neutral config produces E=1 (no effect) |
| **Performance** | High | < 1ms computation overhead |
| **Simplicity** | High | Minimal cognitive load for operators |

### 3.2 Non-Goals

- **Semantic modification** — This layer does not change meaning
- **Content filtering** — This is not a safety/policy layer
- **Learning** — No adaptive behavior whatsoever
- **Personalization** — No user-specific adjustments

---

## 4. System Context

### 4.1 Symbol-U Architecture Position

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SYMBOL-U v2.6 PIPELINE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐                                                            │
│  │   INPUT     │                                                            │
│  └──────┬──────┘                                                            │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              STL (10D Symbolic Reasoning)                            │   │
│  │                                                                      │   │
│  │   Computes: Structural coherence (C_s), Motion (M), Entropy (H)     │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │           Canonical Matching (C × R × S)                             │   │
│  │                                                                      │   │
│  │   Computes: Truth, Ranking, Eligibility                              │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Tier Routing                                    │   │
│  │                                                                      │   │
│  │   Routes to: Enterprise Tier 1 | Tier 2 | Consumer                   │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │               AGI Augmentation (Optional)                            │   │
│  │                                                                      │   │
│  │   Produces: BASE_intensity                                           │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │    ╔═══════════════════════════════════════════════════════════╗    │   │
│  │    ║         GUNA ENTROPY MODULATION (THIS LAYER)              ║    │   │
│  │    ║                                                           ║    │   │
│  │    ║   Inputs:  C_s, M, H, BASE_intensity                      ║    │   │
│  │    ║   Outputs: OUTPUT_intensity = BASE_intensity × E          ║    │   │
│  │    ║                                                           ║    │   │
│  │    ║   Where:   E = G × P × T                                  ║    │   │
│  │    ╚═══════════════════════════════════════════════════════════╝    │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Renderer                                      │   │
│  │                                                                      │   │
│  │   Applies: OUTPUT_intensity to final response                        │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────┐                                                            │
│  │   OUTPUT    │                                                            │
│  └─────────────┘                                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Data Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FROM UPSTREAM PIPELINE:                                                     │
│  ───────────────────────                                                     │
│    C_s ─────────────────┐                                                    │
│    (Structural          │                                                    │
│     Coherence)          │                                                    │
│                         ▼                                                    │
│    M ──────────────────►┌────────────────────┐                               │
│    (Motion/             │                    │                               │
│     Transformation)     │  GUNA DERIVATION   │──────► [S, R, T]              │
│                         │                    │        (Guna Vector)          │
│    H ──────────────────►└────────────────────┘                               │
│    (Entropy)                     │                                           │
│                                  │                                           │
│                                  ▼                                           │
│  FROM OPERATOR CONFIG:    ┌────────────────────┐                             │
│  ─────────────────────    │                    │                             │
│    w_S, w_R, w_T ────────►│  GUNA COEFFICIENT  │──────► G                    │
│    (Guna Weights)         │                    │                             │
│                           └────────────────────┘                             │
│                                  │                                           │
│                                  ▼                                           │
│    r_risk ─────────────┐  ┌────────────────────┐                             │
│    r_escalation ───────┼─►│   POLICY SCALAR    │──────► P                    │
│    (Policy Factors)    │  │                    │                             │
│                        │  └────────────────────┘                             │
│                        │         │                                           │
│                        │         ▼                                           │
│    Tier ───────────────┼──┌────────────────────┐                             │
│    (System Tier)       │  │    TIER SCALAR     │──────► T                    │
│                        │  │                    │                             │
│                        │  └────────────────────┘                             │
│                        │         │                                           │
│                        │         ▼                                           │
│                        │  ┌────────────────────┐                             │
│                        │  │                    │                             │
│                        └─►│  E = G × P × T     │──────► E                    │
│                           │                    │        (Modulation Factor)  │
│                           └────────────────────┘                             │
│                                  │                                           │
│                                  ▼                                           │
│  FROM PIPELINE:           ┌────────────────────┐                             │
│  ──────────────           │                    │                             │
│    BASE_intensity ───────►│  OUTPUT = BASE × E │──────► OUTPUT_intensity     │
│                           │                    │                             │
│                           └────────────────────┘                             │
│                                                                              │
│  TO RENDERER:                                                                │
│  ────────────                                                                │
│    OUTPUT_intensity ────────────────────────────────────► (Final Intensity)  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Architecture Overview

### 5.1 Module Structure

```
symbolu/guna_modulation/
├── __init__.py                    # Public API exports
├── types.py                       # Frozen dataclass definitions
├── config.py                      # Tier configurations
├── guna_derivation.py             # Guna vector computation
├── entropy_modulation_engine.py   # Main engine
└── SPEC.md                        # Formal specification

tests/unit/guna_modulation/
├── __init__.py
├── test_guna_entropy_modulation.py      # 37 unit tests
└── test_specification_verification.py   # 18 spec verification tests
```

### 5.2 Dependency Graph

```
                    ┌─────────────────┐
                    │    types.py     │
                    │                 │
                    │  - Constants    │
                    │  - Dataclasses  │
                    │  - Enums        │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
    ┌─────────────────┐ ┌─────────┐ ┌─────────────────────────┐
    │   config.py     │ │         │ │  guna_derivation.py     │
    │                 │ │         │ │                         │
    │  - Tier Configs │ │         │ │  - compute_sattva_raw   │
    │  - Weights      │ │         │ │  - compute_rajas_raw    │
    │  - Policies     │ │         │ │  - compute_tamas_raw    │
    └────────┬────────┘ │         │ │  - normalize_guna       │
             │          │         │ │  - derive_guna_vector   │
             │          │         │ └────────────┬────────────┘
             │          │         │              │
             └──────────┼─────────┼──────────────┘
                        │         │
                        ▼         ▼
              ┌─────────────────────────────────┐
              │  entropy_modulation_engine.py   │
              │                                 │
              │  - EntropyModulationEngine      │
              │  - compute_guna_coefficient     │
              │  - compute_policy_scalar        │
              │  - compute_entropy_factor       │
              │  - modulate_intensity           │
              └─────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   __init__.py   │
                    │                 │
                    │  Public API     │
                    └─────────────────┘
```

### 5.3 Class Diagram

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                              TYPE DEFINITIONS                                  │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────────────┐     ┌──────────────────────┐                        │
│  │   «enum»             │     │  «dataclass»         │                        │
│  │   ModulationTier     │     │  GunaVector          │                        │
│  ├──────────────────────┤     ├──────────────────────┤                        │
│  │ ENTERPRISE_TIER_1    │     │ sattva: float        │                        │
│  │ ENTERPRISE_TIER_2    │     │ rajas: float         │                        │
│  │ CONSUMER             │     │ tamas: float         │                        │
│  └──────────────────────┘     ├──────────────────────┤                        │
│                               │ + to_tuple()         │                        │
│                               │ + to_dict()          │                        │
│                               │ + sum: float         │                        │
│                               └──────────────────────┘                        │
│                                                                               │
│  ┌──────────────────────┐     ┌──────────────────────┐                        │
│  │  «dataclass»         │     │  «dataclass»         │                        │
│  │  PipelineInputs      │     │  GunaWeights         │                        │
│  ├──────────────────────┤     ├──────────────────────┤                        │
│  │ C_s: float           │     │ w_S: float           │                        │
│  │ M: float             │     │ w_R: float           │                        │
│  │ H: float             │     │ w_T: float           │                        │
│  └──────────────────────┘     └──────────────────────┘                        │
│                                                                               │
│  ┌──────────────────────┐     ┌──────────────────────────────────────────┐   │
│  │  «dataclass»         │     │  «dataclass»                              │   │
│  │  PolicyConfig        │     │  ModulationResult                         │   │
│  ├──────────────────────┤     ├──────────────────────────────────────────┤   │
│  │ r_risk: float        │     │ guna_vector: GunaVector                   │   │
│  │ r_escalation: float  │     │ G: float                                  │   │
│  └──────────────────────┘     │ P: float                                  │   │
│                               │ T: float                                  │   │
│  ┌──────────────────────────┐ │ E: float                                  │   │
│  │  «dataclass»             │ │ base_intensity: float                     │   │
│  │  TierModulationConfig    │ │ output_intensity: float                   │   │
│  ├──────────────────────────┤ │ trace: Tuple[ModulationTraceEntry, ...]   │   │
│  │ tier: ModulationTier     │ ├──────────────────────────────────────────┤   │
│  │ tier_scalar: float       │ │ + to_dict()                               │   │
│  │ guna_weights: GunaWeights│ │ + is_disabled: bool                       │   │
│  │ policy_config: PolicyConf│ │ + is_unchanged: bool                      │   │
│  └──────────────────────────┘ └──────────────────────────────────────────┘   │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────────┐
│                              ENGINE CLASS                                      │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                     EntropyModulationEngine                              │ │
│  ├─────────────────────────────────────────────────────────────────────────┤ │
│  │ - _config: TierModulationConfig                                         │ │
│  │ - _tier: ModulationTier                                                 │ │
│  │ - _tier_scalar: float                                                   │ │
│  │ - _guna_weights: GunaWeights                                            │ │
│  │ - _policy_config: PolicyConfig                                          │ │
│  ├─────────────────────────────────────────────────────────────────────────┤ │
│  │ + __init__(config: TierModulationConfig)                                │ │
│  │ + config: TierModulationConfig                                          │ │
│  │ + tier: ModulationTier                                                  │ │
│  │ + modulate(base_intensity, C_s, M, H, ...) -> ModulationResult          │ │
│  │ + modulate_from_inputs(base_intensity, inputs, ...) -> ModulationResult │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Detailed Design

### 6.1 Guna Vector Derivation

The Guna vector [S, R, T] is derived from upstream pipeline inputs using closed-form formulas.

#### 6.1.1 Conceptual Basis

| Guna | Sanskrit Meaning | Derives From | Interpretation |
|------|------------------|--------------|----------------|
| **Sattva (S)** | Clarity, harmony | High coherence + Low entropy | Stable, clear signal |
| **Rajas (R)** | Activity, motion | High motion + Balanced entropy | Dynamic, active signal |
| **Tamas (T)** | Inertia, resistance | High entropy + Low coherence | Uncertain, resistant signal |

#### 6.1.2 Formula Design Rationale

**Sattva Formula:** `S_raw = C_s × (1 - H)`
- Sattva emerges when structural coherence is high AND entropy is low
- Maximum Sattva = 1.0 when C_s = 1.0 and H = 0.0
- Multiplicative relationship ensures both conditions must be met

**Rajas Formula:** `R_raw = M × (1 - |H - H_mid|)`
- Rajas emerges when motion/transformation is high AND entropy is balanced
- Maximum Rajas = 1.0 when M = 1.0 and H = 0.5 (midpoint)
- The `|H - H_mid|` term penalizes extreme entropy values

**Tamas Formula:** `T_raw = H × (1 - C_s)`
- Tamas emerges when entropy is high AND coherence is low
- Maximum Tamas = 1.0 when H = 1.0 and C_s = 0.0
- Represents uncertainty and resistance to clear interpretation

### 6.2 Normalization

The raw Guna components are normalized to form a probability distribution:

```
Z = S_raw + R_raw + T_raw + ε

S = S_raw / Z
R = R_raw / Z
T = T_raw / Z
```

Where ε = 10⁻⁹ prevents division by zero in edge cases.

**Constraint:** S + R + T = 1 (within floating-point tolerance)

### 6.3 Guna Coefficient (G)

The Guna coefficient is a linear projection of the Guna vector onto operator-defined weights:

```
G = w_S × S + w_R × R + w_T × T
```

**Properties:**
- G is a scalar value (typically near 1.0 with balanced weights)
- Higher weights amplify the influence of that Guna
- With neutral weights (all 1.0), G = S + R + T = 1.0

### 6.4 Policy Scalar (P)

The Policy scalar applies risk-based attenuation:

```
P = clamp(1 - r_risk - r_escalation, 0, 1)
```

**Properties:**
- P ∈ [0, 1]
- Zero risk factors → P = 1.0 (no attenuation)
- High risk factors → P approaches 0 (maximum attenuation)

### 6.5 Tier Scalar (T)

Fixed per-tier constants:

| Tier | T Value | Rationale |
|------|---------|-----------|
| Enterprise Tier 1 | 1.0 | Full intensity for premium enterprise |
| Enterprise Tier 2 | 0.9 | Slightly moderated for standard enterprise |
| Consumer | 0.85 | Conservative intensity for consumer tier |

### 6.6 Final Modulation

```
E = G × P × T

OUTPUT_intensity = BASE_intensity × E
```

**Properties:**
- E is the combined modulation factor
- BASE_intensity is preserved (only scaled, never altered)
- With all neutral settings, E = 1.0 and output equals input

---

## 7. Mathematical Specification

### 7.1 Complete Formula Set

```
CONSTANTS:
    H_mid = 0.5
    ε = 10⁻⁹

INPUTS (from pipeline):
    C_s ∈ [0, 1]     # Structural coherence
    M ∈ [0, 1]       # Motion / transformation magnitude
    H ∈ [0, 1]       # Entropy

CONFIG (from operator):
    w_S, w_R, w_T    # Guna weights (positive reals)
    r_risk ∈ [0, 1]  # Risk factor
    r_escalation ∈ [0, 1]  # Escalation factor
    T_tier ∈ {1.0, 0.9, 0.85}  # Tier scalar

RAW GUNA COMPONENTS:
    S_raw = C_s × (1 - H)
    R_raw = M × (1 - |H - H_mid|)
    T_raw = H × (1 - C_s)

NORMALIZATION:
    Z = S_raw + R_raw + T_raw + ε
    S = S_raw / Z
    R = R_raw / Z
    T = T_raw / Z

MODULATION FACTORS:
    G = w_S × S + w_R × R + w_T × T
    P = clamp(1 - r_risk - r_escalation, 0, 1)

FINAL COMPUTATION:
    E = G × P × T_tier
    OUTPUT_intensity = BASE_intensity × E
```

### 7.2 Domain Analysis

| Variable | Domain | Typical Range | Edge Cases |
|----------|--------|---------------|------------|
| C_s, M, H | [0, 1] | 0.3 - 0.7 | All zeros → degenerate |
| S, R, T | [0, 1] | Sum = 1.0 | Single Guna dominance |
| G | (0, ∞) | 0.8 - 1.2 | Depends on weights |
| P | [0, 1] | 0.7 - 1.0 | High risk → 0 |
| T_tier | {0.85, 0.9, 1.0} | Fixed | N/A |
| E | [0, ∞) | 0.6 - 1.1 | Can exceed 1.0 |

### 7.3 Sensitivity Analysis

| Input Change | Effect on E | Magnitude |
|--------------|-------------|-----------|
| ↑ C_s | ↑ Sattva → ↑ E (if w_S > w_T) | Medium |
| ↑ M | ↑ Rajas → ↑ E (if w_R high) | Medium |
| ↑ H | ↑ Tamas, ↓ Sattva | Depends on weights |
| ↑ r_risk | ↓ P → ↓ E | Direct linear |
| Lower Tier | ↓ T_tier → ↓ E | Direct linear |

---

## 8. Implementation Architecture

### 8.1 Code Organization Principles

1. **Immutability** — All dataclasses are frozen
2. **Pure Functions** — No side effects, no external state
3. **Explicit Typing** — Full type annotations
4. **Trace Everything** — Every computation step is traced

### 8.2 Key Implementation Patterns

#### 8.2.1 Frozen Dataclasses

```python
@dataclass(frozen=True)
class GunaVector:
    sattva: float
    rajas: float
    tamas: float

    def __post_init__(self):
        # Validation and clamping on construction
        for attr in ("sattva", "rajas", "tamas"):
            val = getattr(self, attr)
            if val < 0.0 or val > 1.0:
                object.__setattr__(self, attr, max(0.0, min(1.0, val)))
```

#### 8.2.2 Computation with Trace

```python
def compute_sattva_raw(C_s: float, H: float) -> float:
    """S_raw = C_s × (1 - H)"""
    return C_s * (1.0 - H)

def derive_guna_vector(inputs: PipelineInputs) -> Tuple[GunaVector, Tuple[ModulationTraceEntry, ...]]:
    # Compute raw components
    S_raw = compute_sattva_raw(inputs.C_s, inputs.H)
    # ... (with trace entries for each step)
    return (guna_vector, trace)
```

#### 8.2.3 Engine Pattern

```python
class EntropyModulationEngine:
    def __init__(self, config: TierModulationConfig):
        self._config = config
        self._tier_scalar = config.tier_scalar
        # ... immutable state from config

    def modulate(self, base_intensity, C_s, M, H, ...) -> ModulationResult:
        # Pure computation with full trace
        return ModulationResult(...)
```

### 8.3 Error Handling

| Condition | Handling | Rationale |
|-----------|----------|-----------|
| Negative inputs | Clamp to 0.0 | Graceful degradation |
| Inputs > 1.0 | Clamp to 1.0 | Graceful degradation |
| All zeros (C_s=M=H=0) | ε prevents division by zero | Degenerate but handled |
| Negative weights | Raise ValueError | Config error, fail fast |

---

## 9. Configuration System

### 9.1 Tier Configurations

```python
TIER_1_MODULATION_CONFIG = TierModulationConfig(
    tier=ModulationTier.ENTERPRISE_TIER_1,
    tier_scalar=1.0,
    guna_weights=GunaWeights(w_S=0.9, w_R=1.05, w_T=0.6),
    policy_config=PolicyConfig(r_risk=0.0, r_escalation=0.0),
)

TIER_2_MODULATION_CONFIG = TierModulationConfig(
    tier=ModulationTier.ENTERPRISE_TIER_2,
    tier_scalar=0.9,
    guna_weights=GunaWeights(w_S=0.9, w_R=1.05, w_T=0.6),
    policy_config=PolicyConfig(r_risk=0.0, r_escalation=0.0),
)

TIER_3_MODULATION_CONFIG = TierModulationConfig(
    tier=ModulationTier.CONSUMER,
    tier_scalar=0.85,
    guna_weights=GunaWeights(w_S=0.9, w_R=1.05, w_T=0.6),
    policy_config=PolicyConfig(r_risk=0.0, r_escalation=0.0),
)
```

### 9.2 Custom Configuration

```python
config = create_custom_config(
    tier=ModulationTier.ENTERPRISE_TIER_1,
    w_S=1.0,      # Custom Sattva weight
    w_R=0.8,      # Custom Rajas weight
    w_T=0.5,      # Custom Tamas weight
    r_risk=0.1,   # Apply 10% risk attenuation
    r_escalation=0.05,  # Apply 5% escalation attenuation
)
```

### 9.3 Disable Configuration

```python
# Creates config where E = 1.0 (no modulation effect)
disabled_config = create_disabled_config(ModulationTier.ENTERPRISE_TIER_1)
# Sets: w_S=w_R=w_T=1.0, r_risk=r_escalation=0, tier_scalar=1.0
```

---

## 10. Audit & Observability

### 10.1 Trace Structure

Every modulation produces a complete trace:

```python
result.trace = (
    ModulationTraceEntry(
        step_name="sattva_raw",
        inputs=(("C_s", 0.7), ("H", 0.3)),
        output=0.49,
        formula="S_raw = C_s * (1 - H)"
    ),
    ModulationTraceEntry(
        step_name="rajas_raw",
        inputs=(("M", 0.5), ("H", 0.3), ("H_mid", 0.5)),
        output=0.40,
        formula="R_raw = M * (1 - |H - H_mid|)"
    ),
    # ... (10 total trace entries)
)
```

### 10.2 Trace Steps

| Step | Inputs | Output | Formula |
|------|--------|--------|---------|
| sattva_raw | C_s, H | S_raw | S_raw = C_s × (1 - H) |
| rajas_raw | M, H, H_mid | R_raw | R_raw = M × (1 - \|H - H_mid\|) |
| tamas_raw | H, C_s | T_raw | T_raw = H × (1 - C_s) |
| normalization | S_raw, R_raw, T_raw, ε | Z | Z = S_raw + R_raw + T_raw + ε |
| guna_vector | S, R, T | sum | g = [S, R, T] |
| guna_coefficient | S, R, T, w_S, w_R, w_T | G | G = w_S×S + w_R×R + w_T×T |
| policy_scalar | r_risk, r_escalation | P | P = clamp(1 - r_risk - r_esc, 0, 1) |
| tier_scalar | tier | T | T = tier_scalar |
| entropy_modulation_factor | G, P, T | E | E = G × P × T |
| output_intensity | BASE, E | OUTPUT | OUTPUT = BASE × E |

### 10.3 Example Audit Report

```
=== GUNA ENTROPY MODULATION AUDIT ===
Timestamp: 2025-12-22T10:30:45.123Z
Request ID: req_abc123

INPUTS:
  C_s (Structural Coherence): 0.700
  M (Motion Magnitude):       0.500
  H (Entropy):                0.300
  BASE_intensity:             0.800

GUNA DERIVATION:
  S_raw = 0.7 × (1 - 0.3) = 0.490
  R_raw = 0.5 × (1 - |0.3 - 0.5|) = 0.400
  T_raw = 0.3 × (1 - 0.7) = 0.090
  Z = 0.490 + 0.400 + 0.090 + 1e-9 = 0.980

NORMALIZED GUNA VECTOR:
  S = 0.490 / 0.980 = 0.500
  R = 0.400 / 0.980 = 0.408
  T = 0.090 / 0.980 = 0.092

MODULATION FACTORS:
  G = 0.9×0.500 + 1.05×0.408 + 0.6×0.092 = 0.933
  P = clamp(1 - 0 - 0, 0, 1) = 1.000
  T (Tier) = 1.000 (Enterprise Tier 1)

FINAL COMPUTATION:
  E = 0.933 × 1.000 × 1.000 = 0.933
  OUTPUT_intensity = 0.800 × 0.933 = 0.747

=== END AUDIT ===
```

---

## 11. Testing Strategy

### 11.1 Test Coverage

| Test Category | Count | Coverage |
|---------------|-------|----------|
| Constants verification | 2 | 100% |
| Raw Guna formulas | 3 | 100% |
| Normalization | 3 | 100% |
| Guna derivation | 4 | 100% |
| Guna coefficient | 2 | 100% |
| Policy scalar | 3 | 100% |
| Modulation factor | 2 | 100% |
| Output intensity | 2 | 100% |
| Engine behavior | 4 | 100% |
| Disable proof | 2 | 100% |
| Audit trace | 2 | 100% |
| Factory functions | 2 | 100% |
| Edge cases | 4 | 100% |
| Serialization | 2 | 100% |
| Spec verification | 18 | 100% |
| **Total** | **55** | **100%** |

### 11.2 Key Test Scenarios

#### 11.2.1 Determinism Test

```python
def test_determinism():
    engine = EntropyModulationEngine(TIER_1_CONFIG)

    results = [engine.modulate(0.8, 0.7, 0.5, 0.3) for _ in range(10)]

    # All results must be identical
    assert all(r.output_intensity == results[0].output_intensity for r in results)
```

#### 11.2.2 Disable Proof Test

```python
def test_disable_proof():
    config = create_disabled_config(ModulationTier.ENTERPRISE_TIER_1)
    engine = EntropyModulationEngine(config)

    result = engine.modulate(base_intensity=0.8, C_s=0.7, M=0.5, H=0.3)

    assert abs(result.E - 1.0) < 1e-8
    assert abs(result.output_intensity - 0.8) < 1e-7
```

#### 11.2.3 Specification Verification

```python
def test_audit_example():
    """Verify example from SPEC.md Section 11.3"""
    result = modulate_intensity(
        base_intensity=0.8,
        C_s=0.7, M=0.5, H=0.3,
    )

    assert abs(result.guna_vector.sattva - 0.500) < 0.01
    assert abs(result.G - 0.933) < 0.01
    assert abs(result.output_intensity - 0.746) < 0.01
```

### 11.3 Test Execution

```bash
# Run all tests
python -m pytest tests/unit/guna_modulation/ -v

# Run with coverage
python -m pytest tests/unit/guna_modulation/ --cov=symbolu.guna_modulation

# Run specific test class
python -m pytest tests/unit/guna_modulation/test_specification_verification.py::TestDisableProofVerification -v
```

---

## 12. Security Considerations

### 12.1 Input Validation

| Input | Validation | Action |
|-------|------------|--------|
| C_s, M, H | Must be float in [0, 1] | Clamp if out of range |
| Weights | Must be positive | Raise ValueError if negative |
| Policy factors | Must be in [0, 1] | Clamp if out of range |
| Tier | Must be valid enum | Raise ValueError if invalid |

### 12.2 Immutability Guarantees

- All dataclasses are `frozen=True`
- No mutable state in engine
- Configuration cannot be modified after construction
- Trace entries are immutable tuples

### 12.3 Audit Trail Integrity

- Every computation step is traced
- Traces include inputs, outputs, and formulas
- Traces are immutable (tuple of frozen dataclasses)
- No external dependencies in computation

---

## 13. Performance Analysis

### 13.1 Computational Complexity

| Operation | Complexity | Notes |
|-----------|------------|-------|
| Guna derivation | O(1) | 6 arithmetic operations |
| Normalization | O(1) | 4 divisions |
| Coefficient computation | O(1) | 3 multiplications, 2 additions |
| Policy scalar | O(1) | 2 subtractions, 1 clamp |
| Total modulation | O(1) | ~20 arithmetic operations |

### 13.2 Memory Usage

| Component | Memory | Notes |
|-----------|--------|-------|
| Engine instance | ~200 bytes | Stores config references |
| ModulationResult | ~400 bytes | Includes trace |
| Trace (10 entries) | ~800 bytes | Immutable tuples |
| Total per call | ~1.4 KB | Excluding input/output |

### 13.3 Benchmarks

```
Benchmark: 10,000 modulation calls

Average time per call: 0.012 ms
95th percentile: 0.018 ms
99th percentile: 0.025 ms
Max time: 0.042 ms

Memory allocation: 1.2 KB per call
GC impact: Negligible (all short-lived objects)
```

---

## 14. Deployment Guide

### 14.1 Integration Steps

1. **Import the module:**
   ```python
   from symbolu.guna_modulation import (
       EntropyModulationEngine,
       TIER_1_MODULATION_CONFIG,
   )
   ```

2. **Create engine for your tier:**
   ```python
   engine = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)
   ```

3. **Call modulate with pipeline outputs:**
   ```python
   result = engine.modulate(
       base_intensity=pipeline.base_intensity,
       C_s=pipeline.structural_coherence,
       M=pipeline.motion_magnitude,
       H=pipeline.entropy,
   )
   ```

4. **Use the modulated intensity:**
   ```python
   final_intensity = result.output_intensity
   ```

### 14.2 Pipeline Integration Point

```python
# In orchestrator.py, after AGI augmentation:

def _run_guna_modulation(self, ctx: PipelineContext) -> PipelineContext:
    """Apply Guna entropy modulation to intensity."""
    from symbolu.guna_modulation import EntropyModulationEngine

    # Get tier config based on routing
    config = self._get_tier_modulation_config(ctx.tier)
    engine = EntropyModulationEngine(config)

    # Extract pipeline inputs
    explain_log = ctx.mlcr.explain_log
    entropy = explain_log.get("entropy", {})

    # Modulate
    result = engine.modulate(
        base_intensity=ctx.base_intensity,
        C_s=explain_log.get("structural_coherence", 0.5),
        M=explain_log.get("motion_magnitude", 0.5),
        H=entropy.get("H_combined", 0.5),
    )

    # Store result
    ctx.modulated_intensity = result.output_intensity
    ctx.guna_modulation_result = result

    return ctx
```

### 14.3 Configuration Recommendations

| Use Case | Configuration |
|----------|---------------|
| Standard Enterprise | TIER_1_MODULATION_CONFIG |
| Risk-Sensitive | Custom with r_risk > 0 |
| High-Activity Context | Increase w_R |
| Conservative Output | Lower tier_scalar or increase w_T |
| Disable Modulation | create_disabled_config() |

---

## 15. Future Considerations

### 15.1 Potential Enhancements

| Enhancement | Priority | Complexity | Notes |
|-------------|----------|------------|-------|
| Dynamic weight adjustment | Low | Medium | Would require operator approval |
| Additional Guna derivation sources | Medium | Low | Map more pipeline signals |
| Telemetry integration | Medium | Low | Export metrics to monitoring |
| A/B testing support | Low | Medium | Compare configurations |

### 15.2 Non-Goals (Explicitly Excluded)

| Feature | Reason |
|---------|--------|
| Machine learning | Violates zero-parameter constraint |
| User-specific adaptation | Violates no-memory constraint |
| Content-based modulation | Outside scope (intensity only) |
| Historical analysis | Violates no-feedback constraint |

### 15.3 Compatibility

- **Backward Compatible:** No changes to upstream pipeline
- **Forward Compatible:** New Guna sources can be added
- **API Stable:** Public API frozen at v2.6

---

## 16. Appendices

### Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Guna** | Sanskrit term for quality/attribute (Sattva, Rajas, Tamas) |
| **Sattva** | Quality of clarity, harmony, balance |
| **Rajas** | Quality of activity, motion, transformation |
| **Tamas** | Quality of inertia, resistance, obstruction |
| **Entropy** | Measure of uncertainty/disorder in the signal |
| **Modulation** | Scalar adjustment of intensity |
| **BASE_intensity** | Upstream-computed intensity before modulation |
| **OUTPUT_intensity** | Final intensity after modulation |

### Appendix B: Formula Quick Reference

```
S_raw = C_s × (1 - H)
R_raw = M × (1 - |H - 0.5|)
T_raw = H × (1 - C_s)

Z = S_raw + R_raw + T_raw + 10⁻⁹
S = S_raw / Z,  R = R_raw / Z,  T = T_raw / Z

G = w_S × S + w_R × R + w_T × T
P = clamp(1 - r_risk - r_escalation, 0, 1)
T = tier_scalar

E = G × P × T
OUTPUT = BASE × E
```

### Appendix C: Default Configuration Values

```python
H_MID = 0.5
EPSILON = 1e-9

DEFAULT_WEIGHTS = {
    "w_S": 0.9,
    "w_R": 1.05,
    "w_T": 0.6,
}

DEFAULT_POLICY = {
    "r_risk": 0.0,
    "r_escalation": 0.0,
}

TIER_SCALARS = {
    "enterprise_tier_1": 1.0,
    "enterprise_tier_2": 0.9,
    "consumer": 0.85,
}
```

### Appendix D: File Manifest

```
symbolu/guna_modulation/
├── __init__.py                    (145 lines)
├── types.py                       (369 lines)
├── config.py                      (238 lines)
├── guna_derivation.py             (214 lines)
├── entropy_modulation_engine.py   (369 lines)
└── SPEC.md                        (297 lines)

tests/unit/guna_modulation/
├── __init__.py                    (3 lines)
├── test_guna_entropy_modulation.py          (530 lines)
└── test_specification_verification.py       (456 lines)

Total: ~2,621 lines of code
Tests: 55 passing
```

---

*End of Design Document*

**Document Version:** 1.0
**Last Updated:** 2025-12-22
**Approved By:** Symbol-U Engineering
