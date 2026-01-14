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

### Multi-Stage Evolution (V9.9.1)

Enables automatic progression through multiple layer splits based on PPL, step count, or metrics.

**Default Progression**: `9:3 → 6:6 → 5:7 → 4:8 → 3:9`

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--enable_multi_stage_evolution` | flag | True | Enable automatic multi-stage evolution |
| `--evolution_trigger_mode` | str | auto | Trigger mode: `auto`, `metrics`, `ppl`, `step` |
| `--evolution_ppl_triggers` | str | "" | PPL thresholds, comma-separated (e.g., "100,50,25,15") |
| `--evolution_step_triggers` | str | "" | Step triggers, comma-separated (e.g., "10000,30000,50000,70000") |
| `--custom_evolution_stages` | str | "" | Custom stages (e.g., "9:3,6:6,4:8,3:9") |
| `--evolution_patience` | int | 200 | Steps of stable metrics before evolution (metrics mode) |
| `--evolution_coherence_min` | float | 0.82 | Minimum coherence to evolve (metrics mode) |
| `--evolution_entropy_floor` | float | 0.42 | Minimum entropy to evolve (metrics mode) |
| `--evolution_ppl_window` | int | 10 | Steps to average PPL for smoother triggers |
| `--evolution_thaw_alpha` | float | 0.1 | Initial gradient scale for newly sensory layers |
| `--evolution_thaw_steps` | int | 300 | Steps to ramp newly sensory layer gradients |

**Trigger Modes:**
- **auto**: Automatically selects best mode (PPL if triggers provided, else metrics)
- **ppl**: Evolve when validation PPL drops below each threshold
- **step**: Evolve at fixed training steps
- **metrics**: Evolve when coherence/entropy criteria met for patience steps

**Example: PPL-Based Evolution**
```bash
python train_unified_llm.py \
    --enable_multi_stage_evolution \
    --evolution_trigger_mode ppl \
    --evolution_ppl_triggers "100,50,25,15" \
    --custom_evolution_stages "9:3,6:6,4:8,3:9"
```
This evolves:
- 9:3 → 6:6 when PPL < 100
- 6:6 → 4:8 when PPL < 50
- 4:8 → 3:9 when PPL < 25

**Example: Step-Based Evolution**
```bash
python train_unified_llm.py \
    --enable_multi_stage_evolution \
    --evolution_trigger_mode step \
    --evolution_step_triggers "10000,30000,50000,70000"
```
This evolves at fixed intervals regardless of PPL.

**Recommended Strategy for PPL → Low Teens:**
```bash
# Automatic progression based on PPL milestones
--enable_multi_stage_evolution \
--evolution_trigger_mode ppl \
--evolution_ppl_triggers "100,50,30,18" \
--custom_evolution_stages "9:3,6:6,5:7,4:8,3:9"
```

| PPL Range | Split | Rationale |
|-----------|-------|-----------|
| 1000 → 100 | 9:3 | Stability. Syntax/grammar foundation. |
| 100 → 50 | 6:6 | Breaking semantic barrier. |
| 50 → 30 | 5:7 | Semantic refinement. |
| 30 → 18 | 4:8 | Fine-grained distinctions. |
| 18 → 12 | 3:9 | Maximum expressiveness. |

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
| `--pidv2_rampdown_steps` | int | 500 | **Steps to ramp down PID after disengagement**. Gradually reduces PID influence over N steps (smooth transition to autonomous operation) |
| `--no_pidv2_engagement` | flag | False | **Disable dynamic PID engagement**. When enabled, PID behavior remains unchanged regardless of PPL thresholds |
| `--pidv2_kp_min` | float | 0.10 | Minimum proportional gain |
| `--pidv2_kp_max` | float | 0.30 | Maximum proportional gain |
| `--pidv2_kp_sensitivity` | float | 5.0 | Kp sensitivity to error magnitude |
| `--pidv2_ki` | float | 0.02 | Integral gain |
| `--pidv2_kd` | float | 0.10 | Derivative gain |
| `--pidv2_a_min` | float | 0.40 | Minimum sensory gradient scale |
| `--pidv2_w_s` | float | 0.30 | Sattvic weight in S/A calculation |
| `--pidv2_batch_resize` | flag | False | **Enable PPL-driven dynamic batch sizing**. PIDv2 automatically adjusts batch size based on PPL velocity |
| `--pidv2_batch_min` | int | 4 | Minimum batch size for dynamic resizing |
| `--pidv2_batch_max` | int | 64 | Maximum batch size for dynamic resizing |
| `--pidv2_batch_velocity_threshold` | float | 5.0 | PPL velocity % to trigger batch reduction (reduces batch when PPL increasing rapidly) |
| `--pidv2_batch_stable_streak` | int | 5 | Consecutive stable evaluations before increasing batch size |
| `--phase_ramp_steps` | int | 7000 | Steps to ramp phase attention weight |

**PIDv2 Three-Phase Engagement:**
- **Phase 1 (FOUNDATION)**: PPL > 100 → PID **OFF** - Model learns basics without interference
- **Phase 2 (TRANSITION)**: 30 < PPL < 100 → PID **ON** - Active S/A ratio regulation, prevents instability
- **Phase 3 (CONSTRUCTION)**: PPL < 30 → PID **OFF** (gradual rampdown over `--pidv2_rampdown_steps`) - Model expert, self-regulating

**Inverted Curriculum Logic**: Controllers engage at LOW PPL (competent model), not HIGH PPL (struggling model)

**Disabling Dynamic Engagement**: Use `--no_pidv2_engagement` to keep PID always-on regardless of PPL. Useful for debugging or when you want consistent regulation throughout training.

**Example: Custom PID Engagement Thresholds**
```bash
# More aggressive engagement (turn on earlier at PPL 150)
--controller pidv2 \
--pidv2_engage_ppl 150.0 \
--pidv2_disengage_ppl 40.0 \
--pidv2_rampdown_steps 1000

