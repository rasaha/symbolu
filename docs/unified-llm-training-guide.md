# Unified LLM Training Guide

Comprehensive guide to training Sovereign-1 LLM with SymbolU12 architecture using `train_unified_llm.py`.

## Overview

The Unified LLM Trainer supports multiple model architectures with advanced training features:
- **9:3 Hierarchical Gradient Scaling** (Formula [1331])
- **Phase Attention** (LRA-optimized O(n) complex attention)
- **Dynamic Relaxation** (9:3 → 6:6 transition)
- **WeightTransfer** with Guna-Lock protection
- **PIDv2 Controller** for S/A ratio regulation

## Architecture

```
Input Tokens → Embedding → Authority Layers (0-8) → Witness (Layer 8)
                                    ↓
                              R-Signal (48D)
                                    ↓
                          Sensory Layers (9-11) with Phase Bias
                                    ↓
                          128D Sovereign State
                          [Guna:16 + S:32 + R:48 + C:32]
                                    ↓
                              LM Head → Logits
```

### Key Components

1. **Authority Layers (0-8)**: Use `StateDeltaPhaseBlock` with Phase Attention
2. **Witness Layer (8)**: Finalizes R-Signal for sensory injection
3. **Sensory Layers (9-11)**: Use `QuadraticAttentionWithPhaseBias` with R-Signal phase bias
4. **Sovereign State**: 128D state vector combining Guna, S-Signal, R-Signal, C-Signal

## Quick Start

```bash
# Basic training
python train_unified_llm.py --model_type ontological --model_size medium

# Full Sovereign-1 training with 9:3 split
python train_unified_llm.py \
    --model_type ontological \
    --model_size medium \
    --max_seq_len 1024 \
    --batch_size 16 \
    --gradient_accumulation 2 \
    --use_9_3_split \
    --alpha_sens_initial 0.1 \
    --alpha_sens_max 0.7 \
    --enable_dynamic_relaxation \
    --relaxation_mode average \
    --controller pidv2 \
    --gradient_checkpointing \
    --use_per_layer_clipping \
    --tensorboard \
    --dataset wikitext103 \
    --max_steps 20000
```

## CLI Parameters

### Model Configuration

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--model_type` | str | ontological | Model architecture: `baseline`, `ontological`, `local`, `phase`, `local_phase`, `hybrid` |
| `--model_size` | str | small | Model size: `tiny`, `small`, `medium`, `large` |
| `--max_seq_len` | int | 2048 | Maximum sequence length |

### Training Core

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--batch_size` | int | 8 | Training batch size |
| `--gradient_accumulation` | int | 1 | Gradient accumulation steps |
| `--max_steps` | int | 10000 | Maximum training steps |
| `--learning_rate` | float | 3e-4 | Base learning rate |
| `--use_per_layer_clipping` | flag | False | Enable per-layer gradient clipping |
| `--seed` | int | 42 | Random seed for reproducibility |

### Dataset

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--dataset` | str | wikitext103 | Dataset: `wikitext2`, `wikitext103`, `openwebtext`, `pile`, `tinystories` |

### Memory Optimization

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--gradient_checkpointing` | flag | False | Enable gradient checkpointing |
| `--mixed_precision` | str | bf16 | Precision: `none`, `fp16`, `bf16` |

### Local/Phase Attention (Hybrid Models)

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--local_backend` | str | auto | Local attention backend: `auto`, `unfold`, `native` |
| `--window_size` | int | 256 | Local attention window size |
| `--local_layers` | int | 4 | Number of local attention layers |
| `--alpha_local` | float | 0.8 | Local attention weight |
| `--alpha_phase` | float | 0.2 | Phase attention weight |
| `--alpha_phase_start` | float | 0.6 | Phase α at training start |
| `--alpha_phase_end` | float | 0.4 | Phase α at training end |
| `--alpha_decay_steps` | int | 10000 | Steps to decay α from start to end |

### Loss Functions

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--lambda_bhava` | float | 0.1 | Bhava consistency loss weight |
| `--lambda_coherence` | float | 0.05 | Coherence loss weight |
| `--no_coherence_loss` | flag | False | Disable coherence loss |

