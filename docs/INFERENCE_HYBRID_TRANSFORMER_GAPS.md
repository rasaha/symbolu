# Inference vs Training Gaps: Hybrid Transformer Logic

**Document Version:** 5.0
**Date:** February 2026
**Status:** ✅ ALL PHASES COMPLETE (Including V11.0.0 Inference Filter Wiring)
**Related File:** `train_unified_llm.py` (V10.6.6)
**Implementation:** `symbolu/inference/` module, `generate_sovereign.py`

---

## Executive Summary

This document catalogs the gaps between training-time logic in `train_unified_llm.py` and inference-time behavior. **All phases (1-6) are now complete**, including full support for V10.0 Binding Cache architectures and V11.0.0 three-plane inference filter wiring.

**V10.0 Update:** Both V10.0 model architectures now have full inference support:
- **`BindingCacheTransformer`** (V10.0): Protected Phase + Top-K Query with proposal_mode ✅
- **`OntologicalBindingCacheTransformer`** (V10.0): AGI Architecture combining Binding Cache + 32D Sovereign State ✅

**V11.0.0 Update:** Inference filters wired per Training/Inference filter table:
- **Vritti Gate (CRITICAL)**: Hallucination gating — reversal_risk → cool_resample, low quality → boost diversity ✅
- **Kosha Depth Control**: MATERIAL → broaden top_k, INTELLECTUAL → sharpen temperature ✅
- **Sovereign Bridge**: Control plane [12:28] → ConfidenceGate / SafetyContract signals ✅
- **JEPA Exclusion**: Reserved[28:32] explicitly not consumed at inference ✅

### Implementation Summary