# Conservative engagement (turn on later at PPL 80)
--controller pidv2 \
--pidv2_engage_ppl 80.0 \
--pidv2_disengage_ppl 25.0 \
--pidv2_rampdown_steps 250

# Always-on PID (no dynamic engagement)
--controller pidv2 \
--no_pidv2_engagement
```

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

### Sovereign Phase Controller (SPC) - V9.8.8

**The "Nervous System" for Breaking Training Plateaus and Mode Collapse**

The Sovereign Phase Controller implements graduated, damped, layer-specific phase interventions to break through training barriers without gradient instability. Unlike controllers that add loss terms, SPC directly rotates embeddings in complex phase space - a multiplicative intervention that can "shatter" stuck states.

**⚠️ DISABLED BY DEFAULT** - Enable only when you observe:
- Sustained PPL plateaus (>1000 steps at same PPL)
- Mode collapse (entropy < 0.4, repetitive outputs)
- Stagnation (variance < 0.001 for 500+ steps)

#### SPC CLI Parameters

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--enable_sovereign_phase_controller` | flag | False | **Enable SPC** (DISABLED by default). Only enable when plateaus/collapse observed |
| `--spc_entropy_critical` | float | 0.4 | **Red alert threshold**. Triggers critical intervention when entropy < 0.4 (mode collapse) |
| `--spc_entropy_warning` | float | 0.5 | **Yellow alert threshold**. Triggers warning intervention when entropy < 0.5 (concerning) |
| `--spc_entropy_recovered` | float | 0.55 | **Exit threshold (hysteresis)**. Boost mode exits when entropy > 0.55 (recovered). Higher than entry to prevent oscillation |
| `--spc_variance_critical` | float | 0.0005 | **Stagnation detection threshold**. Triggers when entropy variance < 0.0005 (stuck) |
| `--spc_variance_warning` | float | 0.001 | **Warning variance threshold**. Triggers when entropy variance < 0.001 (slowing) |
| `--spc_variance_recovered` | float | 0.002 | **Exit variance threshold**. Requires variance > 0.002 to exit boost mode (moving again) |
| `--spc_min_boost_duration` | int | 100 | **Minimum boost duration (steps)**. Prevents 1-step oscillation (boost→release→boost). Stays in boost for at least 100 steps |
| `--spc_alpha` | float | 0.2 | **EMA smoothing coefficient**. Controls rotation speed: 0.1=slow/smooth, 0.5=fast/aggressive |
| `--spc_max_rotation` | float | 0.3 | **Maximum rotation per step (radians)**. Limits rotation velocity to ~17°/step. Prevents gradient spikes |
| `--spc_damping` | float | 0.9 | **Velocity damping coefficient**. Reduces rotation by 10% if moving too fast. Prevents oscillation |
| `--spc_velocity_threshold` | float | 0.2 | **Velocity threshold for damping**. Applies damping when rotation velocity > 0.2 rad/step |