### Logging & Checkpointing

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--log_every` | int | 10 | Log metrics every N steps |
| `--eval_every` | int | 100 | Run evaluation every N steps |
| `--save_every` | int | 1000 | Save checkpoint every N steps |
| `--checkpoint_dir` | str | checkpoints_unified | Checkpoint directory |
| `--tensorboard` | flag | True | Enable TensorBoard logging |
| `--no_tensorboard` | flag | False | Disable TensorBoard logging |

### Resume Training

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--resume` | str | "" | Path to checkpoint to resume from |
| `--resume_weights_only` | flag | False | Only load weights, reset optimizer |

### Quality Sampling

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--sample_every` | int | 500 | Generate quality samples every N steps |

Quality samples use these default prompts:
- "The history of the Roman Empire began when"
- "In computer science, algorithms are"
- "The weather today is expected to be"
- "Once upon a time in a small village"
- "The meaning of life is often debated"

### 9:3 Hierarchical Gradient Scaling (Formula [1331])

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--use_9_3_split` | flag | False | Enable 9:3 Authority/Sensory split |
| `--authority_layers` | int | 9 | Number of Authority layers (frozen α=1.0) |
| `--sensory_layers` | int | 3 | Number of Sensory layers (variable α) |
| `--alpha_sens_initial` | float | 0.1 | Initial Sensory layer gradient scale |
| `--alpha_sens_max` | float | 0.7 | Maximum Sensory layer gradient scale |
| `--gradient_warmup_steps` | int | 500 | Steps to warm up gradient scaling |

### Dynamic Relaxation (9:3 → 6:6 Transition)

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--enable_dynamic_relaxation` | flag | False | Enable dynamic relaxation controller |
| `--relaxation_mode` | str | average | Stability metric: `average`, `min`, `median` |
| `--relaxation_stability_threshold` | float | 0.78 | S/A threshold to trigger relaxation |
| `--relaxation_stability_window` | int | 500 | Window size for stability averaging |
| `--relaxation_streak_target` | int | 5 | Consecutive windows above threshold |
| `--relaxation_target_authority` | int | 6 | Target Authority layers after relaxation |
| `--relaxation_target_sensory` | int | 6 | Target Sensory layers after relaxation |
| `--relaxation_thaw_alpha` | float | 0.05 | Gradient scale for newly thawed layers |
| `--relaxation_thaw_steps` | int | 500 | Steps to ramp thawed layer gradients |
| `--relaxation_ppl_spike_threshold` | float | 0.20 | PPL spike threshold for rollback |
| `--relaxation_recovery_steps` | int | 100 | Steps to wait after PPL spike |

### Weight Transfer & Guna-Lock

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--enable_weight_transfer` | flag | True | Enable weight transfer during relaxation |
| `--guna_lock_steps` | int | 50 | Steps to freeze W_q, W_k post-transfer |

**Weight Transfer Process:**
1. **Capture State**: Saves weights from Layers 6, 7, 8 (old sensory)
2. **State-Inference**: Initializes new QuadraticAttentionWithPhaseBias Q,K from V
3. **48D Anchor**: Re-anchors R_to_phase_bias to Layer 5 (new Witness)
4. **Guna-Lock**: Freezes W_q, W_k for 50 steps to prevent Rajasic noise

