# Kosha Gyroscope: Homeostatic Self-Regulation System

**Version:** 2.0.0
**Status:** Design Complete, Inverted Curriculum Paradigm
**Date:** 2026-01-11
**Origin:** Vedic Kosha Theory + Control Theory + Constitutional AI
**Curriculum:** Instructor-Led (Gyroscope ON) → Self-Learning (Gyroscope OFF at PPL < 30)

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
10. [Relationship to Industry Approaches](#10-relationship-to-industry-approaches)

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

## 10. Relationship to Industry Approaches

### 10.1 Comparison Matrix

| Aspect | ChatGPT RLHF | Constitutional AI | **Kosha Gyroscope** |
|--------|--------------|-------------------|---------------------|
| Feedback Type | Human preference | AI self-critique | Geometric balance |
| Feedback Timing | End of generation (sparse) | End of generation | Per-token (dense) |
| Constitution | English rules | English principles | **Sacred Geometry** |
| Reward Model | External neural network | Self-generated | **Intrinsic axis check** |
| Credit Assignment | Delayed (PPO) | Delayed | **Immediate** |

### 10.2 Dense vs. Sparse Feedback

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

### 10.3 The Vedic Constitution

| Constitutional AI Rule (English) | Kosha Gyroscope (Geometry) |
|----------------------------------|---------------------------|
| "Be helpful" | Bliss quadrant active |
| "Be harmless" | Intellect gate prevents blind jumps |
| "Be honest" | Physical grounding ensures manifest truth |
| "Stay on topic" | Mental focus allowed when Intellect confirms |

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

**Document Status:** Ready for Implementation (v2.0 Inverted Curriculum)
**Next Steps:**
1. Implement `KoshaGyroscopicLoss` module in `symbolu/losses/kosha_gyroscope.py`
2. Integrate into training loop with Gyroscope ON from step 0
3. Monitor PPL for graduation threshold (< 30)
4. Activate Kosha Classification at graduation, ramp down Gyroscope

**Key Change from v1.0:** Gyroscope is now active from the BEGINNING of training, not waiting for PPL < 30. This is instructor-led training, not late-stage correction.