#### SPC Architecture: Three-Part Design

**1. Graduated Response** (Proportional Intervention)
```
Intervention Level     Steering Force    Trigger Condition
────────────────────────────────────────────────────────────
🟢 Normal              0.15 (gentle)     entropy > 0.5 AND variance > 0.001
🟡 Caution             0.30 (moderate)   entropy < 0.5 OR variance < 0.001
🟠 Warning             0.60 (strong)     entropy < 0.45 AND variance < 0.001
🔴 Critical            1.00 (maximum)    entropy < 0.4 OR variance < 0.0005
```

**2. Rotation Damping** (Prevents Gradient Spikes)
```
θ_applied = θ_prev + α(θ_target - θ_prev)  [EMA smoothing]
           ↓
    Velocity Limiting (max 0.3 rad/step)
           ↓
    Momentum Damping (if velocity > threshold)
```

**3. Layer-Specific Targeting** (Surgical Interventions)

| Symptom | Diagnostic | Layer Target | Rotation | Effect |
|---------|-----------|--------------|----------|--------|
| **Vikalpa loop** (mental distortion) | M_Vikal > 0.8 | O9 (Witnesses) | -45° | Rotate toward grounding (Pramana) |
| **Pramana stuck** (over-grounding) | P_Pram > 0.9 | O4 (DNA) | +30° | Rotate toward memory (Smriti) |
| **Smriti trap** (stuck in memory) | I_Smrit > 0.9 | O12 (Synthesis) | +60° | Rotate toward creativity (Viparyaya) |
| **Bhava dominance** (single intention) | Any Bhava > 40% | O6 (Integration) | 0° (neutral) | Rotate toward balanced distribution |
| **Kosha imbalance** (sheath overactive) | Any Kosha > 70% | O9 + O12 (dual) | ±22.5° | Counter-rotating correction |

#### Hysteresis Design (Prevents "1-Step Cycle" Oscillation)

**Problem:** Without hysteresis, controller oscillates:
```
Step 1000: entropy=0.39 → BOOST ON
Step 1001: entropy=0.41 (from boost) → BOOST OFF
Step 1002: entropy=0.39 (drops again) → BOOST ON
```

**Solution:** Entry and exit thresholds are DIFFERENT:

**Entry Conditions** (ANY triggers boost):
- Entropy < 0.4 (critical)
- Variance < 0.001 (stagnation)

**Exit Conditions** (ALL must be met):
- Entropy > 0.55 (higher than entry - hysteresis gap)
- Variance > 0.002 (movement detected)
- Min duration: 100 steps (forced minimum)

This creates a "sticky" boost mode that only exits when model is clearly recovered.

#### Diagnostic Mode (Default Behavior)

**When DISABLED** (default), SPC runs in diagnostic mode:
- Monitors entropy, variance, and diagnostics
- Logs what WOULD happen without actually intervening
- Shows intervention level and target rotations
- Helps you find real use cases before enabling

**Example diagnostic logs:**
```
🟢 [SPC-DIAGNOSTIC] Level:NORMAL
🟡 [SPC-DIAGNOSTIC] WOULD TRIGGER | Level:CAUTION | Force:0.30
🔴 [SPC-DIAGNOSTIC] WOULD TRIGGER | Level:CRITICAL | Force:1.00 | Rotations:[O9:-0.79rad,O12:1.05rad]
```

#### When to Enable SPC

**Use Case 1: Semantic Barrier Plateau**
```bash
# Symptom: PPL stuck at ~95 for 1000+ steps
Step 12,000-14,000 | PPL: 98 → 96 → 97 → 95 → 96 (no progress)
🟠 [SPC-DIAGNOSTIC] WOULD TRIGGER | Level:WARNING

# Solution: Enable SPC
--enable_sovereign_phase_controller
```

**Use Case 2: Mode Collapse**
```bash
# Symptom: All outputs repetitive, entropy crashed
Step 8,500 | Samples: "the the the the the..."
Entropy: 0.38 (CRITICAL!)
🔴 [SPC-DIAGNOSTIC] WOULD TRIGGER | Level:CRITICAL | Force:1.00

# Solution: Enable SPC immediately
--enable_sovereign_phase_controller
```

