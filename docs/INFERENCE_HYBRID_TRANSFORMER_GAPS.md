# Inference vs Training Gaps: Hybrid Transformer Logic

**Document Version:** 2.0
**Date:** January 2026
**Status:** ✅ IMPLEMENTED (Phases 1-3 Complete)
**Related File:** `train_unified_llm.py` (V9.5.2)
**Implementation:** `symbolu/inference/` module

---

## Executive Summary

This document catalogs the gaps between training-time logic in `train_unified_llm.py` and inference-time behavior. **All priority 1 and 2 gaps have been addressed** with the implementation of the `symbolu.inference` module.

### Implementation Summary

| Phase | Status | Components |
|-------|--------|------------|
| Phase 1 (Critical) | ✅ Complete | `EvolutionaryInferenceEngine`, `extract_layers` parameter |
| Phase 2 (Important) | ✅ Complete | `InferenceMetacognition`, `InferenceGunas`, `CSRInferenceGuard`, `SovereignInferenceScorer` |
| Phase 3 (Orchestration) | ✅ Complete | `InferenceManager` with Fast/Standard/Sovereign modes |

### Quick Start

```python
from symbolu.inference import InferenceManager, InferenceMode

# Create manager with desired mode
manager = InferenceManager(model, mode=InferenceMode.SOVEREIGN)

# Generate with full pipeline
output, metrics = manager.generate(
    input_ids,
    max_new_tokens=100,
    compute_alignment=True,
)

# Check quality metrics
print(f"Mode: {metrics['mode']}")
print(f"Sovereign alignment: {metrics['sovereign_score']:.3f}")
print(f"Karma stored: {metrics['karma_stored']}")
print(f"Interventions: {metrics['interventions']}")
```

---

## Table of Contents

