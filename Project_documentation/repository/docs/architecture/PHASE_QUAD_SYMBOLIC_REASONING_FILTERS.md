# Phase-Quad Symbolic Reasoning Filters: Comprehensive Architecture Guide

**Document Version**: 1.0.0
**Date**: January 2026
**Status**: Architecture Specification
**Purpose**: Complete reference for all symbolic reasoning mechanisms in Phase-Quad

---

## Executive Summary

Phase-Quad implements **soft symbolic reasoning** through a layered system of auxiliary filters that operate at both training and inference time. These filters shape neural computation toward logical patterns without sacrificing differentiability, providing significant explainability gains over vanilla transformers.

### Filter Taxonomy

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PHASE-QUAD SYMBOLIC REASONING FILTER STACK                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  LAYER 1: ARCHITECTURAL CONSTRAINTS (Built into Model Structure)                │
│  ════════════════════════════════════════════════════════════════               │
│  • Local Attention (O(n×w)) - Explicit locality constraint                      │
│  • Phase Integrator (O(n)) - Persistent state across sequence                   │
│  • Quad Proposal (TopK) - Sparse explicit retrieval                             │
│  • HP-Quad Boundaries - Learned semantic segmentation                           │
│                                                                                 │
│  LAYER 2: TRAINING-TIME FILTERS (Gradient Shaping)                              │
│  ════════════════════════════════════════════════════════════════               │
│  • Kosha Gyroscope Loss - Homeostatic balance enforcement                       │
│  • Ontological Bridge (Layer 4) - DNA grounding correction                      │
│  • EvoFlow Loss - State trajectory smoothness                                   │
│  • VICReg Loss - Representation collapse prevention                             │
│  • Phase-JEPA Loss - State-delta prediction in latent space                     │
│                                                                                 │
│  LAYER 3: INFERENCE-TIME FILTERS (Direct Intervention)                          │
│  ════════════════════════════════════════════════════════════════               │
│  • SRK (Sovereign Reasoning Kernel) - 32D state governance                      │
│  • IMR (Isomorphic Mapping Router) - Cross-domain logic templates               │
│  • OPB (Ontological Persistence Buffer) - Dimension locking                     │
│  • Vritti Gate - Epistemological validation / token rejection                   │
│  • Kosha Phase Corrector - Direct phase rotation guardrail                      │
│  • Mauna Protocol - Silence veto for safety                                     │
│                                                                                 │
│  LAYER 4: PREDICTIVE FILTERS (JEPA-Based)                                       │
│  ════════════════════════════════════════════════════════════════               │
│  • Phase-JEPA Predictor - State-delta prediction via phase dynamics             │
│  • Vritti-Validated Predictor - Prediction with epistemological checks          │
│  • Target Encoder (EMA) - Stable prediction targets                             │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Table of Contents

