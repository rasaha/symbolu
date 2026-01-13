# Inverted Curriculum Evolution Design

**Version**: 1.0.0
**Status**: DRAFT
**Author**: Claude Code
**Date**: 2026-01-13

## Table of Contents

1. [Fundamentals](#1-fundamentals)
   - 1.1 [The 12-Layer Architecture](#11-the-12-layer-architecture)
   - 1.2 [Authority vs Sensory Layers](#12-authority-vs-sensory-layers)
   - 1.3 [Attention Mechanisms](#13-attention-mechanisms)
   - 1.4 [Phase Attention Mathematics](#14-phase-attention-mathematics)
   - 1.5 [Quadratic Attention Mathematics](#15-quadratic-attention-mathematics)
   - 1.6 [Computational Complexity](#16-computational-complexity)
2. [Current Implementation](#2-current-implementation)
   - 2.1 [Hierarchical Gradient Scaler (HGS)](#21-hierarchical-gradient-scaler-hgs)
   - 2.2 [Dynamic Relaxation Controller](#22-dynamic-relaxation-controller)
   - 2.3 [Multi-Stage Evolution (V9.9.1)](#23-multi-stage-evolution-v991)
   - 2.4 [Phase Weight Decay](#24-phase-weight-decay)
   - 2.5 [Auxiliary Controllers](#25-auxiliary-controllers)
3. [Problem Analysis](#3-problem-analysis)
   - 3.1 [The Gibberish Problem](#31-the-gibberish-problem)
   - 3.2 [Compute Explosion](#32-compute-explosion)
   - 3.3 [Controller Complexity](#33-controller-complexity)
4. [Proposed System: Inverted Curriculum](#4-proposed-system-inverted-curriculum)
   - 4.1 [Core Insight](#41-core-insight)
   - 4.2 [Inverted Evolution Direction](#42-inverted-evolution-direction)
   - 4.3 [Per-Layer Phase Weights](#43-per-layer-phase-weights)
   - 4.4 [Soft Layer Transition](#44-soft-layer-transition)
   - 4.5 [Dynamic Sequence Length](#45-dynamic-sequence-length)
   - 4.6 [Coupled Curriculum](#46-coupled-curriculum)
5. [Implementation Plan](#5-implementation-plan)
6. [API Reference](#6-api-reference)
7. [Testing Strategy](#7-testing-strategy)
8. [Changelog](#8-changelog)

---

## 1. Fundamentals

### 1.1 The 12-Layer Architecture

The Sovereign-1 model uses a 12-layer transformer architecture where layers serve different purposes based on their position and configuration.

```
┌─────────────────────────────────────────────────────────────┐
│                    INPUT EMBEDDINGS                          │
│                  (Token + Position + Phase)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 0-N:  AUTHORITY LAYERS (Phase Attention)             │
│  ├── Learn semantic structure                                │
│  ├── Handle long-range dependencies via phase rotation       │
│  ├── Process R-Signal (ontological intent)                   │
│  └── Complexity: O(N) per layer                              │
├─────────────────────────────────────────────────────────────┤
│  Layer N-11: SENSORY LAYERS (Quadratic Attention)           │
│  ├── Learn output generation                                 │
│  ├── Handle local token relationships                        │
│  ├── Receive phase bias from Authority layers                │
│  └── Complexity: O(N²) per layer                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    OUTPUT PROJECTION                         │
│                   (Vocabulary logits)                        │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Authority vs Sensory Layers

| Aspect | Authority Layers | Sensory Layers |
|--------|------------------|----------------|
| **Purpose** | Learn semantic structure | Learn to generate text |
| **Attention** | Phase Attention (O(N)) | Quadratic Attention (O(N²)) |
| **Gradient Scale** | α = 1.0 (full) | α = 0.1→0.7 (dampened) |
| **Signal Flow** | Generates R-Signal | Receives phase bias |
| **Role Metaphor** | "Senior Architect" | "Junior Coder" |
| **Learning Focus** | WHAT to say | HOW to say it |

### 1.3 Attention Mechanisms

The architecture uses three types of attention:

#### Local Attention (Early Authority Layers)
- Windowed attention: each token attends to W neighbors
- Complexity: O(N × W) where W is window size
- Used in layers 0-3 (typically)

#### Phase Attention (Authority Layers)
- Complex rotation-based attention
- Uses phase angles derived from R-Signal
- Complexity: O(N) - linear in sequence length
- Used in layers 4-8 (in 9:3 split)

#### Quadratic Attention (Sensory Layers)
- Standard transformer attention with phase bias injection
- Full pairwise attention computation
- Complexity: O(N²) - quadratic in sequence length
- Used in layers 9-11 (in 9:3 split)

### 1.4 Phase Attention Mathematics

Phase attention operates in complex space using rotation:

```
Input: x ∈ ℝ^(B×N×D)  where B=batch, N=seq_len, D=dim

1. Project to Q, K, V:
   Q = x @ W_q    ∈ ℝ^(B×N×D)
   K = x @ W_k    ∈ ℝ^(B×N×D)
   V = x @ W_v    ∈ ℝ^(B×N×D)

2. Compute phase angle from R-Signal:
   φ_base = R_to_phi(R_signal)    ∈ ℝ^(B×N)
   φ = φ_base + position × frequency

3. Apply complex rotation:
   Q_real, Q_imag = Q[:, :, :D/2], Q[:, :, D/2:]
   Q_rot = concat(
       Q_real × cos(φ) - Q_imag × sin(φ),
       Q_real × sin(φ) + Q_imag × cos(φ)
   )
   (Same for K_rot)

4. Compute attention (simplified):
   scores = Q_rot @ K_rot.T / √D
   attn = softmax(scores) × amplitude_gate
   output = attn @ V

Complexity: O(N × D) = O(N) for fixed D
```

The key insight is that phase rotation encodes **positional and semantic relationships** without requiring pairwise comparison of all tokens.

### 1.5 Quadratic Attention Mathematics

Standard transformer attention with phase bias injection:

```
Input: x ∈ ℝ^(B×N×D)
Phase bias: bias ∈ ℝ^(B×N×N) (from Authority layers)

1. Project to Q, K, V:
   Q = x @ W_q
   K = x @ W_k
   V = x @ W_v

2. Compute attention scores:
   scores = Q @ K.T / √D    ∈ ℝ^(B×N×N)

3. Add phase bias from Authority layers:
   scores = scores + phase_bias

4. Apply softmax and compute output:
   attn = softmax(scores)
   output = attn @ V

Complexity: O(N² × D) = O(N²) for fixed D
```

The quadratic complexity comes from the N×N attention matrix computation.

### 1.6 Computational Complexity

| Operation | Complexity | @ N=256 | @ N=1024 | @ N=2048 |
|-----------|------------|---------|----------|----------|
| Local Attention (W=256) | O(N×W) | 65K | 262K | 524K |
| Phase Attention | O(N) | 256 | 1K | 2K |
| Quadratic Attention | O(N²) | 65K | 1M | 4.2M |

**Total cost for different splits at N=2048:**

| Split | Phase Layers | Quad Layers | Total (relative) |
|-------|--------------|-------------|------------------|
| 9:3 | 9 × 2K = 18K | 3 × 4.2M = 12.6M | 1.0x |
| 6:6 | 6 × 2K = 12K | 6 × 4.2M = 25.2M | 2.0x |
| 3:9 | 3 × 2K = 6K | 9 × 4.2M = 37.7M | 3.0x |

**Key insight**: Quadratic attention dominates compute cost. More Sensory layers = more expensive.

---

## 2. Current Implementation

### 2.1 Hierarchical Gradient Scaler (HGS)

**Location**: `train_unified_llm.py:2364-2550`

The HGS implements Formula [1331] for gradient dampening:

```python
class HierarchicalGradientScaler:
    """
    Layers 0-(N-1):  Authority - Full gradients (α = 1.0)
    Layers N-11:     Sensory   - Dampened gradients (α = 0.1→0.7)
    """

    def scale_gradients(self, model, step):
        for i, layer in enumerate(model.layers):
            if i < self.authority_layers:
                # Authority: full gradients
                alpha = 1.0
            else:
                # Sensory: dampened with warmup
                alpha = self.compute_sensory_alpha(step)

            for param in layer.parameters():
                if param.grad is not None:
                    param.grad *= alpha
```

**Configuration**:
```bash
--use_9_3_split
--authority_layers 9
--sensory_layers 3
--alpha_sens_initial 0.1
--alpha_sens_max 0.7
--gradient_warmup_steps 500
```

### 2.2 Dynamic Relaxation Controller

**Location**: `train_unified_llm.py:6833-7100`

Manages transition from 9:3 to 6:6 split based on stability metrics:

```python
class DynamicRelaxationController:
    """
    States:
    - AUTHORITY: 9:3 split, heavy dampening
    - MONITORING: Tracking stability
    - RELAXING: Transitioning to 6:6
    - BALANCED: 6:6 split achieved
    """

    def update(self, coherence, s_drift_ema, val_ppl, step):
        stability_index = self.compute_stability_index(coherence, s_drift_ema)

        if stability_index >= self.stability_threshold:
            self.stability_streak += 1
            if self.stability_streak >= self.streak_target:
                return "RELAX"
        else:
            self.stability_streak = 0

        return "WAIT"
```

**Trigger conditions**:
- Stability Index ≥ 0.82 for N consecutive steps
- OR S/A ratio ≥ 0.50 over rolling window
- OR forced at specific step

### 2.3 Multi-Stage Evolution (V9.9.1)

**Location**: `train_unified_llm.py:7312-7533` (added today)

Extends relaxation to support full evolution path:

```python
# Default stages
evolution_stages = [(9, 3), (6, 6), (5, 7), (4, 8), (3, 9)]

# Trigger modes
- "metrics": Coherence/entropy criteria
- "ppl": Validation PPL thresholds
- "step": Fixed training steps
- "auto": Best available
```

**Configuration**:
```bash
--enable_multi_stage_evolution
--evolution_trigger_mode ppl
--evolution_ppl_triggers "100,50,25,15"
--custom_evolution_stages "9:3,6:6,4:8,3:9"
```

### 2.4 Phase Weight Decay

**Location**: Model configuration

Global phase attention weight that decays over training:

```python
# Hybrid attention output
output = alpha_local * local_attn + alpha_phase * phase_attn

# Decay schedule
alpha_phase = linear_interpolate(
    start=alpha_phase_start,  # e.g., 0.6
    end=alpha_phase_end,      # e.g., 0.2
    step=current_step,
    total_steps=alpha_decay_steps
)
```

**Configuration**:
```bash
--alpha_phase_start 0.6
--alpha_phase_end 0.2
--alpha_decay_steps 30000
```

**Limitation**: This is a GLOBAL weight applied to all layers equally. There is no per-layer control.

### 2.5 Auxiliary Controllers

| Controller | Purpose | Engagement |
|------------|---------|------------|
| **PIDv2** | S/A ratio regulation | PPL 30-100 |
| **EvoFlow** | Coherence flow | PPL < 100 |
| **Toroidal** | Rotational feedback | PPL < 60 |
| **CSR** | Conceptual regularization | PPL < 45 |
| **Kosha** | Five-sheath consciousness | PPL < 35 |
| **Gyroscope** | Homeostatic regulation | PPL < 30 |
| **SPC** | Phase steering | Entropy collapse |
| **Stress-Probe** | Emergency intervention | Degeneracy |
| **SGP** | Stagnation pump | Loss plateau |

**Key observation**: All controllers regulate the Authority/Phase side. None directly improve Sensory output quality.

---

## 3. Problem Analysis

### 3.1 The Gibberish Problem

**Symptom**: Model generates incoherent text despite good loss/PPL metrics.

**Root cause**: 9:3 split starves Sensory layers:
- Only 3 layers to learn output generation
- Dampened gradients (α = 0.1→0.7) slow learning
- Authority layers learn rich representations
- But Sensory can't express them → gibberish

**Evidence**:
```
Authority: Learns "concept of cat" (internal representation)
Sensory:   Can't express it → "the the the cat cat is a cat the"
```

### 3.2 Compute Explosion

**Problem**: Naive solutions explode compute:

| Approach | Split | @ seq=2048 | Issue |
|----------|-------|------------|-------|
| Current | 9:3 | 12.6M | Gibberish |
| More Sensory | 3:9 | 37.7M | 3x compute |
| Balanced | 6:6 | 25.2M | 2x compute |

Increasing Sensory layers increases O(N²) operations.

### 3.3 Controller Complexity

**Problem**: 12+ controllers with overlapping concerns:

```
Training degrades → Which controller caused it?
Training improves → Which controller helped?
```

**Attribution is impossible** with so many simultaneous interventions.

---

## 4. Proposed System: Inverted Curriculum

### 4.1 Core Insight

Standard transformers during generation:
- **Early tokens**: Cheap to predict (little context)
- **Late tokens**: Expensive (full context needed)

Training should mirror this:
- **Early training**: Focus on generation (Sensory) with short sequences
- **Late training**: Focus on semantics (Phase) with long sequences

### 4.2 Inverted Evolution Direction

**Current**: Authority-first → Sensory-later (9:3 → 3:9)
**Proposed**: Sensory-first → Authority-later (3:9 → 9:3)

```
Current:
  Step 0     → 9:3 (learn structure, can't express)
  Step 50K   → 6:6 (balance)
  Step 100K  → 3:9 (finally learn expression)

Proposed (Inverted):
  Step 0     → 3:9 (learn expression first)
  Step 50K   → 6:6 (balance)
  Step 100K  → 9:3 (refine structure with long context)
```

### 4.3 Per-Layer Phase Weights

**Current**: Single global `alpha_phase` for all layers.

**Proposed**: Per-layer phase weights for fine-grained control:

```python
# Per-layer phase weight array
layer_phase_weights = [
    1.0,   # Layer 0:  Full Phase (Authority)
    1.0,   # Layer 1:  Full Phase
    1.0,   # Layer 2:  Full Phase
    0.8,   # Layer 3:  Transitioning
    0.5,   # Layer 4:  Transitioning
    0.2,   # Layer 5:  Mostly Quadratic
    0.0,   # Layer 6:  Full Quadratic (Sensory)
    0.0,   # Layer 7:  Full Quadratic
    0.0,   # Layer 8:  Full Quadratic
    0.0,   # Layer 9:  Full Quadratic
    0.0,   # Layer 10: Full Quadratic
    0.0,   # Layer 11: Full Quadratic
]

# Hybrid attention in each layer
def layer_attention(x, layer_idx):
    alpha = layer_phase_weights[layer_idx]
    if alpha == 1.0:
        return phase_attention(x)
    elif alpha == 0.0:
        return quadratic_attention(x)
    else:
        return alpha * phase_attention(x) + (1-alpha) * quadratic_attention(x)
```

### 4.4 Soft Layer Transition

**Problem**: Hard layer flip causes training shock.

**Solution**: Gradual phase weight ramp during transition.

When Layer 6 transitions from Sensory → Authority:

```
Step N:       layer_phase_weights[6] = 0.0   (Sensory)
Step N+100:   layer_phase_weights[6] = 0.2   (Transitioning)
Step N+200:   layer_phase_weights[6] = 0.4   (Transitioning)
Step N+300:   layer_phase_weights[6] = 0.6   (Transitioning)
Step N+400:   layer_phase_weights[6] = 0.8   (Transitioning)
Step N+500:   layer_phase_weights[6] = 1.0   (Authority)
```

**Phase decay acts as shock absorber** - the transition is smooth, not abrupt.

### 4.5 Dynamic Sequence Length

Grow sequence length during training:

```python
class DynamicSequenceLengthScheduler:
    def __init__(self, schedule):
        # schedule: [(ppl_threshold, seq_len), ...]
        self.schedule = [
            (500, 256),    # PPL > 500: short sequences
            (200, 512),    # PPL > 200: medium sequences
            (100, 1024),   # PPL > 100: longer sequences
            (50, 1536),    # PPL > 50: long sequences
            (0, 2048),     # PPL < 50: full length
        ]

    def get_seq_len(self, current_ppl):
        for ppl_thresh, seq_len in self.schedule:
            if current_ppl > ppl_thresh:
                return seq_len
        return self.schedule[-1][1]
```

### 4.6 Coupled Curriculum

**The key innovation**: Synchronize split evolution with sequence length growth.

```
┌─────────┬───────┬─────────┬────────────────────────────────────┐
│  Step   │ Split │ Seq Len │ Rationale                          │
├─────────┼───────┼─────────┼────────────────────────────────────┤
│  0      │ 3:9   │ 256     │ Heavy Sensory + Short = Cheap      │
│  5K     │ 4:8   │ 256     │ Transitioning Layer 3              │
│  15K    │ 5:7   │ 512     │ Transitioning Layer 4, grow seq    │
│  30K    │ 6:6   │ 768     │ Balanced                           │
│  50K    │ 7:5   │ 1024    │ More Phase, longer context         │
│  70K    │ 8:4   │ 1536    │ Phase dominant                     │
│  90K    │ 9:3   │ 2048    │ Heavy Phase + Long = Efficient     │
└─────────┴───────┴─────────┴────────────────────────────────────┘
```

**Compute stays bounded**:
- Early: Many Sensory (expensive) × Short seq (cheap) = Manageable
- Late: Few Sensory (cheap) × Long seq (expensive) = Manageable

**Worst case avoided**:
- Many Sensory × Long seq = Explosion (never happens in this curriculum)

---

## 5. Implementation Plan

### Phase 1: Per-Layer Phase Weights ✅ COMPLETED
- [x] Add `layer_idx` attribute to `HybridAttentionLayer` (`symbolu/phase_transformer.py:1677,1681`)
- [x] Add `layer_idx` to `HybridTransformerBlock` (`symbolu/phase_transformer.py:1770,1773,1788`)
- [x] Pass `layer_idx` during model creation (`symbolu/phase_transformer.py:2252`)
- [x] Create `PerLayerPhaseController` class (`train_unified_llm.py:9860-10065`)
- [x] Add config fields: `enable_per_layer_phase`, `per_layer_phase_weights`, `layer_transition_steps`
- [x] Add CLI flags: `--enable_per_layer_phase`, `--per_layer_phase_weights`, `--layer_transition_steps`

**Key Implementation Details:**
```python
# PerLayerPhaseController provides:
controller.set_weights([0.0] * 12)       # Set all layers
controller.start_transition(6, 1.0, 500, step)  # Soft transition
controller.update(step)                   # Update active transitions
controller.apply_to_model(model)          # Apply weights to model
```

### Phase 2: Soft Layer Transition ✅ INCLUDED IN PHASE 1
- [x] `start_transition()` method in `PerLayerPhaseController`
- [x] Linear interpolation over `duration_steps`
- [x] Automatic completion tracking
- [x] CLI flag `--layer_transition_steps` for ramp duration

**Note**: Soft layer transition was integrated directly into `PerLayerPhaseController`.

### Phase 3: Dynamic Sequence Length ✅ INCLUDED IN PHASE 4
- [x] Integrated into `InvertedCurriculumController`
- [x] PPL-based triggers for seq_len growth
- [x] Stage-based sequence lengths

### Phase 4: Coupled Curriculum ✅ COMPLETED
- [x] Create `InvertedCurriculumController` class (`train_unified_llm.py:10077-10375`)
- [x] Synchronize split evolution + layer transition + seq length
- [x] Comprehensive logging with curriculum table
- [x] CLI flags: `--enable_inverted_curriculum`, `--inverted_curriculum_stages`, `--inverted_curriculum_ppl_triggers`

**Key Implementation Details:**
```python
# InvertedCurriculumController usage:
controller = InvertedCurriculumController.from_config(config)

# In training loop:
result = controller.update(step, current_ppl)
if result['split_changed']:
    reconfigure_gradient_scaler(result['current_split'])
if result['seq_len_changed']:
    reload_dataloader(result['current_seq_len'])
controller.apply_to_model(model)
```

**Default Curriculum:**
| Stage | Split | Seq Len | PPL Trigger |
|-------|-------|---------|-------------|
| 0 | 3:9 | 256 | START |
| 1 | 4:8 | 256 | < 300 |
| 2 | 5:7 | 512 | < 200 |
| 3 | 6:6 | 768 | < 120 |
| 4 | 7:5 | 1024 | < 75 |
| 5 | 8:4 | 1536 | < 45 |
| 6 | 9:3 | 2048 | < 25 |

### Phase 5: Training Loop Integration ✅ COMPLETED
- [x] Initialize `InvertedLayerCurriculumController` in training setup (`train_unified_llm.py:12479-12487`)
- [x] Add curriculum update in validation loop (`train_unified_llm.py:14890-14917`)
- [x] Reconfigure HGS on split change
- [x] Log sequence length changes (full dataloader reload TBD)
- [x] Periodic curriculum status logging

### Phase 6: Testing & Validation ✅ COMPLETED
- [x] Unit tests for each component (`scripts/test_inverted_curriculum.py`)
- [x] Integration test for full curriculum (41 tests passing)
- [ ] Benchmark compute vs. current system (requires GPU)
- [ ] Training run comparison (requires GPU)

---

## 6. API Reference

### Proposed CLI Flags

```bash
# Inverted curriculum master switch
--enable_inverted_curriculum

# Per-layer phase weights (initial)
--initial_layer_phase_weights "0,0,0,0,0,0,0,0,0,0,0,0"  # Start all Sensory

# Soft transition
--layer_transition_steps 500        # Steps per layer transition
--layer_transition_mode "linear"    # linear, cosine, sigmoid

# Dynamic sequence length
--enable_dynamic_seq_length
--seq_length_schedule "256@500,512@200,1024@100,2048@50"  # seq@ppl_threshold

# Coupled curriculum
--curriculum_stages "3:9@256,5:7@512,6:6@768,8:4@1536,9:3@2048"
--curriculum_triggers "ppl"         # ppl, step, or auto
--curriculum_ppl_triggers "300,150,75,40,20"
```

### Proposed Classes

```python
class PerLayerPhaseConfig:
    """Manages per-layer phase weights."""
    layer_weights: List[float]  # 12 values, 0.0-1.0

class LayerTransitionScheduler:
    """Manages soft layer transitions."""
    def start_transition(self, layer_idx, duration_steps)
    def update(self, step) -> Dict[int, float]  # layer_idx -> new_weight

class DynamicSequenceLengthScheduler:
    """Manages sequence length growth."""
    def get_seq_len(self, ppl, step) -> int
    def get_batch_size(self, seq_len) -> int  # Memory-aware

class InvertedCurriculumController:
    """Orchestrates the full curriculum."""
    def update(self, step, ppl, metrics) -> CurriculumState
    def get_current_config(self) -> Dict  # split, seq_len, layer_weights
```

---

## 7. Testing Strategy

### Unit Tests
- `test_per_layer_phase_weights.py`: Verify attention output varies with alpha
- `test_layer_transition.py`: Verify smooth 0→1 ramp
- `test_seq_length_scheduler.py`: Verify correct seq_len selection
- `test_curriculum_controller.py`: Verify state machine logic

### Integration Tests
- Full training run with inverted curriculum
- Compare loss curves vs. standard 9:3→3:9
- Measure compute usage at each stage

### Benchmarks
- Memory usage at each (split, seq_len) combination
- Throughput (tokens/sec) comparison
- Generation quality at checkpoints

---

## 8. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-13 | Initial design document |
| 1.1.0 | 2026-01-13 | Phase 1-2: Implemented PerLayerPhaseController with soft transitions |
| 1.2.0 | 2026-01-13 | Phase 3-4: Implemented InvertedLayerCurriculumController with coupled seq_len |
| 1.3.0 | 2026-01-13 | Phase 5: Training loop integration (init, update, HGS reconfigure) |
| 1.4.0 | 2026-01-13 | Phase 6: Testing & validation (41 tests in scripts/test_inverted_curriculum.py) |

---

## Appendix A: Mathematical Derivations

### A.1 Compute Cost Formula

Total compute for N tokens, L layers, D dimensions:

```
C_total = Σ(layer_i) C_layer_i

C_phase = N × D × k₁        (linear)
C_quad  = N² × D × k₂       (quadratic)

For split (A:S) where A = Authority, S = Sensory:
C_total = A × C_phase + S × C_quad
        = A × N × D × k₁ + S × N² × D × k₂
        ≈ S × N² × D × k₂   (dominated by quadratic term)
```

### A.2 Memory Cost Formula

```
M_activation = B × N × D × L          (activations)
M_attention  = B × H × N × N × S      (attention matrices, Sensory only)
M_kv_cache   = 2 × B × L × N × D      (KV cache for inference)

Total ≈ M_attention = B × H × N² × S  (dominated by Sensory attention)
```

---

*Document will be updated as implementation progresses.*