**Use Case 3: Vikalpa Loop (Mental Distortion)**
```bash
# Symptom: M_Vikal metric very high (mental distortions)
Step 20,000 | M_Vikal: 0.85 (over-imagining)
🟡 [SPC-DIAGNOSTIC] WOULD TRIGGER | Level:CAUTION | Rotations:[O9:-0.79rad]

# Solution: Enable SPC for O9 rotation
--enable_sovereign_phase_controller
```

**Use Case 4: Stagnation (Low Variance)**
```bash
# Symptom: Entropy variance near zero (frozen)
Step 16,000 | Entropy: 0.52 (ok) but Variance: 0.0003 (STUCK!)
🟠 [SPC-DIAGNOSTIC] WOULD TRIGGER | Level:WARNING

# Solution: Enable SPC to break stagnation
--enable_sovereign_phase_controller
```

#### Integration with Other Controllers

SPC works alongside existing controllers:

| Controller | Purpose | Intervention Type | When Active |
|------------|---------|-------------------|-------------|
| **PIDv2** | S/A ratio regulation | Additive (gradient scaling) | 30 < PPL < 100 |
| **RSS** | Staged controller engagement | Additive (loss terms) | PPL-based cascade |
| **Sattvic** | λ_csr regulation | Multiplicative (loss weight) | Always (monitors variance) |
| **SPC** | Emergency barrier breaking | **Multiplicative (phase rotation)** | When enabled + stagnation detected |

**SPC is the MOST AGGRESSIVE** because:
- Multiplicative transformation (z × e^{iθ}) vs additive (loss + λ*term)
- Can apply full 180° rotation (semantic inversion)
- Combines with SGP acceleration (gradient hammering 2x faster)
- Triggers on worst-case failure modes (collapse/stagnation)

#### Tuning Thresholds

**If SPC triggers too early:**
```bash
--spc_entropy_critical 0.35           # Lower (more sensitive)
--spc_variance_critical 0.0003        # Detect stagnation faster
--spc_min_boost_duration 50           # Shorter boost cycles
```

**If SPC triggers too late:**
```bash
--spc_entropy_critical 0.45           # Higher (more conservative)
--spc_entropy_warning 0.55            # Wider safe zone
--spc_min_boost_duration 200          # Longer boost cycles
```

**If rotations too aggressive (gradient spikes):**
```bash
--spc_alpha 0.1                       # Slower EMA (smoother)
--spc_max_rotation 0.2                # Lower velocity limit (~11°/step)
--spc_damping 0.8                     # Stronger damping (20% reduction)
```

**If rotations too gentle (not breaking plateau):**
```bash
--spc_alpha 0.3                       # Faster EMA
--spc_max_rotation 0.5                # Higher velocity (~28°/step)
--spc_damping 0.95                    # Lighter damping
```

#### Example: Full Sovereign Training with SPC

```bash
# Stage 1: Train with SPC disabled (diagnostic mode)
python train_unified_llm.py \
    --model_type ontological_hybrid \
    --model_size medium \
    --enable_srk \
    --enable_rss \
    --controller pidv2 \
    --max_steps 50000 \
    # SPC disabled by default - watch for diagnostic logs

# Stage 2: If plateau observed, enable SPC
python train_unified_llm.py \
    --model_type ontological_hybrid \
    --model_size medium \
    --enable_srk \
    --enable_rss \
    --controller pidv2 \
    --enable_sovereign_phase_controller \    # ← Enable when plateau hits
    --spc_entropy_warning 0.5 \              # Optional: tune thresholds
    --spc_min_boost_duration 150 \           # Optional: longer boost
    --resume checkpoints_medium/checkpoint_15000.pt \
    --max_steps 50000
```

#### SPC Status Logs

**When ENABLED:**
```
🟢 [SPC] MONITORING | Level:NORMAL | Force:0.15
🟡 [SPC] ACTIVE | Level:CAUTION | Force:0.30 | Rotations:[O9:-0.16rad]
🟠 [SPC] ACTIVE | Level:WARNING | Force:0.60 | Rotations:[O9:-0.47rad,O12:0.31rad]
🔴 [SPC] ACTIVE | Level:CRITICAL | Force:1.00 | Rotations:[O9:-0.79rad,O12:1.05rad,O6:0.00rad]
```

**When DISABLED (diagnostic):**
```
🟢 [SPC-DIAGNOSTIC] Level:NORMAL
🟠 [SPC-DIAGNOSTIC] WOULD TRIGGER | Level:WARNING | Force:0.60
```

#### Important Notes