| Phase | Status | Components |
|-------|--------|------------|
| Phase 1 (Critical) | ✅ Complete | `EvolutionaryInferenceEngine`, `extract_layers` parameter |
| Phase 2 (Important) | ✅ Complete | `InferenceMetacognition`, `InferenceGunas`, `CSRInferenceGuard`, `SovereignInferenceScorer` |
| Phase 3 (Orchestration) | ✅ Complete | `InferenceManager` with Fast/Standard/Sovereign modes |
| Phase 4 (Deployment) | ✅ Complete | `generate_sovereign.py` CLI script, `generate_full_sequence()` method |
| Phase 5 (V10.0 Models) | ✅ Complete | `BindingCacheInferenceEngine`, `OntologicalBindingCacheInferenceEngine`, `SovereignStateMonitor` |
| **Phase 6 (V11.0.0 Filters)** | ✅ **Complete** | Vritti gate, Kosha depth, Sovereign Bridge, JEPA exclusion |

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
3. [Enhancement Gaps (Priority 3)](#3-enhancement-gaps-priority-3) - ✅ IMPLEMENTED
4. [Implementation Roadmap](#4-implementation-roadmap) - All Phases ✅
5. [Architecture Considerations](#5-architecture-considerations)
6. [Usage Guide](#6-usage-guide)
7. [Phase 4: Deployment Script](#7-phase-4-deployment-script) - ✅ COMPLETE
8. [Phase 5: BindingCacheTransformer](#8-phase-5-bindingcachetransformer-gaps) - ✅ IMPLEMENTED
9. [Phase 5: OntologicalBindingCacheTransformer](#9-phase-5-ontologicalbindingcachetransformer-gaps) - ✅ IMPLEMENTED
10. [Phase 5: Implementation Roadmap](#10-phase-5-implementation-roadmap) - ✅ COMPLETE
11. [Phase 6: V11.0.0 Inference Filter Wiring](#11-phase-6-v1100-inference-filter-wiring) - ✅ IMPLEMENTED

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

## 3. Enhancement Gaps (Priority 3) ✅ IMPLEMENTED

### 3.1 9:3 Hierarchical Split Awareness ✅ IMPLEMENTED

**Training Behavior:**
`HierarchicalGradientScaler` (`train_unified_llm.py`) applies different gradient scales to:
- Authority layers (0-8): Full gradients
- Sensory layers (9-11): Dampened gradients (α_sens)

**✅ Implementation:**

Located in `symbolu/inference/layer_config.py`:

- **`LayerInferenceConfig`**: Configuration class for 9:3 split
- **`LayerType` enum**: AUTHORITY / SENSORY classification
- **`CachePriority` enum**: HIGH / MEDIUM / LOW levels

**Key Features:**
- `get_cache_priority()`: Authority=HIGH, Sensory=MEDIUM
- `get_temperature_adjustment()`: Sensory layers get 0.9x sharper temperature
- `get_extraction_layers()`: Preset modes (minimal, endpoints, full)
- `get_layer_weights()`: For weighted aggregation operations
- Ontological layer names (O1-Potential through O12-Integration)

**Usage:**
```python
from symbolu.inference import LayerInferenceConfig, AUTHORITY_LAYERS, SENSORY_LAYERS

# Get layer-adjusted temperature
for layer_idx in range(12):
    temp = LayerInferenceConfig.get_temperature_adjustment(layer_idx, base_temp=1.0)
    priority = LayerInferenceConfig.get_cache_priority(layer_idx)
    print(f"{LayerInferenceConfig.get_layer_name(layer_idx)}: temp={temp:.2f}, cache={priority}")

# Via InferenceManager
manager = InferenceManager(model)
temp = manager.get_layer_temperature(layer_idx=10, base_temp=1.0)  # 0.9
```

---

### 3.2 Toroidal Coherence Metrics ✅ IMPLEMENTED

**Training Behavior:**
`ToroidalConsistencyLoss` computes coherence between:
- Seed (previous O12) and Harvest (current O12)
- Optional 3-way consistency with current O1

**✅ Implementation:**

Located in `symbolu/inference/evolutionary_inference.py`:

- **`compute_generation_coherence()`**: 2-way coherence (Seed ↔ O12)
- **`compute_3way_toroidal_coherence()`**: Full 3-way cognitive flow
- **`get_cognitive_flow_status()`**: Formatted status string

**3-Way Coherence Components:**
1. **Birth Similarity**: Seed ↔ O1 (karma injection effectiveness)
2. **Flow Similarity**: O1 ↔ O12 (internal coherence)
3. **Evolution Similarity**: Seed ↔ O12 (loop closure)

**Usage:**
```python
from symbolu.inference import EvolutionaryInferenceEngine

engine = EvolutionaryInferenceEngine(model)

# After generation, compute full cognitive flow
flow_score, details = engine.compute_3way_toroidal_coherence(
    o1_hidden=layer_states[0],
    o12_hidden=layer_states[11],
)

print(f"Cognitive Flow: {flow_score:.3f}")
print(f"  Birth: {details['birth_similarity']:.3f}")
print(f"  Flow: {details['flow_similarity']:.3f}")
print(f"  Evolution: {details['evolution_similarity']:.3f}")

# Status line
print(engine.get_cognitive_flow_status())
# Output: "Flow:0.72(strong/3way)"
```

---

### 3.3 Dynamic Relaxation State Persistence ✅ IMPLEMENTED

**Training Behavior:**
`DynamicRelaxationController` manages state transitions:
- STATE_AUTHORITY (9:3) → STATE_BALANCED (6:6) → Evolution stages

**✅ Implementation:**

Located in `symbolu/inference/checkpoint_utils.py`:

- **`InferenceConfig`**: Dataclass for inference configuration
- **`save_sovereign_checkpoint()`**: Save with inference hints
- **`load_sovereign_config()`**: Load configuration from checkpoint
- **`load_model_with_config()`**: Load model + config together
- **`get_checkpoint_info()`**: Inspect checkpoint metadata

**Checkpoint Metadata:**
```python
inference_config = {
    "authority_sensory_split": (9, 3),  # or (6, 6) for balanced
    "evolution_stage": 2,
    "recommended_alpha": 0.1,
    "training_state": "authority",
    "sgp_rate": 25,
}
```

**Usage:**
```python
from symbolu.inference import (
    save_sovereign_checkpoint,
    load_sovereign_config,
    load_model_with_config,
)

# Save with inference hints
save_sovereign_checkpoint(
    model=model,
    path="checkpoint.pt",
    drc_state="authority",
    evolution_stage=2,
)

# Load and auto-configure
config = load_sovereign_config("checkpoint.pt")
print(f"Recommended alpha: {config.recommended_alpha}")
print(f"Split: {config.authority_sensory_split}")

# Or load model + config together
model, config = load_model_with_config("checkpoint.pt", model)
```

**InferenceManager Integration:**
```python
# Checkpoint config is auto-applied when loading
manager = InferenceManager(model, checkpoint_path="checkpoint.pt")
# resonance_alpha is automatically set from checkpoint
```

---

## 4. Implementation Roadmap (All Phases ✅ COMPLETE)

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

### Phase 3 Enhancements ✅

| Task | Status | Files |
|------|--------|-------|
| `LayerInferenceConfig` (9:3 split) | ✅ Done | `symbolu/inference/layer_config.py` |
| Checkpoint metadata utilities | ✅ Done | `symbolu/inference/checkpoint_utils.py` |
| 3-way toroidal coherence | ✅ Done | `symbolu/inference/evolutionary_inference.py` |

**Deliverables:**
- ✅ `symbolu/inference/layer_config.py`
- ✅ `symbolu/inference/checkpoint_utils.py`
- ✅ Enhanced `EvolutionaryInferenceEngine` with `compute_3way_toroidal_coherence()`
- ✅ Enhanced `InferenceManager` with layer config integration

### Phase 4: Deployment Script ✅ COMPLETE

| Task | Status | Files |
|------|--------|-------|
| Create `generate_sovereign.py` CLI | ✅ Done | `generate_sovereign.py` (root) |
| Implement `generate_full_sequence()` | ✅ Done | `symbolu/inference/manager.py` |
| Interactive sovereign loop | ✅ Done | `generate_sovereign.py` |
| Cognitive telemetry output | ✅ Done | `generate_sovereign.py` |

**Deliverables:**
- ✅ `generate_sovereign.py` - CLI entry point with interactive, single, and batch modes
- ✅ `InferenceManager.generate_full_sequence()` - High-level metabolic generation loop
- ✅ `InferenceManager.get_cognitive_status_line()` - Status line for monitoring
- ✅ `InferenceMode.SOVEREIGN` - Full metabolic loop mode

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

## 7. Phase 4: Deployment Script (✅ COMPLETE)

### 7.1 Implementation Notes

**The Chassis is Now Built.**

The inference script `generate_sovereign.py` is now fully implemented and can work with any checkpoint that contains a trained model. The script gracefully handles missing components (e.g., evolutionary bridge weights) and will disable those features if not available.

#### 7.1.1 Graceful Degradation

The script implements graceful degradation for missing checkpoint components:

- **Missing evolutionary_bridge weights**: Karma injection/persistence disabled
- **Missing inference_config**: Default parameters used
- **Missing CSR weights**: CSR guard disabled
- **Missing SOVEREIGN_R_MATRIX**: Basic scoring used

#### 7.1.2 Parameter Defaults

The script uses sensible defaults that work well for most models:

- **Resonance Alpha (α):** 0.1 (can be overridden from checkpoint's `recommended_alpha`)
- **Entropy Threshold:** 2.0
- **Temperature:** 0.7

These can be tuned via CLI arguments or through the checkpoint's `inference_config`.

#### 7.1.3 Usage Modes

The script supports three usage modes:

1. **Interactive Mode:** `--interactive` - Multi-turn conversation with karma persistence
2. **Single Generation:** `--prompt "..."` - One-shot generation
3. **Batch Mode:** `--input prompts.txt` - Process multiple prompts from file

---

### 7.2 Checkpoint Requirements (Optional)

For full functionality, the checkpoint should contain:

| Component | Required | Effect if Missing |
|-----------|----------|-------------------|
| Model weights (`model` or `model_state_dict`) | ✅ Required | Script will fail |
| `evolutionary_bridge` weights | Optional | Karma disabled |
| `inference_config` metadata | Optional | Default params used |
| `SOVEREIGN_R_MATRIX` | Optional | Basic scoring used |
| `csr_weights` | Optional | CSR guard disabled |

**The script works with any valid checkpoint, gracefully disabling features that require missing components.**

---

### 7.3 Implemented Script: `generate_sovereign.py`

The inference script is now fully implemented at the project root. It serves as the inference counterpart to `train_unified_llm.py`.

#### 7.3.1 CLI Interface

```bash
usage: generate_sovereign.py [-h] --checkpoint CHECKPOINT
                             [--mode {fast,standard,full,safe,sovereign}]
                             [--prompt PROMPT] [--temp TEMP] [--top_p TOP_P]
                             [--top_k TOP_K] [--max_tokens MAX_TOKENS]
                             [--interactive] [--input INPUT] [--output OUTPUT]
                             [--clear_between] [--tokenizer TOKENIZER]
                             [--device DEVICE] [--verbose] [--no_banner]
```

#### 7.3.2 Key Features

| Feature | Description |
|---------|-------------|
| **Interactive Mode** | `--interactive` - Multi-turn conversation with karma persistence between turns |
| **Single Generation** | `--prompt "..."` - One-shot generation with cognitive telemetry |
| **Batch Processing** | `--input file.txt` - Process multiple prompts from file |
| **5 Inference Modes** | `fast`, `standard`, `full`, `safe`, `sovereign` |
| **Graceful Degradation** | Works with any checkpoint, disabling missing components |
| **Cognitive Telemetry** | Displays Guna state, coherence, recommendations |

#### 7.3.3 Interactive Session Commands

| Command | Action |
|---------|--------|
| `exit` / `quit` | End session |
| `clear` | Clear karma buffer (reset conversation memory) |
| `status` | Show current cognitive status line |

#### 7.3.4 Example Session

```
======================================================================
  SYMBOLU SOVEREIGN GENERATION ENGINE
  Version 1.0.0 | January 2026
======================================================================
  Device: cuda
  Checkpoint: checkpoints/sovereign.pt
======================================================================

Loading tokenizer...
Loading checkpoint from checkpoints/sovereign.pt...
  Detected model type: hybrid
  Creating HybridPhaseTransformer...
  Loaded model with 124,439,808 parameters

Initializing inference manager...
  Mode: sovereign
  Karma: enabled
  CSR Guard: enabled
  Metacognition: enabled

======================================================================
  SOVEREIGN ENGINE ACTIVE
  Mode: SOVEREIGN | Temp: 0.7 | Max Tokens: 128
  Type 'exit' or 'quit' to end session
  Type 'clear' to clear karma buffer
  Type 'status' to show cognitive status
======================================================================

[Sovereign Query] > The meaning of consciousness is

| Mode: SOVEREIGN | Scaling: 9:3 Hierarchical |
--------------------------------------------------
[Cognitive Log] Sattva dominant | S:0.45 R:0.32 T:0.23
[Metacognition] Recommendation: CONTINUE
[Coherence] 3-Way Flow: 0.7234 (Birth:0.68, Flow:0.81, Evolution:0.65)
[Stats] Tokens:47 | Interventions:0 | Karma:stored
--------------------------------------------------
[Response] fundamentally tied to the integration of information across
distributed neural networks. When we examine the hard problem...

[Sovereign Query] > status
[SOVEREIGN] | Karma:0.72(strong)|avg:0.72 | Guna:S|s=0.45|r=0.32|t=0.23 | Meta:CONT|c=0.68➡️

[Sovereign Query] > exit
Ending sovereign session.
Sovereign session complete.
```

#### 7.3.5 Batch Processing Example

```bash
# Create prompts file
echo "What is the nature of reality?" > prompts.txt
echo "Explain quantum entanglement" >> prompts.txt
echo "The future of AI is" >> prompts.txt

# Run batch processing
python generate_sovereign.py --checkpoint model.pt \
    --input prompts.txt \
    --output results.txt \
    --mode sovereign \
    --max_tokens 100

# Results written to results.txt
```

---

### 7.4 Implemented Method: `InferenceManager.generate_full_sequence()`

This method is the high-level metabolic orchestrator. It's now fully implemented in `symbolu/inference/manager.py`.

#### 7.4.1 Method Signature

```python
@torch.no_grad()
def generate_full_sequence(
    self,
    prompt_ids: torch.Tensor,
    max_tokens: int = 128,
    base_temp: float = 0.7,
    top_p: float = 0.9,
    top_k: int = 50,
    on_step_callback: Optional[callable] = None,
) -> Dict[str, Any]:
```

#### 7.4.2 Return Value

```python
{
    # Core outputs
    'generated_ids': torch.Tensor,  # [B, T+N] full sequence
    'text': str,                     # Decoded text (if tokenizer available)

    # Cognitive state
    'gunas': Tuple[float, float, float],  # Final (sattva, rajas, tamas)
    'recommendation': str,                 # Final metacognitive recommendation

    # Toroidal coherence
    'coherence': float,              # Combined 3-way coherence [0, 1]
    'coherence_details': {
        'birth_similarity': float,   # Seed <-> O1
        'flow_similarity': float,    # O1 <-> O12
        'evolution_similarity': float,  # Seed <-> O12
        '3way': bool,                # True if 3-way computed
    },

    # Generation status
    'aborted': bool,                 # Whether ABORT was triggered
    'abort_reason': Optional[str],   # 'coherence_collapse' if aborted
    'interventions': int,            # Number of CSR interventions
    'karma_stored': bool,            # Whether karma was stored for next turn
    'karma_injected': bool,          # Whether previous karma was injected
    'tokens_generated': int,         # Number of new tokens
    'temperature_history': List[float],  # Temperature per step

    # Sovereign alignment (if scorer available)
    'sovereign_score': Optional[float],
    'sovereign_info': Dict[str, Any],
}
```

#### 7.4.3 The Metabolic Loop (10 Steps)

The implementation follows a rigorous 10-step metabolic process:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  THE METABOLIC GENERATION LOOP                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STEP 1: Initialize with Evolutionary Seed                                  │
│  ─────────────────────────────────────────                                  │
│  Check if karma_buffer exists from previous conversation                    │
│  If yes, mark karma_injected = True (injection happens in forward pass)     │
│                                                                             │
│  FOR each step in range(max_tokens):                                        │
│                                                                             │
│      A. FORWARD PASS                                                        │
│         Request extract_layers=[0, 11] for O1/O12 hidden states             │
│         Get logits, hidden_states, last_hidden                              │
│                                                                             │
│      B. CSR SAFETY CHECK                                                    │
│         If enable_csr_guard: check_and_gate(hidden, logits)                 │
│         Count interventions                                                 │
│                                                                             │
│      C. METACOGNITIVE MONITORING                                            │
│         metacognition.update(logits, hidden, token_id=None)                 │
│         Get recommendation: CONTINUE | BRAKE | RECOVER | ABORT              │
│                                                                             │
│      D. METACOGNITIVE ADJUSTMENT                                            │
│         BRAKE → current_temp *= 0.8 (sharpen focus)                         │
│         RECOVER → current_temp = min(base_temp, temp * 1.2)                 │
│         ABORT → break loop, set aborted=True                                │
│                                                                             │
│      E. GUNA-BASED TEMPERATURE                                              │
│         effective_temp = gunas.get_temperature_modifier(current_temp)       │
│                                                                             │
│      F. LAYER-AWARE TEMPERATURE (9:3 Split)                                 │
│         effective_temp *= layer_config.get_temperature_multiplier(11)       │
│         Sensory layers (9-11) get 0.9x sharper temperature                  │
│                                                                             │
│      G. SAMPLING                                                            │
│         Apply temperature, top-k, top-p filtering                           │
│         Sample next_token from softmax(logits)                              │
│                                                                             │
│      H. UPDATE GUNA STATE                                                   │
│         gunas.update(token_id, token_prob)                                  │
│         Track (sattva, rajas, tamas) evolution                              │
│                                                                             │
│      I. SEQUENCE UPDATE                                                     │
│         Append next_token to generated sequence                             │
│         Call on_step_callback if provided                                   │
│                                                                             │
│      J. STOP CONDITION                                                      │
│         Break if next_token == eos_token_id                                 │
│                                                                             │
│  STEP 3: Final Harvest (Toroidal Bridge)                                    │
│  ───────────────────────────────────────                                    │
│  Extract O1 and O12 from final sequence                                     │
│  Compute 3-way toroidal coherence:                                          │
│    - birth_similarity: Seed <-> O1 (karma injection effectiveness)          │
│    - flow_similarity: O1 <-> O12 (internal coherence)                       │
│    - evolution_similarity: Seed <-> O12 (loop closure)                      │
│  Store new karma: bridge.compute_seed(O12) * karma_decay                    │
│                                                                             │
│  STEP 4: Build Result                                                       │
│  ─────────────────────                                                      │
│  Decode text, compute sovereign_score, return comprehensive dict            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 7.4.4 Key Implementation Details

| Component | Implementation |
|-----------|----------------|
| **Gated Toroidal Harvest** | Uses `bridge.compute_seed(O12)` with sigmoid gating to compress sequence essence into karma_buffer |
| **3-Way Coherence** | Geometric mean of 3 cosine similarities mapped to [0, 1]: `(birth × flow × evolution)^(1/3)` |
| **Adaptive Temperature** | BRAKE → 0.8x, RECOVER → 1.2x (capped at base_temp) |
| **9:3 Layer Awareness** | Sensory layers (9-11) get 0.9x temperature multiplier for sharper focus |
| **Graceful Fallback** | Falls back to 2-way coherence (O1 <-> O12) if no karma_buffer exists |

---

### 7.5 Implementation Status Summary

| Component | Logic ("What") | Script ("How") |
|-----------|----------------|----------------|
| `EvolutionaryInferenceEngine` | ✅ Implemented | ✅ Integrated |
| `InferenceMetacognition` | ✅ Implemented | ✅ Integrated |
| `InferenceGunas` | ✅ Implemented | ✅ Integrated |
| `CSRInferenceGuard` | ✅ Implemented | ✅ Integrated |
| `SovereignInferenceScorer` | ✅ Implemented | ✅ Integrated |
| `LayerInferenceConfig` | ✅ Implemented | ✅ Integrated |
| `InferenceManager` | ✅ Implemented | ✅ Integrated |
| `generate_full_sequence()` | ✅ Implemented | ✅ Integrated |
| `generate_sovereign.py` | ✅ Implemented | ✅ Complete |

**All components are fully implemented and integrated.**

---

### 7.6 Quick Start Guide

**Basic Usage:**

```bash
# Single generation
python generate_sovereign.py --checkpoint checkpoints/model.pt \
    --prompt "The meaning of life is"

# Interactive session
python generate_sovereign.py --checkpoint checkpoints/model.pt --interactive

# Batch processing
python generate_sovereign.py --checkpoint checkpoints/model.pt \
    --input prompts.txt --output results.txt
```

**Mode Selection:**

```bash
# Fast mode (minimal overhead)
python generate_sovereign.py --checkpoint model.pt --mode fast --prompt "..."

# Standard mode (karma + basic monitoring)
python generate_sovereign.py --checkpoint model.pt --mode standard --prompt "..."

# Sovereign mode (full metabolic loop)
python generate_sovereign.py --checkpoint model.pt --mode sovereign --prompt "..."
```

**Generation Parameters:**

```bash
python generate_sovereign.py --checkpoint model.pt \
    --temp 0.7 \           # Temperature
    --top_p 0.9 \          # Nucleus sampling
    --top_k 50 \           # Top-k sampling
    --max_tokens 256 \     # Max generation length
    --prompt "Once upon a time"
```

---

## 8. Phase 5: BindingCacheTransformer (✅ IMPLEMENTED)

**Model Location:** `symbolu/phase_transformer.py:3375-3724`
**Training Config:** `--model_type binding_cache`

### 8.1 Architecture Overview

The `BindingCacheTransformer` (V10.0) introduces a fundamentally different attention mechanism validated by diagnostic probes:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BINDING CACHE ARCHITECTURE (O(n) + O(nk) vs O(n²))                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Three-Path Collaboration:                                                  │
│  ────────────────────────                                                   │
│  1. Phase: O(n) state accumulator (global compression) - PROTECTED ROLE    │
│  2. Quad: O(nk) memory query via Top-K cache (global retrieval)            │
│  3. Local: O(n*w) direct token-to-token attention (syntax learning)        │
│                                                                             │
│  V10.4 Proposal Mode Enhancement:                                          │
│  ─────────────────────────────────                                          │
│  - Phase computes confidence score from memory state                        │
│  - If confidence > threshold: SKIP Quad query (efficiency)                 │
│  - Quad returns proposals (no softmax mixing)                              │
│  - Phase integrates proposals with gating                                   │
│                                                                             │
│  Validated by Diagnostic Probes:                                            │
│  - Phase ablation drop: -50% to -54% (Phase is ESSENTIAL)                  │
│  - When Phase mixed with Quad: ~0% drop (DECORATIVE - bad!)                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Critical Gaps (Priority 1)

#### 8.2.1 Model Type Recognition ✅ IMPLEMENTED

**Training Behavior:**
`train_unified_llm.py` creates `BindingCacheTransformer` when `--model_type binding_cache`:

```python
# train_unified_llm.py:10738
model = BindingCacheTransformer(
    vocab_size=config.vocab_size,
    embed_dim=preset["embed_dim"],
    top_k=config.binding_cache_top_k,
    proposal_mode=False,  # V10.4 optional
    confidence_threshold=0.7,
    ...
)
```

**✅ Implementation:**

`generate_sovereign.py` now recognizes both `binding_cache` and `ontological_binding_cache` model types:

```python
# generate_sovereign.py - Model type detection
elif model_type == 'binding_cache':
    from symbolu.phase_transformer import BindingCacheTransformer
    ModelClass = BindingCacheTransformer
elif model_type == 'ontological_binding_cache':
    from symbolu.phase_transformer import OntologicalBindingCacheTransformer
    ModelClass = OntologicalBindingCacheTransformer
```

`InferenceManager` auto-detects architecture from model class:

```python
# symbolu/inference/manager.py - Architecture detection
if 'OntologicalBindingCache' in model.__class__.__name__:
    self.architecture_mode = ArchitectureMode.ONTOLOGICAL_BINDING_CACHE
elif 'BindingCache' in model.__class__.__name__:
    self.architecture_mode = ArchitectureMode.BINDING_CACHE
```

**Files Modified:**
- ✅ `generate_sovereign.py` - Model type detection and loading
- ✅ `symbolu/inference/manager.py` - Architecture auto-detection
- ✅ `symbolu/inference/layer_config.py` - Added `ArchitectureMode.BINDING_CACHE` enum

#### 8.2.2 Proposal Mode Inference ✅ IMPLEMENTED

**Training Behavior (`symbolu/phase_transformer.py:3340-3359`):**
```python
# V10.4: Proposal Mode - quad proposes, phase integrates
confidence = self.phase_state.compute_confidence(memory_state)

# Track metrics for monitoring
self._last_confidence_mean = confidence.mean().item()
self._last_skip_rate = (confidence > self.confidence_threshold).float().mean().item()

# Get proposals from quad (no softmax mixing)
proposals, proposal_scores = self.quad_query.get_proposals(x, memory_state)

# Phase integrates proposals
mem_out = self.phase_state.integrate_proposals(x, memory_state, proposals, proposal_scores)
```

**✅ Implementation:**

Located in `symbolu/inference/binding_cache_inference.py`:

- **`BindingCacheInferenceEngine`**: Main inference engine with full proposal mode support
- **`BindingCacheInferenceConfig`**: Configuration with adaptive confidence settings

```python
from symbolu.inference import BindingCacheInferenceEngine

engine = BindingCacheInferenceEngine(model)

# Access proposal mode metrics during generation
metrics = engine.get_proposal_metrics()
print(f"Confidence: {metrics['confidence_mean']:.2f}")
print(f"Skip rate: {metrics['skip_rate']:.1%}")

# Dynamically adjust confidence threshold
engine.set_confidence_threshold(0.8)

# Generate with metrics tracking
output, meta = engine.generate(
    input_ids,
    max_new_tokens=100,
    track_metrics=True,
)
print(f"Avg confidence: {meta['avg_confidence']:.2f}")
print(f"Avg skip rate: {meta['avg_skip_rate']:.1%}")
```

**Key Features:**
- `get_proposal_metrics()`: Returns confidence_mean, skip_rate, per_layer metrics
- `set_confidence_threshold()`: Propagates threshold to all blocks
- Adaptive confidence tracking via `BindingCacheInferenceConfig.adaptive_confidence`

**Files Created:**
- ✅ `symbolu/inference/binding_cache_inference.py`

#### 8.2.3 Intent Phase Injection ✅ IMPLEMENTED

**Training Behavior:**
The `BindingCacheTransformer` accepts optional `intent_phase` to modulate Phase behavior:

```python
# phase_transformer.py:3630-3640
def forward(
    self,
    input_ids: torch.Tensor,
    intent_phase: Optional[torch.Tensor] = None,  # [B, H] or [B, H, D_h]
    binding_salience: Optional[torch.Tensor] = None,
    enable_slots_read: bool = True,
    ...
)
```

**✅ Implementation:**

Located in `symbolu/inference/binding_cache_inference.py`:

- **`IntentPhaseInferenceModule`**: Computes and manages intent phase during inference

```python
from symbolu.inference.binding_cache_inference import IntentPhaseInferenceModule

intent_module = IntentPhaseInferenceModule(num_heads=12, head_dim=64)

# Compute intent from hidden states
intent_phase = intent_module.compute_intent_from_hidden(
    hidden_states,  # [B, T, D]
    pooling='mean',  # 'mean', 'last', or 'first'
)

# Inject external intent with optional blending
intent_phase = intent_module.inject_external_intent(
    external_intent,
    blend_alpha=0.7,  # Blend with current intent
)

# Track intent evolution
evolution = intent_module.get_intent_evolution()

# Use with BindingCacheInferenceEngine
output, meta = engine.generate(
    input_ids,
    intent_phase=intent_phase,  # Direct injection
    compute_intent_from_context=True,  # Or auto-compute from hidden states
)
```

**Key Features:**
- `compute_intent_from_hidden()`: Projects hidden states → intent phase [B, H]
- `inject_external_intent()`: Allows external intent injection with blending
- `get_intent_evolution()`: Tracks intent phase history across tokens
- Device management via `.to(device)`

**Files Created:**
- ✅ `symbolu/inference/binding_cache_inference.py` (includes `IntentPhaseInferenceModule`)

### 8.3 Important Gaps (Priority 2)

#### 8.3.1 Binding Salience Control ✅ IMPLEMENTED

**Training Behavior:**
`binding_salience` biases Top-K selection without modifying attention math:

```python
# phase_transformer.py:3693
x = block(x, intent_phase=intent_phase, binding_salience=binding_salience)
```

**✅ Implementation:**

Located in `symbolu/inference/binding_cache_inference.py`:

- **`BindingSalienceController`**: Controls binding salience during inference

```python
from symbolu.inference.binding_cache_inference import BindingSalienceController

salience = BindingSalienceController(default_boost=1.0)

# Boost specific positions
salience.boost_position(position=5, boost=2.0)

# Boost all positions of a specific token
salience.boost_token_positions(input_ids, token_id=100, boost=1.5)

# Compute salience for sequence
binding_salience = salience.compute_salience(input_ids)  # [B, T]

# Use with engine
output, meta = engine.generate(
    input_ids,
    binding_salience=binding_salience,
)
```

#### 8.3.2 Enable Slots Read Gating ✅ IMPLEMENTED

**Training Behavior (V10.6.2 D.2 Recommendation):**
```python
# Separates READ path gating from WRITE path
# Write path (phase accumulation) remains deterministic
# Read path (quad retrieval) can be gated
if not enable_slots_read:
    attn_out = local_out  # Skip quad retrieval entirely
```

**✅ Implementation:**

```python
# Enable/disable Quad retrieval globally
engine.set_enable_slots_read(enabled=False)  # Skip quad, local only

# Per-generation control
output, meta = engine.generate(
    input_ids,
    enable_slots_read=False,  # Skip quad for this generation
)
```

#### 8.3.3 Phase Health Monitoring ✅ IMPLEMENTED

**Training Behavior:**
```python
# phase_transformer.py:3501-3511
def get_phase_health(self) -> dict:
    """Aggregate Phase health metrics from all blocks."""
    return {
        "r_k_mean": ...,  # Phase coherence
        "r_k_per_layer": ...,
    }
```

**✅ Implementation:**

```python
# Access Phase health during generation
health = engine.get_phase_health()
print(f"Phase coherence: {health['r_k_mean']:.3f}")
print(f"Per-layer: {health['r_k_per_layer']}")

# Tracked per-step during generation with track_metrics=True
output, meta = engine.generate(input_ids, track_metrics=True)
for step_health in meta['phase_health']:
    print(f"r_k_mean: {step_health['r_k_mean']:.3f}")
```

#### 8.3.4 Cache Instrumentation ✅ IMPLEMENTED

**Training Behavior:**
```python
# phase_transformer.py:3513-3534
def get_instrumentation(self) -> dict:
    return {
        "cache_hit_rate": ...,
        "mean_alpha": ...,
        "cache_key_cosine_mean": ...,  # > 0.85 = redundancy
        "cache_key_cosine_max": ...,   # > 0.95 = collision
    }
```

**✅ Implementation:**

```python
# Access cache metrics
cache = engine.get_cache_instrumentation()
print(f"Hit rate: {cache['cache_hit_rate']:.1%}")
print(f"Mean alpha: {cache['mean_alpha']:.3f}")
print(f"Cosine mean: {cache['cache_key_cosine_mean']:.3f}")
print(f"Cosine max: {cache['cache_key_cosine_max']:.3f}")

# Check for issues
if cache['cache_key_cosine_mean'] > 0.85:
    print("Warning: Cache redundancy detected!")
if cache['cache_key_cosine_max'] > 0.95:
    print("Warning: Slot collision detected!")

# Tracked per-step with track_metrics=True
```

### 8.4 Enhancement Gaps (Priority 3)

#### 8.4.1 Ablation/Rotation Testing ✅ IMPLEMENTED

**Training Methods Available:**
```python
model.set_ablation(mode='shuffle', seed=42)  # Test Phase contribution
model.set_rotation(angle_radians=math.pi/4)  # Test phase encoding
model.clear_rotation()
```

**✅ Implementation:**

```python
import math

# Set ablation mode for diagnostic testing
engine.set_ablation(mode='shuffle', seed=42)  # Options: 'none', 'shuffle', 'zero', 'random'

# Set phase rotation
engine.set_rotation(angle_radians=math.pi/4)

# Clear rotation
engine.clear_rotation()

# Generate with ablation for A/B testing
output_normal, _ = engine.generate(input_ids)
engine.set_ablation(mode='shuffle', seed=42)
output_ablated, _ = engine.generate(input_ids)
# Compare outputs to measure Phase contribution
```

#### 8.4.2 Control Contract Enforcement ✅ IMPLEMENTED

**Training Behavior (V10.6.6):**
```python
# Hard-fail on control signal violations
model.set_enforce_control_contract(enabled=True)
# Raises ControlShapeViolation if intent_phase/binding_salience are wrong shape
```

**✅ Implementation:**

```python
# Enable contract enforcement
engine.set_enforce_control_contract(enabled=True)

# Bad inputs will now raise exceptions instead of silent failures
try:
    output, _ = engine.generate(
        input_ids,
        intent_phase=wrong_shape_tensor,  # Will raise ControlShapeViolation
    )
except ControlShapeViolation as e:
    print(f"Contract violated: {e}")
```

---

## 9. Phase 5: OntologicalBindingCacheTransformer (✅ IMPLEMENTED)

**Model Location:** `symbolu/phase_transformer.py:3740-4075`
**Training Config:** `--model_type ontological_binding_cache`

### 9.1 Architecture Overview

The `OntologicalBindingCacheTransformer` (V10.0) is the AGI Architecture combining:
1. **Binding Cache**: Protected Phase + Top-K Query (validated by probes)
2. **32D Sovereign State**: Ontological reasoning (Bhava, Kosha, Vritti, Guna)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ONTOLOGICAL BINDING CACHE - AGI ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Two-Pass Architecture:                                                     │
│  ──────────────────────                                                     │
│  Pass 1: Get hidden states WITHOUT intent phase                             │
│  │                                                                          │
│  ▼                                                                          │
│  Compute State Delta: hidden → SovereignState[32] → ΔS                      │
│  │                                                                          │
│  ▼                                                                          │
│  Convert ΔS → Intent Phase: ΔS[32] → θ[H] or θ[H, D_h]                     │
│  │                                                                          │
│  ▼                                                                          │
│  Compute Binding Salience: OntologicalBindingAnnotator                     │
│  │                                                                          │
│  ▼                                                                          │
│  Pass 2: Full forward WITH intent phase AND binding salience               │
│                                                                             │
│  32D Sovereign State Structure (V11.0.0 Three-Plane):                      │
│  ─────────────────────────────────────────────────────                      │
│  PHASE PLANE    [0:12]  - 12 Bhavas → ΔBhava → θ → attention rotation     │
│  CONTROL PLANE  [12:17] - 5 Koshas (Consciousness Sheaths)                  │
│                 [17:22] - 5 Vrittis (Mental Modifications) → Vritti Gate    │
│                 [22:28] - 6 Gunas (Energy States)                           │
│  LEARNING PLANE [28:32] - 4 Reserved (JEPA, training-only)                  │
│                                                                             │
│  Theory: System 2 (Ontological) → ΔS → System 1 (Binding Cache)            │
│          Slow deliberate reasoning → Phase rotation → Fast completion       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Critical Gaps (Priority 1)

#### 9.2.1 Model Type Recognition ✅ IMPLEMENTED

**Same as Section 8.2.1** - `generate_sovereign.py` now recognizes `ontological_binding_cache`:

```python
# generate_sovereign.py
elif model_type == 'ontological_binding_cache':
    from symbolu.phase_transformer import OntologicalBindingCacheTransformer
    ModelClass = OntologicalBindingCacheTransformer
```

#### 9.2.2 Two-Pass Generation Loop ✅ IMPLEMENTED

**Training Behavior (`phase_transformer.py:3988-4028`):**
```python
def forward(self, input_ids, ...):
    # Pass 1: Get hidden WITHOUT intent
    with torch.no_grad():
        hidden = self.binding_cache.forward_hidden(input_ids, intent_phase=None)

    # Compute state delta (V11.0.0: returns 3-tuple)
    state, delta_S, delta_bhava = self.compute_state_delta(hidden, reset_state)

    # Convert to intent phase (V11.0.0: uses 12D delta_bhava, not 32D delta_S)
    intent_phase = self.intent_projector(delta_bhava)

    # Compute binding salience
    binding_salience = self.binding_annotator(hidden, state, ...)

    # Pass 2: Full forward WITH intent and salience
    result = self.binding_cache(input_ids, intent_phase=intent_phase, binding_salience=binding_salience)
```

**✅ Implementation:**

Located in `symbolu/inference/ontological_binding_cache_inference.py`:

- **`OntologicalBindingCacheInferenceEngine`**: Implements full two-pass generation

```python
from symbolu.inference import OntologicalBindingCacheInferenceEngine

engine = OntologicalBindingCacheInferenceEngine(model)
engine.to('cuda')

# Generate with two-pass ontological reasoning
output, meta = engine.generate_with_ontology(
    input_ids,
    max_new_tokens=100,
    reset_state=True,  # Start fresh
    track_trajectory=True,
)

# Access state trajectory
print(f"States tracked: {len(meta['state_trajectory'])}")
print(f"Final state: {meta['final_state'].shape}")  # [B, 32]

# Check for warnings
for warning in meta['warnings']:
    print(f"Warning: {warning['type']} at step {warning['step']}")
```

**The Two-Pass Loop (V11.0.0):**
```
FOR each token:
    1. Forward WITHOUT intent → hidden states
    2. Compute state delta: hidden → SovereignState[32] → (state, ΔS, ΔBhava[12D])
    3. Convert ΔBhava → intent phase: ΔBhava[12D] → θ[H]
    4. Compute binding salience from annotator
    5. Forward WITH intent phase AND binding salience → logits
    6. Sovereign Bridge: state → ConfidenceSignals (Vritti/Kosha/Guna)
    7. Vritti Gate: reversal_risk → cool_resample, low quality → boost diversity
    8. Kosha Depth: MATERIAL → broaden top_k, INTELLECTUAL → sharpen temp
    9. Sample next token with effective_temperature, effective_top_k
    10. Update state
```

**Files Created:**
- ✅ `symbolu/inference/ontological_binding_cache_inference.py`

#### 9.2.3 32D Sovereign State Tracking ✅ IMPLEMENTED

**Training Behavior:**
```python
# Compute state delta (System 2 reasoning)
state, delta_S = self.compute_state_delta(hidden, reset_state)

# State structure:
# state[0:12]  = Bhava activations (POT, IDN, EXE, STR, COG, AGY, RSN, PRP, WIT, UNI, INT, ABS)
# state[12:17] = Kosha activations (MATERIAL, VITAL, MENTAL, INTELLECTUAL, BLISSFUL)
# state[17:22] = Vritti activations (FACT, ERROR, IMAGINATION, VOID, MEMORY)
# state[22:28] = Guna activations (LUCIDITY, ACTIVITY, STABILITY, VELOCITY, ACCEL, STABLE)
# state[28:32] = Reserved (Toroidal feedback)
```

**✅ Implementation:**

Located in `symbolu/inference/sovereign_state_monitor.py`:

- **`SovereignStateMonitor`**: Real-time 32D state monitoring
- **`SovereignStateMetrics`**: Comprehensive state analysis dataclass
- **`DepthLevel`** and **`ReliabilityLevel`** enums

```python
from symbolu.inference import SovereignStateMonitor, SovereignStateMetrics

monitor = SovereignStateMonitor(
    warn_thresholds={
        'error_risk': 0.5,
        'turbulence': 0.8,
        'low_lucidity': 0.2,
    }
)

# Analyze a state tensor
metrics = monitor.analyze_state(state)  # [B, 32] or [32]

# Bhava analysis (12 Ontological Aspects)
print(f"Dominant Bhava: {metrics.dominant_bhava}")  # e.g., 'COG'
print(f"Bhava entropy: {metrics.bhava_entropy:.2f}")

# Kosha analysis (Depth level)
print(f"Depth: {metrics.depth_level.name}")  # MATERIAL/VITAL/MENTAL/INTELLECTUAL/BLISSFUL
print(f"Depth confidence: {metrics.depth_confidence:.2f}")

# Vritti analysis (Reliability)
print(f"Reliability: {metrics.vritti_dominant.name}")  # FACT/ERROR/IMAGINATION/VOID/MEMORY
print(f"Fact confidence: {metrics.fact_confidence:.2f}")
print(f"Error risk: {metrics.error_risk:.2f}")
if metrics.error_risk > 0.5:
    print("⚠️ High hallucination risk!")

# Guna dynamics
print(f"Lucidity: {metrics.lucidity:.2f}")
print(f"Turbulence: {metrics.turbulence:.2f}")
print(f"Stability: {metrics.stability:.2f}")

# Aggregate scores
print(f"Coherence: {metrics.coherence_estimate:.2f}")
print(f"Reliability score: {metrics.reliability_score:.2f}")

# Track trajectory
trajectory = monitor.get_state_trajectory()
print(f"Depth progression: {monitor.get_depth_progression()}")
print(f"Bhava sequence: {monitor.get_bhava_sequence()}")
print(f"Reliability trend: {monitor.get_reliability_trend()}")

# Get warnings
for warning in monitor.get_warnings():
    print(f"Warning: {warning['type']} (value={warning['value']:.2f})")
```

**Files Created:**
- ✅ `symbolu/inference/sovereign_state_monitor.py`

#### 9.2.4 Intent Phase Projection ✅ IMPLEMENTED

**Training Behavior (V11.0.0: 12D input):**
```python
# IntentPhaseProjector: ΔBhava[12D] → θ[H] or θ[H, D_h]
# V11.0.0: defaults to PHASE_STATE_DIM=12 (Bhava-only), not full 32D
self.intent_projector = IntentPhaseProjector(
    state_dim=12,  # V11.0.0: PHASE_STATE_DIM
    num_heads=num_heads,
    head_dim=head_dim,
    project_per_head_dim=project_per_head_dim,
)

intent_phase = self.intent_projector(delta_bhava)  # 12D → θ
```

**✅ Implementation:**

```python
# Access intent phase during generation
output, meta = engine.generate_with_ontology(
    input_ids,
    track_trajectory=True,
)

# Intent phase trajectory
for intent in meta['intent_phase_trajectory']:
    print(f"Intent shape: {intent.shape}")  # [B, H] or [B, H, D_h]

# Get current engine state
state = engine.get_current_state()  # [B, 32]
metrics = engine.get_state_metrics()  # SovereignStateMetrics
```

### 9.3 Important Gaps (Priority 2)

#### 9.3.1 OntologicalBindingAnnotator ✅ IMPLEMENTED

**Training Behavior:**
```python
# Computes binding salience from hidden + sovereign state
# CSR/Kosha/SRK act as SELECTORS (semantics), not attention modifiers
self.binding_annotator = OntologicalBindingAnnotator(
    embed_dim=embed_dim,
    state_dim=32,
    num_heads=num_heads,
    use_csr=True,      # CSR phonological grounding
    use_kosha=True,    # Depth-based selection
    use_srk=True,      # Sovereignty signals
)

binding_salience = self.binding_annotator(
    hidden_states=hidden,
    sovereign_state=state,
    kosha_activations=state[:, 12:17],
    csr_mask=csr_mask,
)
```

**✅ Implementation:**

```python
# Configure binding annotator components
engine.set_annotator_config(
    use_csr=True,    # Enable CSR phonological grounding
    use_kosha=True,  # Enable depth-based selection
    use_srk=False,   # Disable Sovereignty signals
)

# Config via OntologicalBindingCacheInferenceConfig
config = OntologicalBindingCacheInferenceConfig(
    use_csr_annotation=True,
    use_kosha_annotation=True,
    use_srk_annotation=True,
)
engine = OntologicalBindingCacheInferenceEngine(model, config)
```

#### 9.3.2 External Delta State Injection ✅ IMPLEMENTED

**Training Behavior:**
```python
# Support for external state delta (e.g., from multi-turn context)
def forward(self, input_ids, ..., external_delta_S=None):
    if external_delta_S is not None:
        delta_S = external_delta_S
```

**✅ Implementation:**

```python
# Inject external delta for multi-turn context
external_delta = compute_delta_from_context(conversation_history)
engine.set_external_delta(external_delta)  # [B, 32]

# Generation will use this delta
output, meta = engine.generate_with_ontology(input_ids)

# Clear when done
engine.clear_external_delta()

# Enable external delta usage via config
config = OntologicalBindingCacheInferenceConfig(
    use_external_delta=True,
)
```

#### 9.3.3 CSR Mask Integration ✅ IMPLEMENTED

**Training Behavior:**
```python
# CSR content word mask for phonological grounding
binding_salience = self.binding_annotator(
    ...,
    csr_mask=csr_mask,  # [B, N] content word positions
)
```

**✅ Implementation:**

```python
# Provide CSR mask during generation
csr_mask = compute_csr_mask(input_ids)  # [B, T]

output, meta = engine.generate_with_ontology(
    input_ids,
    csr_mask=csr_mask,  # Will be auto-extended for new tokens
)
```

### 9.4 Enhancement Gaps (Priority 3)

#### 9.4.1 Built-in Generate Method ✅ ENHANCED

**Training Behavior:**
```python
# phase_transformer.py:4049-4070
def generate(self, input_ids, max_new_tokens=50, temperature=1.0, top_k=50):
    """Generation with Ontological state tracking."""
    self.prev_state = None
    for _ in range(max_new_tokens):
        result = self(input_ids, reset_state=(self.prev_state is None))
        logits = result['logits'][:, -1, :]
        ...
```

**✅ Implementation:**

The `OntologicalBindingCacheInferenceEngine.generate_with_ontology()` method provides:
- Full callback support for token-by-token monitoring
- Trajectory tracking for state, delta, and intent phase
- Warning detection and reliability assessment
- Integration with InferenceManager for karma/metacognition/gunas

```python
def on_token(token_id, step_meta):
    print(f"Step {step_meta['step']}: token={token_id}, prob={step_meta['prob']:.3f}")
    if step_meta['metrics'] and step_meta['metrics'].error_risk > 0.5:
        print("  ⚠️ High error risk!")

output, meta = engine.generate_with_ontology(
    input_ids,
    on_token_callback=on_token,
    track_trajectory=True,
)
```

#### 9.4.2 State Persistence Across Conversations ✅ IMPLEMENTED

**✅ Implementation:**

```python
# Save state between sessions
engine.save_state_to_file("session_state.pt")

# Load state in new session
engine = OntologicalBindingCacheInferenceEngine(model)
engine.load_state_from_file("session_state.pt")

# Continue generation with previous state
output, meta = engine.generate_with_ontology(
    input_ids,
    reset_state=False,  # Use loaded state
)

# Manual state management
state_dict = engine.get_state()  # Serializable dict
# ... save to database, send over network, etc.
engine.load_state(state_dict)  # Restore later
```

---

## 10. Phase 5: Implementation Roadmap (✅ COMPLETE)

### 10.1 Phase 5a: Model Recognition ✅ COMPLETE

| Task | Priority | Status | Files |
|------|----------|--------|-------|
| Add `binding_cache` to `generate_sovereign.py` | P0 | ✅ Done | `generate_sovereign.py` |
| Add `ontological_binding_cache` to `generate_sovereign.py` | P0 | ✅ Done | `generate_sovereign.py` |
| Update `InferenceManager` auto-detection | P0 | ✅ Done | `symbolu/inference/manager.py` |
| Update checkpoint utilities for new models | P0 | ✅ Done | `symbolu/inference/checkpoint_utils.py` |

**Deliverables:**
- ✅ Modified `generate_sovereign.py` with model type detection
- ✅ Modified `symbolu/inference/manager.py` with architecture auto-detection
- ✅ Added `ArchitectureMode.BINDING_CACHE` and `ArchitectureMode.ONTOLOGICAL_BINDING_CACHE`

### 10.2 Phase 5b: BindingCacheTransformer Inference ✅ COMPLETE

| Task | Priority | Status | Files |
|------|----------|--------|-------|
| Create `BindingCacheInferenceEngine` | P1 | ✅ Done | `binding_cache_inference.py` |
| Implement proposal mode metrics access | P1 | ✅ Done | `binding_cache_inference.py` |
| Add intent phase injection support | P1 | ✅ Done | `IntentPhaseInferenceModule` |
| Add binding salience control | P2 | ✅ Done | `BindingSalienceController` |
| Add enable_slots_read gating | P2 | ✅ Done | `set_enable_slots_read()` |
| Add Phase health monitoring | P2 | ✅ Done | `get_phase_health()` |
| Add cache instrumentation access | P3 | ✅ Done | `get_cache_instrumentation()` |
| Add ablation/rotation testing | P3 | ✅ Done | `set_ablation()`, `set_rotation()` |

**Deliverables:**
- ✅ `symbolu/inference/binding_cache_inference.py` (696 lines)
  - `BindingCacheInferenceConfig`
  - `IntentPhaseInferenceModule`
  - `BindingSalienceController`
  - `BindingCacheInferenceEngine`

### 10.3 Phase 5c: OntologicalBindingCacheTransformer Inference ✅ COMPLETE

| Task | Priority | Status | Files |
|------|----------|--------|-------|
| Create `OntologicalBindingCacheInferenceEngine` | P1 | ✅ Done | `ontological_binding_cache_inference.py` |
| Implement two-pass generation loop | P1 | ✅ Done | `generate_with_ontology()` |
| Add 32D Sovereign State tracking | P1 | ✅ Done | `_state_history`, `_delta_history` |
| Create `SovereignStateMonitor` | P1 | ✅ Done | `sovereign_state_monitor.py` |
| Add intent phase projection access | P2 | ✅ Done | `_intent_phase_history` |
| Add OntologicalBindingAnnotator control | P2 | ✅ Done | `set_annotator_config()` |
| Add external delta_S injection | P2 | ✅ Done | `set_external_delta()` |
| Add CSR mask integration | P2 | ✅ Done | `csr_mask` parameter |
| Add state persistence utilities | P3 | ✅ Done | `save_state_to_file()`, `load_state_from_file()` |

**Deliverables:**
- ✅ `symbolu/inference/ontological_binding_cache_inference.py` (542 lines)
  - `OntologicalBindingCacheInferenceConfig`
  - `OntologicalBindingCacheInferenceEngine`
- ✅ `symbolu/inference/sovereign_state_monitor.py` (507 lines)
  - `SOVEREIGN_STATE_DIM`, slices, and name constants
  - `DepthLevel` and `ReliabilityLevel` enums
  - `SovereignStateMetrics` dataclass
  - `SovereignStateMonitor` class

### 10.4 Phase 5d: InferenceManager Integration ✅ COMPLETE

| Task | Priority | Status | Files |
|------|----------|--------|-------|
| Add `ArchitectureMode.BINDING_CACHE` | P1 | ✅ Done | `layer_config.py` |
| Add `ArchitectureMode.ONTOLOGICAL_BINDING_CACHE` | P1 | ✅ Done | `layer_config.py` |
| Integrate engines with InferenceManager | P1 | ✅ Done | `manager.py` |
| Add cognitive status line for new models | P2 | ✅ Done | `get_status_line()` |
| Update documentation | P3 | ✅ Done | This document |

**Deliverables:**
- ✅ Modified `symbolu/inference/manager.py`
  - Auto-detection of V10.0 architectures
  - `_initialize_v10_engines()` method
  - `generate_v10()` method routing
- ✅ Modified `symbolu/inference/layer_config.py`
  - `ArchitectureMode.BINDING_CACHE`
  - `ArchitectureMode.ONTOLOGICAL_BINDING_CACHE`
- ✅ Updated `symbolu/inference/__init__.py` with all V10.0 exports

### 10.5 Implementation Summary

| Phase | Status | Lines of Code | Key Components |
|-------|--------|---------------|----------------|
| 5a | ✅ Complete | ~200 | Model detection, ArchitectureMode enums |
| 5b | ✅ Complete | 696 | BindingCacheInferenceEngine, IntentPhaseInferenceModule, BindingSalienceController |
| 5c | ✅ Complete | 1,049 | OntologicalBindingCacheInferenceEngine, SovereignStateMonitor, SovereignStateMetrics |
| 5d | ✅ Complete | ~300 | Manager integration, status lines, routing |

**Total Phase 5 Implementation: ~2,245 lines of production code**

---

## Appendix C: V10.0 Model Comparison

| Feature | HybridPhaseTransformer | BindingCacheTransformer | OntologicalBindingCacheTransformer |
|---------|------------------------|-------------------------|-----------------------------------|
| Attention Complexity | O(n²) + O(n) | O(n) + O(nk) + O(nw) | O(n) + O(nk) + O(nw) |
| Phase Role | Mixed | Protected (validated) | Protected + Intent modulated |
| Memory Query | Full attention | Top-K cache | Top-K cache + Salience |
| Local Attention | No | Yes (syntax) | Yes (syntax) |
| Ontological State | No | No | 32D Sovereign State (V11.0.0: 3 planes) |
| Proposal Mode | No | Optional | No (uses delta_S instead) |
| Binding Salience | No | Optional | Required (CSR/Kosha/SRK) |
| Two-Pass | No | No | Yes (hidden → delta → intent) |
| Vritti Gate | No | No | ✅ V11.0.0 (hallucination gating) |
| Kosha Depth Control | No | No | ✅ V11.0.0 (depth-aware sampling) |
| Sovereign Bridge | No | No | ✅ V11.0.0 (tensor → agentic) |
| Inference Support | ✅ Complete | ✅ Complete | ✅ Complete (V11.0.0) |

---

## Appendix D: 32D Sovereign State Reference (V11.0.0)

```python
# From symbolu/phase_transformer.py
# V11.0.0 Three-Plane Separation:
#   Phase Plane:    [0:12]  → ΔBhava → IntentPhaseProjector → θ → attention rotation
#   Control Plane:  [12:28] → Kosha + Vritti + Guna → Sovereign Bridge → Agentic
#   Learning Plane: [28:32] → JEPA training-time feedback only (NOT consumed at inference)

SOVEREIGN_STATE_DIM = 32
PHASE_STATE_DIM = 12      # Bhava-only, feeds phase rotation
CONTROL_STATE_DIM = 16    # Kosha + Vritti + Guna, governance
LEARNING_STATE_DIM = 4    # JEPA, training-time only

# Bhava indices [0:12] - PHASE PLANE: Ontological Aspects
BHAVA_NAMES = [
    'POT',  # 0: Potential - latent possibility
    'IDN',  # 1: Identity - self-recognition
    'EXE',  # 2: Execution - action/manifestation
    'STR',  # 3: Structure - form/organization
    'COG',  # 4: Cognition - knowing/understanding
    'AGY',  # 5: Agency - will/intention
    'RSN',  # 6: Reason - logic/analysis
    'PRP',  # 7: Purpose - meaning/direction
    'WIT',  # 8: Witness - observation/awareness
    'UNI',  # 9: Unity - integration/wholeness
    'INT',  # 10: Intent - focused will
    'ABS',  # 11: Absolute - transcendent ground
]

# Sheath indices [12:17] - CONTROL PLANE: Depth Mapping
KOSHA_NAMES = [
    'MATERIAL',     # 12: Physicality/Syntax
    'VITAL',        # 13: Flow/Energy
    'MENTAL',       # 14: Semantics/Meaning
    'INTELLECTUAL', # 15: Pattern/Wisdom
    'BLISSFUL',     # 16: Unity/Integration
]

# State indices [17:22] - CONTROL PLANE: Reliability Mapping
VRITTI_NAMES = [
    'FACT',        # 17: Verified Truth
    'ERROR',       # 18: Hallucination
    'IMAGINATION', # 19: Conceptualization
    'VOID',        # 20: Null State
    'MEMORY',      # 21: Recall/Weights
]

# Qualia/Dynamics indices [22:28] - CONTROL PLANE: System Dynamics
GUNA_NAMES = [
    'LUCIDITY',  # 22: Clarity/Precision
    'ACTIVITY',  # 23: Dynamism/Turbulence
    'STABILITY', # 24: Inertia/Fixedness
    'VELOCITY',  # 25: Rate of state change
    'ACCEL',     # 26: Acceleration of change
    'STABLE',    # 27: Stability measure
]

# Reserved indices [28:32] - LEARNING PLANE: JEPA Feedback (training-only)
RESERVED_NAMES = ['VOID_0', 'VOID_1', 'VOID_2', 'VOID_3']
# V11.0.0: NOT consumed at inference — RESERVED_SLICE = slice(28, 32)
```

---

## 11. Phase 6: V11.0.0 Inference Filter Wiring (✅ IMPLEMENTED)

### 11.1 Overview: Training/Inference Filter Table

V11.0.0 separates the 32D Sovereign State into three planes and defines which filters are active at inference:

| Filter | Training | Inference | Implementation |
|--------|----------|-----------|----------------|
| **CSR** | Optional (soft) | **YES** | `CSRInferenceGuard` in `InferenceManager` (Phase 2, unchanged) |
| **Ontology** | YES | **Validate only** | `SovereignStateMonitor` observe-only invariant (Phase 5c, unchanged) |
| **JEPA** | YES (core) | **NO** | `RESERVED_SLICE = slice(28, 32)` explicitly excluded |
| **Kosha** | Optional | **YES** | Depth-aware top_k / temperature via Sovereign Bridge |
| **Vritti** | NO | **YES (CRITICAL)** | Hallucination gating via Sovereign Bridge signals |

### 11.2 Three-Plane Dimensional Separation

```
32D Sovereign State
├── Phase Plane    [0:12]   12D Bhava → ΔBhava → IntentPhaseProjector → θ → attention
├── Control Plane  [12:28]  16D Kosha[5] + Vritti[5] + Guna[6] → Sovereign Bridge → Agentic
└── Learning Plane [28:32]   4D Reserved/JEPA → training-time only (inference-excluded)
```

**Key principle:** The Phase Plane feeds attention rotation (model-internal). The Control Plane feeds governance signals via Sovereign Bridge (inference-active). The Learning Plane is explicitly NOT consumed at inference.

### 11.3 Sovereign Bridge (`sovereign_bridge.py`) ✅ IMPLEMENTED

The Sovereign Bridge converts tensor-level Control Plane signals into agentic framework signals:

```
Control Plane [12:28]
├── Vritti [17:22] → ConfidenceSignals (quality_score, prediction_reversal_risk, emptiness_index)
├── Kosha  [12:17] → BudgetSignals (depth_complexity, processing_completeness)
└── Guna   [22:28] → StabilitySignals (state_volatility, directional_confidence)
```

**File:** `symbolu/agentic_framework/sovereign_bridge.py`

**Key functions:**
- `signals_from_sovereign_state(state, delta_S, batch_idx)` → `ConfidenceSignals`
- `coherence_from_sovereign_state(state, delta_S, batch_idx)` → `CoherenceState`

**Usage in inference engine:**
```python
# After state tracking, before token sampling
bridge_signals = signals_from_sovereign_state(
    current_state, delta_S, batch_idx=0,
)
# bridge_signals.quality_score        → [0, 1] factual confidence
# bridge_signals.prediction_reversal_risk → [0, 1] hallucination risk
# bridge_signals.emptiness_index       → [0, 1] void/disengagement
```

**Tests:** 19 tests in `symbolu/agentic_framework/tests/test_sovereign_bridge.py`

### 11.4 Vritti Gate (CRITICAL) ✅ IMPLEMENTED

The Vritti gate is the hallucination-detection mechanism at inference. It monitors `prediction_reversal_risk` (derived from VIPARYAYA activation) and `quality_score` (derived from PRAMANA activation) to intervene during token sampling.

**Logic:**
```
IF reversal_risk > vritti_error_resample_threshold (default 0.5):
    → cool_resample: set effective_temperature = vritti_resample_temperature (0.5)
    → This sharpens the distribution to reduce hallucination risk

ELIF quality_score < vritti_low_quality_threshold (default 0.25):
    → boost_diversity: set effective_temperature = min(temperature * 1.2, 1.5)
    → This broadens the distribution to escape low-quality modes
```

**Configuration:**
```python
OntologicalBindingCacheInferenceConfig(
    enable_vritti_gate=True,                    # Master switch
    vritti_error_resample_threshold=0.5,         # VIPARYAYA above this → resample
    vritti_low_quality_threshold=0.25,           # quality below this → boost diversity
    vritti_resample_temperature=0.5,             # cooler temperature for resampling
    vritti_max_resamples=2,                      # max resamples per token
)
```

**Metadata exposed:**
- `meta['vritti_gate_events']`: List of `{step, type, reversal_risk, quality, new_temp}`
- `meta['vritti_gate_count']`: Total interventions

### 11.5 Kosha Depth Control ✅ IMPLEMENTED

Kosha depth control adjusts sampling parameters based on which consciousness sheath is dominant, allowing the model to adapt its generation strategy to the depth of processing.

**Logic:**
```
MATERIAL (kosha_argmax == 0):
    → Surface processing: broaden top_k by kosha_surface_top_k_boost (default +20)
    → Encourages exploring more tokens for surface-level content

INTELLECTUAL (kosha_argmax == 3):
    → Deep reasoning: sharpen temperature by kosha_intellectual_temp_scale (default 0.85x)
    → Focuses the distribution for precise analytical output
```

**Configuration:**
```python
OntologicalBindingCacheInferenceConfig(
    enable_kosha_depth_control=True,             # Master switch
    kosha_surface_top_k_boost=20,                # Extra top_k at MATERIAL depth
    kosha_intellectual_temp_scale=0.85,           # Temperature scale at INTELLECTUAL depth
)
```

**Metadata exposed:**
- `meta['kosha_depth_events']`: List of `{step, dominant_kosha, adjustment_type, value}`
- `meta['kosha_depth_adjustments']`: Total adjustments

### 11.6 JEPA Exclusion ✅ IMPLEMENTED

The Learning Plane `[28:32]` is explicitly excluded from inference consumption:

```python
RESERVED_SLICE = slice(28, 32)  # JEPA/Learning plane — inference-excluded
```

This is documented in both the engine module docstring and the `SovereignStateMonitor` docstring. The `SovereignStateMonitor` tracks these dimensions for observability but they do not influence token generation.

### 11.7 InferenceManager Return Dict Updates ✅ IMPLEMENTED

The `InferenceManager.generate_v10()` return dict now includes V11.0.0 signals:

```python
{
    # ... existing fields ...
    # V11.0.0 Sovereign Bridge signals
    'bridge_signals': engine_meta.get('final_bridge_signals'),   # ConfidenceSignals
    'coherence': engine_meta.get('final_coherence'),             # CoherenceState
    'vritti_gate_count': engine_meta.get('vritti_gate_count', 0),
    'kosha_depth_adjustments': engine_meta.get('kosha_depth_adjustments', 0),
}
```

### 11.8 Implementation Roadmap

| Task | Priority | Status | Files |
|------|----------|--------|-------|
| Create Sovereign Bridge | P0 | ✅ Done | `symbolu/agentic_framework/sovereign_bridge.py` |
| Wire Vritti gate into inference engine | P0 | ✅ Done | `ontological_binding_cache_inference.py` |
| Wire Kosha depth control into inference engine | P1 | ✅ Done | `ontological_binding_cache_inference.py` |
| Exclude JEPA at inference | P1 | ✅ Done | `ontological_binding_cache_inference.py` |
| Update SovereignStateMonitor docstrings | P2 | ✅ Done | `sovereign_state_monitor.py` |
| Expose bridge signals in InferenceManager | P2 | ✅ Done | `manager.py` |
| Write bridge tests | P1 | ✅ Done | `test_sovereign_bridge.py` (19 tests) |

**Deliverables:**
- ✅ `symbolu/agentic_framework/sovereign_bridge.py` — Bridge: tensor → agentic signals
- ✅ `symbolu/agentic_framework/tests/test_sovereign_bridge.py` — 19 tests
- ✅ Modified `symbolu/inference/ontological_binding_cache_inference.py` — Vritti gate + Kosha depth + Bridge
- ✅ Modified `symbolu/inference/sovereign_state_monitor.py` — V11.0.0 docstrings
- ✅ Modified `symbolu/inference/manager.py` — Bridge signal pass-through in return dict

### 11.9 Data Flow Diagram

```
                    OntologicalBindingCacheInferenceEngine
                    ──────────────────────────────────────
                    FOR each token step:

                    ┌─────────────────────────────────────────┐
                    │  Two-Pass Forward                        │
                    │  Pass 1: hidden (no intent)              │
                    │  → compute_state_delta() → 3-tuple       │
                    │    state[32D], delta_S[32D], delta_bhava  │
                    │  → IntentPhaseProjector(delta_bhava[12D]) │
                    │  Pass 2: logits (with intent + salience) │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────┐
                    │  Sovereign Bridge                        │
                    │  signals_from_sovereign_state(           │
                    │      state, delta_S, batch_idx=0)        │
                    │  → ConfidenceSignals                     │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────┐
                    │  VRITTI GATE (CRITICAL)                   │
                    │  reversal_risk > 0.5 → cool_resample     │
                    │  quality < 0.25     → boost_diversity    │
                    │  → effective_temperature                 │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────┐
                    │  KOSHA DEPTH CONTROL                     │
                    │  MATERIAL    → broaden top_k (+20)       │
                    │  INTELLECTUAL → sharpen temp (×0.85)     │
                    │  → effective_top_k, effective_temperature │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────┐
                    │  Token Sampling                           │
                    │  top_k → top_p → temperature → softmax   │
                    │  → next_token                            │
                    └─────────────────────────────────────────┘
```

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 5.0 | 2026-02-09 | Claude | **Phase 6 COMPLETE**: V11.0.0 inference filter wiring — Vritti gate (CRITICAL), Kosha depth control, Sovereign Bridge integration, JEPA exclusion. Three-plane dimensional separation documented. Updated Appendix D with plane labels. |
| 4.0 | 2026-01-20 | Claude | **Phase 5 COMPLETE**: Implemented `BindingCacheInferenceEngine`, `OntologicalBindingCacheInferenceEngine`, `SovereignStateMonitor`. Full V10.0 model support in `generate_sovereign.py` and `InferenceManager`. ~2,245 lines of production code added. |
| 3.0 | 2026-01-20 | Claude | **V10.0 Gap Analysis**: Added Phase 5 for BindingCacheTransformer and OntologicalBindingCacheTransformer, new sections 8-10, implementation roadmap |
| 2.3 | 2026-01-06 | Claude | Phase 4 COMPLETE: `generate_sovereign.py` CLI, `generate_full_sequence()` implemented |
| 2.2 | 2026-01-05 | Claude | Phase 4 specification added (BLOCKED awaiting training), `generate_full_sequence()` documented |
| 2.1 | 2026-01-05 | Claude | Priority 3 enhancements complete: LayerInferenceConfig, checkpoint utilities, 3-way coherence |
| 2.0 | 2026-01-05 | Claude | Full implementation complete (Phases 1-3), added Usage Guide |
| 1.0 | 2026-01-05 | Claude | Initial comprehensive gap analysis |

