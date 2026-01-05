# Inference vs Training Gaps: Hybrid Transformer Logic

**Document Version:** 1.0
**Date:** January 2026
**Status:** Active Gap Analysis
**Related File:** `train_unified_llm.py` (V9.5.2)

---

## Executive Summary

This document comprehensively catalogs the gaps between the training-time logic implemented in `train_unified_llm.py` and the inference-time behavior of the hybrid transformer models. Many sophisticated training components—designed to improve model quality and cognitive coherence—are not utilized during inference, potentially leaving significant capabilities on the table.

---

## Table of Contents

1. [Critical Gaps (Priority 1)](#1-critical-gaps-priority-1)
2. [Important Gaps (Priority 2)](#2-important-gaps-priority-2)
3. [Enhancement Gaps (Priority 3)](#3-enhancement-gaps-priority-3)
4. [Implementation Roadmap](#4-implementation-roadmap)
5. [Architecture Considerations](#5-architecture-considerations)

---

## 1. Critical Gaps (Priority 1)

### 1.1 Evolutionary Bridge (O12→O1 Karma Transfer)

**Training Behavior:**
The `EvolutionaryBridge` class (`train_unified_llm.py:373-538`) implements toroidal state persistence where the final hidden state from O12 (Absolving layer) is projected and stored as a "karma buffer" to seed O1 (Potential layer) in the next sequence.

```python
# Training: Karma buffer enables cross-sequence intelligence
evolutionary_bridge.store_harvest(harvest=o12_hidden, global_step=step)
seed = evolutionary_bridge.retrieve_seed()  # For next sequence
```

**Inference Behavior:**
The `generate_sample()` function (`train_unified_llm.py:5605-5724`) and `HybridPhaseTransformer.generate()` method (`symbolu/phase_transformer.py:1793-1810`) perform simple autoregressive decoding with no state carryover between sequences.

**Gap Impact:**
- Loss of cognitive continuity across context windows
- No "memory" of previous conversations/sequences
- Recursive intelligence pattern is broken

**Implementation Recommendation:**

```python
# Priority: HIGH
# Effort: Medium (2-3 days)
# Location: Create inference/evolutionary_inference.py

class EvolutionaryInferenceEngine:
    """Inference-time evolutionary state management."""

    def __init__(self, model, bridge_checkpoint_path: str = None):
        self.model = model
        self.karma_buffer = None
        self.bridge = self._load_bridge(bridge_checkpoint_path)

    def _load_bridge(self, path):
        """Load trained EvolutionaryBridge weights."""
        # Load seed_gate, seed_proj, seed_norm from checkpoint
        pass

    def generate_with_karma(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 128,
        inject_karma: bool = True,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Generate with evolutionary state injection.

        1. If karma_buffer exists, inject into initial hidden state
        2. Generate tokens
        3. Extract O12 hidden state and store as new karma
        """
        # Step 1: Inject previous karma into embeddings
        if inject_karma and self.karma_buffer is not None:
            # Add karma to initial embedding (at O1 position)
            hidden_0 = self.karma_buffer * self.resonance_alpha

        # Step 2: Forward pass with hidden state extraction
        outputs = self.model(input_ids, return_hidden=True)

        # Step 3: Store harvest for next sequence
        o12_hidden = outputs['hidden_states'][-1]  # Last layer
        self.karma_buffer = self.bridge.compute_seed(o12_hidden.mean(dim=1))

        return outputs['logits'], {'karma_coherence': self._compute_coherence()}
```

**Files to Modify:**
- Create: `symbolu/inference/evolutionary_inference.py`
- Modify: `symbolu/phase_transformer.py` - Add `return_hidden=True` support to all model variants
- Modify: `generate_sample()` to optionally use `EvolutionaryInferenceEngine`

---

### 1.2 Delayed Resonance Injection

**Training Behavior:**
The `EvolutionaryIntelligenceEngine.apply_delayed_resonance()` method (`train_unified_llm.py:1513-1558`) injects previous step's O12 state into current O1 with Guna-scaled alpha:

```python
# Training: Dynamic alpha based on Sattva/Rajas/Tamas
dynamic_alpha = self.resonance_alpha * (1.0 + (s * 1.5) - (r * 0.5))
current_states[0] = o1_current + (dynamic_alpha * o12_prev)
```

**Inference Behavior:**
No resonance injection occurs during generation.

**Gap Impact:**
- Tokens generated without benefit of accumulated cognitive state
- Long-range coherence may suffer in multi-turn conversations

**Implementation Recommendation:**

```python
# Priority: HIGH
# Effort: Low (1 day)
# Location: Extend EvolutionaryInferenceEngine

def apply_inference_resonance(
    self,
    current_hidden: torch.Tensor,
    alpha: float = 0.1,
) -> torch.Tensor:
    """
    Apply resonance from stored karma to current hidden state.

    For inference, use fixed alpha (no Guna tracking available).
    Consider: User-configurable "memory strength" parameter.
    """
    if self.karma_buffer is None:
        return current_hidden

    # Reshape karma to match current hidden
    karma_expanded = self.karma_buffer.unsqueeze(1).expand_as(current_hidden)

    # Inject with fixed alpha (could expose as generation parameter)
    return current_hidden + (alpha * karma_expanded)
```

---

### 1.3 Hidden State Extraction for Ontological Models

**Training Behavior:**
The `HiddenStateExtractor` class (`train_unified_llm.py:1291-1427`) uses forward hooks to capture hidden states from all 12 layers, enabling:
- Evolutionary flow processing
- CSR safety layer integration
- Coherence loss computation

**Inference Behavior:**
The `HybridPhaseTransformer.forward()` method supports `return_hidden=True` but only returns the final hidden state list, not intermediate layer outputs in a hook-based manner.

**Gap Impact:**
- Cannot compute layer-wise coherence metrics at inference
- Cannot apply CSR safety layers during generation
- Cannot monitor ontological health during inference

**Implementation Recommendation:**

```python
# Priority: HIGH
# Effort: Medium (2 days)
# Location: symbolu/inference/state_extractor.py

class InferenceStateExtractor:
    """
    Lightweight hidden state extraction for inference.

    Unlike training HiddenStateExtractor which uses hooks,
    this modifies the forward pass to return states efficiently.
    """

    def __init__(self, model: nn.Module, layers_to_extract: List[int] = None):
        """
        Args:
            model: The transformer model
            layers_to_extract: Specific layer indices to extract (None = all)
                             For efficiency, extract only [0, 5, 11] (O1, mid, O12)
        """
        self.model = model
        self.layers_to_extract = layers_to_extract or list(range(12))

    def forward_with_states(
        self,
        input_ids: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[int, torch.Tensor]]:
        """
        Forward pass that efficiently extracts specified layer states.

        Returns:
            logits: Model output logits
            layer_states: Dict mapping layer_idx -> hidden state
        """
        # Implementation requires model modification to return intermediates
        # OR use gradient checkpointing infrastructure to cache states
        pass
```

**Recommended Approach:**
1. Modify `HybridPhaseTransformer.forward()` to accept `extract_layers: List[int]` parameter
2. Only extract specified layers to minimize memory overhead
3. Default to extracting O1 and O12 only for karma/resonance purposes

---

## 2. Important Gaps (Priority 2)

### 2.1 Metacognitive Tracking

**Training Behavior:**
The `MetacognitiveTracker` class (`train_unified_llm.py:666-825`) monitors:
- Coherence history and alarms
- Guna state (Sattva/Rajas/Tamas)
- Evolutionary velocity
- Generates recommendations: BRAKE, SLOW_DOWN, RECOVER, ACCELERATE, STABILIZE, CONTINUE

**Inference Behavior:**
No metacognitive monitoring during generation.

**Gap Impact:**
- Cannot detect when generation quality is degrading
- Cannot adaptively adjust generation parameters
- No early warning for incoherent outputs

**Implementation Recommendation:**

```python
# Priority: MEDIUM
# Effort: Medium (2-3 days)
# Location: symbolu/inference/metacognitive_monitor.py

class InferenceMetacognition:
    """
    Real-time generation quality monitoring.

    Tracks coherence signals and can signal when generation
    should be aborted, restarted, or parameters adjusted.
    """

    def __init__(
        self,
        coherence_window: int = 10,
        alarm_threshold: float = 0.3,
    ):
        self.coherence_history = []
        self.alarm_threshold = alarm_threshold
        self.coherence_window = coherence_window

    def update(
        self,
        token_logits: torch.Tensor,
        hidden_state: torch.Tensor = None,
    ) -> Dict[str, Any]:
        """
        Update metacognitive state with new generation step.

        Computes:
        - Entropy of token distribution (proxy for confidence)
        - Optional: Hidden state coherence with previous

        Returns recommendation for generation control.
        """
        # Compute token entropy
        probs = F.softmax(token_logits, dim=-1)
        entropy = -(probs * torch.log(probs + 1e-10)).sum().item()

        # Normalize to [0, 1] range (vocab_size dependent)
        normalized_entropy = entropy / math.log(token_logits.shape[-1])

        # Track as proxy for coherence (lower entropy = higher confidence)
        coherence_proxy = 1.0 - normalized_entropy
        self.coherence_history.append(coherence_proxy)

        # Check for alarm conditions
        if len(self.coherence_history) >= 3:
            recent = self.coherence_history[-3:]
            if all(c < self.alarm_threshold for c in recent):
                return {
                    "recommendation": "ABORT",
                    "reason": "Coherence dropped below threshold for 3 consecutive tokens",
                    "coherence": coherence_proxy,
                }

        return {
            "recommendation": "CONTINUE",
            "coherence": coherence_proxy,
            "entropy": normalized_entropy,
        }

    def get_generation_adjustment(self) -> Dict[str, float]:
        """
        Suggest generation parameter adjustments based on state.

        Returns adjustments to temperature, top_p, etc.
        """
        if not self.coherence_history:
            return {}

        avg_coherence = sum(self.coherence_history[-10:]) / min(10, len(self.coherence_history))

        if avg_coherence < 0.3:
            # Low coherence: reduce temperature for more deterministic outputs
            return {"temperature_multiplier": 0.7, "top_p_adjustment": -0.1}
        elif avg_coherence > 0.8:
            # High coherence: can afford more creativity
            return {"temperature_multiplier": 1.1, "top_p_adjustment": 0.05}

        return {}
```

---

### 2.2 Training Gunas (Sattva/Rajas/Tamas)

**Training Behavior:**
The `TrainingGunas` class (`train_unified_llm.py:3440-3539`) computes cognitive state from training dynamics:
- **Sattva (Clarity):** coherence × (1 - entropy)
- **Rajas (Action):** normalized gradient activity
- **Tamas (Inertia):** loss velocity stagnation

**Inference Behavior:**
No Guna computation during generation.

**Gap Impact:**
- Cannot characterize generation "quality mode"
- Cannot adjust behavior based on cognitive state
- Resonance alpha cannot be dynamically scaled (uses fixed value)

**Implementation Recommendation:**

```python
# Priority: MEDIUM
# Effort: Low (1 day)
# Location: symbolu/inference/guna_inference.py

class InferenceGunas:
    """
    Inference-time Guna approximation using available signals.

    Without gradients, we approximate:
    - Sattva: Token probability confidence × sequence coherence
    - Rajas: Token-to-token probability variance (activity)
    - Tamas: Repetition rate (inertia/stuckness)
    """

    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.token_probs = []
        self.generated_tokens = []

    def update(
        self,
        token_id: int,
        token_prob: float,
        top_probs: torch.Tensor = None,
    ) -> Tuple[float, float, float]:
        """
        Update Guna state with new generated token.

        Returns (sattva, rajas, tamas) normalized to sum to 1.
        """
        self.token_probs.append(token_prob)
        self.generated_tokens.append(token_id)

        # Keep window
        if len(self.token_probs) > self.window_size:
            self.token_probs = self.token_probs[-self.window_size:]
            self.generated_tokens = self.generated_tokens[-self.window_size:]

        # Sattva: Average confidence (higher prob = clearer)
        sattva = sum(self.token_probs) / len(self.token_probs)

        # Rajas: Probability variance (activity/change)
        if len(self.token_probs) >= 2:
            mean_prob = sum(self.token_probs) / len(self.token_probs)
            variance = sum((p - mean_prob) ** 2 for p in self.token_probs) / len(self.token_probs)
            rajas = min(1.0, variance * 10)  # Scale variance to [0, 1]
        else:
            rajas = 0.33

        # Tamas: Repetition rate (stuckness)
        if len(self.generated_tokens) >= 3:
            unique_ratio = len(set(self.generated_tokens[-10:])) / min(10, len(self.generated_tokens))
            tamas = 1.0 - unique_ratio  # More repetition = higher tamas
        else:
            tamas = 0.33

        # Normalize to sum to 1
        total = sattva + rajas + tamas
        return sattva / total, rajas / total, tamas / total
```

---

### 2.3 CSR Safety Layers (EntropySink, SynthesisGate)

**Training Behavior:**
When enabled, CSR phoneme-ontological grounding applies:
- `EntropySink`: Absorbs high-entropy states to prevent divergence
- `SynthesisGate`: Controls information flow based on coherence

```python
# Training integration (train_unified_llm.py:6748-6767)
csr_provider, csr_entropy_sink, csr_synthesis_gate = create_csr_for_training(...)
```

**Inference Behavior:**
CSR layers are not applied during generation.

**Gap Impact:**
- Generation may produce high-entropy (incoherent) sequences without intervention
- No phoneme-ontological grounding during output
- Safety constraints trained into model not enforced at inference

**Implementation Recommendation:**

```python
# Priority: MEDIUM-HIGH
# Effort: Medium (2-3 days)
# Location: symbolu/inference/csr_inference.py

class CSRInferenceGuard:
    """
    Apply CSR safety layers during inference.

    Monitors generation entropy and can:
    1. Flag high-entropy tokens for review
    2. Apply synthesis gating to hidden states
    3. Optionally reject/resample tokens exceeding entropy threshold
    """

    def __init__(
        self,
        entropy_sink: 'EntropySink',
        synthesis_gate: 'SynthesisGate',
        entropy_threshold: float = 2.0,  # Log-entropy threshold
    ):
        self.entropy_sink = entropy_sink
        self.synthesis_gate = synthesis_gate
        self.entropy_threshold = entropy_threshold

    def check_and_gate(
        self,
        hidden_state: torch.Tensor,
        token_logits: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Apply CSR safety checks to generation step.

        Args:
            hidden_state: Current hidden state [B, D]
            token_logits: Logits for next token [B, V]

        Returns:
            gated_logits: Possibly modified logits
            safety_info: Dict with entropy, gate values, warnings
        """
        # Compute token entropy
        probs = F.softmax(token_logits, dim=-1)
        entropy = -(probs * torch.log(probs + 1e-10)).sum(dim=-1)

        # Apply entropy sink if threshold exceeded
        if entropy.max().item() > self.entropy_threshold:
            # Sink absorbs high-entropy energy
            hidden_state = self.entropy_sink(hidden_state, entropy_level=entropy.mean())

            # Re-project to logits with dampened hidden state
            # (Requires access to lm_head - consider passing as parameter)

            return token_logits, {
                "entropy": entropy.mean().item(),
                "sink_activated": True,
                "warning": "High entropy detected - sink applied",
            }

        # Apply synthesis gate for coherence control
        gate_value = self.synthesis_gate.compute_gate(hidden_state)

        return token_logits, {
            "entropy": entropy.mean().item(),
            "gate_value": gate_value.mean().item(),
            "sink_activated": False,
        }
```

---

### 2.4 Sovereign-1 Loss Components at Inference

**Training Behavior:**
Sovereign-1 loss (`train_unified_llm.py:6690-6703`) provides:
- Guna signal weighting
- S-Signal (referent) tracking
- R-Signal (ontology) enforcement
- C-Signal (phoneme) grounding

**Inference Behavior:**
No Sovereign-1 signal computation during generation.

**Gap Impact:**
- Cannot verify if generated tokens maintain ontological alignment
- No runtime check for Guna balance
- Coherence signals used for training not available for inference quality scoring

**Implementation Recommendation:**

```python
# Priority: MEDIUM
# Effort: Medium (2 days)
# Location: symbolu/inference/sovereign_scorer.py

class SovereignInferenceScorer:
    """
    Compute Sovereign-1 style signals during inference for quality scoring.

    Not used for loss/backprop, but for:
    1. Scoring generated sequences
    2. Detecting quality degradation
    3. Providing interpretable quality metrics
    """

    def __init__(self, sovereign_config: 'SovereignLossConfig'):
        self.config = sovereign_config
        self.r_matrix = SOVEREIGN_R_MATRIX  # From train_unified_llm.py

    def score_sequence(
        self,
        hidden_states: List[torch.Tensor],
        generated_tokens: torch.Tensor,
    ) -> Dict[str, float]:
        """
        Score a generated sequence using Sovereign-1 metrics.

        Returns interpretable quality scores:
        - guna_balance: How well Sattva/Rajas/Tamas are balanced
        - ontological_alignment: How well hidden states align with R-Matrix targets
        - coherence_score: Cross-layer coherence
        """
        scores = {}

        # Compute per-layer Vṛtti alignment
        if hidden_states:
            layer_alignments = []
            for i, hs in enumerate(hidden_states[:12]):  # Up to 12 layers
                target_vrtti = self.r_matrix[:, min(i, 11)]
                # Compute alignment (simplified - actual would use learned projections)
                layer_alignments.append(self._compute_vrtti_alignment(hs, target_vrtti))

            scores['ontological_alignment'] = sum(layer_alignments) / len(layer_alignments)

        # Compute token-level coherence
        if generated_tokens.numel() > 1:
            # Use bigram/trigram repetition as proxy for coherence
            tokens = generated_tokens.tolist()
            unique_bigrams = len(set(zip(tokens[:-1], tokens[1:])))
            total_bigrams = len(tokens) - 1
            scores['coherence_score'] = unique_bigrams / max(1, total_bigrams)

        return scores
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

## 4. Implementation Roadmap

### Phase 1: Core Inference Infrastructure (Week 1-2)

| Task | Priority | Effort | Dependency |
|------|----------|--------|------------|
| Create `EvolutionaryInferenceEngine` | P1 | 2-3 days | None |
| Add hidden state extraction to models | P1 | 2 days | None |
| Implement delayed resonance injection | P1 | 1 day | EvolutionaryInferenceEngine |

**Deliverables:**
- `symbolu/inference/evolutionary_inference.py`
- Modified `HybridPhaseTransformer.forward()` with layer extraction
- Unit tests for karma persistence

### Phase 2: Quality Monitoring (Week 3)

| Task | Priority | Effort | Dependency |
|------|----------|--------|------------|
| Create `InferenceMetacognition` | P2 | 2-3 days | None |
| Implement `InferenceGunas` | P2 | 1 day | None |
| Add CSR safety guard | P2 | 2-3 days | Hidden state extraction |

**Deliverables:**
- `symbolu/inference/metacognitive_monitor.py`
- `symbolu/inference/guna_inference.py`
- `symbolu/inference/csr_inference.py`
- Integration tests for quality monitoring

### Phase 3: Advanced Features (Week 4)

| Task | Priority | Effort | Dependency |
|------|----------|--------|------------|
| Sovereign inference scorer | P2 | 2 days | Hidden state extraction |
| Layer configuration | P3 | 0.5 days | None |
| Toroidal coherence metrics | P3 | 0.5 days | EvolutionaryInferenceEngine |
| Checkpoint metadata enhancement | P3 | 0.5 days | None |

**Deliverables:**
- `symbolu/inference/sovereign_scorer.py`
- `symbolu/inference/layer_config.py`
- Enhanced checkpoint format documentation

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

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-05 | Claude | Initial comprehensive gap analysis |

