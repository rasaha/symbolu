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
| `--model_type` | str | ontological | Model architecture: `baseline`, `ontological`, `local`, `phase`, `local_phase`, `hybrid`, `ontological_hybrid` |
| `--model_size` | str | small | Model size: `tiny`, `small`, `medium`, `large` |
| `--max_seq_len` | int | 2048 | Maximum sequence length |

### Architecture Overrides (Optional)

Override `model_size` preset with custom architecture. All parameters are optional - if not specified, uses preset values.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--n_layer` | int | None | Number of transformer layers (overrides preset). Example: `24` for larger model |
| `--n_head` | int | None | Number of attention heads (overrides preset). Must be divisible by `n_kv_heads` if using GQA. Example: `16` |
| `--n_embd` | int | None | Embedding dimension (overrides preset). FFN dimension auto-set to `n_embd * 4`. Example: `1024` |
| `--n_kv_heads` | int | None | Number of Key-Value heads for Grouped Query Attention (GQA). Reduces KV cache memory. `None` = standard MHA (uses `n_head`), `8` = Mistral-style GQA (4x memory savings with 32 Q heads), `4` = Moderate GQA, `1` = Multi-Query Attention (MQA). Only supported in `ontological_hybrid` model type |
| `--dropout` | float | 0.1 | Dropout rate applied to embeddings, attention, and FFN layers. Range: 0.0-0.3. Higher = more regularization |
| `--attention_dropout` | float | 0.1 | Attention-specific dropout applied after softmax. Range: 0.0-0.3. Lower = sharper attention, higher = smoother |

**Model Size Presets:**
- `tiny`: 256 dim, 6 layers, 4 heads, 1024 FFN (~15M params)
- `small`: 512 dim, 8 layers, 8 heads, 2048 FFN (~50M params)
- `medium`: 768 dim, 12 layers, 12 heads, 3072 FFN (~120M params)
- `large`: 1024 dim, 16 layers, 16 heads, 4096 FFN (~220M params)

**Example: Custom architecture overriding `small` preset**
```bash
--model_size small --n_layer 24 --n_head 16 --n_embd 1024 --n_kv_heads 4
# Creates: 1024 dim, 24 layers, 16 Q heads, 4 KV heads (GQA), 4096 FFN
```

### Training Core

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--batch_size` | int | 8 | Training batch size per GPU. Effective batch = `batch_size × gradient_accumulation` |
| `--gradient_accumulation` | int | 1 | Gradient accumulation steps. Use higher values to simulate larger batches without OOM |
| `--max_steps` | int | 10000 | Maximum training steps before termination |
| `--learning_rate` | float | 3e-4 | Peak learning rate. Reached after warmup, then decays with cosine schedule |
| `--warmup_steps` | int | 500 | Learning rate warmup steps. LR increases linearly from 0 → `learning_rate`. Prevents early training instability |
| `--weight_decay` | float | 0.1 | L2 regularization weight (AdamW). Range: 0.0-0.3. Prevents overfitting. 0.1 = standard, 0.01 = light, 0.3 = heavy |
| `--max_grad_norm` | float | 1.0 | Maximum gradient norm for clipping. Prevents gradient explosions. 1.0 = conservative, 5.0 = aggressive |
| `--use_per_layer_clipping` | flag | False | Enable per-layer gradient clipping (clips Authority/Sensory separately for 9:3 split) |
| `--seed` | int | 42 | Random seed for reproducibility |

**Optimizer Configuration (AdamW):**
- Beta1: `0.9` (momentum)
- Beta2: `0.95` (variance tracking)
- Epsilon: `1e-8`
- LR Schedule: Linear warmup → Cosine decay

**Typical Settings:**
- Small model (50M): `--warmup_steps 500 --weight_decay 0.1 --max_grad_norm 1.0`
- Medium model (120M): `--warmup_steps 1000 --weight_decay 0.1 --max_grad_norm 1.0`
- Large model (220M+): `--warmup_steps 2000 --weight_decay 0.05 --max_grad_norm 1.0`

