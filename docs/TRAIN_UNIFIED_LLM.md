# Unified LLM Training Script V9.5

## Overview

The `train_unified_llm.py` script provides comprehensive training for Sovereign-1 models with support for:

- **SymbolU12 with Bhava**: Standard attention + 12D ontological + 144D Bhava
- **Phase Attention**: O(n) complexity attention mechanism
- **Hybrid Models**: Local + Phase attention combination
- **Gen 2**: Hierarchical Complex Bhava (3-tier phase rotation)

## Key Features (V9.5)

### Formula [1331] 9:3 Hierarchical Gradient Scaling

Prevents sensory over-dampening (S/A ratio = 0.00 issue) by applying differentiated gradient scaling:

- **Authority Layers (0-8)**: α = 1.0 (full gradient)
- **Sensory Layers (9-11)**: α = 0.1 → 0.7 (warmup over 500 steps)

Uses `register_hook` on parameters to ensure gradients are scaled BEFORE the optimizer sees them.

### Dynamic Relaxation Controller (9:3 → 6:6)

Monitors training stability and automatically relaxes the layer boundary:

```
StabilityIndex (SSI) = 0.7 × GC + 0.3 × (1 - Drift)
```

Where:
- **GC**: Guna Coherence (from dims 0-15 of 128D header)
- **Drift**: S-Signal drift magnitude

**Trigger Condition**: When 500-step rolling average of SSI ≥ 0.78

**Dampened Thaw**: Newly relaxed layers (6-8) start at α = 0.05 and ramp to 0.7 over 500 steps to prevent Rajasic Crash.

## Usage Examples

### Basic Ontological Training
```bash
python train_unified_llm.py \
    --model_type ontological \
    --model_size small \
    --dataset wikitext103 \
    --max_steps 10000
```

### Training with 9:3 Split
```bash
python train_unified_llm.py \
    --model_type ontological \
    --model_size large \
    --use_9_3_split \
    --authority_layers 9 \
    --sensory_layers 3 \
    --alpha_sens_initial 0.1 \
    --alpha_sens_max 0.7 \
    --controller pidv2 \
    --learning_rate 1e-4 \
    --batch_size 8 \
    --max_seq_len 2048 \
    --gradient_checkpointing \
    --dataset wikitext103 \
    --max_steps 20000
```

### Training with Dynamic Relaxation (9:3 → 6:6)
```bash
python train_unified_llm.py \
    --model_type ontological \
    --model_size large \
    --use_9_3_split \
    --authority_layers 9 \
    --sensory_layers 3 \
    --enable_dynamic_relaxation \
    --relaxation_mode average \
    --relaxation_stability_threshold 0.78 \
    --relaxation_target_authority 6 \
    --relaxation_target_sensory 6 \
    --controller pidv2 \
    --learning_rate 1e-4 \
    --batch_size 8 \
    --max_seq_len 2048 \
    --gradient_checkpointing \
    --dataset wikitext103 \
    --max_steps 20000
```

### Hybrid Model with Friction Controller
```bash
python train_unified_llm.py \
    --model_type hybrid \
    --model_size medium \
    --local_layers 6 \
    --controller pidv2 \
    --dataset wikitext103 \
    --max_steps 10000
```

## CLI Arguments

### Model Configuration
| Argument | Default | Description |
|----------|---------|-------------|
| `--model_type` | ontological | Model type: ontological, phase, hybrid, gen2 |
| `--model_size` | small | Model size: tiny, small, medium, large |
| `--max_seq_len` | 2048 | Maximum sequence length |

### Formula [1331] 9:3 Split
| Argument | Default | Description |
|----------|---------|-------------|
| `--use_9_3_split` | False | Enable 9:3 Authority/Sensory gradient split |
| `--authority_layers` | 9 | Number of authority layers (R-Signal focus) |
| `--sensory_layers` | 3 | Number of sensory layers (S-Signal focus) |
| `--alpha_sens_initial` | 0.1 | Initial sensory gradient multiplier |
| `--alpha_sens_max` | 0.7 | Maximum sensory gradient after warmup |

### Dynamic Relaxation
| Argument | Default | Description |
|----------|---------|-------------|
| `--enable_dynamic_relaxation` | False | Enable 9:3 → 6:6 transition |
| `--relaxation_mode` | average | Stability tracking: consecutive or average |
| `--relaxation_stability_threshold` | 0.78 | SSI threshold for relaxation |
| `--relaxation_streak_target` | 5 | Consecutive stable evals for consecutive mode |
| `--relaxation_target_authority` | 6 | Target authority layers after relaxation |
| `--relaxation_target_sensory` | 6 | Target sensory layers after relaxation |