### PID Controller

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--controller` | str | none | Controller type: `none`, `pid`, `pidv2` |
| `--pidv2_kp_min` | float | 0.10 | Minimum proportional gain |
| `--pidv2_kp_max` | float | 0.30 | Maximum proportional gain |
| `--pidv2_kp_sensitivity` | float | 5.0 | Kp sensitivity to error magnitude |
| `--pidv2_ki` | float | 0.02 | Integral gain |
| `--pidv2_kd` | float | 0.10 | Derivative gain |
| `--pidv2_a_min` | float | 0.30 | Minimum sensory gradient scale |
| `--pidv2_w_s` | float | 0.30 | Sattvic weight in S/A calculation |
| `--phase_ramp_steps` | int | 7000 | Steps to ramp phase attention weight |

### Stress Testing

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--stress_test` | flag | False | Enable stress testing mode |
| `--stress_start` | int | 1000 | Step to start stress injection |
| `--stress_duration` | int | 200 | Duration of stress injection |
| `--corruption_rate` | float | 0.10 | Token corruption rate |
| `--corruption_mode` | str | noise | Corruption mode: `noise`, `shuffle`, `mask` |

## Training Modes

### 1. Basic Training (Baseline)

```bash
python train_unified_llm.py \
    --model_type baseline \
    --model_size medium \
    --max_steps 10000
```

### 2. Ontological with 9:3 Split

```bash
python train_unified_llm.py \
    --model_type ontological \
    --model_size medium \
    --use_9_3_split \
    --alpha_sens_initial 0.1 \
    --alpha_sens_max 0.7 \
    --max_steps 20000
```

### 3. Full Sovereign-1 with PIDv2

```bash
python train_unified_llm.py \
    --model_type ontological \
    --model_size medium \
    --use_9_3_split \
    --controller pidv2 \
    --enable_dynamic_relaxation \
    --relaxation_stability_threshold 0.78 \
    --enable_weight_transfer \
    --guna_lock_steps 50 \
    --gradient_checkpointing \
    --tensorboard \
    --max_steps 50000
```

### 4. Stress Testing

```bash
python train_unified_llm.py \
    --model_type ontological \
    --use_9_3_split \
    --controller pidv2 \
    --stress_test \
    --stress_start 5000 \
    --stress_duration 500 \
    --corruption_rate 0.15 \
    --max_steps 10000
```

## Key Metrics

### S/A Ratio (Sensory/Authority)

The core metric for training stability:
- **S/A < 0.3**: Sensory over-dampened, increase `alpha_sens`
- **S/A = 0.6-0.8**: Optimal range
- **S/A > 1.0**: Sensory runaway, decrease `alpha_sens`

### Perplexity Targets

| Phase | Target PPL |
|-------|------------|
| Initial (0-1K steps) | < 100,000 |
| Early (1K-5K) | < 10,000 |
| Mid (5K-15K) | < 1,000 |
| Late (15K+) | < 100 |

## Troubleshooting

### PPL Stuck High

1. Check S/A ratio (should be 0.6-0.8)
2. Enable PIDv2 controller
3. Increase `alpha_sens_max`

### S/A Ratio = 0.00

1. Sensory layers over-dampened
2. Increase `alpha_sens_initial` to 0.2-0.3
3. Use PIDv2 controller with higher `pidv2_a_min`

### OOM Errors

1. Enable `--gradient_checkpointing`
2. Reduce `--batch_size`
3. Increase `--gradient_accumulation`
4. Reduce `--max_seq_len`

### Training Instability Post-Relaxation

1. Increase `--guna_lock_steps` to 100
2. Lower `--relaxation_thaw_alpha` to 0.02
3. Increase `--relaxation_thaw_steps` to 1000

## File Structure

```
symbolu/
├── symbolu/ontological/
│   ├── symbolu12_bhava.py          # SymbolU12 with Phase Attention
│   └── ...
├── train_unified_llm.py            # Main training script
└── docs/
    ├── ontological-training-guide.md   # 100D Engine training
    └── unified-llm-training-guide.md   # This file
```

## References

- [Phase Attention Paper](https://arxiv.org/abs/...) - LRA-optimized O(n) attention
- [Formula 1331](docs/formula-1331.md) - 9:3 Hierarchical Gradient Scaling
- [Sovereign State Design](docs/sovereign-state.md) - 128D state architecture