### Dataset

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--dataset` | str | wikitext103 | Dataset: `wikitext2`, `wikitext103`, `openwebtext`, `pile`, `tinystories` |

### Memory Optimization

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--gradient_checkpointing` | flag | False | Enable gradient checkpointing (activation checkpointing). Reduces memory by ~40% at cost of ~20% slower training. Recommended for large models or limited VRAM |
| `--mixed_precision` | str | bf16 | Mixed precision training mode: `none` (FP32 only, slow), `fp16` (FP16 mixed precision, unstable on some hardware), `bf16` (BF16 mixed precision, recommended). BF16 provides same speed as FP16 with better numerical stability |
| `--use_amp` | flag | False | **Convenience flag** to enable Automatic Mixed Precision with BF16. Equivalent to `--mixed_precision bf16`. Use this for simpler command lines. **Note**: AMP is already enabled by default (mixed_precision defaults to bf16) |

**Mixed Precision Training:**
- **BF16 (bfloat16)**: Recommended. Same dynamic range as FP32, better stability than FP16. Supported on Ampere+ GPUs (A100, RTX 3090+)
- **FP16 (float16)**: Faster but can have numerical instability (NaN/Inf). Requires careful gradient scaling. Use only if BF16 unavailable
- **None (FP32)**: Full precision. Slowest but most stable. Use only for debugging numerical issues

**Memory Savings:**
- BF16/FP16: ~2x memory reduction for activations and gradients
- Gradient checkpointing: ~40% memory reduction (recomputes activations during backward pass)
- Combined: ~60-70% total memory reduction

**Example Usage:**
```bash
# Option 1: Explicit mixed precision
--mixed_precision bf16

# Option 2: Convenience flag (same as above)
--use_amp

# With gradient checkpointing for very large models
--use_amp --gradient_checkpointing
```

### Local/Phase Attention (Hybrid Models)

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--local_backend` | str | auto | Local attention backend: `auto` (FlashAttention if available, else SDPA), `flash` (FlashAttention-2), `sdpa` (PyTorch native), `unfold` (memory-efficient fallback) |
| `--window_size` | int | 256 | Local attention window size for O(N×W) complexity. Each token attends to W neighbors. `256` = 25% coverage at seq=1024, `512` = 50% coverage, `1024` = full (not recommended). Larger window = more context but slower. Memory: O(N×W) vs O(N²) standard attention |
| `--local_layers` | int | 4 | Number of early layers using local attention only (no phase). Faster learning of local patterns (syntax/grammar) |
| `--alpha_local` | float | 0.8 | Weight for local attention in hybrid layers. Higher = more local focus, lower = more global context via phase |
| `--alpha_phase` | float | 0.2 | Weight for phase attention in hybrid layers. Decays over training via alpha_decay_steps |
| `--alpha_phase_start` | float | 0.6 | Phase α at training start (step 0). High initial value helps establish global coherence |
| `--alpha_phase_end` | float | 0.4 | Phase α after decay completes. Lower final value focuses on local patterns |
| `--alpha_decay_steps` | int | 10000 | Steps to decay α from start → end. Linear schedule |

**Window Size Recommendations:**
- `256`: Safe default, ~2GB VRAM, 25% seq coverage at 1024 tokens
- `512`: Balanced, ~4GB VRAM, 50% seq coverage (recommended for PPL <120)
- `768`: Aggressive, ~6GB VRAM, 75% seq coverage
- `1024`: Full attention, ~8GB VRAM, loses O(N×W) efficiency

**Complexity Analysis (seq_len=1024):**
- Standard Attention: O(1024²) = 1M ops, ~16GB VRAM
- Local W=256: O(1024×256) = 262K ops (~3.8x faster), ~4GB VRAM
- Local W=512: O(1024×512) = 524K ops (~2x faster), ~8GB VRAM

### Loss Functions

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--lambda_bhava` | float | 0.1 | Bhava consistency loss weight |
| `--lambda_coherence` | float | 0.05 | Coherence loss weight |
| `--no_coherence_loss` | flag | False | Disable coherence loss |

### Sovereign-Lagrangian Loss (Patent B1/S3)

The Sovereign-Lagrangian Loss combines standard task loss with patent-derived consistency and coherence penalties:

