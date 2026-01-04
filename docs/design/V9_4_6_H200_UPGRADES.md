# V9.4.6 Sovereign Intelligence Upgrades (H200 Deployment)

**Status**: PENDING - Awaiting H200 migration
**Target GPU**: NVIDIA H200 141GB
**Current Testing**: A100 80GB

---

## Overview

Four refinements to transform the "Stiff Ontological Skeleton" into a "Fluid Intelligent Agent" with self-correcting evolutionary trajectory.

---

## Upgrade #1: Elastic Resonance (Guna-Scaled Alpha)

**File**: `train_unified_llm.py`
**Location**: `EvolutionaryIntelligenceEngine.apply_delayed_resonance()` (~Line 1434)
**Risk**: Low
**Reward**: Context-aware memory retention

### Current Behavior
```python
# Static resonance_alpha = 0.1
current_states[0] = o1_current + (self.resonance_alpha * o12_prev)
```

### Proposed Change
```python
def apply_delayed_resonance(self, current_states: List[torch.Tensor]) -> List[torch.Tensor]:
    """
    V9.4.6: Elastic Resonance Update.
    Dynamically scales resonance_alpha based on Guna state (Sattva vs Rajas).
    """
    if self.resonance_buffer is None or len(self.resonance_buffer) == 0:
        return current_states

    # 1. Compute Dynamic Alpha based on Gunas
    s, r, t = self.current_gunas

    # Logic: Sattva increases retention; Rajas (error/heat) reduces it
    # Base is 0.1; range is [0.05, 0.25]
    dynamic_alpha = self.resonance_alpha * (1.0 + (s * 1.5) - (r * 0.5))
    dynamic_alpha = max(0.05, min(0.25, dynamic_alpha))

    # 2. Inject Layer 11 (O12) into Layer 0 (O1)
    if len(self.resonance_buffer) >= 12 and len(current_states) >= 1:
        o12_prev = self.resonance_buffer[11]
        o1_current = current_states[0]

        if o12_prev.shape == o1_current.shape:
            current_states[0] = o1_current + (dynamic_alpha * o12_prev)
        elif o12_prev.shape[-1] == o1_current.shape[-1]:
            if o12_prev.dim() == 3 and o1_current.dim() == 3:
                o12_avg = o12_prev.mean(dim=1, keepdim=True).expand_as(o1_current)
                current_states[0] = o1_current + (dynamic_alpha * o12_avg)

    # Log for monitoring
    self.last_dynamic_alpha = dynamic_alpha
    return current_states
```

### Monitoring
- Log `dynamic_alpha` value in training output
- Watch Toroidal Coherence: should remain >0.70

---

## Upgrade #2: PIDv2 Relaxation Sensitivity

**File**: `train_unified_llm.py`
**Location**: PIDv2 Governor logic (~Line 2200)
**Risk**: Low
**Reward**: Smoother 9:3 → 6:6 transition, reduced Integration Tax

### Current Behavior
- PIDv2 uses SNR-based dynamic Kp regardless of relaxation state
- Integration Tax is logged but not acted upon

### Proposed Change
```python
# In PIDv2 Governor update logic
def compute_authority_factor(self, coherence, snr, global_step, relaxation_controller=None):
    """
    V9.4.6: Context-aware Kp during post-relaxation period.
    """
    # Check if we're in post-relaxation recovery window
    in_recovery = False
    if relaxation_controller is not None:
        steps_since_swap = global_step - relaxation_controller.last_swap_step
        in_recovery = (0 < steps_since_swap <= 100)

    # Compute base Kp from SNR
    base_kp = self._compute_dynamic_kp(snr)

    # If in recovery AND derivative is positive (PPL rising), dampen Kp
    if in_recovery and self.ppl_derivative > 0:
        # Force minimum Kp to let sensory layers stabilize
        effective_kp = self.kp_min  # 0.15
        self.recovery_dampening_active = True
    else:
        effective_kp = base_kp
        self.recovery_dampening_active = False

    return effective_kp
```

### Monitoring
- Log `[PIDv2] Recovery dampening active` when triggered
- Watch Integration Tax: should reduce from ~10-15% to <5%

---

## Upgrade #3: Stochastic Gradient Persistence

**File**: `train_unified_llm.py`
**Location**: `EvolutionaryIntelligenceEngine.update_resonance_buffer()` (~Line 1470)
**Risk**: Medium (VRAM spike every 50 steps)
**Reward**: Recursive "meta-learning" - model learns to generate better seeds

### Requirements
- **H200 141GB required** - A100 80GB will OOM on persistence steps
- Expected VRAM spike: ~10-15GB every 50 steps

### Current Behavior
```python
def update_resonance_buffer(self, current_states: List[torch.Tensor]):
    # Always detach - no gradient flow
    self.resonance_buffer = [s.detach().clone() for s in current_states]
```

