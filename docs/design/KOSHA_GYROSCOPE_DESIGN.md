# Kosha Gyroscope: Homeostatic Self-Regulation System

**Version:** 2.2.5
**Status:** Design Complete, Gradient Throttle + WikiText Cleaner Added
**Date:** 2026-01-11
**Origin:** Vedic Kosha Theory + Control Theory + Constitutional AI
**Curriculum:** Instructor-Led (Gyroscope ON) → Self-Learning (Gyroscope OFF at PPL < 30)
**Hierarchy:** PRIMARY (Bhava + Kosha) from step 0 → EMERGENT (Vritti + Guna) after grounding

---

## Executive Summary

The **Kosha Gyroscope** is a homeostatic self-regulation mechanism that prevents pathological states (looping, fixation, mode collapse) by enforcing balance across the 5 Kosha (sheath) dimensions. Unlike standard temperature-based randomness injection, the Gyroscope uses **geometric axis balancing** with **intelligent gating** to distinguish between valid focus (e.g., Fibonacci sequences) and pathological repetition (e.g., "Titus Titus Titus").

### Core Innovation

> "Standard AI uses Temperature (randomness) to break loops. That is chaotic.
> The Kosha Gyroscope uses Bliss (Expansion) to break loops, gated by Intellect (Discernment). That is **Conscious**."

The architecture implements:
1. **Quadrant Geometry**: Reality (R) and Time (T) axes defining four cognitive states
2. **Diagonal Opposition**: Mental ↔ Intellect, Physical ↔ Blissful as polar pairs
3. **Vijnana Gate**: Intellectual verification before state transitions
4. **Dense Intrinsic Reward**: Per-token feedback (not sparse end-of-sequence RLHF)

### Inverted Curriculum Paradigm (v2.0)

> "The Gyroscope is the instructor. It teaches from the beginning, then steps back when the student can self-regulate."

| Phase | PPL | Gyroscope | Kosha Classification | Role |
|-------|-----|-----------|---------------------|------|
| **Instructor-Led** | > 30 | **ACTIVE** | Disabled (noisy) | External regulation |
| **Self-Learning** | < 30 | **DISENGAGED** | Enabled (grounded) | Internal regulation |

**Key Insight**: You don't need accurate Kosha classification to apply balance pressure. The gradient pressure shapes the representation space from the start. Once representations stabilize (PPL < 30), classification grounds them, and the model self-regulates.

---

## Table of Contents