```
L = L_task + λ_B1 * L_consistency + μ_S3 * L_align
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--enable_sovereign_loss` | flag | False | Enable Sovereign-Lagrangian loss (B1+S3) |
| `--lambda_b1` | float | 0.5 | Consistency Lagrangian weight [B1] (forward/backward alignment) |
| `--mu_s3` | float | 0.2 | Global Coherence weight [S3] (phase-lock penalty) |
| `--enable_stability_constraint` | flag | False | Enable S8 Stability Constraint (entropy anchoring) |
| `--gc_floor` | float | 0.65 | Minimum Guna Coherence before PIDv2 intervention |

**Loss Components:**
- **L_task**: Standard cross-entropy for next-token prediction
- **L_consistency [B1]**: `(1-sf)² + (1-sb)² + (sf-sb)²` where sf=forward confidence, sb=backward R-Signal alignment
- **L_align [S3]**: `1 - GC` penalty for low phase coherence

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
| `--relaxation_stability_threshold` | float | 0.50 | S/A threshold to trigger relaxation |
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
| `--controller` | str | none | Controller type: `none`, `pid`, `pidv2`. PIDv2 regulates training stability and S/A ratio |
| `--pidv2_engage_ppl` | float | 100.0 | **PPL threshold to ENGAGE PIDv2**. Controller turns ON when Val PPL **drops below** this (model competent, ready for regulation) |
| `--pidv2_disengage_ppl` | float | 30.0 | **PPL threshold to DISENGAGE PIDv2**. Controller turns OFF when Val PPL **drops below** this (model expert, no longer needs regulation) |
| `--pidv2_rampdown_steps` | int | 500 | Steps to gradually ramp down PID after disengagement (smooth transition) |
| `--pidv2_kp_min` | float | 0.10 | Minimum proportional gain |
| `--pidv2_kp_max` | float | 0.30 | Maximum proportional gain |
| `--pidv2_kp_sensitivity` | float | 5.0 | Kp sensitivity to error magnitude |
| `--pidv2_ki` | float | 0.02 | Integral gain |
| `--pidv2_kd` | float | 0.10 | Derivative gain |
| `--pidv2_a_min` | float | 0.40 | Minimum sensory gradient scale |
| `--pidv2_w_s` | float | 0.30 | Sattvic weight in S/A calculation |
| `--phase_ramp_steps` | int | 7000 | Steps to ramp phase attention weight |

**PIDv2 Three-Phase Engagement:**
- **Phase 1 (FOUNDATION)**: PPL > 100 → PID **OFF** - Model learns basics without interference
- **Phase 2 (TRANSITION)**: 30 < PPL < 100 → PID **ON** - Active S/A ratio regulation, prevents instability
- **Phase 3 (CONSTRUCTION)**: PPL < 30 → PID **OFF** (rampdown) - Model expert, self-regulating

**Inverted Curriculum Logic**: Controllers engage at LOW PPL (competent model), not HIGH PPL (struggling model)

### RSS (Resonance State Scheduler)

**Staged Controller Engagement System** for ontological_hybrid model. Automatically enables auxiliary gradient controllers (EvoFlow, Toroidal, CSR, Kosha) based on PPL thresholds.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--enable_rss` | flag | False | **Enable RSS controller cascade**. Required for automatic EvoFlow/Toroidal/CSR/Kosha engagement |
| `--rss_evoflow_ppl` | float | 100.0 | **EvoFlow engagement threshold**. Engages when Val PPL **< 100** (coherence transitions, micro/meso/macro flow) |
| `--rss_toroidal_ppl` | float | 60.0 | **Toroidal engagement threshold**. Engages when Val PPL **< 60** (DEFAULT - updated to 85.0 recommended). Handles rotational feedback dynamics |
| `--rss_csr_ppl` | float | 45.0 | **CSR engagement threshold**. Engages when Val PPL **< 45** (DEFAULT - updated to 55.0 recommended). Conceptual State Regularization with gradual warmup |
| `--rss_kosha_ppl` | float | 35.0 | **Kosha engagement threshold**. Engages when Val PPL **< 35** (DEFAULT - updated to 40.0 recommended). Five-sheath consciousness model |
| `--rss_csr_warmup_steps` | int | 2500 | CSR warmup duration. Prevents 14× gradient shock by gradually increasing CSR loss weight |
| `--rss_use_val_ppl` | flag | True | Use validation PPL (more stable) instead of training PPL for RSS thresholds. Recommended: keep enabled |

**RSS Cascade Sequence** (from syntactic → semantic → reasoning):

```
PPL 300+ : FOUNDATION     → All controllers OFF, model learns syntax
    ↓