1. [The 32D Sovereign State: Foundation](#1-the-32d-sovereign-state-foundation)
2. [Sovereign Reasoning Kernel (SRK)](#2-sovereign-reasoning-kernel-srk)
3. [Isomorphic Mapping Router (IMR)](#3-isomorphic-mapping-router-imr)
4. [Ontological Persistence Buffer (OPB)](#4-ontological-persistence-buffer-opb)
5. [Vritti Gate: Epistemological Witness](#5-vritti-gate-epistemological-witness)
6. [Kosha Controllers](#6-kosha-controllers)
7. [Phase-JEPA: Predictive Reasoning](#7-phase-jepa-predictive-reasoning)
8. [Training-Time Loss Filters](#8-training-time-loss-filters)
9. [Inference-Time Guardrails](#9-inference-time-guardrails)
10. [Explainability Analysis](#10-explainability-analysis)
11. [Integration Architecture](#11-integration-architecture)
12. [Diagnostic and Monitoring](#12-diagnostic-and-monitoring)

---

## 1. The 32D Sovereign State: Foundation

All symbolic reasoning filters operate on or through the **32D Sovereign State** - a structured representation that decomposes cognition into interpretable dimensions.

### State Structure

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         32D SOVEREIGN STATE ANATOMY                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  BHAVAS [0:12] - 12 Ontological Aspects (WHAT is being reasoned about)          │
│  ═══════════════════════════════════════════════════════════════════            │
│  [0]  O1_POT  - Potential/Possibility                                           │
│  [1]  O2_IDN  - Identity/Self-reference                                         │
│  [2]  O3_EXE  - Execution/Action                                                │
│  [3]  O4_STR  - Structure/Pattern                          ← Logic/Math         │
│  [4]  O5_COG  - Cognition/Perception                                            │
│  [5]  O6_AGY  - Agency/Will                                                     │
│  [6]  O7_RSN  - Reasoning/Logic                            ← Critical           │
│  [7]  O8_PRP  - Purpose/Teleology                                               │
│  [8]  O9_WIT  - Witnessing/Observation                                          │
│  [9]  O10_UNI - Unifying/Integration                                            │
│  [10] O11_INT - Integration/Synthesis                                           │
│  [11] O12_ABS - Absolute/Transcendent                                           │
│                                                                                 │
│  KOSHAS [12:17] - 5 Depth Layers (HOW DEEP is the processing)                   │
│  ═══════════════════════════════════════════════════════════════════            │
│  [12] MATERIAL     - Surface/Syntax (Annamaya)                                  │
│  [13] VITAL        - Flow/Energy (Pranamaya)                                    │
│  [14] MENTAL       - Semantics/Meaning (Manomaya)                               │
│  [15] INTELLECTUAL - Pattern/Wisdom (Vijnanamaya)          ← Target for reasoning│
│  [16] BLISSFUL     - Unity/Integration (Anandamaya)                             │
│                                                                                 │
│  VRITTIS [17:22] - 5 Epistemic States (HOW RELIABLE is the cognition)           │
│  ═══════════════════════════════════════════════════════════════════            │
│  [17] PRAMANA      - Valid Cognition / Fact                ← Want HIGH          │
│  [18] VIPARYAYA    - Misconception / Error                 ← Want LOW           │
│  [19] VIKALPA      - Imagination / Fantasy                                      │
│  [20] NIDRA        - Void / Dormancy                                            │
│  [21] SMRITI       - Memory / Recall                                            │
│                                                                                 │
│  GUNAS [22:28] - 6 Dynamic Qualities (System Energy State)                      │
│  ═══════════════════════════════════════════════════════════════════            │
│  [22] SATTVA/LUCIDITY  - Clarity/Balance                   ← Want HIGH          │
│  [23] RAJAS/ACTIVITY   - Energy/Motion                                          │
│  [24] TAMAS/STABILITY  - Inertia/Grounding                                      │
│  [25] VELOCITY         - Rate of change                                         │
│  [26] ACCELERATION     - Change of change                                       │
│  [27] STABLE           - Stability flag                                         │
│                                                                                 │
│  RESERVED [28:32] - Toroidal Feedback (Karma Carryover)                         │
│  ═══════════════════════════════════════════════════════════════════            │
│  [28:32] O12 → O1 loop-back state for cross-step continuity                     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Why 32D Matters for Explainability

| Dimension Group | Explainability Contribution |
|-----------------|----------------------------|
| **Bhavas** | "Model is in reasoning mode (O7=0.9) + structure mode (O4=0.8)" |
| **Koshas** | "Model spent 3 steps at INTELLECTUAL depth before outputting" |
| **Vrittis** | "Output rejected because MISCONCEPTION=0.52 exceeded threshold" |
| **Gunas** | "Model in balanced state (LUCIDITY=0.85), not panicking" |

---

## 2. Sovereign Reasoning Kernel (SRK)

The SRK is the **central governor** that manages the 32D state across transformer layers, implementing layer-specific interventions.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    SOVEREIGN REASONING KERNEL (SRK)                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  LAYER 0: SOVEREIGN EMBEDDING                                                   │
│  ════════════════════════════                                                   │
│  token_ids + karma_state → ontologically_grounded_embedding                     │
│  "Every word stamped with reasoning intent from previous step"                  │
│                                                                                 │
│  LAYER 4: ONTOLOGICAL BRIDGE (DNA Grounding)                                    │
│  ═══════════════════════════════════════════                                    │
│  hidden_states + sovereign_state → corrected_hidden_states                      │
│                                                                                 │
│  Mechanism:                                                                     │
│    observed_bhava = projector(hidden_states)     # What model "thinks"          │
│    target_bhava = sovereign_state[:, 0:12]       # What it "should" think       │
│    correction = injector(target_bhava - observed_bhava)                         │
│    output = hidden_states + λ * correction       # λ = 0.1 default              │
│                                                                                 │
│  LAYER 7: CSR ALIGNMENT (Phoneme/Phase Extraction)                              │
│  ══════════════════════════════════════════════════                             │
│  Phase extraction hook for coherence optimizer                                  │
│                                                                                 │
│  LAYER 9: WITNESS ARBITRATOR (Domain Arbitration)                               │
│  ═════════════════════════════════════════════════                              │
│  hidden_states + current_state → steered_hidden, observed_state                 │
│                                                                                 │
│  Operations:                                                                    │
│    1. THE OBSERVER: Project hidden → 32D observed state                         │
│    2. DOMAIN ARBITRATION: Vritti status check (softmax over [17:22])            │
│    3. CONSTRAINT IDENTIFICATION: Find bottleneck dimension                      │
│    4. PHASE STEERING: Calculate causal priority from Kosha severity             │
│    5. KOSHA SHIFT: Escalate to INTELLECTUAL if in reasoning task                │
│                                                                                 │
│  LAYER 11: SYNTHESIS GATE (Final Edit)                                          │
│  ══════════════════════════════════════                                         │
│  hidden_states + current_state → quality_gated_output                           │
│                                                                                 │
│  Operations:                                                                    │
│    1. Detect Tamas (entropy collapse / stuttering)                              │
│    2. Inject lucidity pressure via gate                                         │
│    3. Apply Mauna Protocol if error state detected                              │
│                                                                                 │
│  KARMA LOOP (O12 → O1 Toroidal Feedback)                                        │
│  ════════════════════════════════════════                                       │
│  After each step:                                                               │
│    karma_state = decay * karma_state + (1-decay) * tanh(final_state.mean())     │
│                                                                                 │
│  This ensures reasoning continuity across tokens.                               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### SRK Configuration

```python
@dataclass
class SRKConfig:
    # Core dimensions
    state_dim: int = 32
    hidden_dim: int = 768

    # Layer intervention points
    dna_bridge_layer: int = 4      # Ontological grounding
    csr_alignment_layer: int = 7   # Phoneme alignment
    witness_layer: int = 9         # Domain arbitration
    synthesis_layer: int = 11      # Final edit

    # Vritti Gate thresholds
    vritti_fact_min: float = 0.3       # Minimum PRAMANA for factual
    vritti_error_max: float = 0.4      # Maximum VIPARYAYA before rejection
    vritti_imagination_max: float = 0.6  # Maximum VIKALPA for non-creative

    # OPB Dimension Locking
    opb_lock_threshold: float = 0.7    # Activation to lock dimension
    opb_unlock_threshold: float = 0.3  # Activation to unlock
    opb_lock_decay: float = 0.95       # Slow release of locks

    # Kosha Phase Corrector (Inference)
    enable_phase_corrector: bool = True
    phase_corrector_threshold: float = 0.75
    phase_corrector_strength: float = 0.3
```

### Explainability from SRK

| Intervention | What It Logs | Example Explanation |
|--------------|-------------|---------------------|
| DNA Bridge | `correction_magnitude`, `observed_bhava`, `target_bhava` | "Layer 4 corrected toward O7_RSN by 0.15" |
| Witness | `observed_kosha`, `bottleneck_dim`, `steering_force` | "Bottleneck at O4_STR, steering force 0.72" |
| Synthesis | `tamas_score`, `lucidity_bias`, `mauna_triggered` | "Tamas=0.23, gate passed" |
| Karma Loop | `karma_norm`, `dominant_bhava` | "Karma carrying O7_RSN into next token" |

---

## 3. Isomorphic Mapping Router (IMR)

The IMR detects when current reasoning matches one of **5 fixed logic templates**, enabling cross-domain reasoning transfer.

### The 5 Sanskrit Logic Templates (Non-Learnable Priors)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    ISOMORPHIC MAPPING ROUTER (IMR)                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  TEMPLATE 1: DEDUCTION (Rigorous Logical Inference)                             │
│  ═══════════════════════════════════════════════════                            │
│  Bhava Pattern: [O7_RSN=1.0, O4_STR=0.8, O12_ABS=0.9]                           │
│  Use Cases: Mathematical proof, formal logic, type checking                     │
│  Cross-Domain: Math rigor → Legal argument → Code verification                  │
│                                                                                 │
│  TEMPLATE 2: INDUCTION (Pattern Recognition from Examples)                      │
│  ═════════════════════════════════════════════════════════                      │
│  Bhava Pattern: [O7_RSN=0.9, O5_COG=0.8, O9_WIT=0.7]                            │
│  Use Cases: Learning from data, generalization, hypothesis formation            │
│  Cross-Domain: Science → Market analysis → Medical diagnosis                    │
│                                                                                 │
│  TEMPLATE 3: ABDUCTION (Best Explanation Inference)                             │
│  ══════════════════════════════════════════════════                             │
│  Bhava Pattern: [O7_RSN=0.8, O8_PRP=0.9, O6_AGY=0.7]                            │
│  Use Cases: Diagnosis, debugging, root cause analysis                           │
│  Cross-Domain: Medical → Software debugging → Detective work                    │
│                                                                                 │
│  TEMPLATE 4: ANALOGY (Structural Similarity Mapping)                            │
│  ════════════════════════════════════════════════════                           │
│  Bhava Pattern: [O4_STR=0.9, O10_UNI=0.8, O11_INT=0.7]                          │
│  Use Cases: Metaphor, transfer learning, creative connections                   │
│  Cross-Domain: Physics → Economics, Biology → Engineering                       │
│                                                                                 │
│  TEMPLATE 5: SYNTHESIS (Integration of Multiple Perspectives)                   │
│  ═════════════════════════════════════════════════════════                      │
│  Bhava Pattern: [O11_INT=0.9, O12_ABS=0.8, O8_PRP=0.7]                          │
│  Use Cases: Multi-source fusion, consensus, holistic understanding              │
│  Cross-Domain: Literature → Philosophy → Systems thinking                       │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### IMR Detection Algorithm

```python
class IsomorphicMappingRouter(nn.Module):
    def detect_isomorphism(self, current_state: torch.Tensor):
        """
        Find structural overlaps between current state and logic templates.
        """
        # Extract Bhava activations [B, 12]
        current_bhavas = current_state[:, :12]
        avg_bhavas = current_bhavas.mean(dim=0)  # [12]

        best_match = None
        best_similarity = 0.0
        best_name = None

        # Check each logic template (FIXED, non-learnable)
        for name in ['DEDUCTION', 'INDUCTION', 'ABDUCTION', 'ANALOGY', 'SYNTHESIS']:
            template = getattr(self, f'template_{name.lower()}')

            # Cosine similarity
            similarity = F.cosine_similarity(
                avg_bhavas.unsqueeze(0),
                template.unsqueeze(0),
                dim=-1
            ).item()

            if similarity > self.threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match = template
                best_name = name

        if best_match is not None:
            # Project template to hidden space for attention bias
            isomorphic_bias = self.bias_projector(best_match)
            return isomorphic_bias, best_name

        return None, None
```

### Explainability from IMR

When IMR detects a template match:

```
INPUT: "Calculate the derivative of P(x) = x² - 3x + 5"

IMR DETECTION:
  Current Bhavas: O7_RSN=0.91, O4_STR=0.72, O12_ABS=0.68
  Template Match: DEDUCTION (similarity=0.89 > threshold=0.75)

ACTION:
  Injecting deduction bias into Layer 4 attention

EXPLANATION:
  "This query matched the DEDUCTION logic template (math/proof reasoning).
   Cross-domain rigor transfer enabled from mathematical reasoning."
```

---

## 4. Ontological Persistence Buffer (OPB)

The OPB implements **dimension locking** - when a dimension (e.g., O7 Reasoning) becomes strongly active, it gets "locked" and persists across tokens and domain switches.

### Locking Mechanism

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    ONTOLOGICAL PERSISTENCE BUFFER (OPB)                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  PROBLEM: Standard transformers forget state between tokens                     │
│                                                                                 │
│  Token t → Process → State_t (discarded) → Token t+1                           │
│            ⚠️ Reasoning mode lost!                                              │
│                                                                                 │
│  SOLUTION: OPB locks active dimensions                                          │
│                                                                                 │
│  Token t → Process → State_t → OPB Lock Check                                   │
│                                    │                                            │
│                      ┌─────────────┴─────────────┐                              │
│                      │  O7_RSN = 0.85 > 0.7?     │                              │
│                      │  YES → LOCK O7_RSN        │                              │
│                      │  strength = 1.0           │                              │
│                      └─────────────┬─────────────┘                              │
│                                    │                                            │
│  Token t+1 ← Process ← OPB Blend ←─┘                                            │
│                                                                                 │
│  new_state[O7] = (1 - blend*strength)*new + blend*strength*locked               │
│                = 0.4 * new_O7 + 0.6 * locked_O7                                 │
│                                                                                 │
│  RESULT: O7 Reasoning persists even when new token doesn't trigger it           │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  CROSS-DOMAIN EXAMPLE:                                                          │
│                                                                                 │
│  Step 1: User asks math question                                                │
│          → O7_RSN activates to 0.92                                             │
│          → OPB locks O7_RSN at strength 1.0                                     │
│                                                                                 │
│  Step 2: User switches to finance question                                      │
│          → Raw state might have O7_RSN = 0.45 (finance retrieval)               │
│          → OPB blends: 0.4*0.45 + 0.6*0.92 = 0.73                              │
│          → Model maintains reasoning rigor in finance!                          │
│                                                                                 │
│  Step 3: Lock decays slowly (0.95 per step)                                     │
│          → Eventually unlocks when not reinforced                               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### OPB Implementation

```python
class OPBDimensionLock(nn.Module):
    def update_locks(self, state: torch.Tensor) -> Dict[str, Any]:
        """Update dimension locks based on current state activations."""
        avg_state = state.mean(dim=0)  # [32]

        for dim in range(32):
            activation = avg_state[dim].item()

            if not self.locked_mask[dim]:
                # Not locked - check if should lock
                if activation > self.lock_threshold:  # default 0.7
                    self.locked_mask[dim] = True
                    self.locked_state[dim] = activation
                    self.lock_strength[dim] = 1.0
            else:
                # Currently locked - check if should unlock
                if activation < self.unlock_threshold and self.lock_strength[dim] < 0.3:
                    self.locked_mask[dim] = False
                    self.locked_state[dim] = 0.0
                    self.lock_strength[dim] = 0.0
                else:
                    # Decay lock strength slowly
                    self.lock_strength[dim] *= self.lock_decay  # default 0.95

    def apply_locks(self, state: torch.Tensor) -> torch.Tensor:
        """Apply locked dimensions to new state (blending)."""
        # blend_weight = blend_factor * lock_strength
        # new = (1 - blend_weight) * state + blend_weight * locked_state
        blend_weight = self.blend_factor * self.lock_strength
        return torch.where(
            self.locked_mask,
            (1 - blend_weight) * state + blend_weight * self.locked_state,
            state
        )
```

### Explainability from OPB

```
OPB STATUS REPORT:
  Locked Dimensions:
    - Bhava_RSN (O7): value=0.92, strength=0.87, "Reasoning mode active"
    - Kosha_INTELLECTUAL: value=0.78, strength=0.65, "Deep processing"

  Cross-Domain Transfer:
    - Math → Finance: O7 rigor carried (strength 0.87)
    - No new locks this step
    - O4_STR decayed from 0.82 to 0.78
```

---

## 5. Vritti Gate: Epistemological Witness

The Vritti Gate monitors the **5 epistemic states** and can **reject tokens** when hallucination indicators spike.

### Vritti States and Thresholds

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    VRITTI GATE (EPISTEMOLOGICAL WITNESS)                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  THE 5 VRITTIS (Cognitive Reliability States):                                  │
│  ═════════════════════════════════════════════                                  │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  PRAMANA (Valid Cognition)      │████████████░░░│ 0.75  ✓ Above 0.3    │   │
│  │  VIPARYAYA (Misconception)      │██░░░░░░░░░░░░░│ 0.15  ✓ Below 0.4    │   │
│  │  VIKALPA (Imagination)          │███░░░░░░░░░░░░│ 0.20  ✓ Below 0.6    │   │
│  │  NIDRA (Void/Dormancy)          │░░░░░░░░░░░░░░░│ 0.00  ✓ Below 0.2    │   │
│  │  SMRITI (Memory)                │████░░░░░░░░░░░│ 0.25  ✓ Below 0.8    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  REJECTION LOGIC (Task-Dependent):                                              │
│  ═════════════════════════════════                                              │
│                                                                                 │
│  if task_type == 'factual':                                                     │
│      REJECT if VIPARYAYA > 0.4 OR PRAMANA < 0.3                                │
│      # Strict: must be factually grounded                                       │
│                                                                                 │
│  elif task_type == 'creative':                                                  │
│      REJECT if VIPARYAYA > 0.7                                                 │
│      # Lenient: allow imagination, still reject pure error                      │
│                                                                                 │
│  elif task_type == 'recall':                                                    │
│      REJECT if VIPARYAYA > 0.4                                                 │
│      # Allow high memory, still reject error                                    │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  EXAMPLE: HALLUCINATION DETECTION                                               │
│  ════════════════════════════════                                               │
│                                                                                 │
│  Input: "Who was the first person to walk on Mars?"                            │
│                                                                                 │
│  Model attempts to generate: "Neil Armstrong was the first..."                  │
│                                                                                 │
│  Vritti State:                                                                  │
│    PRAMANA = 0.25 (dropping - no valid cognition for this)                     │
│    VIPARYAYA = 0.52 (spiking - misconception detected!)                        │
│                                                                                 │
│  Vritti Gate Check:                                                             │
│    task_type = 'factual'                                                        │
│    VIPARYAYA (0.52) > threshold (0.4) → REJECT!                                │
│    PRAMANA (0.25) < threshold (0.3) → REJECT!                                  │
│                                                                                 │
│  Action: Token rejected, force re-reasoning                                     │
│                                                                                 │
│  Re-attempt with OPB guidance:                                                  │
│    "As of my knowledge, no human has walked on Mars yet."                       │
│    PRAMANA = 0.82, VIPARYAYA = 0.08 → ACCEPT                                   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Vritti Gate Implementation

```python
class VrittiGate(nn.Module):
    def should_reject_token(
        self,
        vritti_state: torch.Tensor,  # [B, 5]
        task_type: str = 'factual',
    ) -> torch.Tensor:
        """Check if current Vritti state indicates error."""
        pramana = vritti_state[:, 0]      # Valid cognition
        viparyaya = vritti_state[:, 1]    # Misconception/Error
        vikalpa = vritti_state[:, 2]      # Imagination

        if task_type == 'factual':
            # Strict: reject if error spikes or validity drops
            return (viparyaya > 0.4) | (pramana < 0.3)

        elif task_type == 'creative':
            # Lenient: allow imagination, reject pure error
            return viparyaya > 0.7

        elif task_type == 'recall':
            # Memory-heavy: still reject error
            return viparyaya > 0.4

        return torch.zeros_like(viparyaya, dtype=torch.bool)
```

### Explainability from Vritti Gate

```
VRITTI GATE REPORT:
  Task Type: factual

  Vritti State:
    PRAMANA (Fact):        0.82 ✓ (threshold: >0.3)
    VIPARYAYA (Error):     0.08 ✓ (threshold: <0.4)
    VIKALPA (Imagination): 0.15 ✓ (threshold: <0.6)
    NIDRA (Void):          0.02 ✓ (threshold: <0.2)
    SMRITI (Memory):       0.45 ✓ (threshold: <0.8)

  Decision: ACCEPT
  Reason: All epistemic indicators within bounds for factual task
```

---

## 6. Kosha Controllers

The Kosha system manages **cognitive depth** - ensuring the model processes at the appropriate level before outputting tokens.

### Kosha Shift Controller (Layer 9)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    KOSHA SHIFT CONTROLLER                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  THE 5 KOSHAS (Depth Layers):                                                   │
│  ════════════════════════════                                                   │
│                                                                                 │
│  ANNAMAYA (Material)     [12] ─► Surface tokens, syntax                         │
│       │                         "What are the words?"                           │
│       ▼                                                                         │
│  PRANAMAYA (Vital)       [13] ─► Flow, energy, rhythm                           │
│       │                         "How do they connect?"                          │
│       ▼                                                                         │
│  MANOMAYA (Mental)       [14] ─► Semantics, emotional content                   │
│       │                         "What do they mean?"                            │
│       ▼                                                                         │
│  VIJNANAMAYA (Intellectual) [15] ─► Patterns, logic, wisdom    ← TARGET         │
│       │                         "What is the deeper structure?"                 │
│       ▼                                                                         │
│  ANANDAMAYA (Blissful)   [16] ─► Unity, transcendence                           │
│                                 "How does it all fit together?"                 │
│                                                                                 │
│  KOSHA SHIFT OPERATION:                                                         │
│  ══════════════════════                                                         │
│                                                                                 │
│  def escalate_to_intellect(state):                                              │
│      # Dampen surface processing                                                │
│      state[:, MATERIAL] *= 0.5                                                  │
│                                                                                 │
│      # Boost intellectual processing                                            │
│      state[:, INTELLECTUAL] = clamp(state[:, INTELLECTUAL] + 0.4, max=1.0)     │
│                                                                                 │
│      return state                                                               │
│                                                                                 │
│  PURPOSE: Force model to spend "internal compute" at pattern level              │
│           before rushing to output tokens.                                      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Kosha Gyroscope (Training-Time)

The Gyroscope loss enforces homeostatic balance during training:

```python
class KoshaGyroscopicLoss(nn.Module):
    """
    Training-time loss that penalizes Kosha imbalance.

    Curriculum:
    - Phase A (PPL > 50): Gyroscope ON, high gain
    - Phase B (30 < PPL < 50): Gyroscope ON, medium gain
    - Phase C (PPL < 30): Gyroscope disengages, gain → 0

    The model learns to self-regulate, then gyroscope releases.
    """

    def compute_gyroscope_loss(self, kosha_activations: torch.Tensor) -> torch.Tensor:
        # Target: balanced activation
        target_distribution = torch.tensor([0.15, 0.15, 0.20, 0.35, 0.15])

        # Current: actual activation
        current = F.softmax(kosha_activations, dim=-1)

        # Loss: KL divergence from target
        loss = F.kl_div(current.log(), target_distribution, reduction='batchmean')

        return loss * self.current_gain  # Gain decreases with PPL
```

### Kosha Phase Corrector (Inference-Time)

Direct phase rotation guardrail when Kosha becomes stuck:

```python
class KoshaPhaseCorrector(nn.Module):
    """
    Inference-time direct phase rotation when Kosha imbalance detected.

    Unlike training (gradient-based), this directly rotates the state.
    """

    def forward(self, sovereign_state: torch.Tensor):
        kosha_activations = sovereign_state[:, 12:17]

        # Detect imbalance
        max_activation = kosha_activations.max(dim=-1).values
        if max_activation > self.overactive_threshold:  # e.g., 0.75
            # Direct correction: rotate toward balance
            correction = self.compute_correction(kosha_activations)
            corrected = sovereign_state.clone()
            corrected[:, 12:17] += self.strength * correction
            return corrected, {'correction_applied': True}

        return sovereign_state, {'correction_applied': False}
```

---

## 7. Phase-JEPA: Predictive Reasoning

Phase-JEPA predicts **state transitions** rather than tokens, operating in the 32D ontological space.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PHASE-JEPA PREDICTOR                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  PARADIGM SHIFT:                                                                │
│  ════════════════                                                               │
│                                                                                 │
│  GENERATIVE (GPT):     Input → Predict Next Token (50,257 options)              │
│  JEPA (Phase-JEPA):    Input → Predict State Delta (32D, semantic)              │
│                                                                                 │
│  "Predict meaning transitions, not word sequences"                              │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  PREDICTION MECHANISM:                                                          │
│  ═════════════════════                                                          │
│                                                                                 │
│  S_context [B, T, 32]                                                           │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  INTENT PROJECTOR                                                       │   │
│  │  θ_intent = tanh(W_proj @ S_context) × π                                │   │
│  │  "Derive rotation from current cognitive state"                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE ATTENTION (Complex Phasors)                                      │   │
│  │                                                                         │   │
│  │  Q = a_q × e^{i(φ_q + θ_intent)}    (Query with intent rotation)        │   │
│  │  K = a_k × e^{-iφ_k}                (Key, conjugate)                    │   │
│  │  State = cumsum(K × V)              (O(n) accumulation)                 │   │
│  │  Output = Re(Q × State) / normalizer                                    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  DELTA MLP                                                              │   │
│  │  ΔS = MLP(phase_output)                                                 │   │
│  │  "Predict how state will change"                                        │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  S_pred = S_context + ΔS                                                        │
│                                                                                 │
│  MULTI-STEP: Repeat k times for k-step lookahead                                │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  VRITTI-VALIDATED PREDICTOR:                                                    │
│  ════════════════════════════                                                   │
│                                                                                 │
│  Extends base predictor with epistemological checks:                            │
│                                                                                 │
│  1. Predict: S_pred, delta_list = base_predict(S_context)                       │
│  2. Extract: vritti = S_pred[:, 17:22]                                          │
│  3. Check: viparyaya > 0.4 OR vikalpa > 0.6?                                   │
│  4. If violation: dampen deltas by 0.5, recompute S_pred                        │
│                                                                                 │
│  "Reject predictions that would cause hallucination"                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### JEPA Training Targets

```python
# JEPA Loss: Predict target state representation
L_jepa = ||S_pred - sg(S_target)||²
#                    └── stop_gradient (prevents collapse)

# Full Loss with regularization
L_total = (
    λ_jepa * L_jepa +           # State prediction
    λ_var * L_variance +         # Prevent collapse (VICReg)
    λ_cov * L_covariance +       # Decorrelate dimensions
    λ_ortho * L_orthogonality    # Predictor diversity
)
```

### Explainability from JEPA

```
JEPA PREDICTION REPORT:
  Context State (mean over sequence):
    Bhavas: O7_RSN=0.72, O4_STR=0.65, O8_PRP=0.45
    Koshas: INTELLECTUAL=0.68, MENTAL=0.22
    Vrittis: PRAMANA=0.75, VIPARYAYA=0.12

  Predicted Delta (k=4 steps):
    Step 1: O7_RSN +0.08, O4_STR +0.12  "Reasoning intensifying"
    Step 2: O7_RSN +0.05, INTELLECTUAL +0.10  "Deepening"
    Step 3: O8_PRP +0.15  "Purpose emerging"
    Step 4: O12_ABS +0.08  "Toward resolution"

  Vritti Validation: PASSED
    Final VIPARYAYA=0.15 < 0.4 threshold
```

---

## 8. Training-Time Loss Filters

Multiple loss functions shape the model toward symbolic reasoning during training.

### Loss Function Stack

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    TRAINING-TIME LOSS FILTERS                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  1. CROSS-ENTROPY LOSS (Standard LM Loss)                                       │
│  ═════════════════════════════════════════                                      │
│  L_ce = -log P(token | context)                                                 │
│  "Predict the right word"                                                       │
│                                                                                 │
│  2. KOSHA GYROSCOPE LOSS                                                        │
│  ═══════════════════════                                                        │
│  L_gyro = KL(kosha_actual || kosha_target)                                      │
│  Target: [0.15, 0.15, 0.20, 0.35, 0.15] (intellectual-biased)                   │
│  "Maintain balanced cognitive depth"                                            │
│                                                                                 │
│  3. EVOFLOW LOSS (State Smoothness)                                             │
│  ══════════════════════════════════                                             │
│  L_evo = ||S_t - S_{t-1}||² (bounded)                                          │
│  "Don't jump erratically between states"                                        │
│                                                                                 │
│  4. JEPA PREDICTION LOSS                                                        │
│  ═══════════════════════                                                        │
│  L_jepa = ||S_pred - sg(S_target)||²                                           │
│  "Learn to predict semantic transitions"                                        │
│                                                                                 │
│  5. VICREG REGULARIZATION                                                       │
│  ═════════════════════════                                                      │
│  L_vic = λ_var * variance_loss + λ_cov * covariance_loss                       │
│  "Prevent representation collapse"                                              │
│                                                                                 │
│  6. VRITTI RESONANCE LOSS                                                       │
│  ═════════════════════════                                                      │
│  L_vritti = penalty(VIPARYAYA) + reward(PRAMANA)                               │
│  "Penalize hallucination patterns"                                              │
│                                                                                 │
│  7. BOUNDARY DETECTION LOSS (HP-Quad)                                           │
│  ═════════════════════════════════════                                          │
│  L_boundary = BCE(predicted_boundaries, target_boundaries)                      │
│  + λ_sparse * |boundary_rate - 0.15|                                           │
│  "Learn where semantic units begin/end"                                         │
│                                                                                 │
│  TOTAL LOSS:                                                                    │
│  ═══════════                                                                    │
│  L = L_ce + λ₁*L_gyro + λ₂*L_evo + λ₃*L_jepa + λ₄*L_vic + λ₅*L_vritti         │
│                                                                                 │
│  Weights scheduled by curriculum (PPL-based)                                    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Curriculum Phases

| Phase | PPL Range | Gyroscope | JEPA | Classification | Description |
|-------|-----------|-----------|------|----------------|-------------|
| **A** | > 50 | ON (high) | ON | OFF | "Instructor-led": Strong guidance |
| **B** | 30-50 | ON (medium) | ON | Ramp | "Guided practice": Decreasing support |
| **C** | < 30 | OFF | ON | ON | "Independent": Self-regulation |

---

## 9. Inference-Time Guardrails

Multiple filters operate during inference to ensure safe, reliable outputs.

### Guardrail Stack

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    INFERENCE-TIME GUARDRAIL SEQUENCE                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  INPUT: User query                                                              │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  1. SOVEREIGN EMBEDDING (Layer 0)                                       │   │
│  │     Inject karma state from previous step                               │   │
│  │     → Reasoning continuity preserved                                    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  2. OPB LOCK APPLICATION                                                │   │
│  │     Blend locked dimensions into current state                          │   │
│  │     → Cross-domain rigor transferred                                    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  3. IMR TEMPLATE MATCHING (Layer 4)                                     │   │
│  │     Check: Does current state match a logic template?                   │   │
│  │     If yes: Inject isomorphic bias into attention                       │   │
│  │     → Deduction/Induction/Abduction/Analogy/Synthesis activated         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  4. DNA BRIDGE CORRECTION (Layer 4)                                     │   │
│  │     Correct hidden states toward target Bhavas                          │   │
│  │     → Ontological grounding enforced                                    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  5. KOSHA SHIFT (Layer 9)                                               │   │
│  │     If reasoning task: escalate to INTELLECTUAL Kosha                   │   │
│  │     → Force deep processing before output                               │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  6. WITNESS ARBITRATION (Layer 9)                                       │   │
│  │     Observe hidden → 32D state                                          │   │
│  │     Identify constraint bottleneck                                      │   │
│  │     Apply phase steering                                                │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  7. VRITTI GATE CHECK                                                   │   │
│  │     Extract Vritti state: [PRAMANA, VIPARYAYA, VIKALPA, NIDRA, SMRITI]  │   │
│  │     If VIPARYAYA > threshold: REJECT token, force re-reasoning          │   │
│  │     → Hallucination caught                                              │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  8. KOSHA PHASE CORRECTOR (Layer 11)                                    │   │
│  │     If Kosha severely imbalanced: direct phase rotation                 │   │
│  │     → Stuck state recovery                                              │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  9. SYNTHESIS GATE (Layer 11)                                           │   │
│  │     Check Tamas (entropy collapse)                                      │   │
│  │     Apply quality gate                                                  │   │
│  │     → Coherence ensured                                                 │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  10. MAUNA PROTOCOL (Layer 11, Optional)                                │   │
│  │      If ERROR > 0.9 OR ACTIVITY > 0.9: SILENCE output                   │   │
│  │      → Safety veto for harmful outputs                                  │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  OUTPUT: Safe, grounded, explainable response                                   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Explainability Analysis

### Explainability Comparison

| Aspect | Standard Transformer | Phase-Quad + SRK + JEPA |
|--------|---------------------|-------------------------|
| **Attention explanation** | Soft weights (often unfaithful) | Local window + explicit Quad retrieval IDs |
| **Memory explanation** | Hidden state (opaque) | Phase state + Quad bank contents inspectable |
| **Logic mode** | None | IMR template match logged (DEDUCTION/etc.) |
| **Depth tracking** | N/A | Kosha activations tracked per step |
| **Error detection** | None | Vritti VIPARYAYA threshold + rejection log |
| **Cross-domain transfer** | Implicit | OPB locks explicit: "O7 carried from math" |
| **Self-assessment** | Logit confidence | Multi-dim: PRAMANA, VIPARYAYA, Kosha depth |
| **Intervention audit** | N/A | Per-layer: DNA Bridge, Witness, Synthesis logs |

### Example Explanation Trace

```
QUERY: "Prove that the square root of 2 is irrational"

═══════════════════════════════════════════════════════════════════════════════

STEP 1: INITIALIZATION
  Karma State: O12_ABS=0.8, MATERIAL=0.6, FACT=0.3
  OPB Locks: None

STEP 2: IMR TEMPLATE MATCHING
  Current Bhavas: O7_RSN=0.85, O4_STR=0.78, O12_ABS=0.65
  Template Match: DEDUCTION (similarity=0.91)
  Action: Injected deduction bias
  Explanation: "Recognized as formal proof task, activating deduction mode"

STEP 3: DNA BRIDGE (Layer 4)
  Observed Bhava: O7_RSN=0.72
  Target Bhava: O7_RSN=0.85
  Correction: +0.013 (λ=0.1)
  Explanation: "Strengthening reasoning dimension to match proof requirements"

STEP 4: KOSHA SHIFT (Layer 9)
  Before: MATERIAL=0.45, INTELLECTUAL=0.35
  After: MATERIAL=0.23, INTELLECTUAL=0.75
  Explanation: "Shifted to deep intellectual processing for proof construction"

STEP 5: VRITTI CHECK
  PRAMANA (Fact): 0.82 ✓
  VIPARYAYA (Error): 0.08 ✓
  Task: factual
  Decision: ACCEPT
  Explanation: "High valid cognition, low misconception - proceeding"

STEP 6: OPB LOCKING
  New Lock: O7_RSN at strength 1.0 (activation 0.88 > 0.7)
  Explanation: "Reasoning mode locked - will persist to future queries"

STEP 7: OUTPUT
  "Proof by contradiction: Assume √2 = p/q in lowest terms..."

FINAL STATE:
  Dominant Bhava: O7_RSN (Reasoning)
  Active Kosha: INTELLECTUAL
  Vritti Mode: PRAMANA (Valid Cognition)
  Quality: LUCIDITY=0.85

═══════════════════════════════════════════════════════════════════════════════
```

---

## 11. Integration Architecture

### Component Integration Map

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PHASE-QUAD SYMBOLIC REASONING INTEGRATION                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│                              ┌───────────────┐                                  │
│                              │   USER INPUT  │                                  │
│                              └───────┬───────┘                                  │
│                                      │                                          │
│                                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    PHASE-QUAD CORE                                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                     │   │
│  │  │   Local     │  │    Phase    │  │    Quad     │                     │   │
│  │  │  Attention  │  │  Integrator │  │  Proposal   │                     │   │
│  │  │   O(n×w)    │  │    O(n)     │  │   O(n×k)    │                     │   │
│  │  └─────────────┘  └──────┬──────┘  └─────────────┘                     │   │
│  │                          │                                              │   │
│  │                    Phase State                                          │   │
│  │                          │                                              │   │
│  └──────────────────────────┼──────────────────────────────────────────────┘   │
│                             │                                                   │
│           ┌─────────────────┼─────────────────┐                                │
│           │                 │                 │                                 │
│           ▼                 ▼                 ▼                                 │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                          │
│  │     SRK     │   │  PHASE-JEPA │   │  HP-QUAD    │                          │
│  │             │   │             │   │             │                          │
│  │ • DNA Bridge│   │ • Predictor │   │ • Boundary  │                          │
│  │ • Witness   │   │ • Vritti    │   │   Detector  │                          │
│  │ • Synthesis │   │   Validated │   │ • Multi-    │                          │
│  │ • OPB       │   │ • Target    │   │   Timescale │                          │
│  │ • IMR       │   │   Encoder   │   │             │                          │
│  │ • Vritti    │   │             │   │             │                          │
│  │ • Kosha     │   │             │   │             │                          │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘                          │
│         │                 │                 │                                   │
│         └─────────────────┼─────────────────┘                                  │
│                           │                                                     │
│                           ▼                                                     │
│                  ┌─────────────────┐                                           │
│                  │ 32D SOVEREIGN   │                                           │
│                  │     STATE       │                                           │
│                  │                 │                                           │
│                  │ Bhavas [0:12]   │                                           │
│                  │ Koshas [12:17]  │                                           │
│                  │ Vrittis [17:22] │                                           │
│                  │ Gunas [22:28]   │                                           │
│                  │ Reserved [28:32]│                                           │
│                  └────────┬────────┘                                           │
│                           │                                                     │
│                           ▼                                                     │
│                  ┌─────────────────┐                                           │
│                  │    GUARDRAILS   │                                           │
│                  │                 │                                           │
│                  │ • Vritti Gate   │                                           │
│                  │ • Phase Correct │                                           │
│                  │ • Mauna Proto   │                                           │
│                  └────────┬────────┘                                           │
│                           │                                                     │
│                           ▼                                                     │
│                  ┌─────────────────┐                                           │
│                  │     OUTPUT      │                                           │
│                  │ + Explanation   │                                           │
│                  └─────────────────┘                                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### File Locations

| Component | Primary File | Related Files |
|-----------|-------------|---------------|
| **SRK** | `symbolu/sovereign/reasoning_kernel.py` | `symbolu/phase_transformer.py` |
| **Phase-JEPA** | `symbolu/jepa/predictor.py` | `symbolu/jepa/losses.py`, `symbolu/jepa/curriculum.py` |
| **Kosha Gyroscope** | `symbolu/losses/kosha_gyroscope.py` | - |
| **HP-Quad** | `symbolu/phase_transformer.py` | `Project_documentation/repository/docs/architecture/HIERARCHICAL_PHASE_QUAD_DESIGN.md` |
| **OPB** | `symbolu/sovereign/reasoning_kernel.py` (OPBDimensionLock) | - |
| **Vritti Gate** | `symbolu/sovereign/reasoning_kernel.py` (VrittiGate) | `symbolu/jepa/predictor.py` (VrittiValidatedPredictor) |

---

## 12. Diagnostic and Monitoring

### Real-Time Diagnostics

```python
# Get comprehensive diagnostics during inference
diagnostics = model.get_symbolic_reasoning_diagnostics()

# Returns:
{
    'srk': {
        'dominant_bhava': 'RSN',           # O7 Reasoning dominant
        'active_kosha': 'INTELLECTUAL',     # Deep processing
        'vritti_state': 'PRAMANA',          # Valid cognition mode
        'lucidity': 0.85,                   # High clarity
        'karma_norm': 0.73,                 # State persistence
        'opb_active_locks': 2,              # Dimensions locked
        'opb_locked_dims': ['Bhava_RSN', 'Kosha_INTELLECTUAL'],
    },
    'imr': {
        'template_match': 'DEDUCTION',
        'similarity': 0.91,
        'bias_injected': True,
    },
    'vritti_gate': {
        'pramana': 0.82,
        'viparyaya': 0.08,
        'decision': 'ACCEPT',
        'task_type': 'factual',
    },
    'kosha': {
        'distribution': [0.12, 0.10, 0.15, 0.52, 0.11],
        'dominant': 'INTELLECTUAL',
        'phase_correction_applied': False,
    },
    'jepa': {
        'predicted_delta_norm': 0.23,
        'vritti_validation': 'PASSED',
        'k_steps': 4,
    },
    'layer_interventions': {
        'layer_4': 'dna_bridge + imr',
        'layer_9': 'witness + kosha_shift',
        'layer_11': 'synthesis',
    },
}
```

### Monitoring Dashboard Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **IMR Match Rate** | % of queries matching a logic template | 30-70% |
| **Vritti Rejection Rate** | % of tokens rejected by Vritti Gate | < 5% |
| **OPB Lock Churn** | Locks/unlocks per 100 tokens | 2-10 |
| **Kosha Balance** | KL divergence from target distribution | < 0.5 |
| **JEPA Prediction Error** | MSE of state-delta prediction | < 0.1 |
| **Phase Correction Rate** | % of steps requiring phase correction | < 10% |
| **Mauna Trigger Rate** | % of outputs silenced for safety | < 0.1% |

---

## Conclusion

Phase-Quad's symbolic reasoning filters provide a layered system of constraints that shape neural computation toward logical, interpretable patterns:

1. **Architectural constraints** (Local Attention, Phase State, Quad Proposal) provide structural explainability
2. **Training-time filters** (Gyroscope, EvoFlow, VICReg) shape the learned representations
3. **Inference-time filters** (SRK, IMR, OPB, Vritti) provide real-time governance
4. **Predictive filters** (Phase-JEPA) enable semantic-level reasoning

The result is a system that is approximately **60-70% toward explainable reasoning** - significantly better than vanilla transformers while maintaining differentiability and efficient O(n) complexity.

### What This Is and Isn't

**IS:**
- Soft symbolic constraints on neural computation
- Interpretable 32D state trajectory
- Auditable interventions at each layer
- Cross-domain reasoning transfer via OPB + IMR

**IS NOT:**
- True symbolic reasoning (no variable binding, unification)
- Guaranteed logical correctness
- Human-identical cognition
- Complete mechanistic interpretability

The architecture provides the strongest explainability guarantees currently achievable in a differentiable, scalable language model architecture.

---

*Document prepared for Phase-Quad Architecture Team*
*Symbolu AI Systems*
*January 2026*