1. **Start Disabled**: Always start training with SPC disabled. Enable only when you observe actual plateaus/collapse.

2. **Monitor Diagnostics**: Watch for `WOULD TRIGGER` logs during normal training to understand when SPC would activate.

3. **Gradient Monitoring**: After enabling, monitor gradient norms. If you see >10x spikes, reduce `--spc_max_rotation` or `--spc_alpha`.

4. **Hysteresis is Critical**: Don't lower `--spc_min_boost_duration` below 50 steps or you risk oscillation.

5. **Layer Targeting is Automatic**: SPC automatically determines which layers need rotation based on Vritti/Bhava/Kosha diagnostics.

6. **Combines with SGP**: When SPC triggers, SGP (Stochastic Gradient Persistence) also accelerates, creating a combined intervention.

7. **Not a Replacement**: SPC is an emergency intervention, not a replacement for proper training dynamics. Fix underlying issues (learning rate, batch size, data quality) first.

**Reference:** Gemini's graduated response, rotation damping, and layer targeting proposal (2026-01-13)

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

## Phase Layer Learning Diagnostics

### Overview

The `debug_phase_layer_learning.py` script provides definitive tests to verify that phase attention layers are actually learning and contributing to model performance. This is critical for ontological models where phase attention handles long-range dependencies.

**When to Use:**
- After training to verify phase layers learned meaningful representations
- When PPL is unexpectedly high or not decreasing
- When model outputs are repetitive despite training
- Before deploying to confirm architecture is working correctly

### Quick Start

```bash
# RECOMMENDED: Quick gradient flow check (runs 5 synthetic training steps)
python debug_phase_layer_learning.py --checkpoint checkpoints/best.pt --check_gradients

# Full evaluation harness (comprehensive phase ablation tests)
python debug_phase_layer_learning.py --checkpoint checkpoints/best.pt --run_full_harness

# Both gradient check + full harness
python debug_phase_layer_learning.py --checkpoint checkpoints/best.pt --check_gradients --run_full_harness
```

### CLI Parameters

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--checkpoint` | str | required | Path to model checkpoint (.pt file) |
| `--device` | str | cuda | Device to use (cuda/cpu) |
| `--batch_size` | int | 4 | Batch size for evaluation |
| `--output` | str | None | Path to save results JSON |
| `--check_gradients` | flag | False | Run gradient flow check (quick training step test) |
| `--gradient_steps` | int | 5 | Number of steps for gradient check |
| `--run_full_harness` | flag | False | Run complete phase evaluation harness |
| `--phase_eval_mode` | str | normal | Phase evaluation mode: `normal`, `zero`, `noise`, `shuffle` |
| `--phase_noise_sigma` | float | 0.03 | Standard deviation for noise mode |
| `--phase_noise_sigmas` | str | 0.00,0.03,0.10,0.30 | Comma-separated noise sigmas for sweep |
| `--phase_eval_lengths` | str | 128,256,512,1024 | Comma-separated sequence lengths (clamped to model's max_seq_len) |
| `--phase_eval_runs` | int | 3 | Number of runs to average for noise mode |

### Test 1: Gradient Flow Check (`--check_gradients`)

**Purpose:** Verify gradients flow through phase layers during training.

**What It Does:**
1. Runs N synthetic training steps with backward passes
2. Computes `phase_grad_norm` vs `total_grad_norm` ratio
3. Identifies which phase layers have zero/tiny/healthy gradients
4. Provides per-layer gradient breakdown

**Example Output:**
```
======================================================================
  PHASE GRADIENT FLOW CHECK
======================================================================

  [PhaseGradientMonitor] Identified 42 phase parameters
    - layers_1_8.0.phase_attn.q_proj.weight
    - layers_1_8.0.phase_attn.k_proj.weight
    ...

  Running 5 gradient check steps...
  Step   Loss         Phase Grad     Total Grad     Ratio      Status
  ----------------------------------------------------------------------
  0      10.8234      0.012456       1.234567       0.0101     ✅ OK
  1      10.7891      0.013201       1.198234       0.0110     ✅ OK
  2      10.8012      0.011987       1.245678       0.0096     ✅ OK
  3      10.7654      0.012789       1.201234       0.0106     ✅ OK
  4      10.7432      0.013456       1.187654       0.0113     ✅ OK

  Summary:
    Average phase_grad_ratio: 0.010520
    Average phase_grad_norm: 0.012778
    Steps with zero phase grad: 0/5

  Gradient Flow Verdict:
    ✅ PASS: Phase gradients are flowing (ratio=0.0105)

  Phase Parameter Gradient Breakdown:
    layers_1_8.0.phase_attn: 0.003456 (8 params)
    layers_1_8.1.phase_attn: 0.002987 (8 params)
    ...