### PIDv2 Controller
| Argument | Default | Description |
|----------|---------|-------------|
| `--controller` | none | Controller: none, pidv2, emergency_pd |
| `--pidv2_kp_min` | 0.10 | Minimum Kp (when noisy) |
| `--pidv2_kp_max` | 0.30 | Maximum Kp (when clean) |
| `--pidv2_a_min` | 0.30 | Minimum authority factor |
| `--pidv2_w_s` | 0.30 | Semantic weight (30% prompt-based) |

### Training
| Argument | Default | Description |
|----------|---------|-------------|
| `--batch_size` | 8 | Batch size per GPU |
| `--learning_rate` | 3e-4 | Peak learning rate |
| `--max_steps` | 10000 | Maximum training steps |
| `--gradient_checkpointing` | False | Enable gradient checkpointing |
| `--mixed_precision` | bf16 | Mixed precision: none, fp16, bf16 |

## Telemetry Output

The training script outputs detailed telemetry including:

```
Step   1000 | Loss: 4.2345 | PPL: 68.89 | LR: 3.00e-04 | Tok/s: 45678 | VRAM: 24.5GB | S/A: 0.35 α_s: 0.45
  --> Val Loss: 4.1234 | Val PPL: 61.89 | PIDv2: A=0.85 Kp=0.22 v=-0.12
  --> DRC: SSI_avg=0.81 | Split=9:3
```

Key metrics:
- **S/A**: Sensory/Authority gradient ratio (should be > 0)
- **α_s**: Current sensory gradient multiplier
- **SSI_avg**: Stability Index rolling average
- **Split**: Current Authority:Sensory layer split

## Troubleshooting

### Issue: S/A ratio = 0.00
**Cause**: Sensory layers receiving no gradients (over-dampened)
**Solution**: Enable 9:3 split with `--use_9_3_split`

### Issue: PPL stuck at high values (>50,000)
**Causes**:
1. Incorrect layer classification
2. Gradient explosion in authority layers
3. Insufficient learning rate

**Solutions**:
1. Verify model architecture matches layer pattern
2. Use `--controller pidv2` for adaptive control
3. Try `--learning_rate 1e-4` with warmup

### Issue: Relaxation streak keeps resetting
**Cause**: Stability Index fluctuating below threshold
**Solutions**:
1. Use `--relaxation_mode average` instead of consecutive
2. Lower threshold: `--relaxation_stability_threshold 0.75`
3. Increase window size (modify in code if needed)

### Issue: VRAM underutilized
**Solution**: Increase batch size or sequence length:
```bash
--batch_size 16 --max_seq_len 4096 --gradient_checkpointing
```

## Architecture

### Layer Classification
```
Layers 0-8 (Authority): Focus on R-Signal (dims 48-95)
  - Higher gradient weight (α = 1.0)
  - Learn "what things mean"

Layers 9-11 (Sensory): Focus on S-Signal (dims 16-47)
  - Lower initial gradient (α = 0.1)
  - Learn "what things are"

Embeddings: Classified as Sensory (grounding)
LM Head: Classified as Authority (meaning output)
```

### Gradient Hook Mechanism
```python
# Hooks are registered on all parameters
def hook(grad):
    if layer_type == "authority":
        return grad * 1.0
    elif layer_type == "sensory":
        return grad * alpha_sens  # Dynamically updated
    return grad
```

### Dampened Thaw (on 9:3 → 6:6 transition)
```
1. Relaxation triggered at SSI_avg >= 0.78
2. Layers 6-8 reclassified: Authority → Sensory
3. These layers start at α = 0.05 (very dampened)
4. α ramps to 0.7 over 500 steps
5. Prevents "Rajasic Crash" (volatility spike)
```

## Integration with PIDv2 Controller

The 9:3 split integrates seamlessly with PIDv2:

1. **Authority factor** from PIDv2 multiplies learning rate
2. **Gradient hooks** scale gradients before optimizer
3. **DRC** updates independently during evaluation
4. **Viparyaya safety valve** triggers on PPL spike >20%

Combined control flow:
```
loss.backward()
  ↓
Gradient Hooks (9:3 scaling)
  ↓
optimizer.step()
  ↓
HGS.step() (warmup update)
  ↓
evaluation
  ↓
DRC.update() (stability check)
  ↓
PIDv2.update() (authority adjustment)
```

## References

- Patent Formula [1331]: Hierarchical Gradient Scaling
- Patent Formula [201]: Vritti-Driven Phase Stiffness
- Patent Formula [259]: InsightGate Epistemic Stability Control
- SOVEREIGN_1_DESIGN_IMPLEMENTATION.md: Full architecture specification
