# Unified LLM Training Module

## Overview

`train_unified_llm.py` is the primary training script for Sovereign-1 models implementing the State-Delta Architecture with Vritti system, Guna Coherence, and hierarchical gradient control.

## Quick Start

```bash
# Basic training with ontological model
python train_unified_llm.py --model_type ontological --model_size small

# Training with 9:3 hierarchical split and PIDv2 controller
python train_unified_llm.py \
    --model_type ontological \
    --model_size medium \
    --use_9_3_split \
    --controller pidv2 \
    --enable_dynamic_relaxation

# Resume from checkpoint
python train_unified_llm.py --resume checkpoints_unified/step_5000.pt
```

---

## CLI Arguments Reference

### Model Architecture

| Argument | Type | Default | Choices | Description |
|----------|------|---------|---------|-------------|
| `--model_type` | str | `ontological` | `ontological`, `phase`, `hybrid`, `gen2` | Model architecture type. `gen2` = hierarchical complex Bhava |
| `--model_size` | str | `small` | `tiny`, `small`, `medium`, `large` | Model size preset (see [Model Size Presets](#model-size-presets)) |
| `--max_seq_len` | int | `2048` | - | Maximum sequence length |

### Training Hyperparameters

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--batch_size` | int | `8` | Batch size per GPU |
| `--gradient_accumulation` | int | `1` | Gradient accumulation steps |
| `--max_steps` | int | `10000` | Maximum training steps |
| `--learning_rate` | float | `3e-4` | Peak learning rate |
| `--seed` | int | `42` | Random seed |

### Dataset

| Argument | Type | Default | Choices | Description |
|----------|------|---------|---------|-------------|
| `--dataset` | str | `wikitext103` | `wikitext103`, `wikitext2` | Training dataset |

### Memory Optimization

| Argument | Type | Default | Choices | Description |
|----------|------|---------|---------|-------------|
| `--gradient_checkpointing` | flag | `False` | - | Enable gradient checkpointing to save memory |
| `--mixed_precision` | str | `bf16` | `none`, `fp16`, `bf16` | Mixed precision training mode |

### Hybrid Model Configuration

These options apply when `--model_type hybrid` is used:

| Argument | Type | Default | Choices | Description |
|----------|------|---------|---------|-------------|
| `--local_backend` | str | `auto` | `auto`, `flash`, `sdpa`, `unfold` | LocalAttention backend implementation |
| `--window_size` | int | `256` | - | Local attention window size |
| `--local_layers` | int | `4` | - | Number of local-only attention layers |
| `--alpha_local` | float | `0.8` | - | Weight for local attention in hybrid layers |
| `--alpha_phase` | float | `0.2` | - | Weight for phase attention in hybrid layers |

### Alpha Decay Schedule

Controls the decay of phase attention weight over training (for phase/hybrid models):

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--alpha_phase_start` | float | `0.6` | Initial alpha_phase value |
| `--alpha_phase_end` | float | `0.4` | Final alpha_phase value after decay |
| `--alpha_decay_steps` | int | `10000` | Steps over which alpha_phase decays |

### Ontological Loss Weights

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--lambda_bhava` | float | `0.1` | Bhava relationship consistency loss weight |
| `--lambda_coherence` | float | `0.05` | Global coherence loss weight |
| `--no_coherence_loss` | flag | `False` | Disable coherence loss entirely |

### Logging & Checkpointing

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--log_every` | int | `10` | Log metrics every N steps |
| `--eval_every` | int | `100` | Run validation every N steps |
| `--save_every` | int | `1000` | Save checkpoint every N steps |
| `--checkpoint_dir` | str | `checkpoints_unified` | Directory for saving checkpoints |
| `--tensorboard` | flag | `True` | Enable TensorBoard logging |
| `--no_tensorboard` | flag | `False` | Disable TensorBoard logging |

### Resume Training

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--resume` | str | `""` | Path to checkpoint to resume from |
| `--resume_weights_only` | flag | `False` | Only load model weights, reset optimizer state |

---

## PIDv2 Controller (V9.4.4)

The PIDv2 controller implements adaptive authority scaling based on training stability metrics.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--controller` | str | `none` | `none`, `pidv2`, `emergency_pd` - Authority controller type |
| `--pidv2_kp_min` | float | `0.10` | Minimum Kp (proportional gain) when noisy |
| `--pidv2_kp_max` | float | `0.30` | Maximum Kp when training is clean/stable |
| `--pidv2_kp_sensitivity` | float | `5.0` | Volatility sensitivity for Kp adaptation |
| `--pidv2_ki` | float | `0.02` | Integral gain for accumulated error |
| `--pidv2_kd` | float | `0.10` | Derivative gain for rate of change |
| `--pidv2_a_min` | float | `0.30` | Minimum authority factor floor |
| `--pidv2_w_s` | float | `0.30` | Semantic weight (0.30 = 30% prompt-based) |
| `--phase_ramp_steps` | int | `7000` | Steps for phase LR ramp (handshake dampening) |

### Controller Modes

- **`none`**: No adaptive control, fixed learning rate
- **`pidv2`**: Full PID controller with adaptive Kp based on training stability
- **`emergency_pd`**: PD-only controller for emergency recovery scenarios

---

## Formula [1331]: 9:3 Hierarchical Split

Implements gradient dampening for Authority/Sensory layer split. The first N layers (Authority) receive full gradients while the last M layers (Sensory) receive dampened gradients.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--use_9_3_split` | flag | `False` | Enable 9:3 Authority/Sensory gradient scaling |
| `--authority_layers` | int | `9` | Number of Authority (State-Delta) layers |
| `--sensory_layers` | int | `3` | Number of Sensory (Quadratic) layers |
| `--alpha_sens_min` | float | `0.1` | Minimum sensory gradient scale (heavy dampening) |
| `--alpha_sens_max` | float | `0.5` | Maximum sensory gradient scale (after warmup) |
| `--gradient_warmup_steps` | int | `500` | Steps to ramp α_sens from min to max |

### How It Works

```
Layer 0-8  (Authority): α = 1.0 (full gradients)
Layer 9-11 (Sensory):   α = 0.1 → 0.5 over 500 steps
```

This prevents Rajasic override from the sensory layers during early training.

---

## Dynamic Relaxation Controller

Automatically transitions from 9:3 (Authority-heavy) to 6:6 (Balanced) split based on training stability.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--enable_dynamic_relaxation` | flag | `False` | Enable automatic 9:3 → 6:6 transition |
| `--relaxation_mode` | str | `consecutive` | `consecutive` or `average` stability check mode |
| `--relaxation_stability_threshold` | float | `0.82` | StabilityIndex threshold to trigger relaxation |
| `--relaxation_stability_window` | int | `500` | Steps for stability verification |
| `--relaxation_target_authority` | int | `6` | Target authority layers after relaxation |
| `--relaxation_target_sensory` | int | `6` | Target sensory layers after relaxation |
| `--relaxation_alpha_max` | float | `0.7` | α ceiling after relaxation |
| `--relaxation_thaw_alpha` | float | `0.05` | Dampened Thaw starting α for new sensory layers |
| `--relaxation_thaw_steps` | int | `250` | Steps to ramp new sensory layers |
| `--relaxation_ppl_spike_threshold` | float | `0.20` | PPL increase % to trigger Viparyaya recovery |
| `--relaxation_recovery_steps` | int | `200` | Steps to stay in recovery mode |

### Relaxation Modes

- **`consecutive`** (Default): Requires StabilityIndex ≥ threshold for N consecutive steps. Resets on any dip.
- **`average`**: Requires average StabilityIndex ≥ threshold over rolling N-step window. More tolerant of temporary dips.

### State Machine

```
AUTHORITY (9:3) → MONITORING → RELAXING → BALANCED (6:6)
                                   ↓
                              RECOVERY (Viparyaya)
                                   ↓
                              AUTHORITY (9:3)
```

### StabilityIndex Formula

```
SSI = 0.7 * GunaCoherence + 0.3 * (1 - S_Drift_EMA)
```

---

## Stress Test Mode

Run controlled stress tests with data corruption injection.

| Argument | Type | Default | Choices | Description |
|----------|------|---------|---------|-------------|
| `--stress_test` | flag | `False` | - | Run stress test instead of training |
| `--stress_start` | int | `1000` | - | Step to start corruption injection |
| `--stress_duration` | int | `200` | - | Steps to inject corruption |
| `--corruption_rate` | float | `0.10` | - | Probability of corrupting each batch |
| `--corruption_mode` | str | `noise` | `noise`, `label_flip`, `repeat` | Type of corruption to inject |

---

## Hidden Defaults (Not Exposed via CLI)

These parameters are set in `UnifiedTrainingConfig` but not accessible via CLI:

### Model Architecture

| Parameter | Default | Description |
|-----------|---------|-------------|
| `vocab_size` | `50257` | Vocabulary size (GPT-2 tokenizer) |
| `dropout` | `0.1` | Dropout probability |
| `sync_steps` | `3` | Phase synchronization steps |
| `sync_lr` | `0.1` | Phase synchronization learning rate |
| `bhava_embed_dim` | `128` | Bhava embedding dimension |
| `num_drishti_heads` | `4` | Number of Drishti attention heads |

### Optimizer

| Parameter | Default | Description |
|-----------|---------|-------------|
| `warmup_steps` | `500` | LR warmup steps |
| `weight_decay` | `0.1` | AdamW weight decay |
| `beta1` | `0.9` | Adam beta1 |
| `beta2` | `0.95` | Adam beta2 |
| `max_grad_norm` | `1.0` | Gradient clipping norm |

### Loss Weights

| Parameter | Default | Description |
|-----------|---------|-------------|
| `lambda_lm` | `1.0` | Language modeling loss weight |
| `lambda_entropy` | `0.01` | Entropy regularization weight |

### Sovereign-1 Loss (Hardened Decomposed Loss)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `use_sovereign_loss` | `True` | Enable Sovereign-1 decomposed loss |
| `sovereign_weight_guna` | `1.0` | Guna signal weight |
| `sovereign_weight_s` | `2.0` | S-Signal (referent) weight |
| `sovereign_weight_r` | `5.0` | R-Signal (ontology) weight - CRITICAL |
| `sovereign_weight_c` | `0.5` | C-Signal (phoneme) weight |

### PIDv2 Hidden Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pidv2_c_floor` | `0.68` | Coherence floor for Kp adaptation |
| `pidv2_c_good` | `0.76` | Coherence target for "good" training |
| `pidv2_semantic_scale` | `50.0` | Semantic loss scaling factor |
| `pidv2_handshake_dampen` | `True` | Enable handshake dampening |
| `phase_delay_steps` | `0` | Steps to delay phase activation |

### Hardware

| Parameter | Default | Description |
|-----------|---------|-------------|
| `device` | `auto` | Device selection (auto-detects CUDA) |
| `num_workers` | `4` | DataLoader workers |
| `tokenizer` | `gpt2` | Tokenizer to use |

---

## Model Size Presets

| Size | embed_dim | num_layers | num_heads | ff_dim | ~Params |
|------|-----------|------------|-----------|--------|---------|
| `tiny` | 256 | 6 | 4 | 1024 | ~15M |
| `small` | 512 | 8 | 8 | 2048 | ~50M |
| `medium` | 768 | 12 | 12 | 3072 | ~125M |
| `large` | 1024 | 16 | 16 | 4096 | ~350M |

---

## Example Configurations

### Basic Ontological Training

```bash
python train_unified_llm.py \
    --model_type ontological \
    --model_size small \
    --max_steps 10000 \
    --batch_size 8 \
    --learning_rate 3e-4
```

### Full Sovereign-1 with All Controllers

```bash
python train_unified_llm.py \
    --model_type ontological \
    --model_size medium \
    --max_steps 50000 \
    --batch_size 16 \
    --gradient_accumulation 2 \
    --learning_rate 1e-4 \
    --use_9_3_split \
    --controller pidv2 \
    --enable_dynamic_relaxation \
    --relaxation_mode average \
    --gradient_checkpointing \
    --mixed_precision bf16
```

### Memory-Efficient Large Model

```bash
python train_unified_llm.py \
    --model_type ontological \
    --model_size large \
    --batch_size 4 \
    --gradient_accumulation 8 \
    --gradient_checkpointing \
    --mixed_precision bf16 \
    --use_9_3_split
```

### Hybrid Model with Local Attention

```bash
python train_unified_llm.py \
    --model_type hybrid \
    --model_size medium \
    --local_backend flash \
    --window_size 512 \
    --local_layers 6 \
    --alpha_local 0.7 \
    --alpha_phase 0.3
```

---

## TensorBoard Metrics

When `--tensorboard` is enabled (default), the following metrics are logged:

### Training Metrics
- `train/loss` - Total training loss
- `train/lm_loss` - Language modeling loss
- `train/ppl` - Training perplexity
- `train/lr` - Current learning rate

### Validation Metrics
- `val/loss` - Validation loss
- `val/ppl` - Validation perplexity

### Sovereign-1 Metrics
- `sovereign/guna_coherence` - Guna Coherence (GC)
- `sovereign/s_drift_ema` - S-Drift exponential moving average
- `sovereign/stability_index` - Sattvic Stability Index (SSI)

### Controller Metrics (when `--controller pidv2`)
- `pid/kp` - Current proportional gain
- `pid/authority_factor` - Current authority factor
- `pid/semantic_weight` - Current semantic weight

### Gradient Metrics (when `--use_9_3_split`)
- `gradient/authority_norm` - Authority layer gradient norm
- `gradient/sensory_norm` - Sensory layer gradient norm
- `gradient/sensory_scale` - Current α_sens value

---

## Output Files

```
checkpoints_unified/
├── step_1000.pt          # Full checkpoint (model, optimizer, scheduler, step)
├── step_2000.pt
├── ...
├── best_model.pt         # Best validation loss checkpoint
└── config.json           # Training configuration
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CUDA_VISIBLE_DEVICES` | GPU device selection |
| `TOKENIZERS_PARALLELISM` | Set to `false` to suppress tokenizer warnings |

---

## Notes

1. **9:3 Split Requires Correct Layer Count**: Ensure `authority_layers + sensory_layers` matches your model's total layers. Default 9:3 works with 12-layer models (`small`, `medium`).

2. **Dynamic Relaxation Requires 9:3 Split**: `--enable_dynamic_relaxation` is only active when `--use_9_3_split` is also enabled.

3. **PIDv2 Controller**: The controller monitors Guna Coherence and adjusts training dynamics. Works independently of 9:3 split.

4. **Stress Test Redirect**: When `--stress_test` is used, the script redirects to `stress_test.py` with the specified parameters.