```

**Verdict Meanings:**

| Verdict | Meaning | Action |
|---------|---------|--------|
| ❌ ZERO | Phase gradients are ALWAYS zero | Phase layers not connected to loss. Check model wiring. |
| ⚠️ TINY | Phase gradient ratio < 0.001 | Phase contribution suppressed. Check `alpha_phase`, `aux_scale`. |
| ✅ OK | Gradient ratio 0.001-0.3 | Healthy gradient flow. |
| ⚠️ HUGE | Phase gradient ratio > 0.3 | Phase may dominate local attention. |

### Test 2: Phase Ablation (`--phase_eval_mode zero`)

**Purpose:** Prove phase attention is necessary for performance by zeroing it out.

**Expected Result (if phase is learning):**
- At long context (512-1024 tokens): PPL increases >5% when phase=0
- At short context (128 tokens): Smaller or no effect (local attention sufficient)

**Example:**
```bash
python debug_phase_layer_learning.py --checkpoint checkpoints/best.pt \
    --phase_eval_mode zero --phase_eval_lengths 128,512,1024
```

### Test 3: Phase Noise Sweep (`--phase_eval_mode noise`)

**Purpose:** Prove model is sensitive to phase values (not just using phase as regularization).

**Expected Result (if phase is learning):**
- Monotonic PPL degradation as noise σ increases: 0.03 < 0.10 < 0.30
- Effect stronger at longer sequences

**Example:**
```bash
python debug_phase_layer_learning.py --checkpoint checkpoints/best.pt \
    --phase_eval_mode noise --phase_noise_sigmas 0.00,0.03,0.10,0.30
```

### Test 4: Phase Shuffle (`--phase_eval_mode shuffle`)

**Purpose:** Prove phase content is meaningful (alignment matters).

**Expected Result (if phase is learning):**
- Shuffling phase across batch/time degrades performance
- If shuffle has no effect, phase may be redundant

### Test 5: Full Evaluation Harness (`--run_full_harness`)

**Purpose:** Run complete evaluation matrix across all modes and sequence lengths.

**What It Does:**
1. Evaluates at multiple sequence lengths (128, 256, 512, 1024)
2. Tests all phase modes (normal, zero, noise@σ, shuffle)
3. Computes ΔPPL and ΔRep vs baseline (normal)
4. Generates automated verdict

**Example Output:**
```
======================================================================
  VERDICT TABLE: ΔPPL and ΔRep vs Normal
======================================================================

  Seq Len    Mode            PPL        ΔPPL         ΔRep
  -------------------------------------------------------
  128        zero            25.34      +0.52 (+2.1%)    -0.2%
  512        zero            28.91      +2.45 (+9.3%)↑↑  +1.5%
  1024       zero            32.67      +4.12 (+14.4%)↑↑ +2.8%↑
  1024       noise@0.03      29.12      +0.57 (+2.0%)    +0.3%
  1024       noise@0.10      30.45      +1.90 (+6.6%)↑   +0.8%
  1024       noise@0.30      33.21      +4.66 (+16.3%)↑↑ +1.9%
  1024       shuffle         31.89      +3.34 (+11.7%)↑↑ +2.1%↑

======================================================================
  FINAL VERDICT
======================================================================

  ✅ PHASE LAYERS ARE LEARNING

  Evidence:
    • PASS: Zero ablation at seq=1024 caused 14.4% PPL increase
    • PASS: Shuffle test at seq=1024 caused 11.7% PPL increase
    • PASS: Noise sweep shows monotonic PPL degradation
    • PASS: Length-dependent sensitivity (short: 2.1%, long: 14.4%)
```

### Interpreting Results

**✅ Phase IS Learning (All conditions met):**
1. Zero ablation at long context causes >5% PPL increase
2. Noise sweep shows monotonic degradation
3. Shuffle is worse than normal
4. Effect increases with sequence length

**❌ Phase NOT Learning (Any condition fails):**
1. Zero ablation has <5% effect → Phase not contributing
2. Noise improves PPL → Phase may be harmful noise
3. Shuffle has no effect → Phase content meaningless
4. No length-dependent effect → Phase not handling long-range

### Common Failure Patterns

#### Pattern 1: PPL ~50,000+ (Near Random)

**Symptom:** PPL is near vocab_size, entropy at maximum.

```
  [PHASE-EVAL] mode=normal | seq=1024 | ppl=58733.12 | entropy=10.66