### Proposed Change
```python
def update_resonance_buffer(self, current_states: List[torch.Tensor], step: int = 0):
    """
    V9.4.6: Stochastic Gradient Persistence.
    Enables meta-learning by occasionally allowing gradients to flow back
    through the toroidal bridge.
    """
    persistence_interval = 50  # Every 50 steps
    is_persistence_step = (step % persistence_interval == 0) and (step > 0)

    if is_persistence_step:
        # DO NOT DETACH: Allow gradients to persist
        self.resonance_buffer = [s.clone() for s in current_states]
        self.persistence_active = True
    else:
        # STANDARD: Detach to prevent gradient explosion
        self.resonance_buffer = [s.detach().clone() for s in current_states]
        self.persistence_active = False
```

### Monitoring
- Log `[PERSISTENCE] Gradient flow enabled` on steps 50, 100, 150...
- Watch VRAM: expect ~10GB spike on those steps
- Watch Toroidal Coherence: should climb toward 0.82+

---

## Upgrade #4: Sensory Noise Injection (SNI)

**File**: `train_unified_llm.py`
**Location**: Training loop, after forward pass (~Line 6350)
**Risk**: Low
**Reward**: Breaks "city of the city" repetition loops

### Rationale
- Original proposal: `param.grad *= 2.0` - **rejected** (gradient explosion risk)
- Refined: Stochastic noise to hidden states - **accepted** (bounded, principled)
- Based on Simulated Annealing: provides "vibration" to escape local minima

### Proposed Change
```python
# V9.4.6: Sensory Noise Injection
# Add after forward pass, before loss computation

entropy_floor = 0.30  # Below this = repetitive loops detected

if metrics.get("onto_entropy", 1.0) < entropy_floor:
    # Inject tiny noise to sensory layer activations
    noise_scale = 1e-4

    # Get sensory layer indices (O10-O12 = layers 9-11)
    sensory_layer_indices = [9, 10, 11]

    for idx in sensory_layer_indices:
        if idx < len(hidden_states):
            hidden_states[idx] = hidden_states[idx] + \
                torch.randn_like(hidden_states[idx]) * noise_scale

    if global_step % config.log_every == 0:
        print(f"  [SNI] Low entropy ({metrics['onto_entropy']:.2f}) - injecting sensory noise")
```

### Why This Works
1. **Noise to state ≠ noise to gradient**: State perturbation is bounded
2. **Simulated Annealing principle**: Small perturbation helps escape local minima
3. **Targeted**: Only affects sensory layers (O10-O12), Authority spine (O1-O9) untouched
4. **Conservative scale**: 1e-4 is negligible compared to activation magnitudes

### Monitoring
- Log `[SNI] Low entropy - injecting sensory noise` when triggered
- Watch `onto_entropy`: should recover above 0.30 within 50-100 steps
- Quality samples: "city of the city" patterns should disappear

---

## Implementation Checklist

- [ ] #1 Elastic Resonance - implement after H200 migration
- [ ] #2 PIDv2 Relaxation Sensitivity - implement after H200 migration
- [ ] #3 Stochastic Gradient Persistence - **H200 ONLY** (OOM on A100)
- [ ] #4 Sensory Noise Injection - implement after H200 migration

---

## CLI Arguments to Add

```python
# V9.4.6 Elastic Resonance
parser.add_argument("--elastic_resonance", action="store_true",
                   help="Enable Guna-scaled resonance alpha (0.05-0.25)")

# V9.4.6 Stochastic Persistence
parser.add_argument("--stochastic_persistence", action="store_true",
                   help="Enable gradient flow through toroidal bridge every N steps")
parser.add_argument("--persistence_interval", type=int, default=50,
                   help="Steps between gradient persistence (requires H200)")

# V9.4.6 Sensory Noise Injection
parser.add_argument("--sensory_noise_injection", action="store_true",
                   help="Enable entropy-triggered noise injection to sensory layers")
parser.add_argument("--sni_entropy_floor", type=float, default=0.30,
                   help="Entropy threshold below which SNI activates")
parser.add_argument("--sni_noise_scale", type=float, default=1e-4,
                   help="Scale of injected noise")
```

---

## Expected Results (H200 + V9.4.6)

| Metric | Current (A100 V9.4.5) | Expected (H200 V9.4.6) |
|--------|----------------------|------------------------|
| Toroidal Coherence | 0.65-0.75 | 0.80+ |
| Integration Tax | 10-15% | <5% |
| Repetition Loops | Frequent | Rare |
| Quality Samples | "city of the city" | Fluent reasoning |
| Training Speed | ~45k tok/s | ~90k tok/s |

---

## References

- Gemini Analysis: V9.4.5 Audit (Jan 2026)
- Claude Evaluation: Risk assessment for A100 vs H200
- Simulated Annealing: Kirkpatrick et al., 1983