1. [Critical Gaps (Priority 1)](#1-critical-gaps-priority-1) - ✅ IMPLEMENTED
2. [Important Gaps (Priority 2)](#2-important-gaps-priority-2) - ✅ IMPLEMENTED
3. [Enhancement Gaps (Priority 3)](#3-enhancement-gaps-priority-3)
4. [Implementation Roadmap](#4-implementation-roadmap) - ✅ COMPLETE
5. [Architecture Considerations](#5-architecture-considerations)
6. [Usage Guide](#6-usage-guide) - NEW

---

## 1. Critical Gaps (Priority 1)

### 1.1 Evolutionary Bridge (O12→O1 Karma Transfer) ✅ IMPLEMENTED

**Training Behavior:**
The `EvolutionaryBridge` class (`train_unified_llm.py:373-538`) implements toroidal state persistence where the final hidden state from O12 (Absolving layer) is projected and stored as a "karma buffer" to seed O1 (Potential layer) in the next sequence.

```python
# Training: Karma buffer enables cross-sequence intelligence
evolutionary_bridge.store_harvest(harvest=o12_hidden, global_step=step)
seed = evolutionary_bridge.retrieve_seed()  # For next sequence
```

**✅ Implementation:**

Located in `symbolu/inference/evolutionary_inference.py`:

- **`EvolutionaryBridgeInference`**: Lightweight inference-time bridge for O12→O1 projection
  - Gated seed projection (matching training behavior)
  - Loads weights from training checkpoint
  - LayerNorm for seed stabilization

- **`EvolutionaryInferenceEngine`**: Main engine for karma persistence
  - `generate_with_karma()`: Autoregressive generation with karma injection/storage
  - `apply_inference_resonance()`: Delayed resonance injection with dynamic alpha
  - `compute_generation_coherence()`: Track toroidal coherence
  - `load_bridge_checkpoint()`: Load trained bridge weights

**Usage:**
```python
from symbolu.inference import EvolutionaryInferenceEngine

engine = EvolutionaryInferenceEngine(model, resonance_alpha=0.1)
engine.load_bridge_checkpoint("checkpoint.pt")

# First generation - stores karma
output1, metrics1 = engine.generate_with_karma(input_ids_1, store_karma=True)

# Second generation - injects previous karma
output2, metrics2 = engine.generate_with_karma(input_ids_2, inject_karma=True)
print(f"Karma coherence: {metrics2['karma_coherence']:.3f}")
```

**Files Created/Modified:**
- ✅ Created: `symbolu/inference/evolutionary_inference.py`
- ✅ Modified: `symbolu/phase_transformer.py` - Added `extract_layers` and `return_last_hidden` parameters

---

### 1.2 Delayed Resonance Injection ✅ IMPLEMENTED

**Training Behavior:**
The `EvolutionaryIntelligenceEngine.apply_delayed_resonance()` method (`train_unified_llm.py:1513-1558`) injects previous step's O12 state into current O1 with Guna-scaled alpha:

```python
# Training: Dynamic alpha based on Sattva/Rajas/Tamas
dynamic_alpha = self.resonance_alpha * (1.0 + (s * 1.5) - (r * 0.5))
current_states[0] = o1_current + (dynamic_alpha * o12_prev)
```

**✅ Implementation:**

Located in `symbolu/inference/evolutionary_inference.py`:

- **`apply_inference_resonance()`**: Injects karma into current hidden state
- **`_compute_dynamic_alpha()`**: Computes Guna-scaled alpha (matching training formula)
- **Integration with `InferenceGunas`**: Dynamic alpha scaling based on generation state

**Key Features:**
- Dynamic alpha range: [0.05, 0.25] based on Guna state
- High Sattva → increase retention (trust karma more)
- High Rajas → decrease retention (focus on current)
- Automatic karma expansion to match sequence dimensions

**Usage:**
```python
from symbolu.inference import EvolutionaryInferenceEngine, InferenceGunas

engine = EvolutionaryInferenceEngine(model)
gunas = InferenceGunas()

# Generate with dynamic alpha from Guna state
output, metrics = engine.generate_with_karma(
    input_ids,
    guna_tracker=gunas,  # Feeds Guna state for dynamic alpha
)
```

---

### 1.3 Hidden State Extraction for Ontological Models ✅ IMPLEMENTED

**Training Behavior:**
The `HiddenStateExtractor` class (`train_unified_llm.py:1291-1427`) uses forward hooks to capture hidden states from all 12 layers, enabling:
- Evolutionary flow processing
- CSR safety layer integration
- Coherence loss computation

**✅ Implementation:**

Modified `symbolu/phase_transformer.py` - All transformer variants now support:

- **`extract_layers: List[int]`**: Memory-efficient extraction of specific layers only
- **`return_last_hidden: bool`**: Returns final hidden state before lm_head (for CSR re-projection)

**Transformer Variants Updated:**
- `HybridPhaseTransformer`
- `LocalOnlyTransformer`
- `PhaseTransformer`
- `StandardTransformer`

**Key Features:**
- Only allocates memory for requested layers
- Layer indices map correctly to output list (sorted order)
- Backward compatible with `return_hidden=True` (returns all layers)

**Usage:**
```python
# Efficient extraction of O1 and O12 only
outputs = model(input_ids, extract_layers=[0, 11])

# hidden_states is a list with 2 elements:
# hidden_states[0] = layer 0 (O1)
# hidden_states[1] = layer 11 (O12)
layer_states = outputs['hidden_states']

# For CSR re-projection, get last hidden before lm_head
outputs = model(input_ids, return_last_hidden=True)
last_hidden = outputs['last_hidden_state']  # [B, N, D]
```

**Files Modified:**
- ✅ `symbolu/phase_transformer.py` - Added `extract_layers` and `return_last_hidden` to all variants
- ✅ `symbolu/inference/evolutionary_inference.py` - `_extract_layer_states()` uses efficient extraction

---

## 2. Important Gaps (Priority 2)

### 2.1 Metacognitive Tracking ✅ IMPLEMENTED

**Training Behavior:**
The `MetacognitiveTracker` class (`train_unified_llm.py:666-825`) monitors:
- Coherence history and alarms
- Guna state (Sattva/Rajas/Tamas)
- Evolutionary velocity
- Generates recommendations: BRAKE, SLOW_DOWN, RECOVER, ACCELERATE, STABILIZE, CONTINUE

**✅ Implementation:**

Located in `symbolu/inference/metacognitive_monitor.py`:

- **`InferenceMetacognition`**: Real-time generation quality monitoring
- **`Recommendation` enum**: ABORT, BRAKE, SLOW_DOWN, RECOVER, ACCELERATE, STABILIZE, CONTINUE

**Key Features:**
- Token-level entropy monitoring as confidence proxy
- Coherence trend detection with configurable window
- Consecutive low-coherence detection for ABORT
- Guna integration for informed recommendations
- Automatic temperature adjustment suggestions

**Recommendation Hierarchy:**
1. **ABORT**: Consecutive low coherence (default: 5 tokens below threshold)
2. **BRAKE**: Rapid degradation detected (coherence drop > 0.15 in 3 tokens)
3. **SLOW_DOWN**: Coherence alarm active
4. **RECOVER**: High Tamas (stagnation) with flat coherence
5. **ACCELERATE**: High Sattva + improving trend
6. **STABILIZE**: Declining trend, maintain course
7. **CONTINUE**: Default state

**Usage:**
```python
from symbolu.inference import InferenceMetacognition, Recommendation

monitor = InferenceMetacognition(alarm_threshold=0.3, abort_consecutive=5)

for token_logits in generation:
    status = monitor.update(token_logits)

    if status['recommendation'] == 'ABORT':
        break  # Stop generation

    if status['recommendation'] == 'BRAKE':
        temperature *= 0.7  # Reduce randomness

    print(f"Coherence: {status['coherence']:.2f}, Alarm: {status['alarm']}")
```

---

### 2.2 Training Gunas (Sattva/Rajas/Tamas) ✅ IMPLEMENTED

**Training Behavior:**
The `TrainingGunas` class (`train_unified_llm.py:3440-3539`) computes cognitive state from training dynamics:
- **Sattva (Clarity):** coherence × (1 - entropy)
- **Rajas (Action):** normalized gradient activity
- **Tamas (Inertia):** loss velocity stagnation

**✅ Implementation:**

Located in `symbolu/inference/guna_inference.py`:

- **`InferenceGunas`**: Approximates Guna state from generation dynamics

**Guna Mappings (Inference Approximation):**
- **Sattva (Clarity):** Token probability confidence × (1 - entropy)
- **Rajas (Action):** Token-to-token probability variance
- **Tamas (Inertia):** N-gram repetition rate (bigram weighted)

**Key Features:**
- Configurable window size for trend tracking
- `get_dynamic_alpha_multiplier()`: Computes alpha scaling for resonance
- `get_temperature_adjustment()`: Suggests temperature changes
- `is_repetition_detected()`: Quick check for stuck loops

**Usage:**
```python
from symbolu.inference import InferenceGunas

gunas = InferenceGunas(window_size=20)

for token_id, token_prob in generated_tokens:
    s, r, t = gunas.update(token_id, token_prob)

    # Get dynamic alpha for resonance injection
    alpha = gunas.get_dynamic_alpha_multiplier(base_alpha=0.1)

    # Detect repetition loops
    if gunas.is_repetition_detected(threshold=0.6):
        temperature *= 1.2  # Break the loop

    # Get detailed state
    state = gunas.get_detailed_state()
    print(f"Dominant: {state['dominant']}, Alpha: {state['alpha_multiplier']:.2f}")
```

---

### 2.3 CSR Safety Layers (EntropySink, SynthesisGate) ✅ IMPLEMENTED

**Training Behavior:**
When enabled, CSR phoneme-ontological grounding applies:
- `EntropySink`: Absorbs high-entropy states to prevent divergence
- `SynthesisGate`: Controls information flow based on coherence

```python
# Training integration (train_unified_llm.py:6748-6767)
csr_provider, csr_entropy_sink, csr_synthesis_gate = create_csr_for_training(...)
```

**✅ Implementation:**

Located in `symbolu/inference/csr_inference.py`:

- **`EntropySinkInference`**: Lightweight entropy absorption layer
- **`SynthesisGateInference`**: Information flow control based on coherence
- **`CSRInferenceGuard`**: Main guard that orchestrates CSR layers

**Critical Feature - lm_head Re-projection:**
The guard properly re-projects modified hidden states through lm_head to ensure CSR modifications affect token selection:

```python
# When hidden state is modified by CSR layers
if state_modified and self.lm_head is not None:
    modified_logits = self.lm_head(current_hidden)  # Re-project!
```

**Key Features:**
- Entropy threshold detection with configurable skip threshold
- Intervention counting and statistics
- Per-step or batch application modes
- Loads trained CSR weights from checkpoint

**Usage:**
```python
from symbolu.inference import CSRInferenceGuard

guard = CSRInferenceGuard(
    lm_head=model.lm_head,
    dim=768,
    entropy_threshold=2.0,
    skip_threshold=0.9,  # Skip if confidence > 0.9
)

# Apply to generation step
logits, guard_info = guard.apply(
    hidden_state=last_hidden,
    original_logits=logits,
)

if guard_info['intervention']:
    print(f"CSR intervened! Entropy: {guard_info['entropy']:.2f}")
    print(f"Re-projected: {guard_info['re_projected']}")
```

---

### 2.4 Sovereign-1 Loss Components at Inference ✅ IMPLEMENTED

**Training Behavior:**
Sovereign-1 loss (`train_unified_llm.py:6690-6703`) provides:
- Guna signal weighting
- S-Signal (referent) tracking
- R-Signal (ontology) enforcement
- C-Signal (phoneme) grounding

**✅ Implementation:**

Located in `symbolu/inference/sovereign_scorer.py`:

- **`SovereignInferenceScorer`**: Computes alignment scores for generated sequences
- **`SOVEREIGN_R_MATRIX`**: 5 Vṛttis × 12 Layers target distribution
- **`VRTTI_NAMES`**: Pramāṇa, Vikalpa, Viparyaya, Nidrā, Smṛti

**Key Features:**
- Vṛtti projection layer (learned hidden→Vṛtti mapping)
- Per-layer R-Matrix alignment scoring
- 9:3 Authority/Sensory split awareness
- Composite sovereign score (0-1 range)

**R-Matrix Structure:**
```python
SOVEREIGN_R_MATRIX = torch.tensor([
    [0.1, 0.5, 0.7, 0.7, 0.8, 0.6, 0.9, 0.8, 0.6, 0.7, 0.5, 0.9],  # Pramāṇa (valid knowledge)
    [0.1, 0.2, 0.2, 0.4, 0.4, 0.4, 0.1, 0.1, 0.2, 0.2, 0.2, 0.3],  # Vikalpa (conceptualization)
    [0.1, 0.2, 0.4, 0.4, 0.2, 0.3, 0.1, 0.1, 0.1, 0.1, 0.1, 0.0],  # Viparyaya (error)
    [0.7, 0.1, 0.1, 0.3, 0.1, 0.1, 0.0, 0.0, 0.3, 0.3, 0.4, 0.1],  # Nidrā (latency)
    [0.1, 0.1, 0.3, 0.3, 0.2, 0.2, 0.1, 0.0, 0.2, 0.2, 0.2, 0.8],  # Smṛti (memory)
])
```

**Usage:**
```python
from symbolu.inference import SovereignInferenceScorer

scorer = SovereignInferenceScorer(dim=768)

# Score a generation using layer hidden states
layer_states = {0: h0, 5: h5, 11: h11}  # Dict[layer_idx, tensor]
score, info = scorer.score_generation(layer_states)

print(f"Sovereign alignment: {score:.3f}")
print(f"Authority alignment: {info['authority_alignment']:.3f}")
print(f"Sensory alignment: {info['sensory_alignment']:.3f}")
print(f"Per-layer scores: {info['layer_scores']}")
```

---

## 3. Enhancement Gaps (Priority 3)

### 3.1 9:3 Hierarchical Split Awareness

**Training Behavior:**
`HierarchicalGradientScaler` (`train_unified_llm.py`) applies different gradient scales to:
- Authority layers (0-8): Full gradients
- Sensory layers (9-11): Dampened gradients (α_sens)

**Inference Gap:**
While inference doesn't use gradients, the 9:3 split concept could inform:
- Which layers to cache for KV-cache optimization
- Layer-specific attention temperature adjustments
- Interpretability of layer contributions

**Implementation Recommendation:**

```python
# Priority: LOW
# Effort: Low (0.5 days)
# Location: symbolu/inference/layer_config.py

class LayerInferenceConfig:
    """
    Configuration for layer-specific inference behavior.

    Reflects 9:3 Authority/Sensory split from training.
    """

    # Authority layers: More important for "meaning"
    AUTHORITY_LAYERS = list(range(9))  # O1-O9

    # Sensory layers: More important for "expression"
    SENSORY_LAYERS = list(range(9, 12))  # O10-O12

    @classmethod
    def get_cache_priority(cls, layer_idx: int) -> str:
        """
        Get caching priority for layer (for memory optimization).

        Authority layers: HIGH priority (cache aggressively)
        Sensory layers: MEDIUM priority (can recompute if needed)
        """
        if layer_idx in cls.AUTHORITY_LAYERS:
            return "HIGH"
        return "MEDIUM"

    @classmethod
    def get_temperature_adjustment(cls, layer_idx: int, base_temp: float) -> float:
        """
        Adjust attention temperature per layer type.

        Sensory layers may benefit from sharper attention (lower temp)
        for more precise token selection.
        """
        if layer_idx in cls.SENSORY_LAYERS:
            return base_temp * 0.9  # Slightly sharper for sensory
        return base_temp
```

---

### 3.2 Toroidal Coherence Metrics

**Training Behavior:**
`ToroidalConsistencyLoss` computes coherence between:
- Seed (previous O12) and Harvest (current O12)
- Optional 3-way consistency with current O1

**Inference Gap:**
No coherence tracking across generation sequences.

**Implementation Recommendation:**

```python
# Priority: LOW
# Effort: Low (0.5 days)
# Location: Add to EvolutionaryInferenceEngine

def compute_generation_coherence(self) -> float:
    """
    Compute coherence between stored karma and current generation.

    Useful for:
    - Detecting topic drift in long conversations
    - Measuring "memory retention" quality
    """
    if self.karma_buffer is None or self.current_o12 is None:
        return 0.0

    # Cosine similarity between karma and current O12
    sim = F.cosine_similarity(
        self.karma_buffer.view(1, -1),
        self.current_o12.mean(dim=1).view(1, -1),
    )
    return (sim.item() + 1) / 2  # Map to [0, 1]
```

---

### 3.3 Dynamic Relaxation State Persistence

**Training Behavior:**
`DynamicRelaxationController` manages state transitions:
- STATE_AUTHORITY (9:3) → STATE_BALANCED (6:6) → Evolution stages

**Inference Gap:**
Model inference doesn't know which training state the model was in when saved.

**Implementation Recommendation:**

```python
# Priority: LOW
# Effort: Low (0.5 days)
# Location: Checkpoint metadata

# When saving checkpoint, include DRC state:
checkpoint = {
    "model": model.state_dict(),
    "drc_state": relaxation_controller.get_state(),  # Already saved
    # Add inference-relevant fields:
    "inference_config": {
        "authority_sensory_split": (9, 3) if drc.state == "authority" else (6, 6),
        "evolution_stage": drc.current_stage_idx,
        "recommended_resonance_alpha": 0.1 if drc.state == "authority" else 0.15,
    }
}

# At inference, load and apply:
inference_config = checkpoint.get("inference_config", {})
resonance_alpha = inference_config.get("recommended_resonance_alpha", 0.1)
```

---

## 4. Implementation Roadmap ✅ COMPLETE

### Phase 1: Core Inference Infrastructure ✅

| Task | Status | Files |
|------|--------|-------|
| Create `EvolutionaryInferenceEngine` | ✅ Done | `symbolu/inference/evolutionary_inference.py` |
| Add hidden state extraction to models | ✅ Done | `symbolu/phase_transformer.py` |
| Implement delayed resonance injection | ✅ Done | `symbolu/inference/evolutionary_inference.py` |

**Deliverables:**
- ✅ `symbolu/inference/evolutionary_inference.py`
- ✅ Modified `HybridPhaseTransformer.forward()` with `extract_layers` parameter
- ✅ Unit tests: `tests/test_evolutionary_inference.py`

### Phase 2: Quality Monitoring ✅

| Task | Status | Files |
|------|--------|-------|
| Create `InferenceMetacognition` | ✅ Done | `symbolu/inference/metacognitive_monitor.py` |
| Implement `InferenceGunas` | ✅ Done | `symbolu/inference/guna_inference.py` |
| Add CSR safety guard | ✅ Done | `symbolu/inference/csr_inference.py` |
| Sovereign inference scorer | ✅ Done | `symbolu/inference/sovereign_scorer.py` |

**Deliverables:**
- ✅ `symbolu/inference/metacognitive_monitor.py`
- ✅ `symbolu/inference/guna_inference.py`
- ✅ `symbolu/inference/csr_inference.py`
- ✅ `symbolu/inference/sovereign_scorer.py`
- ✅ Integration tests: `tests/test_inference_integration.py`

### Phase 3: Orchestration ✅

| Task | Status | Files |
|------|--------|-------|
| Create `InferenceManager` | ✅ Done | `symbolu/inference/manager.py` |
| Fast/Standard/Sovereign modes | ✅ Done | `symbolu/inference/manager.py` |
| Unified generate() interface | ✅ Done | `symbolu/inference/manager.py` |

**Deliverables:**
- ✅ `symbolu/inference/manager.py`
- ✅ Unit tests: `tests/test_inference_manager.py`

### Remaining (Priority 3 - Enhancement):

| Task | Status | Notes |
|------|--------|-------|
| Layer configuration | 📋 Optional | Low priority, can be added as needed |
| Checkpoint metadata enhancement | 📋 Optional | Low priority |

---

## 5. Architecture Considerations

### 5.1 Memory Overhead

Enabling full inference features will increase memory usage:

| Feature | Additional Memory | Mitigation |
|---------|-------------------|------------|
| Karma buffer | ~2-4 MB per conversation | Clear on context reset |
| Hidden state extraction | ~50-100 MB per sequence | Extract only O1, O12 |
| Metacognitive history | ~1 MB | Rolling window (50 tokens) |
| CSR layers | ~10-20 MB | Load on-demand |

**Recommendation:** Create tiered inference modes:
- **Fast Mode:** No extra features, minimal memory
- **Standard Mode:** Karma + basic metacognition
- **Full Mode:** All features enabled

### 5.2 Latency Impact

| Feature | Latency Impact | Mitigation |
|---------|----------------|------------|
| Karma injection | +1-2ms per sequence | Batch with embedding |
| Hidden state extraction | +5-10ms per forward | Extract async |
| CSR safety check | +2-5ms per token | Skip if confidence > 0.9 |
| Metacognitive update | +0.5ms per token | Minimal overhead |

**Recommendation:** Make all features optional with sensible defaults.

### 5.3 Backward Compatibility

All new inference features should be:
1. **Opt-in:** Disabled by default for existing code
2. **Graceful degradation:** Work without trained components
3. **Version-aware:** Check checkpoint version for feature availability

```python
# Example: Graceful loading of evolutionary bridge
def load_inference_engine(checkpoint_path: str) -> 'EvolutionaryInferenceEngine':
    checkpoint = torch.load(checkpoint_path)

    engine = EvolutionaryInferenceEngine(model=load_model(checkpoint))

    # Try to load evolutionary bridge if available
    if "evolutionary_bridge" in checkpoint:
        engine.bridge.load_state_dict(checkpoint["evolutionary_bridge"])
        engine.bridge_enabled = True
    else:
        logger.warning("Checkpoint does not contain evolutionary bridge - karma disabled")
        engine.bridge_enabled = False

    return engine
```

---

## Appendix A: Component Location Reference

| Component | Training Location | Proposed Inference Location |
|-----------|-------------------|----------------------------|
| EvolutionaryBridge | `train_unified_llm.py:373-538` | `symbolu/inference/evolutionary_inference.py` |
| MetacognitiveTracker | `train_unified_llm.py:666-825` | `symbolu/inference/metacognitive_monitor.py` |
| TrainingGunas | `train_unified_llm.py:3440-3539` | `symbolu/inference/guna_inference.py` |
| HiddenStateExtractor | `train_unified_llm.py:1291-1427` | `symbolu/inference/state_extractor.py` |
| CSR Safety Layers | `csr_phoneme_provider.py` | `symbolu/inference/csr_inference.py` |
| Sovereign Loss | `symbolu/sovereign/loss.py` | `symbolu/inference/sovereign_scorer.py` |

---

## Appendix B: Testing Strategy

### Unit Tests
- Karma persistence across sequences
- Resonance injection correctness
- Metacognitive state updates
- Guna computation accuracy

### Integration Tests
- Full generation with evolutionary engine
- CSR safety layer intervention
- Multi-turn conversation coherence

### Benchmark Tests
- Memory usage comparison (with/without features)
- Latency impact measurement
- Quality metrics comparison (with/without karma)

---

## 6. Usage Guide

### 6.1 Recommended: Using InferenceManager

The `InferenceManager` is the recommended entry point for all inference operations. It automatically orchestrates all components based on the selected mode.

```python
from symbolu.inference import InferenceManager, InferenceMode

# Load your model
model = HybridPhaseTransformer(...)
model.load_state_dict(checkpoint['model'])

# Create manager with desired mode
manager = InferenceManager(
    model,
    mode=InferenceMode.SOVEREIGN,  # or STANDARD, FAST
    checkpoint_path="checkpoint.pt",  # Optional: load trained component weights
)

# Generate with full pipeline
output_ids, metrics = manager.generate(
    input_ids,
    max_new_tokens=100,
    temperature=0.8,
    top_p=0.9,
)

# Check metrics
print(f"Mode: {metrics['mode']}")
print(f"Karma stored: {metrics['karma_stored']}")
print(f"Aborted: {metrics['aborted']}")
print(f"CSR interventions: {metrics['interventions']}")
print(f"Sovereign alignment: {metrics.get('sovereign_score', 'N/A')}")

# Status line for logging
print(manager.get_status_line())
# Output: [SOVEREIGN] Karma:0.75(strong)|avg:0.72 | Guna:S🔵|s=0.45|r=0.30|t=0.25 | Meta:CONT|c=0.68➡️
```

### 6.2 Inference Modes

| Mode | Components Active | Use Case |
|------|-------------------|----------|
| **FAST** | Raw model only | Benchmarking, latency-sensitive apps |
| **STANDARD** | Engine + Gunas | Production, multi-turn conversations |
| **SOVEREIGN** | All components | High-stakes, alignment research |

**Mode Switching:**
```python
# Start fast
manager = InferenceManager(model, mode=InferenceMode.FAST)

# Switch to sovereign for important generation
manager.set_mode(InferenceMode.SOVEREIGN)
output, metrics = manager.generate(input_ids, max_new_tokens=200)

# Switch back to fast
manager.set_mode(InferenceMode.FAST)
```

### 6.3 Multi-Turn Conversations with Karma

```python
# Karma persists across calls automatically
manager = InferenceManager(model, mode=InferenceMode.STANDARD)

# Turn 1
output1, metrics1 = manager.generate(user_input_1)
print(f"Karma stored: {metrics1['karma_stored']}")  # True

# Turn 2 - previous karma is injected
output2, metrics2 = manager.generate(user_input_2)
print(f"Karma injected: {metrics2['karma_injected']}")  # True
print(f"Coherence: {metrics2['karma_coherence']:.3f}")

# Reset for new conversation
manager.clear_karma()
```

### 6.4 Using Components Directly

For advanced use cases, you can use components directly:

```python
from symbolu.inference import (
    EvolutionaryInferenceEngine,
    InferenceMetacognition,
    InferenceGunas,
    CSRInferenceGuard,
    SovereignInferenceScorer,
)

# Create engine
engine = EvolutionaryInferenceEngine(model, resonance_alpha=0.1)
engine.load_bridge_checkpoint("checkpoint.pt")

# Create quality monitors
metacog = InferenceMetacognition(alarm_threshold=0.3)
gunas = InferenceGunas(window_size=20)

# Create safety guard
guard = CSRInferenceGuard(lm_head=model.lm_head, dim=768)

# Generate with all components
output, metrics = engine.generate_with_karma(
    input_ids,
    metacognition=metacog,
    guna_tracker=gunas,
    csr_guard=guard,
)
```

### 6.5 Configuration Options

**InferenceManager Configuration:**
```python
manager = InferenceManager(
    model,
    mode=InferenceMode.SOVEREIGN,
    # Engine settings
    resonance_alpha=0.1,        # Base alpha for karma injection
    karma_decay=0.99,           # Decay per generation
    # Metacognition settings
    coherence_window=50,        # Tokens to track
    alarm_threshold=0.3,        # Coherence alarm level
    abort_consecutive=5,        # Tokens before ABORT
    # Guna settings
    guna_window_size=20,        # Token window for Guna calc
    # CSR settings
    entropy_threshold=2.0,      # Entropy for intervention
    csr_skip_threshold=0.9,     # Skip if confidence > this
)
```

### 6.6 Metrics Reference

**FAST mode metrics:**
- `mode`: "fast"
- `tokens_generated`: Number of tokens generated

**STANDARD mode metrics:**
- All FAST metrics +
- `karma_injected`: Whether previous karma was used
- `karma_stored`: Whether new karma was stored
- `karma_coherence`: Coherence with previous sequence
- `final_gunas`: (sattva, rajas, tamas) tuple

**SOVEREIGN mode metrics:**
- All STANDARD metrics +
- `aborted`: Whether generation was aborted
- `interventions`: Number of CSR interventions
- `metacognition`: Detailed metacognitive status
- `csr_statistics`: CSR intervention statistics
- `sovereign_score`: R-Matrix alignment score (0-1)
- `sovereign_info`: Detailed alignment breakdown

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 2.0 | 2026-01-05 | Claude | Full implementation complete (Phases 1-3), added Usage Guide |
| 1.0 | 2026-01-05 | Claude | Initial comprehensive gap analysis |