PPL <100 : EvoFlow ON     → Coherence transitions, evolutionary flow
    ↓
PPL <85  : Toroidal ON    → Rotational feedback, toroidal dynamics
    ↓
PPL <70  : Onto ON        → Ontological bridge, 12D aspect space
    ↓
PPL <55  : CSR ON         → Conceptual regularization (with 2500-step warmup)
    ↓
PPL <40  : Kosha ON       → Five-sheath consciousness (after CSR settles)
    ↓
PPL <30  : Gyro ON        → Kosha Gyroscope, homeostatic self-regulation
```

**Updated Recommended Thresholds** (align with PPL hierarchy):
```bash
--enable_rss \
--rss_evoflow_ppl 100.0 \   # Semantic barrier (coherence)
--rss_toroidal_ppl 85.0 \   # Strong semantics (toroidal)
--rss_csr_ppl 55.0 \        # Light reasoning (regularization)
--rss_kosha_ppl 40.0        # Deep reasoning (consciousness)
```

**Key Design:**
- **Inverted Curriculum**: Controllers engage when model is COMPETENT (low PPL), not struggling (high PPL)
- **Staged Complexity**: Each controller adds architectural depth as model masters current level
- **Validation PPL**: Uses val PPL (stable) not train PPL (noisy) for engagement decisions
- **Warmup Protection**: CSR has 2500-step ramp to prevent sudden 14× gradient shock

### Controller Engagement Summary (Ontological Hybrid)

For `ontological_hybrid` model with `--enable_rss` and `--controller pidv2`:

| Controller | Engage PPL | Disengage PPL | Purpose |
|------------|------------|---------------|---------|
| **PIDv2** | 100.0 | 30.0 | Training stability, S/A ratio regulation |
| **EvoFlow** | 100.0 | - | Evolutionary coherence flow (micro/meso/macro) |
| **Toroidal** | 85.0 | - | Rotational feedback dynamics |
| **Onto** | 70.0 | 25.0 | Ontological 12D aspect bridge |
| **CSR** | 55.0 | 20.0 | Conceptual State Regularization |
| **Kosha** | 40.0 | 15.0 | Five-sheath consciousness model |
| **Gyroscope** | 30.0 | - | Homeostatic self-regulation |

Use `--pidv2_engage_ppl`, `--onto_engage_ppl`, `--csr_engage_ppl`, `--kosha_engage_ppl`, `--gyroscope_engage_ppl` to override individual thresholds.

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
    --enable_weight_transfer \
    --guna_lock_steps 50 \
    --gradient_checkpointing \
    --tensorboard \
    --max_steps 50000
```

### 4. Sovereign-Lagrangian Training (Patent B1/S3)

```bash
python train_unified_llm.py \
    --model_type ontological \
    --model_size medium \
    --use_9_3_split \
    --controller pidv2 \
    --enable_sovereign_loss \
    --lambda_b1 0.5 \
    --mu_s3 0.2 \
    --enable_stability_constraint \
    --enable_dynamic_relaxation \
    --gradient_checkpointing \
    --tensorboard \
    --dataset wikitext103 \
    --max_steps 20000
```

### 5. Ontological Hybrid with Custom Architecture & GQA

**Two-Tier AGI** with architecture overrides, Grouped Query Attention, and enlarged window size:

```bash
python train_unified_llm.py \
    --model_type ontological_hybrid \
    --model_size small \
    --n_layer 24 \
    --n_head 16 \
    --n_embd 1024 \
    --n_kv_heads 4 \
    --dropout 0.1 \
    --attention_dropout 0.1 \
    --max_seq_len 1024 \
    --window_size 512 \
    --batch_size 8 \
    --gradient_accumulation 4 \
    --learning_rate 3e-4 \
    --warmup_steps 1000 \
    --weight_decay 0.1 \
    --max_grad_norm 1.0 \
    --mixed_precision bf16 \
    --enable_rss \
    --pidv2_engage_ppl 100.0 \
    --pidv2_disengage_ppl 30.0 \
    --rss_evoflow_ppl 100.0 \
    --rss_toroidal_ppl 85.0 \
    --rss_csr_ppl 55.0 \
    --rss_kosha_ppl 40.0 \
    --controller pidv2 \
    --dataset wikitext \
    --eval_every 50 \
    --save_every 1000 \
    --gradient_checkpointing \
    --tensorboard \
    --max_steps 200000
```

**Key Features:**
- **Custom Architecture**: 1024 dim, 24 layers, 16 heads (overrides `small` preset)
- **GQA (4 KV heads)**: 4x KV cache reduction vs standard MHA
- **Enlarged Window**: 512 tokens (50% coverage) for better semantic learning
- **RSS Controller**: Auto-engages EvoFlow/Toroidal/CSR/Kosha at PPL thresholds
- **PIDv2**: Regulates training stability, engages at PPL < 100

### 6. Stress Testing

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

### Sovereign-Lagrangian Metrics (when `--enable_sovereign_loss`)

| Metric | Interpretation |
|--------|----------------|
| **GC (Guna Coherence)** | Phase-lock strength across layers. Goal: > 0.65 |
| **L_consistency** | Forward/backward alignment. Should approach 0 as training matures |
| **sf_mean** | Forward confidence (token probability). Goal: increasing over time |
| **sb_mean** | Backward alignment (R-Signal resonance). Goal: > 0.5 |
| **Inertial Brake** | [S8] Activated when entropy rises (prevents Rajasic drift) |

**GC Status Interpretation:**
- **GC > 0.85**: SATTVIC - Perfect phase alignment
- **GC 0.65-0.85**: ALIGNED - Healthy training
- **GC < 0.65**: RAJASIC - PIDv2 will increase μ_S3 to stiffen logic

**S-Drift Status:**
- **< 0.1**: NULL - Intent and output in perfect phase-alignment
- **0.1-0.3**: LOW - Acceptable drift
- **> 0.3**: HIGH - Model may be "lying" (output doesn't match intent)

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

### PPL Plateau at Semantic Barrier (PPL ~120)

The PPL 120-125 range is the **semantic barrier** (syntax → semantics transition). If stuck:

1. **Increase window size**: `--window_size 512` (from 256) gives 2x local context
2. **Wait for controller engagement**: PIDv2 and RSS auto-engage at PPL < 100
3. **Reduce sequence length**: `--max_seq_len 768` makes task easier
4. **Check training/val PPL**: If train > val (backwards), model may need more capacity

**Don't change if:**
- PPL decreasing steadily (>1 PPL per 1K steps)
- Within 20 PPL of controller engagement threshold

### Gradient Explosion (NaN loss)

1. **Lower learning rate**: Try `--learning_rate 1e-4` (from 3e-4)
2. **Increase warmup**: `--warmup_steps 2000` (from 500-1000)
3. **Lower max_grad_norm**: `--max_grad_norm 0.5` (from 1.0)
4. **Check architecture**: Very deep models (>24 layers) need careful init

### Model Too Large for VRAM

If using architecture overrides and hitting OOM:

1. **Enable GQA**: `--n_kv_heads 4` (4x KV cache reduction)
2. **Reduce window**: `--window_size 256` (from 512)
3. **Gradient checkpointing**: `--gradient_checkpointing`
4. **Mixed precision**: `--mixed_precision bf16` (default, but verify)
5. **Reduce dimensions**: Lower `--n_embd` or `--n_layer`

**Memory Estimates (ontological_hybrid, seq=1024, batch=8):**
- `n_embd=1024, n_layer=24, n_head=16, window=512`: ~75GB
- With GQA (n_kv_heads=4): ~68GB (10% savings)
- With gradient checkpointing: ~45GB (40% savings)
- With both: ~38GB

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