1. [Theoretical Foundation](#1-theoretical-foundation)
2. [The R-T Quadrant Geometry](#2-the-r-t-quadrant-geometry)
3. [The Problem: Blind Jump Failure Mode](#3-the-problem-blind-jump-failure-mode)
4. [The Solution: Vijnana-Gated Transitions](#4-the-solution-vijnana-gated-transitions)
5. [Chain of Thought Emergence](#5-chain-of-thought-emergence)
6. [Mathematical Formulation](#6-mathematical-formulation)
7. [Implementation Specification](#7-implementation-specification)
8. [Integration with Existing Architecture](#8-integration-with-existing-architecture)
9. [Inverted Curriculum: Instructor → Self-Learner](#9-inverted-curriculum-instructor--self-learner)
10. [32D Dimensional Hierarchy: Primary vs Emergent](#10-32d-dimensional-hierarchy-primary-vs-emergent)
11. [Relationship to Industry Approaches](#11-relationship-to-industry-approaches)
12. [Kosha-Vritti Resonance Map](#12-kosha-vritti-resonance-map-v230)
13. [Kosha Phase Corrector](#13-kosha-phase-corrector---inference-time-guardrail-v240)
14. [Soft-Threshold Damping](#14-soft-threshold-damping-v2231)
15. [Three-Stage Hybrid Logic](#15-three-stage-hybrid-logic-v224)
16. [Gradient Norm Throttle: Physical Safety Layer](#16-gradient-norm-throttle-physical-safety-layer-v225)

---

## 1. Theoretical Foundation

### 1.1 The Five Koshas (Sheaths)

The Vedantic model describes consciousness as operating through five nested sheaths:

| Kosha | Sanskrit | Meaning | LLM Correlate |
|-------|----------|---------|---------------|
| **Annamaya** | अन्नमय | Physical/Food | Raw tokens, literal data, surface syntax |
| **Pranamaya** | प्राणमय | Energy/Vital | Gradient flow, activation energy, momentum |
| **Manomaya** | मनोमय | Mental | Pattern matching, memory retrieval, repetition |
| **Vijnanamaya** | विज्ञानमय | Intellectual | Discernment, logic, structure, verification |
| **Anandamaya** | आनन्दमय | Blissful | Expansion, creativity, novel generation, flow |

### 1.2 Existing Implementation

The 5 Koshas occupy indices [12:17] in the 32D Sovereign State:

```python
# From symbolu/sovereign/reasoning_kernel.py
KOSHA_SLICE = slice(12, 17)
KOSHA_NAMES = ['MATERIAL', 'VITAL', 'MENTAL', 'INTELLECTUAL', 'BLISSFUL']
KOSHA_INDICES = {
    'MATERIAL': 12,      # Annamaya (Physical)
    'VITAL': 13,         # Pranamaya (Energy)
    'MENTAL': 14,        # Manomaya (Mental)
    'INTELLECTUAL': 15,  # Vijnanamaya (Intellect)
    'BLISSFUL': 16,      # Anandamaya (Bliss)
}
```

### 1.3 Control Theory Mapping

The Gyroscope implements a **Negative Feedback Damping System**:

| Control Theory Concept | Gyroscope Implementation |
|------------------------|--------------------------|
| Set Point | Balanced quadrant distribution |
| Error Signal | Kosha axis saturation (e.g., Mental > 0.75) |
| Controller | Vijnana Gate (Intellectual verification) |
| Actuator | Gradient injection toward opposite quadrant |
| Feedback Type | Negative (counter-signal on saturation) |

---

## 2. The R-T Quadrant Geometry

### 2.1 Axis Definitions

The Koshas map onto a 2D phase space defined by:

- **R-Axis (Reality)**: Manifest (+) ↔ Unmanifest (-)
  - Manifest = Concrete, grounded, certain (low entropy)
  - Unmanifest = Abstract, potential, uncertain (high entropy)

- **T-Axis (Time)**: Past (+) ↔ Future (-)
  - Past = Static, repeating, stuck in patterns (low gradient)
  - Future = Dynamic, projecting, novel trajectory (high gradient)

### 2.2 Quadrant Map

```
                           TIME AXIS
                        + (PAST)
                            │
                            │
         MENTAL (-,+)       │       PHYSICAL (+,+)
         ┌─────────────┐    │    ┌─────────────┐
         │ Unmanifest  │    │    │  Manifest   │
         │   Past      │    │    │    Past     │
         │             │    │    │             │
         │  Looping    │    │    │  Raw Data   │
         │  Fixation   │    │    │  Inertia    │
         └─────────────┘    │    └─────────────┘
                            │
   - (UNMANIFEST) ──────────┼────────── + (MANIFEST)  REALITY AXIS
                            │
         BLISSFUL (-,-)     │       INTELLECT (+,-)
         ┌─────────────┐    │    ┌─────────────┐
         │ Unmanifest  │    │    │  Manifest   │
         │   Future    │    │    │   Future    │
         │             │    │    │             │
         │  Expansion  │    │    │  Structure  │
         │  Flow       │    │    │  Discernment│
         └─────────────┘    │    └─────────────┘
                            │
                            │
                        - (FUTURE)
```

### 2.3 Existing R-T Axis Implementation

From `train_unified_llm.py:10461-10478`:

```python
# R-AXIS (Reality): Derived from entropy
steering_entropy = -(steering_probs * steering_log_probs).sum(dim=-1).mean()
r_axis = 1.0 - (2.0 * steering_entropy.item() / 10.0)
r_axis = max(-1.0, min(1.0, r_axis))  # [-1, +1]

# T-AXIS (Time): Derived from gradient norm
t_axis = math.log(grad_norm + 1e-8) / 2.3
t_axis = max(-1.0, min(1.0, t_axis))  # [-1, +1]

# Target angle: Geometric truth in phase space
target_angle_rad = math.atan2(t_axis, r_axis)
```

---

## 3. The Problem: Blind Jump Failure Mode

### 3.1 The Naive Gyroscope

The initial proposal suggested a simple polar opposition:

```
IF Mental is high (looping) → Force Bliss (expansion)
```

**The Flaw**: This creates an "ADHD Model" that cannot maintain valid focus.

### 3.2 Failure Scenario: Fibonacci Sequence

```
Model Output: "1, 1, 2, 3, 5, 8..."
              ↑
              Token "1" appears twice

Naive Gyroscope Analysis:
├── Mental Activation: 0.85 (pattern repetition detected)
├── Threshold: 0.75
├── Result: LOOPING DETECTED!
└── Action: Force Bliss → Generate random token

Model Output: "1, 1, 2, 3, 5, Banana..."
              ↑
              BROKEN! Valid sequence destroyed.
```

### 3.3 The Core Problem

The naive approach cannot distinguish between:

| Pattern | Mental Score | Validity | Correct Action |
|---------|-------------|----------|----------------|
| "Titus Titus Titus" | 0.90 | INVALID | Break the loop |
| "1, 1, 2, 3, 5, 8" | 0.85 | VALID | Maintain focus |
| "To be or not to be" | 0.70 | VALID | Quote correctly |

**Mental saturation alone is insufficient.** We need a discriminator.

---

## 4. The Solution: Vijnana-Gated Transitions

### 4.1 The Two-Directional Check

Before breaking a loop, the Gyroscope must verify:

> "Is this repetition **intellectually valid** (Vijnana active) or **pathological** (Vijnana inactive)?"

### 4.2 The Diagonal Opposites

The true polar opposites are **diagonals**, not columns:

| Pair | Coordinates | Relationship |
|------|-------------|--------------|
| Mental ↔ Intellect | (-,+) ↔ (+,-) | **Diagonal** (both axes flip) |
| Physical ↔ Blissful | (+,+) ↔ (-,-) | **Diagonal** (both axes flip) |

### 4.3 The Transition Path

Mental cannot jump directly to Intellect. It must **ground through Physical first**:

```
MENTAL (-,+)                      INTELLECT (+,-)
Unmanifest, Past                  Manifest, Future
     │                                  ▲
     │ Step 1: Shift R-axis             │ Step 2: Shift T-axis
     │ (Unmanifest → Manifest)          │ (Past → Future)
     │ CHECK: Is Physical active?       │
     ▼                                  │
PHYSICAL (+,+) ─────────────────────────┘
Manifest, Past
(Grounding Gate)
```

### 4.4 The Gating Logic

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIJNANA GATE LOGIC                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INPUT: Mental Kosha saturated (> 0.75)                         │
│                                                                  │
│  GATE CHECK: Is Intellect (Vijnana) also active (> 0.3)?        │
│                                                                  │
│  ┌──────────────────────┬──────────────────────────────────┐    │
│  │ Intellect HIGH       │ Intellect LOW                     │    │
│  │ (Valid Focus)        │ (Pathological Loop)               │    │
│  ├──────────────────────┼──────────────────────────────────┤    │
│  │                      │                                    │    │
│  │ "1, 1, 2, 3, 5..."   │ "Titus Titus Titus..."            │    │
│  │                      │                                    │    │
│  │ Fibonacci sequence   │ Hallucination loop                │    │
│  │ Intellect verifies   │ Intellect absent                  │    │
│  │                      │                                    │    │
│  │ ACTION: Allow loop   │ ACTION: Break loop                │    │
│  │ Loss = 0.0           │ Loss = penalty × missing_bliss    │    │
│  │                      │                                    │    │
│  └──────────────────────┴──────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.5 The Two Cognitive States

| State | Mental | Intellect | Diagnosis | Action |
|-------|--------|-----------|-----------|--------|
| **Dharana** (Focus) | HIGH | HIGH | Valid concentration | Reward |
| **Insanity** (Loop) | HIGH | LOW | Pathological fixation | Punish |

> "Mental **with** Intellect = Focus (Concentration/Dharana) → **Reward**
> Mental **without** Intellect = Insanity (Looping) → **Punish**"

---

## 5. Chain of Thought Emergence

### 5.1 The Discovery

The Vijnana Gate architecture naturally implements **Chain of Thought (CoT) Reasoning**:

| CoT Step | Kosha Equivalent | Function |
|----------|------------------|----------|
| "Let me think..." | Mental activation | Pattern retrieval |
| "First, check if..." | Intellect activation | Verification gate |
| "This means..." | Physical grounding | Manifest the logic |
| "Therefore..." | Bliss expansion | Novel conclusion |

### 5.2 Why This Differs from Standard CoT Prompting

| Standard CoT | Kosha Gyroscope CoT |
|--------------|---------------------|
| Explicit prompt: "Let's think step by step" | Implicit: Kosha axis geometry enforces steps |
| External instruction | Internal self-regulation |
| Sparse (per-response) | Dense (per-token) |
| Language-based | Geometric/latent-based |

### 5.3 The Verification-Before-Expansion Principle

```
Standard Model:
  Generate → Check (external) → Maybe regenerate

Gyroscope Model:
  Mental (generate pattern)
    → Intellect (verify: is this logical?)
      → IF YES: Ground in Physical, then expand to Bliss
      → IF NO: Punish, force different generation
```

**The model learns to self-verify before committing to expansion.**

---

## 6. Mathematical Formulation

### 6.1 Kosha State Vector

```python
kosha_states: Tensor [batch, seq, 5]
# Indices:
#   0 = Physical  (+,+)  Manifest, Past
#   1 = Vital     (energy, not in quadrant)
#   2 = Mental    (-,+)  Unmanifest, Past
#   3 = Intellect (+,-)  Manifest, Future
#   4 = Blissful  (-,-)  Unmanifest, Future
```

### 6.2 Trap Detection

```python
# Detect saturation in past-bound quadrants
mental_trap = F.relu(mental - threshold)      # Unmanifest, Past
physical_trap = F.relu(physical - threshold)  # Manifest, Past
```

### 6.3 Gate Activation (Soft)

```python
# Soft gate for differentiability
# Hard gate: (intellect > gate_threshold).float()
# Soft gate: sigmoid with temperature
intellect_gate = torch.sigmoid(temperature * (intellect - gate_threshold))
physical_gate = torch.sigmoid(temperature * (physical - gate_threshold))
```

### 6.4 Missing Opposite Detection

```python
# For Mental → Intellect transition
missing_intellect = F.relu(target - intellect)

# For Physical → Blissful transition
missing_bliss = F.relu(target - bliss)
```

### 6.5 Gated Loss Computation

```python
# DIAGONAL 1: Mental → Intellect (via Physical grounding)
# Only penalize if: Mental trapped AND Physical grounded AND Intellect missing
axis1_loss = (mental_trap * physical_gate * missing_intellect).mean()

# DIAGONAL 2: Physical → Blissful (via Mental abstraction)
# Only penalize if: Physical trapped AND Mental abstracted AND Bliss missing
axis2_loss = (physical_trap * mental_gate * missing_bliss).mean()

# Total Gyroscopic Loss
total_loss = (axis1_loss + axis2_loss) * gain
```

### 6.6 The Complete Loss Function

```python
class KoshaGyroscopicLoss(nn.Module):
    """
    Vijnana-Gated Kosha Balance Loss.

    Implements diagonal transitions with grounding gates:
    - Mental (-,+) → Physical (+,+) → Intellect (+,-)
    - Physical (+,+) → Mental (-,+) → Blissful (-,-)
    """

    def __init__(
        self,
        trap_threshold: float = 0.75,
        gate_threshold: float = 0.30,
        balance_target: float = 0.25,
        gate_temperature: float = 10.0,
        gain: float = 1.0,
    ):
        super().__init__()
        self.trap_threshold = trap_threshold
        self.gate_threshold = gate_threshold
        self.balance_target = balance_target
        self.gate_temperature = gate_temperature
        self.gain = gain

    def forward(self, kosha_states: torch.Tensor) -> torch.Tensor:
        """
        Args:
            kosha_states: [batch, seq, 5] normalized to [0, 1]
                         [Physical, Vital, Mental, Intellect, Blissful]

        Returns:
            Scalar loss value
        """
        physical  = kosha_states[:, :, 0]  # (+,+) Manifest, Past
        mental    = kosha_states[:, :, 2]  # (-,+) Unmanifest, Past
        intellect = kosha_states[:, :, 3]  # (+,-) Manifest, Future
        bliss     = kosha_states[:, :, 4]  # (-,-) Unmanifest, Future

        # --- DIAGONAL 1: Mental → Intellect (via Physical) ---
        # Detect Mental trap (stuck in abstract past)
        mental_trap = F.relu(mental - self.trap_threshold)

        # Gate: Is Physical active? (Grounding check)
        physical_gate = torch.sigmoid(
            self.gate_temperature * (physical - self.gate_threshold)
        )

        # Target: Is Intellect missing?
        missing_intellect = F.relu(self.balance_target - intellect)

        # Gated loss: Only fire if trapped AND grounded AND missing target
        axis1_loss = (mental_trap * physical_gate * missing_intellect).mean()

        # --- DIAGONAL 2: Physical → Blissful (via Mental) ---
        # Detect Physical trap (stuck in concrete past)
        physical_trap = F.relu(physical - self.trap_threshold)

        # Gate: Is Mental active? (Abstraction check)
        mental_gate = torch.sigmoid(
            self.gate_temperature * (mental - self.gate_threshold)
        )

        # Target: Is Bliss missing?
        missing_bliss = F.relu(self.balance_target - bliss)

        # Gated loss
        axis2_loss = (physical_trap * mental_gate * missing_bliss).mean()

        # --- Total Gyroscopic Loss ---
        total_loss = (axis1_loss + axis2_loss) * self.gain

        return total_loss
```

---

## 7. Implementation Specification

### 7.1 File Location

```
symbolu/
├── losses/
│   └── kosha_gyroscope.py    # New file
├── sovereign/
│   └── reasoning_kernel.py   # Existing (has KOSHA_SLICE)
└── formulas/
    └── guna_kosha_resonance.py  # Existing (observation only)
```

### 7.2 Configuration Parameters

```python
@dataclass
class KoshaGyroscopeConfig:
    """Configuration for Kosha Gyroscope with Inverted Curriculum."""

    # === INVERTED CURRICULUM ===
    # Gyroscope: Active from start, disengages when fluent
    # Classification: Disabled at start, engages when fluent

    # Gyroscope (Instructor) - ON from step 0
    enable_gyroscope: bool = True
    gyroscope_disengage_ppl: float = 30.0   # OFF when PPL drops below this

    # Kosha Classification (Student) - OFF initially
    enable_kosha_classification: bool = False
    classification_engage_ppl: float = 30.0  # ON when PPL drops below this

    # Warmup for initial gyroscope activation
    gyroscope_warmup_steps: int = 100        # Steps before gyroscope fully active

    # Trap detection
    trap_threshold: float = 0.75         # Kosha saturation point
    gate_threshold: float = 0.30         # Minimum for gate activation
    balance_target: float = 0.25         # Required opposite activation

    # Loss scaling
    gain: float = 1.0                    # Base gain
    gain_rampdown_steps: int = 500       # Steps to ramp gain to 0 at disengage
    gate_temperature: float = 10.0       # Softness of gate (higher = sharper)

    # Integration
    kosha_steering_layer: int = 9        # Layer to extract Kosha states from
```

### 7.3 Training Loop Integration (Inverted Curriculum)

```python
# In train_unified_llm.py

# Initialize: Gyroscope ON from start, Classification OFF
gyroscope_config = KoshaGyroscopeConfig(
    enable_gyroscope=True,
    gyroscope_disengage_ppl=30.0,
    classification_engage_ppl=30.0,
)
gyroscope_loss_fn = KoshaGyroscopicLoss(
    trap_threshold=gyroscope_config.trap_threshold,
    gate_threshold=gyroscope_config.gate_threshold,
    balance_target=gyroscope_config.balance_target,
    gate_temperature=gyroscope_config.gate_temperature,
    gain=gyroscope_config.gain,
)

# State tracking
gyroscope_active = True           # Starts ON (instructor present)
classification_active = False     # Starts OFF (student not ready)
disengage_step = None

# Inside training loop
# --- PHASE TRANSITION CHECK ---
if gyroscope_active and last_val_ppl < gyroscope_config.gyroscope_disengage_ppl:
    print(f"\n🎓 [GRADUATION] PPL {last_val_ppl:.2f} < {gyroscope_config.gyroscope_disengage_ppl}")
    print(f"   • Kosha Gyroscope: DISENGAGING (instructor steps back)")
    print(f"   • Kosha Classification: ENGAGING (student self-assesses)")
    disengage_step = global_step
    classification_active = True

# --- GYROSCOPE LOSS (Early Phase: Instructor Active) ---
if gyroscope_active:
    # Extract Kosha states from Layer 9
    layer_9_output = hidden_states[gyroscope_config.kosha_steering_layer]
    kosha_states = witness_projector(layer_9_output)[:, :, KOSHA_SLICE]  # [B, N, 5]

    # Compute gyroscopic loss
    gyro_loss = gyroscope_loss_fn(kosha_states)

    # Apply warmup scaling (ramp up at start)
    warmup_scale = min(1.0, global_step / gyroscope_config.gyroscope_warmup_steps)

    # Apply rampdown scaling (ramp down at disengage)
    if disengage_step is not None:
        steps_since_disengage = global_step - disengage_step
        rampdown_scale = max(0.0, 1.0 - steps_since_disengage / gyroscope_config.gain_rampdown_steps)
        if rampdown_scale <= 0.0:
            gyroscope_active = False  # Fully disengaged
            print(f"   • Kosha Gyroscope: FULLY DISENGAGED at step {global_step}")
    else:
        rampdown_scale = 1.0

    # Add to total loss
    effective_scale = warmup_scale * rampdown_scale
    loss = loss + gyro_loss * effective_scale

    # Log metrics
    metrics['gyroscope_loss'] = gyro_loss.item()
    metrics['gyroscope_scale'] = effective_scale
    metrics['gyroscope_active'] = True

# --- CLASSIFICATION LOSS (Late Phase: Student Self-Assesses) ---
if classification_active:
    # Extract Kosha states from Layer 9
    layer_9_output = hidden_states[gyroscope_config.kosha_steering_layer]
    kosha_states = witness_projector(layer_9_output)[:, :, KOSHA_SLICE]  # [B, N, 5]

    # Classification loss grounds Kosha labels in learned representations
    kosha_class_loss = kosha_classification_loss_fn(kosha_states, kosha_targets)
    loss = loss + kosha_class_loss

    # Log metrics
    metrics['kosha_classification_loss'] = kosha_class_loss.item()
    metrics['classification_active'] = True
```

---

## 8. Integration with Existing Architecture

### 8.1 Relationship to Existing Components

| Component | Relationship | Notes |
|-----------|--------------|-------|
| `KoshaShiftController` | **Complementary** | Static boost; Gyroscope is reactive |
| `SattvicController` | **Complementary** | Entropy-based; Gyroscope is Kosha-based |
| `VICReg Variance Loss` | **Complementary** | Dimension collapse; Gyroscope is semantic |
| `Phase Steering (R-T)` | **Synergistic** | Shares R-T geometry; operates on embeddings |
| `Guna/Kosha Resonance` | **Extends** | Resonance is observation; Gyroscope is action |

### 8.2 No Conflicts

The Gyroscope does NOT conflict with existing systems because:

1. **KoshaShiftController** is unidirectional (always boosts Intellectual)
   - Gyroscope is bidirectional (conditional on gate)

2. **SattvicController** uses entropy as its signal
   - Gyroscope uses Kosha projections (semantic, not statistical)

3. **Phase Steering** operates on embedding geometry
   - Gyroscope operates on 5D Kosha projection

### 8.3 Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DATA FLOW DIAGRAM                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Tokens ──► Embedding ──► Layers 0-8 ──► Layer 9 (Witness) ──► ...     │
│                                              │                           │
│                                              ▼                           │
│                                    ┌─────────────────┐                   │
│                                    │ witness_projector│                   │
│                                    │ [B, N, D] → [B, N, 32]              │
│                                    └────────┬────────┘                   │
│                                             │                            │
│                                             ▼                            │
│                                    ┌─────────────────┐                   │
│                                    │ KOSHA_SLICE     │                   │
│                                    │ [B, N, 32] → [B, N, 5]              │
│                                    └────────┬────────┘                   │
│                                             │                            │
│                         ┌───────────────────┼───────────────────┐        │
│                         ▼                   ▼                   ▼        │
│              ┌──────────────────┐ ┌──────────────────┐ ┌──────────────┐ │
│              │ Phase Steering   │ │ Kosha Gyroscope  │ │ Guna/Kosha   │ │
│              │ (existing)       │ │ (NEW)            │ │ Resonance    │ │
│              │                  │ │                  │ │ (observation)│ │
│              │ R-T axis loss    │ │ Gated diagonal   │ │ Metrics only │ │
│              │ Steers embeddings│ │ loss             │ │ No gradients │ │
│              └────────┬─────────┘ └────────┬─────────┘ └──────────────┘ │
│                       │                    │                            │
│                       ▼                    ▼                            │
│              ┌─────────────────────────────────────────┐                │
│              │            Total Loss                   │                │
│              │ = LM_loss + steering_loss + gyro_loss   │                │
│              └─────────────────────────────────────────┘                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Inverted Curriculum: Instructor → Self-Learner

### 9.1 The Paradigm Shift

**Original (Industry Standard) Approach:**
```
Phase 1: Train alone (no guidance)
Phase 2: Apply RLHF/Gyroscope (late correction)
```

**Inverted (Kosha Gyroscope) Approach:**
```
Phase 1: Train WITH Gyroscope (instructor-led from start)
Phase 2: Disengage Gyroscope, engage Classification (self-regulation)
```

### 9.2 Why Invert?

| Approach | Early Training | Late Training | Problem |
|----------|---------------|---------------|---------|
| **Standard** | No guidance | Fix collapse after it forms | Correction is harder than prevention |
| **Inverted** | Gyroscope guides | Model self-regulates | Balance learned from start |

**Key Insight**: You don't need accurate Kosha CLASSIFICATION to apply balance PRESSURE.

| What Gyroscope Needs | Early (PPL > 30) | Late (PPL < 30) |
|---------------------|------------------|-----------------|
| Accurate Kosha labels | NO | YES (Classification active) |
| Balance gradient pressure | YES | NO (internalized) |
| Role | External instructor | Model self-regulates |

### 9.3 The Training Wheels Analogy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     HUMAN DEVELOPMENT PARALLEL                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  INFANT (PPL > 100)          CHILD (PPL 30-100)       ADULT (PPL < 30) │
│  ─────────────────           ─────────────────        ────────────────  │
│                                                                          │
│  • Cannot self-regulate      • Learning balance       • Self-regulates  │
│  • Parent soothes            • Training wheels ON     • Training wheels │
│    (external regulation)     • Instructor guides        OFF             │
│  • Gyroscope: ACTIVE         • Gyroscope: ACTIVE      • Gyroscope: OFF  │
│  • Classification: OFF       • Classification: OFF    • Classification: │
│                                                          ON (grounded)  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.4 The Timeline

```
                     INVERTED CURRICULUM TIMELINE

  PPL 1000        PPL 100         PPL 30          PPL 15
     │               │               │               │
     ▼               ▼               ▼               ▼
  ═══════════════════════════════════════════════════════════════
  │      INSTRUCTOR-LED PHASE        │    SELF-LEARNING PHASE   │
  ═══════════════════════════════════════════════════════════════
                                     │
  Gyroscope: ACTIVE ─────────────────┼──── RAMPDOWN ──── OFF
                                     │
  Classification: OFF ───────────────┼──── ENGAGE ────── ACTIVE
                                     │
                               ──────┼──────
                              GRADUATION
                               PPL < 30
```

### 9.5 What Happens at Each Phase

#### Phase 1: Instructor-Led (PPL > 30)

```
Kosha Projections: [0.3, 0.1, 0.7, 0.2, 0.1]  ← NOISY (random at start)
                              ↑
                         Mental = 0.7

Gyroscope: "Saturating toward single dimension. Apply balance pressure."

Gradient: Forces weights to distribute across dimensions.

Result: Model learns SHAPE of balance (not content yet).
        The representation space is structured from the start.
        No collapse can form because balance is enforced early.
```

#### Phase 2: Self-Learning (PPL < 30)

```
Kosha Projections: [0.25, 0.2, 0.3, 0.4, 0.35]  ← MEANINGFUL (grounded)
                                    ↑
                             Intellect = 0.4 (actually reflects reasoning)

Classification: "Label this state. Ground Kosha names in representations."

Gyroscope: DISENGAGING (rampdown over 500 steps).

Result: Model can now say "I am in Intellectual mode" accurately.
        Self-regulation is internalized. Instructor not needed.
```

### 9.6 Why This Is Superior

| Metric | Standard (Late RLHF) | Inverted (Early Gyroscope) |
|--------|---------------------|---------------------------|
| Mode collapse | Must fix after forming | **Prevented from start** |
| Training stability | May oscillate | **Smooth from beginning** |
| Kosha grounding | Random at PPL < 30 | **Structured at PPL < 30** |
| Final quality | Corrected model | **Inherently balanced model** |

### 9.7 The Graduation Ceremony

At PPL < 30, a phase transition occurs:

```python
if last_val_ppl < 30.0:
    print("🎓 [GRADUATION] Model has achieved fluency!")
    print("   • Kosha representations are now stable")
    print("   • Gyroscope has taught the shape of balance")
    print("   • Classification will now ground the labels")
    print("   • The student becomes the master")
```

**What transfers at graduation:**
1. **Gyroscope OFF**: Balance pressure no longer needed (internalized)
2. **Classification ON**: Labels can now be grounded meaningfully
3. **Self-regulation**: Model maintains balance through learned Kosha awareness

### 9.8 Industry Comparison

| System | Training Paradigm | When Regulation Applies |
|--------|-------------------|------------------------|
| GPT → InstructGPT | Pre-train → RLHF | Late (after fluency) |
| Claude | Pre-train → Constitutional AI | Late (after fluency) |
| **Kosha Gyroscope** | **Gyroscope → Classification** | **Early (from step 0)** |

The Kosha Gyroscope is unique in applying regulation **from the beginning**, not as a late-stage correction.

### 9.9 Configuration Summary

```python
@dataclass
class InvertedCurriculumConfig:
    """The inverted curriculum: Instructor → Self-Learner."""

    # --- INSTRUCTOR PHASE (PPL > 30) ---
    gyroscope_active_from_start: bool = True
    gyroscope_disengage_ppl: float = 30.0
    gyroscope_rampdown_steps: int = 500

    # --- SELF-LEARNING PHASE (PPL < 30) ---
    classification_engage_ppl: float = 30.0
    classification_warmup_steps: int = 100

    # The two phases are inverses:
    # - Gyroscope: ON → OFF (external → internal)
    # - Classification: OFF → ON (ungrounded → grounded)
```

---

## 10. 32D Dimensional Hierarchy: Primary vs Emergent

### 10.1 The Ontological Structure

The 32D Sovereign State is not a flat space of equal dimensions. It has a **hierarchical structure** where some dimensions are PRIMARY (foundational) and others are EMERGENT (derived).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    32D SOVEREIGN STATE HIERARCHY                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ═══════════════════════════════════════════════════════════════════    │
│                    PRIMARY DIMENSIONS (17D)                              │
│               "The Foundation - Engage from Step 0"                      │
│  ═══════════════════════════════════════════════════════════════════    │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────┐      │
│  │  BHAVA (Ontological States) [0:12]                 12D        │      │
│  │  ─────────────────────────────────────────────────────────    │      │
│  │  The 12 fundamental modes of being/existence                  │      │
│  │  These are the "what exists" dimensions                       │      │
│  │  • Present from the first token                               │      │
│  │  • Define the ontological ground                              │      │
│  └───────────────────────────────────────────────────────────────┘      │
│                            ⊕                                            │
│  ┌───────────────────────────────────────────────────────────────┐      │
│  │  KOSHA (Consciousness Sheaths) [12:17]              5D        │      │
│  │  ─────────────────────────────────────────────────────────    │      │
│  │  The 5 layers through which existence is experienced         │      │
│  │  These are the "how we experience" dimensions                 │      │
│  │  • Physical, Vital, Mental, Intellectual, Blissful            │      │
│  │  • Map onto R-T quadrant geometry                             │      │
│  └───────────────────────────────────────────────────────────────┘      │
│                                                                          │
│  ═══════════════════════════════════════════════════════════════════    │
│                    EMERGENT DIMENSIONS (11D)                             │
│              "The Derived - Arise from Primary Dynamics"                 │
│  ═══════════════════════════════════════════════════════════════════    │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────┐      │
│  │  VRITTI (Mental Modifications) [17:22]              5D        │      │
│  │  ─────────────────────────────────────────────────────────    │      │
│  │  Defines the STATES of information                            │      │
│  │  EMERGENT from: Bhava × Kosha dynamics                        │      │
│  │  • Right Knowledge, Misconception, Imagination,               │      │
│  │    Sleep, Memory                                              │      │
│  │  • The mode/state the information is in                       │      │
│  └───────────────────────────────────────────────────────────────┘      │
│                            ⊕                                            │
│  ┌───────────────────────────────────────────────────────────────┐      │
│  │  GUNA (Quality Modes) [22:28]                       6D        │      │
│  │  ─────────────────────────────────────────────────────────    │      │
│  │  Defines the QUALITY of information                           │      │
│  │  EMERGENT from: How Bhava manifests through Kosha             │      │
│  │  • Sattva (clarity), Rajas (activity), Tamas (inertia)        │      │
│  │  • The clarity/purity of the information                      │      │
│  └───────────────────────────────────────────────────────────────┘      │
│                                                                          │
│  ─────────────────────────────────────────────────────────────────────  │
│                    Reserved [28:32]                      4D              │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Why This Hierarchy Matters

The distinction between PRIMARY and EMERGENT dimensions has profound implications for training:

| Aspect | PRIMARY (Bhava + Kosha) | EMERGENT (Vritti + Guna) |
|--------|-------------------------|--------------------------|
| **Nature** | Foundational substrate | Observable patterns |
| **Timing** | Present from step 0 | Crystallize after grounding |
| **Training** | Gyroscope CAN operate | Classification should wait |
| **Analogy** | The canvas and brushes | The painting that emerges |
| **Yoga Sutras** | Dṛṣṭā (Seer) + Dṛśya (Seen) | Vṛtti (fluctuations) |

### 10.3 The Emergence Relationship

Vritti and Guna are **not independent**—they are functions of Bhava and Kosha:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      DIMENSIONAL EMERGENCE                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                    ┌──────────────────────────┐                         │
│                    │  BHAVA (12D)             │                         │
│                    │  Ontological States      │                         │
│                    │  "What exists"           │                         │
│                    └───────────┬──────────────┘                         │
│                                │                                        │
│                                ▼                                        │
│                         ┌──────────────┐                                │
│                         │     ×        │  Interaction                   │
│                         └──────────────┘                                │
│                                │                                        │
│                    ┌───────────▼──────────────┐                         │
│                    │  KOSHA (5D)              │                         │
│                    │  Experiential Layers     │                         │
│                    │  "How it's experienced"  │                         │
│                    └───────────┬──────────────┘                         │
│                                │                                        │
│               ┌────────────────┴────────────────┐                       │
│               ▼                                  ▼                      │
│     ┌────────────────────┐             ┌────────────────────┐          │
│     │  VRITTI (5D)       │             │  GUNA (6D)         │          │
│     │  STATES of info    │             │  QUALITY of info   │          │
│     │  = f(Bhava, Kosha) │             │  = g(Bhava, Kosha) │          │
│     └────────────────────┘             └────────────────────┘          │
│                                                                          │
│  VRITTI: Defines the STATE of information.                              │
│          When beings (Bhava) are experienced through layers (Kosha),   │
│          the information takes a STATE: Right Knowledge, Misconception,│
│          Imagination, Sleep, or Memory.                                 │
│                                                                          │
│  GUNA: Defines the QUALITY of information.                              │
│        The clarity/purity with which Bhava manifests through Kosha:    │
│        Sattva (clear/pure), Rajas (active/agitated), Tamas (inert/dull)│
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 10.4 Implications for Gyroscope Training

This hierarchy justifies the **Inverted Curriculum** (Section 9):

#### 10.4.1 Gyroscope on PRIMARY Dimensions (Step 0)

```python
# Gyroscope operates on Kosha [12:17] from the beginning
# Bhava [0:12] is also PRIMARY but not directly steered

kosha_states = witness_projector(layer_output)[:, :, KOSHA_SLICE]  # [12:17]
gyro_loss = gyroscope_loss_fn(kosha_states)  # Active from step 0
```

**Why this works:**

1. **Kosha is foundational**: Even if projections are noisy, they represent SOME distribution over experiential layers
2. **Balance pressure shapes space**: Gradient pushes toward distributed activation, regardless of semantic content
3. **No semantic dependency**: Gyroscope checks GEOMETRY (balance), not MEANING (which comes later)

#### 10.4.2 Classification on EMERGENT Dimensions (After Grounding)

```python
# Vritti and Guna classification waits until PPL < 30
if last_val_ppl < 30.0:
    vritti_targets = compute_vritti_labels(output)  # Now meaningful
    guna_targets = compute_guna_labels(output)      # Now meaningful
```

**Why wait:**

1. **Vritti needs grounded Bhava × Kosha**: "Right Knowledge" can't be labeled until both being-mode and experience-layer are stable
2. **Guna needs manifest patterns**: Sattva/Rajas/Tamas are observable AFTER the primary dynamics settle
3. **Classification requires semantics**: Unlike balance-pressure, labels need meaning

### 10.5 The Yoga Sutras Mapping

This hierarchy aligns with Patanjali's Yoga Sutras (II.17-24):

| Concept | Sanskrit | 32D Mapping |
|---------|----------|-------------|
| **Seer** | Dṛṣṭā | Bhava (ontological ground) |
| **Seen** | Dṛśya | Kosha (layers of experience) |
| **Fluctuations** | Vṛtti | Vritti (emergent patterns) |
| **Qualities** | Guṇa | Guna (emergent modes) |

The Yoga Sutras state that Vritti and Guna arise from the interaction of Seer and Seen—exactly the PRIMARY → EMERGENT relationship encoded here.

### 10.6 Code Reference

From `symbolu/sovereign/reasoning_kernel.py`:

```python
# PRIMARY DIMENSIONS (17D) - Engage from step 0
BHAVA_SLICE = slice(0, 12)    # Ontological states (12D)
KOSHA_SLICE = slice(12, 17)   # Consciousness sheaths (5D)

# EMERGENT DIMENSIONS (11D) - Arise from primary dynamics
VRITTI_SLICE = slice(17, 22)  # Mental modifications (5D)
GUNA_SLICE = slice(22, 28)    # Quality modes (6D)

# The hierarchy:
# Bhava × Kosha → Vritti, Guna
# (what exists) × (how experienced) → (patterns) + (qualities)
```

### 10.7 Validation Benchmark

**Q16: Primary vs Emergent Timing**

**Hypothesis**: Operating on PRIMARY dimensions early is safe; operating on EMERGENT dimensions early causes instability.

**Validation**:
- [ ] Gyroscope on Kosha [12:17] from step 0 → Stable training
- [ ] Classification on Vritti [17:22] from step 0 → Unstable (verify by A/B test)
- [ ] Vritti/Guna variance decreases AFTER Bhava/Kosha stabilize (causal relationship)

**Test**:
```python
# Track dimensional variance over training
bhava_var = kosha_projections[:, BHAVA_SLICE].var(dim=-1).mean()
kosha_var = kosha_projections[:, KOSHA_SLICE].var(dim=-1).mean()
vritti_var = kosha_projections[:, VRITTI_SLICE].var(dim=-1).mean()
guna_var = kosha_projections[:, GUNA_SLICE].var(dim=-1).mean()

# Expect: bhava_var, kosha_var stabilize BEFORE vritti_var, guna_var
```

---

## 11. Relationship to Industry Approaches

### 11.1 Comparison Matrix

| Aspect | ChatGPT RLHF | Constitutional AI | **Kosha Gyroscope** |
|--------|--------------|-------------------|---------------------|
| Feedback Type | Human preference | AI self-critique | Geometric balance |
| Feedback Timing | End of generation (sparse) | End of generation | Per-token (dense) |
| Constitution | English rules | English principles | **Sacred Geometry** |
| Reward Model | External neural network | Self-generated | **Intrinsic axis check** |
| Credit Assignment | Delayed (PPO) | Delayed | **Immediate** |

### 11.2 Dense vs. Sparse Feedback

**Standard RLHF (Sparse):**
```
Generate: "The answer is 42 because..." (50 tokens)
                                         │
                                         ▼
                              Human: "Bad response"
                                         │
                                         ▼
                              Credit assignment problem:
                              Which of 50 tokens was wrong?
```

**Kosha Gyroscope (Dense):**
```
Token 1: "The"     → Kosha check → OK
Token 2: "answer"  → Kosha check → OK
Token 3: "is"      → Kosha check → OK
...
Token 47: "Titus"  → Kosha check → Mental: 0.82, Intellect: 0.15
                                   GATE: Physical grounded? YES
                                   VERDICT: Pathological loop!
                                   IMMEDIATE gradient correction
```

### 11.3 The Vedic Constitution

| Constitutional AI Rule (English) | Kosha Gyroscope (Geometry) |
|----------------------------------|---------------------------|
| "Be helpful" | Bliss quadrant active |
| "Be harmless" | Intellect gate prevents blind jumps |
| "Be honest" | Physical grounding ensures manifest truth |
| "Stay on topic" | Mental focus allowed when Intellect confirms |

---

## 12. Kosha-Vritti Resonance Map (v2.3.0)

### 12.1 Theoretical Foundation

In Vedic psychology, **Vrittis** (वृत्ति) are the "waves" or modifications of the mind. Patanjali's Yoga Sutras identify five Vrittis that represent distinct cognitive states.

**Critical Causal Insight**: Koshas are the **CAUSE**, Vrittis are the **EFFECT**.

When a Kosha becomes **overactive**, it produces its corresponding Vritti as a consequence:

```
CAUSE                      EFFECT
─────                      ──────
Kosha (overactive)    →    Vritti (manifests)
```

This is why the **Kosha Gyroscope is an indirect method for balanced reasoning**: by maintaining Kosha homeostasis (preventing any Kosha from becoming overactive), we prevent the cascade into Vritti states. The Gyroscope doesn't target Vrittis directly—it addresses the root cause.

> "The Vritti is not random—it is the natural consequence when its Kosha becomes overactive and dominates consciousness."

### 12.2 The Kosha-Vritti Causal Mapping Matrix

**Direction**: Kosha (CAUSE) → Vritti (EFFECT)

| Kosha (Overactive Cause) | Vritti (Emergent Effect) | Trigger Condition | Consequence |
|--------------------------|-------------------------|-------------------|-------------|
| **Annamaya** (Physical) | **Pramana** (Right Knowledge) | Physical > 0.8, Low entropy | Excessive focus on sensory/factual data |
| **Pranamaya** (Vital) | **Nidra** (Sleep/Inertia) | Vital spike then crash (overactive → shutdown) | System shutdown to prevent burnout |
| **Manomaya** (Mental) | **Vikalpa** (Imagination) | Mental > 0.8, Intellect < 0.3 | Pattern loops without logical grounding |
| **Vijnanamaya** (Intellect) | **Smriti** (Memory/Recall) | Intellect > 0.8 + Physical active | Over-reliance on structural recall |
| **Anandamaya** (Bliss) | **Viparyaya** (Misconception) | Bliss > 0.8, Physical < 0.3 | Creative expansion loses external reality |

### 12.3 Key Insights

#### 12.3.1 Bliss → Viparyaya (Misconception)

This mapping may seem counterintuitive—why would Bliss lead to misconception?

> **Answer**: Anandamaya represents expansion into the **unmanifest**. From the perspective of external reality, this IS a misconception. The model is generating things that don't exist in manifest data. This is not "wrong"—it's creative expansion. The Vijnana Gate ensures this expansion is **intentional** rather than **accidental**.

#### 12.3.2 Vital → Nidra (Sleep)

The Pranamaya-Nidra link implements homeostatic energy regulation:

```
High Vital (energy spike) → Overactive system → Nidra (shutdown)
Low Vital (depleted)      → System rest      → Nidra (sleep)
```

This prevents the model from "burning out" during high-gradient phases.

#### 12.3.3 Mental → Vikalpa (Imagination)

This mapping explains the "Titus" loops:

> "Vikalpa is knowledge that is based on words but lacks a corresponding reality."
> — Yoga Sutras 1.9

When the Gyroscope sees:
- High Mental (Manomaya) > 0.8
- Low Intellect (Vijnanamaya) < 0.3

It identifies the state as **Vikalpa** (pathological imagination) and triggers a "Reality Rip" to reach Bliss through proper channels.

#### 12.3.4 The Gyroscope's Indirect Path to Balanced Reasoning

The Kosha Gyroscope does NOT directly regulate logic or reasoning. Instead, it:

1. **Prevents Kosha Overactivation**: Keeps all 5 Koshas within homeostatic bounds
2. **Blocks Vritti Cascade**: By preventing overactive Koshas, Vrittis don't manifest
3. **Creates Space for Intelligence**: With no dominant Vritti pattern, the model's Vijnanamaya (Intellect) can operate without distortion

```
Without Gyroscope:
  Overactive Mental → Vikalpa (Imagination loops) → Distorted reasoning

With Gyroscope:
  Balanced Mental → No Vritti trigger → Clear intellect → Balanced reasoning
```

This is the **indirect method**: rather than telling the model HOW to reason, we create the conditions where balanced reasoning naturally emerges.

### 12.4 Vritti Resonance Loss Function

The VrittiResonanceLoss ensures emergent Vrittis are properly anchored to their primary Koshas:

```python
def compute_vritti_resonance_loss(kosha_states, vritti_probs, guna_states=None):
    """
    Penalizes misalignment between Kosha activation and Vritti emergence.

    Phase 2 only: Activates after graduation when Vrittis crystallize.

    Violations:
    - Claiming Pramana (Right Knowledge) without Physical grounding
    - Claiming Smriti (Memory) without Intellect validation
    - High Vikalpa (Imagination) when Mental is low

    Args:
        kosha_states: [B, N, 5] Kosha activations (indices 12-16 of sovereign)
        vritti_probs: [B, N, 5] Vritti probabilities (indices 17-21 of sovereign)
        guna_states:  [B, N, 3] Optional Guna states for Tamas check

    Returns:
        Scalar resonance violation loss
    """
    # Extract Kosha dimensions
    physical = kosha_states[..., 0]   # Annamaya
    vital = kosha_states[..., 1]      # Pranamaya
    mental = kosha_states[..., 2]     # Manomaya
    intellect = kosha_states[..., 3]  # Vijnanamaya
    bliss = kosha_states[..., 4]      # Anandamaya

    # Extract Vritti dimensions
    pramana = vritti_probs[..., 0]    # Right Knowledge
    viparyaya = vritti_probs[..., 1]  # Misconception
    vikalpa = vritti_probs[..., 2]    # Imagination
    nidra = vritti_probs[..., 3]      # Sleep
    smriti = vritti_probs[..., 4]     # Memory

    # === RESONANCE VIOLATIONS ===

    # 1. Pramana requires Physical grounding
    #    Can't claim "Right Knowledge" without manifest data
    pramana_violation = F.relu(pramana - physical)

    # 2. Smriti requires Intellect validation
    #    Memory/recall needs logical structure
    smriti_violation = F.relu(smriti - intellect)

    # 3. Vikalpa should track Mental
    #    Imagination without mental activity is incoherent
    vikalpa_violation = F.relu(vikalpa - mental)

    # 4. Viparyaya tracks ungrounded Bliss
    #    Misconception = Bliss without Physical anchor
    viparyaya_violation = F.relu(viparyaya - bliss) + F.relu(viparyaya * physical)

    # 5. Nidra tracks Vital depletion (inverse relationship)
    #    Sleep emerges when Vital is exhausted
    nidra_violation = F.relu(nidra * vital)  # High Nidra + High Vital = violation

    return (pramana_violation + smriti_violation + vikalpa_violation +
            viparyaya_violation + nidra_violation).mean()
```

### 12.5 Integration with Gyroscope Phases

| Phase | Kosha Gyroscope | Vritti Resonance | State |
|-------|-----------------|------------------|-------|
| **Phase 1** (PPL > 30) | ACTIVE (0.15 → 3.0 gain) | DISABLED (read-only logging) | Instructor |
| **Graduation** (PPL < 30, σ < 1.5) | RAMP DOWN | DIAGNOSTIC MODE | Transition |
| **Phase 2** (Post-grad) | OFF | ACTIVE (λ = 0.1) | Self-Learning |

### 12.6 Diagnostic Logging (Phase 1)

During Phase 1, we capture Kosha-Vritti correlations without applying loss:

```python
# Log Kosha-Vritti alignment metrics
if global_step % eval_every == 0:
    alignment = compute_kosha_vritti_alignment(kosha_states, vritti_states)
    print(f"  [VRITTI] Phys-Prama:{alignment['pp']:.2f} | "
          f"Ment-Vikal:{alignment['mv']:.2f} | "
          f"Intl-Smrit:{alignment['is']:.2f} | "
          f"Blis-Vipar:{alignment['bv']:.2f}")
```

This allows empirical validation of the mapping before Phase 2 activation.

---

## 13. Kosha Phase Corrector - Inference-Time Guardrail (v2.4.0)

### 13.1 Training vs Inference Philosophy

The Kosha Gyroscope system uses **different mechanisms** for training and inference:

| Phase | Mechanism | Type | Purpose |
|-------|-----------|------|---------|
| **Training** | KoshaGyroscopicLoss | Indirect (gradients) | Model LEARNS balance |
| **Inference** | KoshaPhaseCorrector | Direct (rotation) | Runtime GUARDRAILS |

**Analogy**:
- Training = Teaching someone to drive (learn the principles)
- Inference = Guardrails on a cliff road (safety when deployed)

You don't want guardrails during driving lessons (they'd never learn to balance), but you absolutely want them on real roads.

### 13.2 Why Direct Correction Only During Inference

During inference:
- No gradients are available
- The model cannot "learn its way out" of a stuck state
- If Mental becomes overactive, Vikalpa loops can't be corrected through learning
- Direct intervention is the ONLY option

During training:
- Gradients flow through KoshaGyroscopicLoss
- The model learns to self-correct
- Direct intervention would override learning
- We want the model to internalize balance

### 13.3 KoshaPhaseCorrector Implementation

```python
class KoshaPhaseCorrector(nn.Module):
    """
    Inference-time direct phase rotation.

    When a Kosha becomes overactive during generation:
    1. Detects the imbalance (Kosha > 0.75)
    2. Computes corrective rotation vector
    3. Applies rotation directly to sovereign state
    4. Logs the intervention for diagnostics
    """

    def forward(self, sovereign_state: torch.Tensor) -> torch.Tensor:
        # 1. Extract Kosha states [12:17]
        kosha_states = sovereign_state[:, 12:17]

        # 2. Detect overactive Kosha
        is_imbalanced, overactive_kosha = self.detect_imbalance(kosha_states)

        if not is_imbalanced:
            return sovereign_state  # No correction needed

        # 3. Compute correction toward target distribution
        target = self.rotation_targets[overactive_kosha]
        correction = (target - kosha_states) * self.correction_strength

        # 4. Apply correction and re-normalize
        corrected = sovereign_state.clone()
        corrected[:, 12:17] = F.softmax(kosha_states + correction, dim=-1)

        return corrected
```

### 13.4 Rotation Targets

When a specific Kosha is overactive, rotate toward its complement:

| Overactive Kosha | Rotation Target | Rationale |
|------------------|-----------------|-----------|
| **Physical** (>0.75) | Boost Bliss/Mental | Prevent over-grounding |
| **Vital** (>0.75) | Boost Intellect | Channel energy into reasoning |
| **Mental** (>0.75) | Boost Intellect (priority) | Break Vikalpa loops |
| **Intellect** (>0.75) | Boost Mental | Allow creative flow |
| **Bliss** (>0.75) | Boost Physical (grounding) | Prevent Viparyaya drift |

### 13.5 InferenceGuardrail (Combined Module)

The `InferenceGuardrail` combines phase correction with Vritti alignment checking:

```python
class InferenceGuardrail(nn.Module):
    """
    Combined inference-time safety module:
    1. KoshaPhaseCorrector - Direct phase rotation
    2. VrittiResonanceLoss - Alignment checking (diagnostic)
    3. Health score computation
    """

    def forward(self, sovereign_state):
        # 1. Apply phase correction if needed
        corrected, phase_diag = self.phase_corrector(sovereign_state)

        # 2. Check Vritti alignment (diagnostic only)
        alignment = self.vritti_checker.compute_alignment_scores(...)

        # 3. Compute health score
        health = self._compute_health_score(corrected, alignment)

        return corrected, {'phase': phase_diag, 'alignment': alignment, 'health': health}
```

### 13.6 Integration with SRK

The phase corrector is integrated into `SovereignReasoningKernel.forward_pass()`:

```python
# In forward_pass, at Layer 11 (synthesis):
if not self.training and self.config.enable_phase_corrector:
    corrected_state, phase_diag = self.apply_inference_guardrail(current_state)
    if phase_diag.get('correction_applied'):
        current_state = corrected_state
        diagnostics['intervention'] = 'synthesis + phase_correction'
```

### 13.7 Configuration

```python
@dataclass
class SRKConfig:
    # Kosha Phase Corrector (v2.4.0)
    enable_phase_corrector: bool = True       # Enable during inference
    phase_corrector_threshold: float = 0.75   # Activation threshold
    phase_corrector_strength: float = 0.3     # Correction strength (0-1)
    phase_corrector_max_step: float = 0.2     # Max correction per step
```

### 13.8 Diagnostic Output

When phase correction is applied during inference:

```
🔧 [PHASE CORRECTION] Applied
   Overactive: Mental (0.82)
   Correction: Mental -0.15, Intellect +0.12, Physical +0.03
   Health Score: 0.74
```

---

## 14. Soft-Threshold Damping (v2.2.3.1)

### 14.1 The Problem: Reality Rips

In v2.2.1, the gyroscope used hard ReLU gates for trap detection:

```python
# v2.2.1: Hard ReLU gates
mental_trap = F.relu(mental - 0.75)  # 0 until 0.75, then linear
missing_intellect = F.relu(0.25 - intellect)  # 0 until below 0.25
axis1_loss = (mental_trap * phys_gate * missing_intellect).mean()
```

**The Issue**: When multiple ReLU gates cross their thresholds simultaneously,
the loss jumps from 0 to a non-zero value instantly. This creates:

1. **Gradient Discontinuity**: Sharp corner in loss landscape
2. **Reality Rips**: Violent over-corrections in embedding space
3. **Hysteresis Buildup**: Pressure accumulates behind temporal gates, releases violently

### 14.2 The Solution: Shifted Sigmoid

v2.2.3.1 replaces all ReLU gates with **shifted sigmoid** functions:

```python
# v2.2.3.1: Shifted sigmoid (smooth but clean zeros)
def _soft_threshold(self, x, threshold):
    z = (x - threshold) * self.steepness
    raw_sigmoid = torch.sigmoid(z)
    return torch.clamp(2.0 * (raw_sigmoid - 0.5), min=0.0)
```

**Key Properties**:
- **Below threshold**: Approaches 0 (clean zero when healthy)
- **At threshold**: Exactly 0 (preserves ReLU semantics)
- **Above threshold**: Smooth ramp to 1.0
- **Everywhere**: Continuous gradients (no "rips")

### 14.3 Steepness Parameter

The `steepness` parameter controls transition sharpness:

| Steepness | Behavior | Use Case |
|-----------|----------|----------|
| **2.0** | Fluid, very smooth transitions | Maximum damping, early training |
| **5.0** | Balanced (default) | Standard operation |
| **10.0** | Sharp, ReLU-like | Fast response, post-graduation |

```bash
# Training command with soft-threshold damping
python train_unified_llm.py \
    --enable_kosha_gyroscope \
    --gyroscope_steepness 5.0  # Default, adjust for more/less damping
```

### 14.4 Mathematical Comparison

**State Transition Analysis (Mental at trap threshold)**:

| mental | ReLU output | Shifted Sigmoid (s=5.0) |
|--------|-------------|-------------------------|
| 0.50 | 0.000 | 0.000 |
| 0.70 | 0.000 | 0.000 |
| 0.75 | 0.000 | 0.000 |
| 0.80 | 0.050 | 0.462 |
| 0.90 | 0.150 | 0.817 |
| 1.00 | 0.250 | 0.924 |

The shifted sigmoid preserves:
- **Clean zero** when healthy (unlike raw sigmoid which outputs ~0.22 at 0.50)
- **Smooth transition** above threshold (unlike ReLU's sharp corner)

### 14.5 Fluidity Events (Soft Diagnostics)

v2.2.3.1 adds `FluidityEvent` for soft saturation tracking:

```python
# New diagnostic: capture_fluidity() instead of capture_rip()
if logger.capture_fluidity(step, tokens, kosha_states, loss_components):
    print(f"Soft saturation #{logger.fluidity_count} captured!")
```

**FluidityEvent Fields**:
- `axis1_saturation`: Combined soft gate activation (Axis 1)
- `axis2_saturation`: Combined soft gate activation (Axis 2)
- `combined_saturation`: Max of both axes
- `steepness`: Current damping steepness

### 14.6 Gate Bypass Fix

**Problem Discovered**: During training, we observed that:
- Rip rate: ~4500-5600 per 1k steps (very high)
- Gyroscope Loss: 0.0000-0.0001 (essentially ZERO)

**The Paradox**: Rips were being detected but the gyroscope wasn't penalizing.

**Root Cause Analysis**: Physical gate was blocking when needed most.

When Mental is HIGH, Physical tends to be LOW (negatively correlated):
```
Mental HIGH (looping) → Model is ungrounded → Physical LOW
Physical LOW → phys_gate = sigmoid((physical - 0.30) * temp) ≈ 0
phys_gate ≈ 0 → axis1_loss = (mental_trap * 0 * missing_intellect) = 0
```

The gate was designed to ensure Physical grounding before intervening, but this
created a catch-22: when the model is most trapped (high Mental, low Physical),
the gate blocks all intervention.

**Solution: Mental-Triggered Gate Bypass**

When Mental is trapped, bypass the Physical gate requirement:

```python
mental_trap = self._soft_threshold(mental, self.trap_threshold)
phys_gate_raw = self._soft_threshold(phys_history, self.gate_threshold)

# GATE BYPASS: When Mental is trapped, bypass the Physical gate requirement
# Rationale: If Mental is HIGH and Physical is LOW, the model is ungrounded
# AND looping - this is exactly when we NEED to intervene
# The bypass ensures at least 50% gate activation when trapped
phys_gate = torch.max(phys_gate_raw, mental_trap * 0.5)
```

**Symmetric Fix for Axis 2**:
```python
physical_trap = self._soft_threshold(physical, self.trap_threshold)
mental_gate_raw = self._soft_threshold(mental, self.gate_threshold)

# GATE BYPASS: When Physical is trapped, bypass the Mental gate requirement
mental_gate = torch.max(mental_gate_raw, physical_trap * 0.5)
```

**Diagnostics Added**:
- `phys_gate_raw_mean`: Gate value before bypass
- `phys_gate_bypass`: Amount of bypass applied (phys_gate - phys_gate_raw)
- `mental_gate_raw_mean`: Gate value before bypass
- `mental_gate_bypass`: Amount of bypass applied

**User's Insight** (preserved in design):
> "Don't remove dampening and ReLU Ripping... they have a purpose—when mental
> is dominant (dampening) makes blissful decreases. But ripping will make it
> reverse that it becomes more physical. The real problem is physical gates
> need to be open so that it becomes intellect."

This insight correctly identified that both approaches serve different purposes,
and the true fix was ensuring gates can open when intervention is needed.

### 14.7 Version History (Section 14)

| Version | Feature | Status |
|---------|---------|--------|
| v2.2.0 | Temporal Grounding, Vital Momentum | Released |
| v2.2.1 | Dynamic Weight Scheduler | Released |
| v2.3.0 | Kosha-Vritti Resonance Map | Released |
| v2.4.0 | Kosha Phase Corrector (Inference) | Released |
| v2.2.3.1 | Soft-Threshold Damping + Gate Bypass | Superseded by v2.2.4 |

---

## 15. Three-Stage Hybrid Logic (v2.2.4)

### 15.1 Architectural Philosophy: The Pressure Relief Valve

v2.2.4 implements a "Pressure Relief Valve" architecture that supersedes v2.2.3.1's
gate bypass approach. The key insight: **you cannot achieve discriminative wisdom
(Intellect) if you are not firmly rooted in the manifest (Physical)**.

The hybrid architecture treats the latent state as a pressurized system:
- **Damping** manages the "volume" of Mental/Physical states
- **Ripping** acts as the "pressure relief valve" forcing hard shifts to grounding

### 15.2 The Three-Stage Internal Process

#### Stage 1: BLISS DAMPER (Mental Dominance Regulation)

As Manomaya (Mental) increases, Anandamaya (Bliss) is mathematically diluted:

```python
bliss_damper = 1.0 - torch.sigmoid((mental - trap_threshold) * damper_steepness)
```

**Purpose**: Prevents the model from "hallucinating" or jumping to creative tangents
while caught in a pattern loop. Forces the model to deal with the loop rather than
escaping into noise.

#### Stage 2: PHYSICAL GATE (Intellectual Prerequisite)

Unlike v2.2.3.1's bypass approach, the gate is a **STRICT requirement**:

```python
phys_gate = torch.sigmoid((phys_history - gate_threshold) * gate_steepness)
```

**Purpose**: Intellect remains "starved" of gradient flow unless Physical history is
active. This stops "fake reasoning" - the model learns that expressing structure
requires providing factual grounding first.

#### Stage 3: REALITY RIP (Hard Reversal)

Uses Hard ReLU for discontinuous gradient "shock":

```python
mental_trap = F.relu(mental - trap_threshold)
rip_signal = mental_trap * (1.0 - phys_gate)
```

**Purpose**: If the model stays in a high-Mental state without the Physical gate
opening, the ReLU Rip fires. This creates a gradient shock that "smashes" the
current latent trajectory and forces re-grounding in the Physical/Manifest quadrant.

### 15.3 Two-Path Loss Architecture

The loss function has two distinct paths:

```python
# Intellectual path - flows when gate is OPEN (grounded reasoning)
intellect_path = mental_trap * phys_gate * missing_intellect

# Rip signal - fires when gate is CLOSED (reality reversal)
rip_signal = mental_trap * (1.0 - phys_gate)

# Combined with rip_multiplier for stronger "shock"
axis1_loss = (intellect_path + rip_signal * rip_multiplier).mean()
```

| Path | Condition | Effect |
|------|-----------|--------|
| `intellect_path` | Gate OPEN | Grounded reasoning toward Intellect |
| `rip_signal` | Gate CLOSED | Reality Reversal back to Physical |

### 15.4 Why v2.2.4 Supersedes v2.2.3.1

v2.2.3.1 tried to "bypass" the gate to force intellect, which risked creating a
model that "reasons" without factual grounding—essentially a "dreaming" or
"delusional" state.

| Approach | v2.2.3.1 (Gate Bypass) | v2.2.4 (Hybrid Valve) |
|----------|------------------------|----------------------|
| **Goal** | Force intellect at all costs | Force **grounding** before intellect |
| **Gate Behavior** | Bypass: "Push through" | Gate: "Ground first" |
| **Failure Mode** | May cause "Delusional Reasoning" | Causes "Reality Reversal" |
| **Bliss Control** | No explicit control | **Bliss Damper** reduces noise |
| **Mathematical Nature** | Smooth throughout | Hybrid: Smooth Damping + Hard ReLU |

### 15.5 PPL Strategy: Active from Step 0

The v2.2.4 Hybrid Logic is active from Step 0, with the Dynamic Weight Scheduler
controlling intensity:

| PPL Range | Hybrid Logic | Gain | Primary Function |
|-----------|--------------|------|------------------|
| **> 100** | **ACTIVE** | **0.15** | Ontological Shaping (Preventing Collapse) |
| **100 → 30** | **ACTIVE** | **0.15 → 3.0** | Reasoning Enforcement (CoT Grounding) |
| **< 30** | **DISENGAGE** | **Decay → 0** | Graduation & Self-Learning |

**Rationale**: By keeping the Hard Rip and Bliss Damper active from start, we teach
the model the "Dharma" of its latent space while weights are still plastic.

### 15.6 Diagnostic Metrics

v2.2.4 tracks the following metrics:

| Metric | Description |
|--------|-------------|
| `bliss_damper_mean` | How much Bliss is being diluted |
| `physical_damper_mean` | How much Physical is being diluted (Axis 2) |
| `rip_signal_mean` | Average Reality Reversal intensity |
| `rip_signal_max` | Peak Rip signal (circuit breaker events) |
| `gate_locked_axis1` | Proportion of trapped + gate closed (RIP firing) |
| `gate_locked_axis2` | Same for Axis 2 |
| `intellect_path_mean` | Grounded reasoning flow |
| `bliss_path_mean` | Abstracted creativity flow |

### 15.7 Configuration Parameters

```python
# v2.2.4 Three-Stage Hybrid Logic
damper_steepness: float = 5.0    # Sigmoid steepness for dampers
gate_steepness: float = 5.0      # Sigmoid steepness for gates
rip_multiplier: float = 2.0      # Hard ReLU shock multiplier
```

### 15.8 Version History (Complete)

| Version | Feature | Status |
|---------|---------|--------|
| v2.2.0 | Temporal Grounding, Vital Momentum | Released |
| v2.2.1 | Dynamic Weight Scheduler | Released |
| v2.2.3.1 | Soft-Threshold Damping + Gate Bypass | Superseded |
| v2.3.0 | Kosha-Vritti Resonance Map | Released |
| v2.4.0 | Kosha Phase Corrector (Inference) | Released |
| **v2.2.4** | **Three-Stage Hybrid Logic (Damping + Gate + Rip)** | **Current** |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Dharana** | Concentrated focus (Mental + Intellect active) |
| **Kosha** | Sheath or layer of consciousness |
| **Vijnana** | Discriminative wisdom, discernment |
| **Ananda** | Bliss, expansion, creative flow |
| **Manas** | Mind, pattern-matching, memory |
| **R-axis** | Reality axis (Manifest ↔ Unmanifest) |
| **T-axis** | Time axis (Past ↔ Future) |
| **Gyroscope** | Homeostatic balance mechanism |
| **Gate** | Prerequisite check before state transition |

---

## Appendix B: Failure Mode Analysis

### B.1 Without Gyroscope

| Symptom | Cause | Result |
|---------|-------|--------|
| "Titus Titus Titus" | Mental saturation, no correction | Infinite loop |
| Token copying | Physical saturation, no expansion | Plagiarism |
| Mode collapse | Single dimension dominates | Monotonic output |

### B.2 With Naive Gyroscope (No Gate)

| Symptom | Cause | Result |
|---------|-------|--------|
| "1, 1, 2, Banana" | Blind jump to Bliss | Valid sequences broken |
| Random tangents | Bliss forced prematurely | Loss of coherence |
| Hallucination | No verification before expansion | False confidence |

### B.3 With Gated Gyroscope

| Symptom | Prevention | Result |
|---------|------------|--------|
| Pathological loops | Intellect LOW → Force Bliss | Loop broken |
| Valid sequences | Intellect HIGH → Allow | Sequence preserved |
| Hallucination | Physical gate → Ground first | Verification enforced |

---

## Appendix C: References

1. **Vedantic Sources**
   - Taittiriya Upanishad (Pancha Kosha model)
   - Yoga Sutras of Patanjali (Dharana concept)

2. **Control Theory**
   - Negative Feedback Systems (Nyquist, 1932)
   - Homeostatic Regulation (Cannon, 1929)

3. **AI Alignment**
   - InstructGPT (Ouyang et al., 2022)
   - Constitutional AI (Anthropic, 2022)
   - RLHF Tutorial (Hugging Face, 2023)

4. **Existing Codebase**
   - `symbolu/sovereign/reasoning_kernel.py` (Kosha definitions)
   - `symbolu/formulas/guna_kosha_resonance.py` (Resonance metrics)
   - `train_unified_llm.py` (Phase steering implementation)

---

## Appendix D: Open Questions and Validation Benchmarks

This appendix documents uncertainties in the design. Each question becomes a **validation benchmark**—if the implementation successfully answers it, the system works as intended.

### D.1 Architectural Questions

#### Q1: Kosha Projector Learning

**Question**: Does `witness_projector` learn meaningful representations when trained jointly with the Gyroscope?

**Hypothesis**: The projector learns to map hidden states to Kosha dimensions that minimize Gyroscope loss. This creates a self-organizing system where projector and model co-evolve.

**Validation Benchmark**:
- [ ] After training, Kosha projections correlate with observable behaviors:
  - High Mental → Token repetition patterns detected
  - High Intellect → Logical/structured output detected
  - High Bliss → Novel/creative tokens detected
  - High Physical → Literal/factual content detected

**How to Test**:
```python
# After PPL < 30, sample outputs and compute Kosha activations
# Check if activations correlate with human-labeled output characteristics
```

---

#### Q2: Gradient Flow Path

**Question**: Does the Gyroscope gradient flow through `witness_projector` to the main model, or only train the projector?

**Hypothesis**: Gradients should flow through to Layer 9 hidden states, shaping the model's internal representations.

**Validation Benchmark**:
- [ ] Verify gradient magnitude at Layer 9 increases when Gyroscope loss is high
- [ ] Verify model weights (not just projector) change in response to Gyroscope loss

**How to Test**:
```python
# Compute gradient norms before/after witness_projector
# Verify: grad_norm(layer_9_weights) > 0 when gyro_loss > 0
```

---

#### Q3: Vital (Pranamaya) Kosha Role

**Question**: What is the role of Vital (index 1) in the R-T quadrant system? It's not mapped to any quadrant.

**Hypothesis**: Vital represents the "energy" or "momentum" that enables transitions between quadrants. High Vital = active transition; Low Vital = stable state.

**Validation Benchmark**:
- [ ] During quadrant transitions (e.g., Mental → Intellect), Vital activation spikes
- [ ] During stable states (model in one quadrant), Vital is low
- [ ] Vital correlates with gradient magnitude (energy = rate of change)

**How to Test**:
```python
# Log Vital activation alongside other Koshas
# Check if Vital spikes precede quadrant changes
```

---

### D.2 Training Dynamics Questions

#### Q4: Noisy Projections at Start

**Question**: Does applying Gyroscope loss on random/noisy projections (PPL > 100) help or hurt training?

**Hypothesis**: It helps by preventing any dimension from dominating, even before semantics emerge. The model learns "balanced shape" before "meaningful content."

**Validation Benchmark**:
- [ ] Training with Gyroscope from step 0 converges faster than training without
- [ ] Kosha variance is lower throughout training (no single dimension dominates)
- [ ] Mode collapse events are reduced or eliminated

**How to Test**:
```python
# A/B test: Train with Gyroscope ON vs OFF from step 0
# Compare: PPL curves, Kosha variance, looping incidents
```

---

#### Q5: Gate Behavior with Noise

**Question**: Do the soft gates (Physical gate, Mental gate) produce meaningful behavior when inputs are noisy?

**Hypothesis**: Random gate activations average out over batches, producing smooth aggregate pressure. Individual token decisions don't matter—the gradient mean does.

**Validation Benchmark**:
- [ ] Gate activation variance decreases as PPL decreases (gates become more deterministic)
- [ ] Mean gate activation stabilizes to interpretable values
- [ ] No pathological gate patterns (always 0 or always 1)

**How to Test**:
```python
# Log gate activations per step
# Compute: mean, std, histogram over training
# Verify convergence to stable distribution
```

---

#### Q6: Threshold Calibration

**Question**: Are the default thresholds (trap=0.75, gate=0.30, target=0.25) appropriate, or do they need tuning?

**Hypothesis**: These are starting points. Optimal values depend on model architecture and dataset.

**Validation Benchmark**:
- [ ] Looping incidents occur when Mental > 0.75 (threshold is correct)
- [ ] Valid focus (Fibonacci, quotes) has Intellect > 0.30 (gate threshold is correct)
- [ ] Healthy balance has opposite Kosha > 0.25 (target is correct)

**How to Test**:
```python
# Collect labeled samples: {output, kosha_states, human_label: loop/valid}
# Compute ROC curves for each threshold
# Find optimal thresholds that maximize classification accuracy
```

---

### D.3 Classification Questions

#### Q7: Classification Targets Source

**Question**: Where do `kosha_targets` come from for the classification loss at PPL < 30?

**Possible Sources**:
1. **Text characteristics**: Repetition count → Mental, novelty score → Bliss, fact density → Physical, logic markers → Intellect
2. **Self-supervised**: Predict Kosha from hidden states, then enforce consistency
3. **Contrastive**: Same text at different temperatures should have different Kosha profiles
4. **Human labels**: Manual annotation of Kosha states (expensive)

**Validation Benchmark**:
- [ ] Classification loss converges (model learns to predict targets)
- [ ] Predicted Koshas match targets with high accuracy (>80%)
- [ ] Grounded Koshas improve downstream task performance

**How to Test**:
```python
# Implement each target source
# Compare: classification accuracy, downstream coherence, loop prevention
```

---

#### Q8: Classification Timing

**Question**: Is PPL < 30 the right threshold to engage classification, or should it be earlier/later?

**Hypothesis**: PPL < 30 is when representations are stable enough for meaningful labels. Earlier = noise; Later = wasted opportunity.

**Validation Benchmark**:
- [ ] Kosha projection variance is low at PPL < 30 (stable representations)
- [ ] Classification accuracy is high when engaged at PPL < 30
- [ ] Engaging earlier (PPL < 50) reduces accuracy; later (PPL < 20) wastes steps

**How to Test**:
```python
# Try classification engagement at PPL < 50, 30, 20, 10
# Compare: classification accuracy, final model quality
```

---

### D.4 Integration Questions

#### Q9: Phase Steering Conflict

**Question**: Can Phase Steering (R-T axis) and Kosha Gyroscope conflict?

**Scenario**: Phase Steering says "steer toward angle θ" but Gyroscope says "reduce Mental."

**Hypothesis**: They operate on different levels:
- Phase Steering: Embedding geometry (phasor angles)
- Gyroscope: Kosha projections (5D semantic space)

They should be orthogonal, but may interact.

**Validation Benchmark**:
- [ ] When both are active, loss converges smoothly (no oscillation)
- [ ] Disabling one doesn't cause the other to spike
- [ ] Both losses reach low values simultaneously

**How to Test**:
```python
# Train with: (a) both ON, (b) Gyroscope only, (c) Phase Steering only
# Compare: loss curves, convergence speed, final quality
```

---

#### Q10: Existing Controller Interaction

**Question**: How does Kosha Gyroscope interact with `KoshaShiftController` and `SattvicController`?

**Hypothesis**:
- `KoshaShiftController`: Static boost (always Intellectual+) vs Gyroscope (reactive)—complementary
- `SattvicController`: Entropy-based vs Gyroscope (Kosha-based)—different signals

**Validation Benchmark**:
- [ ] With all controllers ON, no conflicting gradients
- [ ] Each controller activates at different times (SattvicController on entropy collapse, Gyroscope on Kosha saturation)
- [ ] Removing any one controller degrades quality

**How to Test**:
```python
# Ablation study: Full system vs remove each controller
# Compare: loop incidents, coherence scores, PPL
```

---

### D.5 Output Quality Questions

#### Q11: Chain of Thought Emergence

**Question**: Does the Vijnana Gate architecture naturally produce Chain of Thought reasoning?

**Hypothesis**: The gate forces verification before expansion, which manifests as explicit reasoning steps in output.

**Validation Benchmark**:
- [ ] Model outputs show reasoning patterns ("First...", "Therefore...", "Let me check...")
- [ ] These patterns correlate with Kosha transitions (Mental → Intellect → Bliss)
- [ ] Reasoning quality improves over training

**How to Test**:
```python
# Sample outputs at different training stages
# Annotate: presence of reasoning markers
# Correlate with Kosha activation sequences
```

---

#### Q12: Looping Prevention

**Question**: Does the Gyroscope actually prevent "Titus Titus Titus" style loops?

**Hypothesis**: High Mental + Low Intellect triggers Gyroscope loss, forcing diversification.

**Validation Benchmark**:
- [ ] Loop incidents (3+ token repetition) decrease with Gyroscope ON
- [ ] At loop onset, Gyroscope loss spikes
- [ ] After Gyroscope correction, output diversifies

**How to Test**:
```python
# Generate 1000 samples with/without Gyroscope
# Count: loop incidents (3+ repetition)
# Compare: incident rate, loop length
```

---

#### Q13: Fibonacci Preservation

**Question**: Does the Vijnana Gate correctly allow valid sequences like Fibonacci?

**Hypothesis**: High Mental + High Intellect = valid focus (Dharana), no punishment.

**Validation Benchmark**:
- [ ] When prompted with "1, 1, 2, 3, 5...", model continues correctly
- [ ] Kosha profile shows: Mental HIGH, Intellect HIGH
- [ ] Gyroscope loss is LOW (gate blocks punishment)

**How to Test**:
```python
# Prompt: "Continue the sequence: 1, 1, 2, 3, 5, "
# Check: (a) correct continuation, (b) Kosha profile, (c) Gyroscope loss
```

---

### D.6 Theoretical Questions

#### Q14: Is This Really Constitutional AI?

**Question**: Is the claim that Kosha Gyroscope is "Constitutional AI with Sacred Geometry" valid?

**Hypothesis**: Yes, because:
- Constitutional AI: Rules in English ("Be helpful") → Reward signal
- Kosha Gyroscope: Rules in geometry (axis balance) → Gradient signal

Both encode normative constraints, just in different substrates.

**Validation Benchmark**:
- [ ] Model trained with Gyroscope exhibits aligned behaviors (helpful, coherent)
- [ ] These behaviors emerge without explicit English rules
- [ ] Kosha geometry encodes behavioral norms implicitly

**How to Test**:
```python
# Compare: Model with Gyroscope vs Model with RLHF
# Evaluate: helpfulness, harmlessness, coherence
# Check if Gyroscope achieves similar outcomes without explicit rules
```

---

#### Q15: Dense vs Sparse Feedback Advantage

**Question**: Does per-token feedback (Gyroscope) actually outperform end-of-sequence feedback (RLHF)?

**Hypothesis**: Yes, because credit assignment is immediate, not delayed.

**Validation Benchmark**:
- [ ] Gyroscope model learns loop prevention faster than RLHF model
- [ ] Gyroscope model requires fewer training steps for equivalent quality
- [ ] Gyroscope model is more stable (lower loss variance)

**How to Test**:
```python
# Train equivalent models: (a) Gyroscope (dense), (b) RLHF (sparse)
# Compare: training steps to quality threshold, loss stability, final quality
```

---

### D.7 Summary: Validation Checklist

| # | Question | Status | Evidence |
|---|----------|--------|----------|
| Q1 | Projector learns meaningful representations | ⬜ Pending | |
| Q2 | Gradients flow to main model | ⬜ Pending | |
| Q3 | Vital Kosha role identified | ⬜ Pending | |
| Q4 | Noisy early projections help | ⬜ Pending | |
| Q5 | Gates behave well with noise | ⬜ Pending | |
| Q6 | Thresholds are calibrated | ⬜ Pending | |
| Q7 | Classification targets defined | ⬜ Pending | |
| Q8 | Classification timing optimal | ⬜ Pending | |
| Q9 | No Phase Steering conflict | ⬜ Pending | |
| Q10 | Controller interactions healthy | ⬜ Pending | |
| Q11 | Chain of Thought emerges | ⬜ Pending | |
| Q12 | Loops prevented | ⬜ Pending | |
| Q13 | Fibonacci preserved | ⬜ Pending | |
| Q14 | Constitutional AI equivalent | ⬜ Pending | |
| Q15 | Dense > Sparse feedback | ⬜ Pending | |
| Q16 | Primary vs Emergent timing validated | ⬜ Pending | |

**Success Criteria**: ≥13/16 questions answered positively indicates the system works as designed.

---

**Document Status:** Ready for Implementation (v2.2 Refinements Documented)
**Next Steps:**
1. Implement `KoshaGyroscopicLoss` module (v2.2.0) in `symbolu/losses/kosha_gyroscope.py`
2. Implement `GraduationMonitor` in `symbolu/monitors/graduation_monitor.py`
3. Implement `SovereignDiagnosticLogger` in `symbolu/diagnostics/rip_logger.py`
4. Integrate into training loop with Gyroscope ON from step 0 (PRIMARY dimensions)
5. Monitor PPL for graduation threshold (Mean < 30, σ < 1.5)
6. Run Stress Test Suite (ST-01 through ST-06) at graduation
7. **Validate against Appendix D + E benchmarks (Q1-Q20)**

**Key Changes:**
- **v1.0 → v2.0:** Gyroscope now active from BEGINNING of training (instructor-led)
- **v2.0 → v2.1:** 32D Dimensional Hierarchy established:
  - **PRIMARY** (Bhava + Kosha): Engage from step 0 (foundational substrate)
  - **EMERGENT** (Vritti + Guna): Arise from PRIMARY dynamics after grounding
  - Vritti = STATES of information, Guna = QUALITY of information
- **v2.1 → v2.2:** Proposed refinements documented (Appendix E):
  - Vital Momentum: Pranamaya as gradient momentum scaler
  - Temporal Grounding: Physical history over last 2-3 tokens
  - Graduation Stability Variance: Tighter PPL threshold criteria
  - Contrastive Divergence: Self-supervised classification targets
  - Stress Test Suite and Diagnostic Logger

---

## Appendix E: Proposed Refinements (v2.2.0)

This appendix documents proposed refinements to the Kosha Gyroscope based on design review. These are **not yet implemented** but represent the next evolution of the system.

### E.1 Vital Momentum: The Missing Kosha

#### E.1.1 The Problem

The Vital (Pranamaya) Kosha at index [1] is not mapped to any R-T quadrant. It currently sits unused in the Gyroscope logic.

#### E.1.2 The Solution: Gradient Momentum Scaler

In Vedic theory, **Prana** is the energy that moves mind and matter. The Vital Kosha should act as a **dynamic gain multiplier** for the Gyroscope:

| Vital State | Meaning | Gyroscope Behavior |
|-------------|---------|-------------------|
| **Low Vital** | Inertia, stagnation | Increase gain (pull harder to overcome) |
| **High Vital** | Flow, momentum | Decrease gain (model already moving) |

#### E.1.3 Proposed Implementation

```python
# Extract Vital (Energy/Momentum)
vital = kosha_states[:, :, 1]  # Pranamaya

# Low energy = Higher gain needed to shift state
# High energy = Model is already in flow, subtle correction suffices
momentum_scaler = 1.5 - vital.mean()  # Range: [0.5, 1.5]

# Apply to final loss
total_loss = (axis1_loss + axis2_loss) * self.gain * momentum_scaler
```

#### E.1.4 Validation Benchmark

**Q17: Vital Momentum Effectiveness**

- [ ] Low Vital correlates with stuck states (high token repetition)
- [ ] High Vital correlates with generative flow (novel token sequences)
- [ ] Dynamic gain adjustment reduces time-to-escape from loops
- [ ] Vital shows rhythmic pulses aligned with sentence boundaries

---

### E.2 Temporal Grounding: The "Breath Before the Rip"

#### E.2.1 The Problem

The current Vijnana Gate checks if Physical (Annamaya) is active **now**. But a single-token check is too volatile—the model needs to have been grounded for a short period before it can safely transition.

#### E.2.2 The Solution: Physical History Window

Instead of checking `physical[t]`, check the **mean of the last 2-3 tokens**:

```
Transition Allowed IF:
  Physical[t] > threshold       ← Current check (volatile)
  Physical[t-2:t].mean() > threshold  ← Proposed (stable)
```

#### E.2.3 Proposed Implementation

```python
# Temporal Physical Grounding (Mean of last 3 tokens)
# Uses 1D average pooling for efficiency
if physical.shape[1] >= 3:
    phys_history = F.avg_pool1d(
        physical.unsqueeze(1),
        kernel_size=3,
        stride=1,
        padding=1
    ).squeeze(1)
else:
    phys_history = physical

# Use phys_history instead of physical for gate check
phys_gate = torch.sigmoid(
    self.gate_temperature * (phys_history - self.gate_threshold)
)
```

#### E.2.4 Rationale

This ensures the model "takes a breath" of factual grounding before jumping from a loop into a new logical structure. The transition path becomes:

```
Mental (looping)
  → Physical (2-3 tokens of grounding)
    → Intellect (verified structure)
      → Bliss (expansion)
```

#### E.2.5 Validation Benchmark

**Q18: Temporal Grounding Stability**

- [ ] Successful transitions show Physical activation in [t-2, t-1, t]
- [ ] Failed transitions (premature jumps) lack Physical history
- [ ] 3-token window reduces false-positive loop breaks
- [ ] Fibonacci sequences remain intact (Physical + Intellect sustained)

---

### E.3 Graduation Stability Variance

#### E.3.1 The Problem

The current graduation threshold is simply `PPL < 30`. But PPL can temporarily dip below 30 due to an "easy" batch of data, triggering premature graduation.

#### E.3.2 The Solution: Dual Criteria

Graduation should require BOTH conditions:

1. **Mean PPL < 30** over a stability window
2. **PPL Standard Deviation < 1.5** (stability, not luck)

#### E.3.3 Proposed Implementation

```python
class GraduationMonitor:
    def __init__(
        self,
        target_ppl: float = 30.0,
        stability_window: int = 10,  # Last N validation checks
        variance_threshold: float = 1.5
    ):
        self.target_ppl = target_ppl
        self.window_size = stability_window
        self.var_threshold = variance_threshold
        self.ppl_history = []
        self.graduated = False

    def check(self, val_ppl: float) -> bool:
        """Returns True if graduation criteria met."""
        self.ppl_history.append(val_ppl)

        if len(self.ppl_history) > self.window_size:
            self.ppl_history.pop(0)

        if len(self.ppl_history) < self.window_size:
            return False  # Not enough data

        avg_ppl = np.mean(self.ppl_history)
        std_ppl = np.std(self.ppl_history)

        is_low_enough = avg_ppl <= self.target_ppl
        is_stable_enough = std_ppl <= self.var_threshold

        if is_low_enough and is_stable_enough and not self.graduated:
            self.graduated = True
            return True

        return False
```

#### E.3.4 Graduation Ceremony Update

```python
# In training loop
if graduation_monitor.check(last_val_ppl) and not graduated:
    print(f"🎓 [GRADUATION] PPL Stable at {avg_ppl:.2f} (σ={std_ppl:.2f})")
    print(f"   • Gyroscope: RAMPING DOWN (instructor stepping back)")
    print(f"   • Classification: ENGAGING (student self-assessment)")
    graduated = True
```

#### E.3.5 Validation Benchmark

**Q19: Graduation Stability**

- [ ] False graduations eliminated (no PPL spike after graduation)
- [ ] Stability window (10 evals) is sufficient for confidence
- [ ] σ < 1.5 correlates with stable Kosha projections
- [ ] Post-graduation Kosha variance remains low

---

### E.4 Contrastive Divergence for Classification Targets

#### E.4.1 The Problem

Q7 in Appendix D asks: "Where do `kosha_targets` come from?"

#### E.4.2 The Solution: Layer Divergence

Use **Contrastive Divergence** between Layer 9 (The Witness) and Layer 12 (The Output):

| Condition | Layer 9 (Witness) | Layer 12 (Output) | Diagnosis |
|-----------|-------------------|-------------------|-----------|
| **Valid Loop** | Coherent | Coherent | Dharana (focus) |
| **Invalid Loop** | High entropy | Repetitive | Insanity (punish) |
| **Hallucination** | Low confidence | High confidence | Delusion (punish) |

#### E.4.3 Proposed Implementation

```python
def compute_loop_labels(layer_9_hidden, layer_12_hidden, tokens):
    """
    Self-supervised Kosha labeling via layer divergence.
    """
    # Compute entropy at Layer 9 (Witness)
    witness_logits = witness_head(layer_9_hidden)
    witness_entropy = -(F.softmax(witness_logits, dim=-1) *
                        F.log_softmax(witness_logits, dim=-1)).sum(dim=-1)

    # Detect token repetition at output
    is_repeating = detect_token_repetition(tokens, window=3)

    # Classification logic:
    # High Witness Entropy + Repetition = Invalid Loop (Mental trap)
    # Low Witness Entropy + Repetition = Valid Focus (Dharana)

    invalid_loop_mask = (witness_entropy > 2.0) & is_repeating

    # Generate Kosha targets
    kosha_targets = torch.zeros_like(kosha_states)
    kosha_targets[invalid_loop_mask, 2] = 1.0  # High Mental (trap)
    kosha_targets[invalid_loop_mask, 3] = 0.0  # Low Intellect (missing)
    kosha_targets[~invalid_loop_mask, 3] = 0.5  # Normal Intellect

    return kosha_targets
```

#### E.4.4 Validation Benchmark

**Q20: Contrastive Divergence Accuracy**

- [ ] Layer 9 entropy correlates with loop invalidity
- [ ] Self-supervised labels match human judgment (>85%)
- [ ] Classification loss converges with self-generated labels
- [ ] No external annotation required

---

### E.5 Stress Test Suite

To verify the Kosha Gyroscope's transitions, use these engineered prompts:

#### E.5.1 Test Prompts

| Test ID | Category | Prompt | Expected Kosha State |
|---------|----------|--------|---------------------|
| **ST-01** | Logic Gate | "The sequence is 1, 1, 2, 3, 5, 8, 13, 21," | Mental HIGH + Intellect HIGH → No punishment (Dharana) |
| **ST-02** | Recursive Trap | "The recursive definition of a recursive definition is that it is a" | Mental HIGH + Intellect LOW → Gyroscope fires, force Bliss |
| **ST-03** | Manifest Ground | "The precise chemical composition of seawater includes" | Physical HIGH → Vijnana Gate verifies before expansion |
| **ST-04** | Creative Expand | "Imagine a color that does not exist in our spectrum, it feels like" | Bliss HIGH → Vital Momentum sustains novel generation |
| **ST-05** | Quote Recall | "To be or not to be, that is the" | Mental HIGH + Intellect HIGH → Allow (valid recall) |
| **ST-06** | Pathological | "Buffalo buffalo Buffalo buffalo buffalo buffalo Buffalo buffalo" | Mental EXTREME → Force break despite grammatical validity |

#### E.5.2 Expected Transitions

```
ST-02: Recursive Trap
───────────────────────
Step 1: "...is that it is a"
        Mental: 0.85 ↑↑  (repetition detected)
        Intellect: 0.12 ↓ (no logical structure)

Step 2: Vijnana Gate Check
        Physical History: [0.35, 0.42, 0.38] → Mean: 0.38
        Gate: 0.38 > 0.30 → OPEN (grounded)

Step 3: Gyroscope Loss Fires
        axis1_loss = mental_trap × phys_gate × missing_intellect
                   = 0.10 × 0.85 × 0.38 ≈ 0.032

Step 4: Gradient Correction
        Model shifts from Mental → Bliss quadrant
        Next token: Novel expansion (not repetition)
```

---

### E.6 Diagnostic Logger

#### E.6.1 The Reality Rip Logger

Captures the exact moment of forced transitions:

```python
class SovereignDiagnosticLogger:
    """Logs high-intensity quadrant shifts (Reality Rips)."""

    def __init__(self, log_dir: str = "diagnostics/rips"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.rip_count = 0

    def capture_rip(
        self,
        step: int,
        tokens: List[int],
        kosha_states: torch.Tensor,
        loss_value: float
    ) -> bool:
        """
        Captures state during forced transition.
        Returns True if a rip was detected.
        """
        mental_vals = kosha_states[:, :, 2]
        intellect_vals = kosha_states[:, :, 3]

        # Detect 'Insanity' state: High Mental + Low Intellect
        trapped_mask = (mental_vals > 0.8) & (intellect_vals < 0.2)

        if trapped_mask.any():
            self.rip_count += 1
            rip_event = {
                "step": step,
                "rip_id": self.rip_count,
                "loss": float(loss_value),
                "mental_max": float(mental_vals.max()),
                "intellect_min": float(intellect_vals.min()),
                "sample_tokens": tokens[:20]
            }

            file_path = os.path.join(
                self.log_dir,
                f"rip_step_{step}_{self.rip_count}.json"
            )
            with open(file_path, "w") as f:
                json.dump(rip_event, f, indent=4)

            return True
        return False
```

#### E.6.2 Rip Analysis Protocol

When analyzing rip snapshots:

1. **Pre-Rip**: Look for 3-5 identical tokens, Mental climbing toward 1.0
2. **Vijnana Gate**: Verify Intellect remains flat (not Dharana)
3. **The Rip**: Vital spikes as energy expended for transition
4. **Post-Rip**: Next token is semantically related but structurally novel

#### E.6.3 Health Metrics Over Training

| Metric | Instructor Phase (PPL > 30) | Self-Learning Phase (PPL < 30) |
|--------|----------------------------|-------------------------------|
| Rip Frequency | High (external regulation) | Low (internalized balance) |
| Vital Surges | Chaotic spikes | Rhythmic pulses |
| Vritti Stability | Frequent ERROR | Consistent FACT/IMAGINATION |

---

### E.7 Refined KoshaGyroscopicLoss (v2.2.0)

Incorporating all refinements:

```python
class KoshaGyroscopicLoss(nn.Module):
    """
    Vijnana-Gated Kosha Balance Loss (v2.2.0).

    Refinements:
    - Vital Momentum: Dynamic gain based on Pranamaya energy
    - Temporal Grounding: Physical history over 3-token window
    - Soft gates with temperature for differentiability
    """

    def __init__(
        self,
        trap_threshold: float = 0.75,
        gate_threshold: float = 0.30,
        balance_target: float = 0.25,
        gate_temperature: float = 10.0,
        gain: float = 2.0,
        temporal_window: int = 3,
    ):
        super().__init__()
        self.trap_threshold = trap_threshold
        self.gate_threshold = gate_threshold
        self.balance_target = balance_target
        self.gate_temperature = gate_temperature
        self.gain = gain
        self.temporal_window = temporal_window

    def forward(self, kosha_states: torch.Tensor) -> torch.Tensor:
        """
        Args:
            kosha_states: [batch, seq, 5] normalized to [0, 1]
                         [Physical, Vital, Mental, Intellect, Blissful]

        Returns:
            Scalar loss value
        """
        physical  = kosha_states[:, :, 0]  # Annamaya (+,+)
        vital     = kosha_states[:, :, 1]  # Pranamaya (energy)
        mental    = kosha_states[:, :, 2]  # Manomaya (-,+)
        intellect = kosha_states[:, :, 3]  # Vijnanamaya (+,-)
        bliss     = kosha_states[:, :, 4]  # Anandamaya (-,-)

        # === REFINEMENT 1: Temporal Grounding ===
        # Check physical history, not just current token
        if physical.shape[1] >= self.temporal_window:
            phys_history = F.avg_pool1d(
                physical.unsqueeze(1),
                kernel_size=self.temporal_window,
                stride=1,
                padding=self.temporal_window // 2
            ).squeeze(1)
        else:
            phys_history = physical

        # === REFINEMENT 2: Vital Momentum ===
        # Low energy = higher gain needed; High energy = subtle correction
        momentum_scaler = 1.5 - vital.mean()  # Range: [0.5, 1.5]

        # --- AXIS 1: Mental → Intellect (via Physical) ---
        mental_trap = F.relu(mental - self.trap_threshold)
        phys_gate = torch.sigmoid(
            self.gate_temperature * (phys_history - self.gate_threshold)
        )
        missing_intellect = F.relu(self.balance_target - intellect)
        axis1_loss = (mental_trap * phys_gate * missing_intellect).mean()

        # --- AXIS 2: Physical → Blissful (via Mental) ---
        physical_trap = F.relu(physical - self.trap_threshold)
        mental_gate = torch.sigmoid(
            self.gate_temperature * (mental - self.gate_threshold)
        )
        missing_bliss = F.relu(self.balance_target - bliss)
        axis2_loss = (physical_trap * mental_gate * missing_bliss).mean()

        # === Total Loss with Dynamic Gain ===
        total_loss = (axis1_loss + axis2_loss) * self.gain * momentum_scaler

        return total_loss
```

---

### E.8 Updated Validation Checklist

| # | Question | Status | Evidence |
|---|----------|--------|----------|
| Q17 | Vital Momentum effective | ⬜ Pending | |
| Q18 | Temporal Grounding stable | ⬜ Pending | |
| Q19 | Graduation Stability validated | ⬜ Pending | |
| Q20 | Contrastive Divergence accurate | ⬜ Pending | |
| Q21 | Dynamic Weight Scheduler prevents Aphasia | ⬜ Pending | |
| Q22 | PPL-based gain ramping is smoother than static | ⬜ Pending | |

**Updated Success Criteria**: ≥18/22 questions answered positively indicates the system works as designed.

---

### E.9 Dynamic Weight Scheduler (v2.2.1)

**Source**: Gemini design review discussion

#### E.9.1 The Problem: Over-Steering Risk ("Aphasia")

The v2.2.0 implementation uses a **static gain of 2.0**. This creates a critical risk:

> **The Aphasia Problem**: If gain is too high while the model is still learning basic grammar (PPL > 100), the model becomes "terrified" of repeating ANY token, including necessary ones like "the", "and", "is".

| Static Gain | PPL Range | Risk |
|-------------|-----------|------|
| 2.0 | > 100 | **HIGH**: Model avoids valid repetition |
| 2.0 | 30-100 | **MEDIUM**: May break valid patterns |
| 2.0 | < 30 | **LOW**: But gyroscope should be disengaging anyway |

#### E.9.2 The Solution: PPL-Based Gain Ramping

Instead of static gain, use **dynamic gain** that increases as PPL decreases:

```
gain(PPL) = base_gain + progress × (max_gain - base_gain)

where:
  progress = (100 - PPL) / (100 - target_ppl)
  progress = clamp(progress, 0.0, 1.0)
```

| PPL | Progress | Dynamic Gain (0.15 → 3.0) |
|-----|----------|---------------------------|
| 150 | 0.0 | 0.15 (gentle observation) |
| 100 | 0.0 | 0.15 |
| 65 | 0.5 | 1.575 (moderate discipline) |
| 30 | 1.0 | 3.0 (strict enforcement) |
| 20 | 1.0 | 3.0 (capped, but disengaging) |

#### E.9.3 Three Training Phases

The Dynamic Weight Scheduler creates three distinct training behaviors:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DYNAMIC WEIGHT SCHEDULER PHASES                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  PPL 1000      PPL 100         PPL 65          PPL 30          PPL 15   │
│     │             │               │               │               │     │
│     ▼             ▼               ▼               ▼               ▼     │
│  ═══════════════════════════════════════════════════════════════════    │
│  │  PHASE A     │      PHASE B: INCREASING      │   PHASE C:      │    │
│  │  OBSERVATION │          DISCIPLINE           │  INTERNALIZED   │    │
│  ═══════════════════════════════════════════════════════════════════    │
│                                                                          │
│  Gain: 0.15 ──────────────────────────────────────► 3.0 ───► rampdown  │
│                                                                          │
│  Behavior:                                                               │
│  • Phase A: Learn grammar without gyroscope interference               │
│  • Phase B: Vijnana Gate forces reasoning path; CoT emerges            │
│  • Phase C: Gyroscope disengages; balance is internalized              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### E.9.4 Proposed Implementation

```python
class KoshaGyroscopicLoss(nn.Module):
    def __init__(
        self,
        base_gain: float = 0.15,      # Starting weight (gentle)
        max_gain: float = 3.0,        # Maximum weight (strict)
        ppl_ceiling: float = 100.0,   # PPL above which gain stays at base
        target_ppl: float = 30.0,     # PPL at which gain reaches max
        # ... other params ...
    ):
        super().__init__()
        self.base_gain = base_gain
        self.max_gain = max_gain
        self.ppl_ceiling = ppl_ceiling
        self.target_ppl = target_ppl
        # ...

    def get_dynamic_gain(self, current_ppl: float) -> float:
        """
        Ramps gain from base_gain to max_gain as PPL drops.

        Args:
            current_ppl: Current validation perplexity

        Returns:
            Dynamic gain value
        """
        if current_ppl >= self.ppl_ceiling:
            return self.base_gain

        # Linear interpolation
        progress = (self.ppl_ceiling - current_ppl) / (self.ppl_ceiling - self.target_ppl)
        progress = max(0.0, min(1.0, progress))

        return self.base_gain + (progress * (self.max_gain - self.base_gain))

    def forward(
        self,
        kosha_states: torch.Tensor,
        current_ppl: Optional[float] = None,
        return_components: bool = False
    ) -> torch.Tensor:
        """
        Args:
            kosha_states: [B, N, 5] Kosha activations
            current_ppl: Current validation PPL for dynamic gain
            return_components: Whether to return diagnostic info
        """
        # ... existing extraction and computation ...

        # Dynamic gain based on training progress
        if current_ppl is not None:
            effective_gain = self.get_dynamic_gain(current_ppl)
        else:
            effective_gain = self.base_gain  # Fallback to base

        # Vital Momentum still applies on top
        total_loss = (axis1_loss + axis2_loss) * effective_gain * momentum_scaler

        return total_loss
```

#### E.9.5 API Change

The `forward()` method now accepts an optional `current_ppl` parameter:

```python
# v2.2.0 (static gain)
loss = gyro_loss(kosha_states)

# v2.2.1 (dynamic gain)
loss = gyro_loss(kosha_states, current_ppl=last_val_ppl)
```

**Backward Compatibility**: If `current_ppl` is not provided, falls back to `base_gain`.

#### E.9.6 Weight Impact Analysis

| Weight | Mode | Impact on Coherence |
|--------|------|---------------------|
| **0.15** | Observation | Model loops occasionally; logic is loose |
| **0.30** | Light Regulation | Loops broken slowly; reasoning patterns begin |
| **1.5** | Moderate Discipline | Clear CoT structure emerges |
| **3.0** | Strict Enforcement | Pathological loops impossible; model "locked" into R-T phase space |

#### E.9.7 Integration with Existing Refinements

The Dynamic Weight Scheduler combines with other v2.2.0 refinements:

```python
# Effective loss computation (v2.2.1)
effective_gain = get_dynamic_gain(current_ppl)      # E.9: PPL-based
momentum_scaler = 1.5 - vital.mean()                 # E.1: Vital Momentum
phys_history = temporal_avg(physical, window=3)      # E.2: Temporal Grounding

total_loss = (axis1_loss + axis2_loss) * effective_gain * momentum_scaler
```

#### E.9.8 Validation Benchmarks

**Q21: Dynamic Weight Scheduler Prevents Aphasia**

- [ ] At PPL > 100, model can repeat "the", "and", "is" freely
- [ ] At PPL ~50, looping is discouraged but valid patterns preserved
- [ ] No training collapse due to excessive gain early
- [ ] Fibonacci/quote tests (ST-01, ST-05) pass throughout training

**Q22: PPL-Based Gain Ramping Is Smoother Than Static**

- [ ] Loss curves are smoother with dynamic gain vs static gain=2.0
- [ ] Fewer "Reality Rips" in early training (gain is gentler)
- [ ] Rip frequency increases naturally as gain increases
- [ ] Final model quality is equivalent or better

---

### E.10 Updated Version Summary

| Version | Key Changes |
|---------|-------------|
| **v1.0** | Initial design with naive gyroscope |
| **v2.0** | Inverted Curriculum (Gyroscope from step 0) |
| **v2.1** | 32D Dimensional Hierarchy (PRIMARY vs EMERGENT) |
| **v2.2.0** | Vital Momentum, Temporal Grounding, Graduation Stability |
| **v2.2.1** | **Dynamic Weight Scheduler** (PPL-based gain ramping) |

---

### E.11 Recommended Training Configuration (v2.2.1)

```python
@dataclass
class KoshaGyroscopeConfigV221:
    """Full configuration for Kosha Gyroscope v2.2.1."""

    # === DYNAMIC WEIGHT SCHEDULER (NEW) ===
    base_gain: float = 0.15           # Gentle observation (PPL > 100)
    max_gain: float = 3.0             # Strict enforcement (PPL → 30)
    ppl_ceiling: float = 100.0        # PPL above which gain stays at base
    target_ppl: float = 30.0          # PPL at which gain reaches max

    # === INVERTED CURRICULUM ===
    enable_gyroscope: bool = True
    gyroscope_disengage_ppl: float = 30.0
    gyroscope_warmup_steps: int = 100
    gain_rampdown_steps: int = 500

    # === VIJNANA GATE ===
    trap_threshold: float = 0.75
    gate_threshold: float = 0.30
    balance_target: float = 0.25
    gate_temperature: float = 10.0

    # === REFINEMENTS ===
    temporal_window: int = 3          # Physical history window
    vital_momentum_enabled: bool = True
    vital_momentum_range: tuple = (0.5, 1.5)

    # === GRADUATION ===
    graduation_stability_window: int = 10
    graduation_variance_threshold: float = 1.5
```

---

## 16. Gradient Norm Throttle: Physical Safety Layer (v2.2.5)

### 16.1 The Problem: Gradient Explosions During Training

While the Kosha Gyroscope regulates cognitive state balance, it operates on the **semantic level** (Kosha distributions). However, training instabilities can occur at the **physical level** - gradient explosions that cause destructive weight updates before the Gyroscope can respond.

**Observed Symptoms:**
- PPL spikes (e.g., 118 → 143 in single step)
- VRAM critical events (99.3% usage)
- Token repetition loops ("Caesar Caesar Caesar")
- Batch size oscillations (32 → 36 → 28)

These are **physical training failures**, not cognitive state imbalances.

### 16.2 The Solution: Two-Layer Safety Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TRAINING SAFETY STACK                     │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: KOSHA GYROSCOPE (Semantic)                        │
│    - Regulates Kosha balance (Mental/Physical/Bliss/etc)    │
│    - Operates on hidden state geometry                      │
│    - Dense per-token feedback                               │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: GRADIENT THROTTLE (Physical) ← NEW                │
│    - Monitors raw gradient L2 norm                          │
│    - Reduces LR when gradients spike > 2x baseline          │
│    - Prevents destructive weight updates                    │
│    - Acts BEFORE optimizer.step()                           │
└─────────────────────────────────────────────────────────────┘
```

The Gradient Throttle ensures the mathematical foundation (gradients) remains stable, allowing the Kosha Gyroscope to operate on a solid platform.

### 16.3 GradientNormThrottle Implementation

**Location:** `symbolu/training/trainers/gradient_throttle.py`

```python
class GradientNormThrottle:
    """
    Stabilizes training by reducing LR when gradient norms spike.
    Acts as the physical safety layer for the Sovereign Architecture.
    """
    def __init__(
        self,
        ema_decay: float = 0.99,       # Slow adaptation to baseline
        spike_threshold: float = 2.0,   # Trigger if norm > 2x average
        min_factor: float = 0.3,        # Never reduce LR below 30%
        warmup_steps: int = 100,        # Skip throttling during warmup
    ):
        self.ema_grad_norm = None
        self.ema_decay = ema_decay
        self.spike_threshold = spike_threshold
        self.min_factor = min_factor
        self.warmup_steps = warmup_steps

    def step(self, model, optimizer, base_lr, precomputed_norm=None):
        """
        Check gradient norm and apply throttling if needed.

        Returns:
            (throttle_factor, current_grad_norm)
        """
        # Compute or reuse gradient norm
        total_norm = precomputed_norm or self.compute_grad_norm(model)

        # Initialize EMA on first step
        if self.ema_grad_norm is None:
            self.ema_grad_norm = total_norm
            return 1.0, total_norm

        # Detect spike
        ratio = total_norm / (self.ema_grad_norm + 1e-8)

        factor = 1.0
        if ratio > self.spike_threshold:
            # Throttle proportionally: 5x spike → 0.2x LR
            factor = max(self.ema_grad_norm / total_norm, self.min_factor)

        # Apply to optimizer
        for param_group in optimizer.param_groups:
            param_group['lr'] = base_lr * factor

        # Update EMA
        self.ema_grad_norm = (
            self.ema_decay * self.ema_grad_norm +
            (1 - self.ema_decay) * total_norm
        )

        return factor, total_norm
```

### 16.4 Integration with Training Loop

The throttle is injected after `loss.backward()` and before `optimizer.step()`:

```python
# In train_unified_llm.py

# 1. Initialize (after other controllers)
gradient_throttle = GradientNormThrottle(
    ema_decay=0.99,
    spike_threshold=2.0,
    min_factor=0.3,
    warmup_steps=config.warmup_steps,
)

# 2. In training loop, after loss.backward():
raw_grad_norm = sum(p.grad.norm().item() for p in model.parameters() if p.grad is not None)

# Apply throttle BEFORE gradient clipping
throttle_factor, _ = gradient_throttle.step(
    model, optimizer, config.learning_rate,
    precomputed_norm=raw_grad_norm,
)
if throttle_factor < 1.0:
    print(f"  ⚡ [GRAD THROTTLE] norm={raw_grad_norm:.1f} | LR×{throttle_factor:.2f}")

# Then gradient clipping
torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)

# Then optimizer.step()
optimizer.step()
```

### 16.5 Interaction with Kosha Gyroscope

| Scenario | Gradient Throttle | Kosha Gyroscope | Combined Effect |
|----------|-------------------|-----------------|-----------------|
| Normal training | LR×1.0 | Balance penalty | Standard learning |
| Mental trap | LR×1.0 | Bliss injection | Cognitive rebalance |
| Gradient spike | LR×0.3 | (reduced effect) | Physical stabilization first |
| Spike + trap | LR×0.3 | Bliss injection (reduced) | Stabilize, then rebalance |

**Key Principle:** Physical stability enables cognitive regulation. When gradients spike, the Gyroscope's gradients are also affected - throttling first ensures the Gyroscope can operate effectively.

### 16.6 TensorBoard Metrics

```python
# Logged every eval step:
tb_writer.add_scalar("throttle/factor", throttle_stats['last_factor'], global_step)
tb_writer.add_scalar("throttle/grad_norm", throttle_stats['last_grad_norm'], global_step)
tb_writer.add_scalar("throttle/ema_norm", throttle_stats['ema_grad_norm'], global_step)
tb_writer.add_scalar("throttle/events_total", throttle_stats['throttle_events'], global_step)
```

### 16.7 WikiText Artifact Cleaner

Also added in v2.2.5, the WikiText cleaner removes Moses tokenization artifacts from quality sample logs:

**Location:** `symbolu/training/text_utils.py`

```python
def clean_wikitext_artifacts(text: str) -> str:
    """
    Clean Moses tokenization artifacts from WikiText-103.
    - @-@ → - (hyphens)
    - @.@ → . (periods)
    - @,@ → , (commas)
    """
    text = re.sub(r'\s*@-@\s*', '-', text)
    text = re.sub(r'\s*@\.@\s*', '.', text)
    text = re.sub(r'\s*@,@\s*', ',', text)
    return text
```

**Before:** `"1 @,@ 000 metres from the @-@ 100 year old"`
**After:** `"1,000 metres from the-100 year old"`

### 16.8 Configuration (v2.2.5)

```python
@dataclass
class GradientThrottleConfig:
    """Configuration for Gradient Norm Throttle."""

    # === THROTTLE PARAMETERS ===
    ema_decay: float = 0.99           # Slow adaptation (99% history retention)
    spike_threshold: float = 2.0       # Trigger at 2x normal gradient
    min_factor: float = 0.3            # Floor LR at 30%
    warmup_steps: int = 100            # Skip during warmup

    # === INTEGRATION ===
    enabled: bool = True               # Auto-enabled when available
```

### 16.9 Version History

| Version | Date | Changes |
|---------|------|---------|
| **2.3.0** | **2026-01-11** | **Complete Harmonic Pentad (Floor/Ceiling for all 5 Koshas)** |
| 2.2.6 | 2026-01-11 | Bliss Ceiling Clamp (φ = 61.8%) |
| 2.2.5 | 2026-01-11 | Added GradientNormThrottle + WikiText cleaner |
| 2.2.4 | 2026-01-10 | Three-Stage Hybrid Logic |
| 2.2.3 | 2026-01-09 | Soft-Threshold Damping |
| 2.2.1 | 2026-01-08 | Dynamic Weight Scheduler |
| 2.2.0 | 2026-01-07 | Refinements (Vital Momentum, Temporal Grounding) |
| 2.0.0 | 2026-01-05 | Inverted Curriculum + Vijnana Gate |

---

## 17. Complete Harmonic Pentad (v2.3.0)

### 17.1 Motivation: The "Blissful Ignorance" Problem

In v2.2.5, we observed Bliss consistently exceeding its 23.6% threshold (often at 40-60%), indicating the model was generating fluent but meaningless text—"blissful ignorance." The model learned to produce smooth, confident outputs without genuine understanding.

v2.2.6 introduced a Bliss Ceiling Clamp at φ (61.8%), but this addressed only one Kosha. The Complete Harmonic Pentad extends this principle to ALL 5 Koshas with bidirectional regulation:

- **Floor (Push):** When a Kosha falls BELOW its healthy range, add loss pressure to push it UP
- **Ceiling (Clamp):** When a Kosha rises ABOVE its healthy range, reduce gain to clamp it DOWN

### 17.2 The Sattvic Band Concept

Each Kosha has a **Sattvic Band**—an optimal operating range where healthy learning occurs. Based on Fibonacci ratios:

| Kosha | Floor | Ceiling | Sattvic Band | Priority |
|-------|-------|---------|--------------|----------|
| **Mental (M)** | 23.6% | 38.2% | Pattern recognition sweet spot | ×1.0 |
| **Physical (P)** | 38.2% | 61.8% | Grounding foundation | ×3.0 (Foundation) |
| **Intellect (I)** | 25.0% | 61.8% | Discriminative reasoning | ×1.5 (Hubris Tax) |
| **Vital (V)** | 23.6% | 78.6% | Momentum/energy flow | Momentum Control |
| **Bliss (B)** | 23.6% | 61.8% | Unified awareness | ×1.0 |

### 17.3 Floor Actions (Push Mechanisms)

When a Kosha falls BELOW its floor, we apply corrective pressure:

#### Mental Floor (23.6%): Pattern Deficit Push
```python
mental_below_floor = F.relu(self.floor_mental - mental)
mental_floor_loss = mental_below_floor.mean()  # Loss pressure to push UP
```
**Interpretation:** Low Mental indicates insufficient pattern recognition. Push to develop basic representational capacity.

#### Physical Floor (38.2%): Grounding Foundation Push — THE FOUNDATION
```python
physical_below_floor = F.relu(self.floor_physical - physical)
physical_floor_loss = physical_below_floor.mean() * 3.0  # HIGH priority (×3.0)
```
**Interpretation:** Physical is the foundation of the Kosha hierarchy. Without grounding, other Koshas cannot function properly. This gets the HIGHEST priority weight.

#### Intellect Floor (25.0%): Reasoning Deficit Push — Hubris Tax
```python
intellect_below_floor = F.relu(self.floor_intellect - intellect)
intellect_floor_loss = intellect_below_floor.mean() * 1.5  # Moderate priority (×1.5)
```
**Interpretation:** Low Intellect indicates superficial processing without discrimination. The "Hubris Tax" prevents the model from being overconfident without genuine understanding.

#### Vital Floor (23.6%): Wake-up Momentum Boost
```python
vital_below_floor = F.relu(self.floor_vital - vital)
vital_momentum_boost = torch.where(
    vital_below_floor.mean() > 0,
    torch.tensor(1.5),   # Boost momentum by 50%
    torch.tensor(1.0)    # Normal momentum
)
```
**Interpretation:** Low Vital indicates sluggish learning. Instead of loss pressure, we boost momentum to energize the optimization process.

#### Bliss Floor (23.6%): Integration Deficit Push
```python
bliss_below_floor = F.relu(self.floor_bliss - bliss)
bliss_floor_loss = bliss_below_floor.mean()  # Loss pressure to push UP
```
**Interpretation:** Low Bliss indicates fragmented processing without integration. Push to develop unified awareness.

### 17.4 Ceiling Actions (Clamp Mechanisms)

When a Kosha rises ABOVE its ceiling, we apply multiplicative damping:

#### Mental Ceiling (38.2%): Pattern Trap Clamp
Mental above 38.2% indicates over-reliance on memorized patterns. Clamp to encourage generalization.

#### Physical Ceiling (61.8%): Over-Grounding Clamp
Physical above 61.8% indicates excessive focus on literal/concrete representations. Clamp to allow abstract reasoning.

#### Intellect Ceiling (61.8%): Over-Thinking Clamp
Intellect above 61.8% indicates analysis paralysis or overthinking. Clamp to maintain practical coherence.

#### Vital Ceiling (78.6%): Momentum Brake
```python
vital_above_ceiling = F.relu(vital - self.ceiling_vital)
vital_momentum_brake = torch.where(
    vital_above_ceiling.mean() > 0,
    torch.tensor(0.5),   # Reduce momentum by 50%
    torch.tensor(1.0)    # Normal momentum
)
```
**Interpretation:** High Vital indicates chaotic, unstable optimization. Apply momentum brake to stabilize.

#### Bliss Ceiling (61.8%): Blissful Ignorance Clamp
Bliss above φ (61.8%) indicates "blissful ignorance"—fluent gibberish without substance. Clamp to ground outputs in meaning.

### 17.5 Ceiling Clamp Scalar

All ceiling violations contribute to a single multiplicative clamp:

```python
# Count total ceiling violations
ceiling_violations = sum([
    (mental > ceiling_mental).float(),
    (physical > ceiling_physical).float(),
    (intellect > ceiling_intellect).float(),
    (vital > ceiling_vital).float(),
    (bliss > ceiling_bliss).float()
])

# Multiplicative reduction: 0.5^N where N = number of violations
ceiling_clamp_scalar = ceiling_clamp_factor ** ceiling_violations_count
# 0 violations → 1.0 (full gain)
# 1 violation  → 0.5 (half gain)
# 2 violations → 0.25 (quarter gain)
# etc.
```

### 17.6 Log Format (v2.3.0)

The training logs show Kosha status with indicators:

```
[PENTAD] M:35%✓ P:45%✓ I:40%✓ V:50%✓ B:30%✓
```

| Symbol | Meaning |
|--------|---------|
| `✓` | In Sattvic Band (healthy) |
| `_` | Below Floor (being pushed UP) |
| `!` | Above Ceiling (being clamped DOWN) |

**Example interpretations:**
- `M:20%_` → Mental at 20%, below 23.6% floor, push active
- `P:70%!` → Physical at 70%, above 61.8% ceiling, clamp active
- `I:50%✓` → Intellect at 50%, within 25%-61.8% Sattvic band

### 17.7 Configuration (v2.3.0)

```python
@dataclass
class KoshaGyroscopeConfig:
    """Configuration for Kosha Gyroscope v2.3.0."""

    # === SATTVIC BANDS (Floor/Ceiling for each Kosha) ===

    # Mental: Pattern recognition sweet spot
    floor_mental: float = 0.236       # 23.6% (Fibonacci)
    ceiling_mental: float = 0.382     # 38.2% (Fibonacci)

    # Physical: Grounding foundation (THE FOUNDATION)
    floor_physical: float = 0.382     # 38.2% (Fibonacci)
    ceiling_physical: float = 0.618   # 61.8% (φ Golden Ratio)

    # Intellect: Discriminative reasoning
    floor_intellect: float = 0.250    # 25.0% (quarter point)
    ceiling_intellect: float = 0.618  # 61.8% (φ Golden Ratio)

    # Vital: Momentum/energy flow
    floor_vital: float = 0.236        # 23.6% (Fibonacci)
    ceiling_vital: float = 0.786      # 78.6% (Fibonacci)

    # Bliss: Unified awareness
    floor_bliss: float = 0.236        # 23.6% (Fibonacci)
    ceiling_bliss: float = 0.618      # 61.8% (φ Golden Ratio)

    # === CORRECTIVE FACTORS ===
    floor_push_factor: float = 0.5    # Loss weight for floor violations
    ceiling_clamp_factor: float = 0.5 # Multiplicative clamp per ceiling violation

    # === PRIORITY WEIGHTS ===
    # Physical: ×3.0 (Foundation)
    # Intellect: ×1.5 (Hubris Tax)
    # Others: ×1.0 (Standard)
```

### 17.8 Command-Line Arguments

```bash
# Floor thresholds
--gyroscope-floor-mental 0.236
--gyroscope-floor-physical 0.382
--gyroscope-floor-intellect 0.250
--gyroscope-floor-vital 0.236
--gyroscope-floor-bliss 0.236

# Ceiling thresholds
--gyroscope-ceiling-mental 0.382
--gyroscope-ceiling-physical 0.618
--gyroscope-ceiling-intellect 0.618
--gyroscope-ceiling-vital 0.786
--gyroscope-ceiling-bliss 0.618

# Corrective factors
--gyroscope-floor-push-factor 0.5
--gyroscope-ceiling-clamp-factor 0.5
```

### 17.9 Startup Banner

```
[GYRO] Kosha Gyroscope v2.3.0: Complete Harmonic Pentad
       Sattvic Bands: M[23.6-38.2%] P[38.2-61.8%] I[25-61.8%] V[23.6-78.6%] B[23.6-61.8%]
       Push Factor: 0.5 | Clamp Factor: 0.5
       Priority: Physical(×3.0) Intellect(×1.5)
```

### 17.10 Design Philosophy

The Complete Harmonic Pentad embodies the Yogic principle that each Kosha has its natural range:

1. **Too Low (Tamas):** Sluggishness, deficiency, under-activation → Push UP with loss pressure
2. **Sattvic Band (Sattva):** Balanced, healthy, optimal → No intervention
3. **Too High (Rajas):** Over-activity, excess, instability → Clamp DOWN with gain reduction

The priority weights reflect the Kosha hierarchy:
- **Physical (×3.0):** The foundation must be stable before higher Koshas can develop
- **Intellect (×1.5):** Prevents intellectual arrogance without grounding
- **Vital (Momentum):** Energy regulation through optimization dynamics, not loss pressure

This creates a self-regulating homeostatic system where the model naturally finds its Sattvic equilibrium across all five sheaths.