```

**Diagnosis:** Model hasn't learned language modeling at all. Phase testing is meaningless until base model works.

**Action:** Check training loss history. Resume training or fix data pipeline.

#### Pattern 2: Zero Gradients

**Symptom:** `--check_gradients` shows all zeros.

```
  Gradient Flow Verdict:
    ❌ CRITICAL: Phase gradients are ALWAYS ZERO
```

**Diagnosis:** Phase layers not connected to loss path.

**Action:**
- Check if `phase_attn` is in forward path
- Verify `intent_phase` is passed through hybrid layers
- Check `alpha_phase` is not zero

#### Pattern 3: Tiny Gradients

**Symptom:** Phase gradient ratio < 0.001.

```
  Gradient Flow Verdict:
    ⚠️  WARNING: Phase gradients are very small (ratio=0.000234)
```

**Diagnosis:** Phase contribution suppressed.

**Action:**
- Increase `--alpha_phase` (default 0.2, try 0.4)
- Check `aux_scale` in PhaseAttentionLayer (should be 1.0, not 0.1)
- Reduce double-dampening if present

#### Pattern 4: No Length-Dependent Effect

**Symptom:** Zero ablation has same effect at all lengths.

```
  128: zero → +1.2% PPL
  512: zero → +1.1% PPL
  1024: zero → +1.3% PPL
```

**Diagnosis:** Phase attention not handling long-range dependencies specifically.

**Action:**
- Phase may be acting as generic regularization
- Check sync_steps and sync_lr parameters
- Consider increasing phase temperature for sharper attention

### Integration with Training

You can use `PhaseGradientMonitor` during training to log gradient flow:

```python
from debug_phase_layer_learning import PhaseGradientMonitor

# In training loop
monitor = PhaseGradientMonitor(model)

for step, batch in enumerate(dataloader):
    loss.backward()

    if step % 100 == 0:
        stats = monitor.compute_gradient_stats()
        print(f"Step {step}: phase_ratio={stats['phase_grad_ratio']:.4f}")

        if stats['phase_grad_norm'] == 0:
            print("WARNING: Phase gradients are zero!")
```

### Reference: Expected "Phase is Learning" Signatures

| Metric | Healthy Range | Warning |
|--------|---------------|---------|
| Phase gradient ratio | 0.001 - 0.3 | <0.001 (suppressed) or >0.3 (dominating) |
| Zero ablation ΔPPL (1024 tokens) | >5% increase | <2% (phase not contributing) |
| Noise monotonicity | Strict degradation | PPL improves with noise (phase harmful) |
| Shuffle effect | >3% PPL increase | <1% (alignment doesn't matter) |
| Length-dependent sensitivity | Long > Short effect | Equal effect (not handling long-range) |

### Example: Debugging a Failed Model

```bash
# Step 1: Check gradient flow first (quick)
python debug_phase_layer_learning.py --checkpoint checkpoints_medium/best.pt --check_gradients

# If gradients OK, run full harness
python debug_phase_layer_learning.py --checkpoint checkpoints_medium/best.pt --run_full_harness

# Save results for analysis
python debug_phase_layer_learning.py --checkpoint checkpoints_medium/best.pt \
    --check_gradients --run_full_harness --output phase_diagnostics.json
```

## File Structure

```
symbolu/
├── symbolu/ontological/
│   ├── symbolu12_bhava.py              # SymbolU12 with Phase Attention
│   └── ...
├── symbolu/phase_transformer.py        # Phase attention implementations
├── train_unified_llm.py                # Main training script
├── debug_phase_layer_learning.py       # Phase layer diagnostics (this guide)
├── diagnose_phase_attention.py         # Phase attention analysis
└── docs/
    ├── ontological-training-guide.md   # 100D Engine training
    └── unified-llm-training-guide.md   # This file
```

## References

- [Phase Attention Paper](https://arxiv.org/abs/...) - LRA-optimized O(n) attention
- [Formula 1331](docs/formula-1331.md) - 9:3 Hierarchical Gradient Scaling
- [Sovereign State Design](docs/sovereign-state.md) - 128D state architecture
