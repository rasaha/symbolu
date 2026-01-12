# train_unified_llm.py - CLI Reference

Unified SymbolU LLM Training Script with Phase Attention, Ontological States, and Sovereign-Lagrangian Loss.

## Quick Start

```bash
# Basic training (small model, wikitext103)
python train_unified_llm.py

# Medium model with 8-bit optimizer
python train_unified_llm.py --model_size medium --use_8bit_optimizer

# Hybrid model with Phase Attention
python train_unified_llm.py --model_type hybrid --cosine_mode shifted

# Resume from checkpoint
python train_unified_llm.py --resume checkpoints_unified/step_5000.pt
```

---

## Master Training Script

For production training with all features correctly integrated, use the master training script:

```bash
./scripts/run_master_training.sh
```

### Usage

```bash
# Default: small model, 50K steps with all features
./scripts/run_master_training.sh

# Quick test (~10M params, 1000 steps)
./scripts/run_master_training.sh --quick

# Production medium model
./scripts/run_master_training.sh --size medium --steps 100000

# Resume from checkpoint
./scripts/run_master_training.sh --resume checkpoints_unified/step_25000.pt
```

### Script Options

| Option | Description |
|--------|-------------|
| `--size SIZE` | Model size: tiny, small, medium, large (default: small) |
| `--steps N` | Maximum training steps (default: 50000) |
| `--batch N` | Batch size (default: 8, auto-adjusted for GPU) |
| `--lr RATE` | Base learning rate (default: 3e-4) |
| `--checkpoint DIR` | Checkpoint directory (default: checkpoints_unified) |
| `--resume PATH` | Resume from checkpoint |
| `--dataset NAME` | Dataset: wikitext103, wikitext2, fineweb (default: fineweb) |
| `--quick` | Quick mode: tiny model, 1000 steps |

### Features Enabled

The master script integrates all training features:

1. **Adaptive Learning Rate** - Automatic LR adjustment with safety bounds
2. **PPL-Gated Curriculum** - FOUNDATION → REGULARIZATION → GROUNDING → SOVEREIGN
3. **Sequence Length Curriculum** - Gradual ramping from 256 to 1024
4. **9:3 Hierarchical Gradient Scaling** - Authority/Sensory balance
5. **PIDv2 Controller** - Dynamic S/A ratio control
6. **Sovereign-Lagrangian Loss** - B1/S3 consistency + signal weights
7. **Kosha Gyroscope** - Homeostatic self-regulation
8. **CSR Grounding** - Phoneme-ontological alignment
9. **SGP Cement** - Gradient persistence for stability
10. **SRK** - Sovereign Reasoning Kernel with layer hooks
11. **Phase-JEPA** - Perceptual learning
12. **Ontological Bridge** - Layer 4 projection
13. **Evolutionary Flow** - Layer transition coherence
14. **Dynamic Relaxation** - 9:3 → 6:6 transition
15. **Saturation Gate** - Auto-thaw for frozen layers
16. **Stress Probe** - Emergency recovery

---

## Model Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--model_type` | str | `ontological` | Model architecture type |
| `--model_size` | str | `small` | Model size preset |
| `--max_seq_len` | int | `2048` | Maximum sequence length |

### Model Type Choices
| Value | Description | Use When |
|-------|-------------|----------|
| `standard` | O(n²) baseline attention | Benchmarking, comparison |
| `phase` | Phase attention only | Testing phase mechanism |
| `hybrid` | Local + Phase attention | Production training |
| `ontological` | Ontological state tracking | Sanskrit/semantic tasks |
| `ontological_hybrid` | Two-Tier AGI (full system) | Advanced research |
| `gen2` | Generation 2 architecture | Experimental |

### Model Size Presets
| Size | Layers | Hidden | Heads | Params (approx) |
|------|--------|--------|-------|-----------------|
| `tiny` | 4 | 256 | 4 | ~10M |
| `small` | 12 | 768 | 12 | ~125M |
| `medium` | 24 | 1024 | 16 | ~350M |
| `large` | 32 | 2048 | 32 | ~1.3B |

---

## Training Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--batch_size` | int | `8` | Batch size per GPU |
| `--gradient_accumulation` | int | `1` | Gradient accumulation steps |
| `--max_steps` | int | `10000` | Maximum training steps |
| `--learning_rate` | float | `3e-4` | Peak learning rate |
| `--use_per_layer_clipping` | flag | `False` | Clip authority/sensory gradients separately |
| `--use_8bit_optimizer` | flag | `False` | Use bitsandbytes 8-bit AdamW |
| `--use_compile` | flag | `False` | Use torch.compile() for faster training |
| `--no_compile` | flag | `False` | Disable torch.compile() |
| `--seed` | int | `42` | Random seed |

### Notes
- **batch_size**: Effective batch = `batch_size * gradient_accumulation`
- **use_8bit_optimizer**: Saves ~50% optimizer memory. Requires `bitsandbytes` package.
- **use_per_layer_clipping**: Respects 9:3 Authority/Sensory design. Enable for ontological models.
- **use_compile**: PyTorch 2.0+ only. Can provide 15-30% speedup. May have issues with dynamic shapes.

---

## Dataset

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--dataset` | str | `wikitext103` | Dataset type: `wikitext103`, `wikitext2`, or `fineweb` |
| `--dataset_name` | str | `HuggingFaceFW/fineweb` | HuggingFace dataset name (for fineweb mode) |
| `--dataset_subset` | str | `sample-10BT` | Dataset subset/config (for fineweb mode) |
| `--cache_val_batches` | int | `20` | Pre-cache N validation batches (streaming datasets) |
| `--cache_dataset` | flag | `False` | Download and cache dataset locally (vs streaming) |

### Dataset Choices

| Value | Type | Size | Description |
|-------|------|------|-------------|
| `wikitext103` | Static | ~100M tokens | WikiText-103, recommended for quick experiments |
| `wikitext2` | Static | ~2M tokens | WikiText-2, good for quick tests |
| `fineweb` | Streaming | 10B+ tokens | FineWeb/FineWeb-edu, for production training |

### FineWeb Configuration

For `--dataset fineweb`, configure with:

| dataset_name | Description | Use When |
|--------------|-------------|----------|
| `HuggingFaceFW/fineweb` | Web text (CC-based) | General pretraining |
| `HuggingFaceFW/fineweb-edu` | Educational content | Higher quality, educational focus |

| dataset_subset | Size | Description |
|----------------|------|-------------|
| `sample-10BT` | ~10B tokens | Quick experiments |
| `sample-100BT` | ~100B tokens | Extended training |
| `CC-MAIN-*` | Varies | Specific Common Crawl snapshots |

### Example: FineWeb Training (Streaming)
```bash
python train_unified_llm.py \
    --dataset fineweb \
    --dataset_name "HuggingFaceFW/fineweb-edu" \
    --dataset_subset "sample-10BT" \
    --cache_val_batches 20
```

### Example: FineWeb Training (Cached Locally)
```bash
python train_unified_llm.py \
    --dataset fineweb \
    --dataset_name "HuggingFaceFW/fineweb-edu" \
    --dataset_subset "sample-10BT" \
    --cache_dataset
```

### Notes
- **Streaming** (default): Data streamed on-the-fly, requires network, minimal disk usage
- **cache_dataset**: Downloads to `~/.cache/huggingface/datasets/`, no network after first run
- **cache_val_batches**: Pre-caches validation batches to eliminate 7-minute "Resolving data files" delay
- Set `--cache_val_batches 0` to disable caching (not recommended)

---

## Memory Optimization

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--gradient_checkpointing` | flag | `False` | Enable gradient checkpointing |
| `--checkpoint_offload_cpu` | flag | `False` | Offload checkpoints to CPU |
| `--mixed_precision` | str | `bf16` | Mixed precision mode |

### Mixed Precision Choices
| Value | Description | Use When |
|-------|-------------|----------|
| `none` | Full FP32 | Debugging, numerical issues |
| `fp16` | FP16 with loss scaling | Older GPUs (V100) |
| `bf16` | BF16 (no loss scaling) | Modern GPUs (A100, H100) - **recommended** |

### Notes
- **gradient_checkpointing**: Reduces memory ~30-40% at ~15% speed cost
- **checkpoint_offload_cpu**: For very large models when VRAM is tight (metabolic tuning)

---

## Hybrid/Local Attention

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--local_backend` | str | `auto` | LocalAttention backend |
| `--window_size` | int | `256` | Local attention window size |
| `--local_layers` | int | `4` | Number of local-only layers |
| `--alpha_local` | float | `0.8` | Weight for local attention |
| `--alpha_phase` | float | `0.2` | Weight for phase attention |

### Local Backend Choices
| Value | Description | Use When |
|-------|-------------|----------|
| `auto` | Auto-detect best backend | Default choice |
| `flash` | Flash Attention 2 | Best performance if available |
| `sdpa` | PyTorch SDPA | Good fallback |
| `unfold` | Manual unfold | Debugging, compatibility |

### Notes
- **window_size**: Larger = more context but O(n×w) memory. Try 256-1024.
- **local_layers**: First N layers use local-only attention
- **alpha_local + alpha_phase**: Should sum to 1.0 for hybrid layers

---

## Alpha Decay Schedule

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--alpha_phase_start` | float | `0.6` | Initial alpha_phase value |
| `--alpha_phase_end` | float | `0.4` | Final alpha_phase after decay |
| `--alpha_decay_steps` | int | `10000` | Steps for decay |

### Notes
- Phase attention starts strong (0.6) and decays as local attention learns
- Set `alpha_phase_start = alpha_phase_end` to disable decay

---

## Cosine Mode (Phase Attention)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--cosine_mode` | str | `standard` | Cosine interaction mode |

### Choices
| Value | Range | Description | Use When |
|-------|-------|-------------|----------|
| `standard` | [-1, 1] | Classic cos similarity | Baseline |
| `shifted` | [0, 2] | `1 + cos` (no negative) | Prevents negative cancellation |
| `complex` | N/A | Uses both cos and sin | Directional asymmetry needed |

### Notes
- **shifted**: Often better for training stability - prevents tokens from "canceling out"
- **complex**: Experimental, captures phase direction

---

## State Decay (decay_gamma)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--decay_gamma` | float | `1.0` | State decay factor |

### Values
| Value | Effective Memory | Description |
|-------|-----------------|-------------|
| `1.0` | Infinite | Full context (default) |
| `0.99` | ~100 tokens | Slight recency bias |
| `0.95` | ~20 tokens | Strong local focus (like Mamba/RWKV) |
| `0.9` | ~10 tokens | Very local |

### Notes
- Lower values = more "forgetting" of distant tokens
- Useful for tasks where recent context matters more

---

## Ontological Hybrid (Two-Tier AGI)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--state_dim` | int | `124` | CognitiveState dimension |
| `--project_per_head_dim` | flag | `False` | Project state delta to [H, D_h] |

### State Dimension Breakdown (124)
- 44: Phoneme features
- 64: Topic embeddings
- 12: Bhava (emotional states)
- 4: Dynamics coefficients

### Notes
- **project_per_head_dim**: Finer control but more parameters

---

## Ontological Loss Terms

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--bhava_lambda` | float | `0.1` | Bhava relationship loss weight |
| `--coherence_lambda` | float | `0.05` | Coherence loss weight |
| `--no_coherence_loss` | flag | `False` | Disable coherence loss |

### Notes
- **bhava_lambda**: Higher = stronger emotional consistency
- **coherence_lambda**: Penalizes incoherent state transitions

---

## Sovereign-Lagrangian Loss (Patent B1/S3)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_sovereign_loss` | flag | `False` | Enable Sovereign-Lagrangian loss |
| `--b1_lambda` | float | `0.5` | Consistency Lagrangian weight [B1] |
| `--mu_s3` | float | `0.2` | Global Coherence weight [S3] |
| `--sovereign_weight_r` | float | `5.0` | R-Signal (ontology) weight |
| `--sovereign_weight_s` | float | `2.0` | S-Signal (referent) weight |
| `--sovereign_weight_c` | float | `0.5` | C-Signal (phoneme) weight |
| `--enable_stability_constraint` | flag | `False` | Enable S8 entropy-based anchoring |
| `--gc_floor` | float | `0.65` | Min Guna Coherence before PIDv2 |

### Notes
- Replaces standard cross-entropy with multi-signal loss
- **b1_lambda**: Forward/backward alignment (bidirectional consistency)
- **mu_s3**: Phase-lock penalty for global coherence

---

## Entropy Floor (Anti-Repetition)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_entropy_floor` | flag | `False` | Enable entropy floor penalty |
| `--entropy_floor` | float | `0.48` | Minimum entropy target |
| `--entropy_floor_weight` | float | `0.1` | Penalty weight |

### Notes
- Breaks "repetition curse" by penalizing low-entropy outputs
- Enable if model generates repetitive text
- Lower entropy_floor = allow more focused/repetitive outputs

---

## Force Evolution Stage

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--force_evolution_stage` | int | `None` | Force specific evolution stage |

### Stages
| Stage | Split | Description |
|-------|-------|-------------|
| 1 | 6:6 | Balanced |
| 2 | 5:7 | Sensory bias |
| 3 | 4:8 | Strong sensory |
| 4 | 3:9 | Rajas (emergency) |

### Notes
- Bypasses automatic evolution detection
- Use for debugging or forcing specific behavior

---

## Stress-Probe Emergency System

Automatic detection and recovery from "stiffness" (model collapse).

### Trigger Options
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_stress_probe` | flag | `False` | Enable automatic stress-probe |
| `--force_stress_probe` | flag | `False` | Force immediate activation |
| `--stress_probe_entropy_trigger` | float | `0.42` | Trigger when entropy < this |
| `--stress_probe_rep3_trigger` | float | `0.18` | Trigger when REP-3 > this |
| `--stress_probe_utr_trigger` | float | `0.55` | Trigger when UTR < this |
| `--stress_probe_drs_trigger` | float | `12.0` | Trigger when DRS > this |
| `--stress_probe_coherence_min` | float | `0.80` | Only if coherence > this |
| `--stress_probe_patience` | int | `2` | Consecutive bad evals to trigger |

### Behavior Options
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--stress_probe_authority_scale` | float | `0.05` | Authority gradient scale (nearly frozen) |
| `--stress_probe_lr_factor` | float | `0.60` | LR reduction factor |
| `--stress_probe_min_steps` | int | `100` | Minimum steps in probe |
| `--stress_probe_max_steps` | int | `300` | Maximum steps in probe |

### Exit Conditions
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--stress_probe_exit_entropy` | float | `0.55` | Exit when entropy > this |
| `--stress_probe_exit_rep3` | float | `0.12` | Exit when REP-3 < this |
| `--stress_probe_lr_restore_steps` | int | `50` | Gradual LR restore steps |

### Notes
- Activates 3:9 Rajas split when model becomes "stiff" (high coherence but repetitive)
- Reduces LR and freezes authority layers to allow sensory exploration

---

## Logging & Checkpoints

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--log_every` | int | `10` | Log every N steps |
| `--eval_every` | int | `100` | Evaluate every N steps |
| `--save_every` | int | `1000` | Save checkpoint every N steps |
| `--checkpoint_dir` | str | `checkpoints_unified` | Checkpoint directory |
| `--quiet` | flag | `False` | Only print Critical 5 metrics |
| `--tensorboard` | flag | `True` | Enable TensorBoard logging |
| `--no_tensorboard` | flag | `False` | Disable TensorBoard |

### Resume Options
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--resume` | str | `""` | Path to checkpoint |
| `--resume_weights_only` | flag | `False` | Only load weights, reset optimizer |

### Notes
- **quiet mode**: Prints only Loss, PPL, S/A ratio, Guna Coherence, Confidence
- **resume_weights_only**: Useful for fine-tuning with fresh optimizer state

---

## Kosha-Vritti Diagnostics & Steering

Maps training state to Vedantic coordinate system for ontological debugging and active phase alignment.

### Diagnostic Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_kosha_diagnostics` | flag | `False` | Enable Kosha-Vritti diagnostic output |
| `--kosha_log_every` | int | `0` | Log Kosha every N steps (0 = use log_every) |

### Steering Options (Active Intervention)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_kosha_steering` | flag | `False` | Enable phase coupling steering |
| `--kosha_steering_force` | float | `0.15` | Steering strength (0.0-1.0, start gentle) |
| `--kosha_steering_warmup` | int | `100` | Steps before steering activates |

### Coordinate Axes

| Axis | Source | Range | Interpretation |
|------|--------|-------|----------------|
| Reality (r) | Logits Entropy | -1 to +1 | +1=Unmanifest (uncertain), -1=Manifest (confident) |
| Time (t) | Gradient Norm | -1 to +1 | -1=Past/Memory, +1=Future/Learning |

### Phase Angle (Geometric Truth)

The phase angle is computed as `atan2(t, r)` to ensure the compass matches the map:
- **0°**: Points toward +r (Unmanifest)
- **90°**: Points toward +t (Future)
- **180°**: Points toward -r (Manifest)
- **270°**: Points toward -t (Past)

### Kosha Zones (Cartesian Quadrants)

| Zone | Quadrant | Angle | Coordinates | Description |
|------|----------|-------|-------------|-------------|
| ANANDAMAYA | Q1 | 0-90° | +r, +t | Purpose/Bliss (optimal flow) |
| VIJNANAMAYA | Q2 | 90-180° | -r, +t | Logic/Wisdom (valid learning) |
| ANNAMAYA | Q3 | 180-270° | -r, -t | Action/Physical (execution) |
| MANOMAYA | Q4 | 270-360° | +r, -t | Memory/Mind (recall) |

### Vritti States (Cognitive Modes)

| State | Condition | Description | Icon |
|-------|-----------|-------------|------|
| PRAMANA | r<-0.3, t>0.2 | Valid Learning (confident + progressing) | ✅ |
| VIPARYAYA | r<-0.5, t<-0.2 | Hallucination Risk (over-confident + stagnant) | ⚠️ |
| VIKALPA | -0.3<r<0.3 | Conceptual Exploration (transitional) | 🔍 |
| NIDRA | r>0.3, |t|<0.2 | Plateau/Stalled (uncertain + stuck) | 💤 |
| SMRITI | r<0, t<-0.3 | Memory Recall (confident + decaying) | 📚 |
| PRAJNA | else | Balanced State | ⚖️ |

### Example Output (Diagnostic Only)
```
    🧭 [KOSHA] Coords: r=-0.42 (Manifest) | t=+0.35 (Future) --> Zone: VIJNANAMAYA
    📐 [PHASE] Angle: 140° (Logic) | Entropy: 2.90 | GradNorm: 1.45
    🧠 [VRITTI] State: PRAMANA (Valid Learning) ✅
```

### Example Output (With Steering Active)
```
    🧭 [KOSHA] Coords: r=-0.10 (Transitional) | t=+0.05 (Present) --> Zone: VIJNANAMAYA
    📐 [PHASE] Angle: 153° (Logic) | Entropy: 5.52 | GradNorm: 1.12
    🧠 [VRITTI] State: VIKALPA (Conceptual Exploration) 🔍
    🎯 [STEER] Target: 153° | Current: 41° | Error: 112.0° ↻ | Loss: 0.0234
```

### How Steering Works

1. **Computes Target Angle**: From entropy (r) and gradient norm (t) using `atan2(t, r)`
2. **Reads Current Phase**: Treats embedding pairs as complex numbers (Re, Im)
3. **Applies Phase Loss**: Penalizes deviation from target angle
4. **Gradient Descent**: Model learns to align internal representations with semantic intent

### When to Use Steering

| Symptom | Diagnostic | Action |
|---------|------------|--------|
| Zone correct but wrong outputs | Mind-Body Split | Enable steering at 0.15 |
| Persistent hallucinations | Phase locked at wrong angle | Increase force to 0.25 |
| Loss explodes after steering | Force too strong | Reduce to 0.05-0.10 |

### Notes
- **Diagnostic mode**: Read-only, does not affect training
- **Steering mode**: ACTIVE INTERVENTION - modifies loss landscape
- **Start gentle**: Use `--kosha_steering_force 0.15` initially
- **Monitor phase error**: Should decrease over 500+ steps
- **VIPARYAYA warning**: If persistent, indicates over-confident generation
- Pairs well with EvoFlow metrics for comprehensive monitoring

---

## Kosha Gyroscope (v2.2.5)

Homeostatic self-regulation system that prevents pathological training states (looping, fixation, collapse).

### Core Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_kosha_gyroscope` | flag | `False` | Enable gyroscope system |
| `--gyroscope_base_gain` | float | `0.15` | Gentle observation gain |
| `--gyroscope_max_gain` | float | `3.0` | Strict enforcement gain |
| `--gyroscope_ppl_ceiling` | float | `100.0` | PPL above which gain stays low |
| `--gyroscope_target_ppl` | float | `30.0` | PPL at which max gain kicks in |

### Kosha Thresholds (Golden Ratio Based)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--gyroscope_floor_mental` | float | `0.236` | Minimum Mental Kosha |
| `--gyroscope_ceiling_mental` | float | `0.382` | Maximum Mental (Bliss Damper) |
| `--gyroscope_floor_physical` | float | `0.382` | Minimum Physical Kosha |
| `--gyroscope_ceiling_physical` | float | `0.618` | Maximum Physical Kosha |
| `--gyroscope_floor_intellect` | float | `0.250` | Minimum Intellect Kosha |
| `--gyroscope_ceiling_intellect` | float | `0.618` | Maximum Intellect Kosha |
| `--gyroscope_floor_vital` | float | `0.236` | Minimum Vital Kosha |
| `--gyroscope_ceiling_vital` | float | `0.786` | Maximum Vital Kosha |
| `--gyroscope_floor_bliss` | float | `0.236` | Minimum Bliss Kosha |
| `--gyroscope_ceiling_bliss` | float | `0.618` | Maximum Bliss Kosha |

### Gate and Damper Behavior

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--gyroscope_trap_threshold` | float | `0.618` | Reality Rip trap threshold |
| `--gyroscope_gate_threshold` | float | `0.30` | Physical gate threshold |
| `--gyroscope_balance_target` | float | `0.25` | Target balance ratio |
| `--gyroscope_gate_temperature` | float | `10.0` | Gate softmax temperature |
| `--gyroscope_damper_steepness` | float | `5.0` | Bliss Damper curve steepness |
| `--gyroscope_gate_steepness` | float | `5.0` | Physical Gate curve steepness |
| `--gyroscope_rip_multiplier` | float | `2.0` | Reality Rip penalty multiplier |

### Domain Morphing

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--gyroscope_domain_morph_enabled` | flag | `True` | Enable domain morphing |
| `--disable_gyroscope_domain_morph` | flag | `False` | Disable domain morphing |
| `--gyroscope_domain_morph_ema_decay` | float | `0.9` | EMA decay for morphing |
| `--gyroscope_domain_morph_internal_weight` | float | `0.5` | Internal signal weight |
| `--gyroscope_domain_morph_external_weight` | float | `0.5` | External signal weight |

### Graduation Criteria

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--gyroscope_graduation_ppl` | float | `30.0` | PPL threshold for graduation |
| `--gyroscope_graduation_variance` | float | `1.5` | Max PPL variance for graduation |
| `--gyroscope_graduation_window` | int | `10` | Stability window for graduation |
| `--gyroscope_warmup_steps` | int | `100` | Steps before gyroscope fully active |
| `--gyroscope_rampdown_steps` | int | `500` | Steps for graduation rampdown |

### Advanced Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--gyroscope_temporal_window` | int | `3` | Temporal smoothing window |
| `--gyroscope_vital_momentum` | flag | `True` | Enable Vital momentum tracking |
| `--disable_gyroscope_vital_momentum` | flag | `False` | Disable Vital momentum |
| `--gyroscope_floor_push_factor` | float | `0.5` | Floor push strength |
| `--gyroscope_ceiling_clamp_factor` | float | `0.5` | Ceiling clamp strength |
| `--gyroscope_steepness` | float | `5.0` | Overall sigmoid steepness |

### Notes
- Golden Ratio thresholds (φ = 0.618) based on optimal activation patterns
- Bliss Damper dilutes creative expansion when Mental dominance exceeds ceiling
- Physical Gate requires minimum grounding before Intellectual activation
- Reality Rip triggers hard reversal when model gets trapped with gate closed

---

## PIDv2 Controller

Automatic authority/sensory balance controller.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--controller` | str | `none` | Controller type |
| `--pidv2_kp_min` | float | `0.10` | Minimum Kp (when noisy) |
| `--pidv2_kp_max` | float | `0.30` | Maximum Kp (when clean) |
| `--pidv2_kp_sensitivity` | float | `5.0` | Volatility sensitivity |
| `--pidv2_ki` | float | `0.02` | Integral gain |
| `--pidv2_kd` | float | `0.10` | Derivative gain |
| `--pidv2_a_min` | float | `0.40` | Minimum authority factor |
| `--pidv2_w_s` | float | `0.30` | Semantic weight (prompt-based) |
| `--phase_ramp_steps` | int | `7000` | Phase LR ramp steps |

### Controller Choices
| Value | Description |
|-------|-------------|
| `none` | No controller |
| `pidv2` | Full PID controller |
| `emergency_pd` | PD-only for emergencies |

### Notes
- Adjusts authority/sensory gradient scaling based on training dynamics
- **pidv2_a_min**: Sensory floor - never reduces sensory below this

---

## Quality Sampling

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--sample_every` | int | `50` | Generate samples every N steps |

### Notes
- Set to `0` to disable sample generation
- Samples show model's current generation quality
- Higher values reduce overhead but less visibility

---

## LRA Validation (Long-Range Retrieval)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--lra_validate_every` | int | `0` | Run LRA every N steps (0=disabled) |
| `--lra_haystack_lengths` | str | `256,512,1024` | Comma-separated lengths |
| `--lra_num_samples` | int | `50` | Samples per test |

### Notes
- Tests model's ability to retrieve information from long contexts
- Enable to track long-range attention quality

---

## 9:3 Hierarchical Split (Formula 1331)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--use_9_3_split` | flag | `False` | Enable 9:3 gradient scaling |
| `--enable_gradient_scaling` | flag | `False` | Enable for ANY split |
| `--authority_layers` | int | `9` | Authority (State-Delta) layers |
| `--sensory_layers` | int | `3` | Sensory (Quadratic) layers |
| `--alpha_sens_initial` | float | `0.05` | Initial sensory gradient scale |
| `--alpha_sens_max` | float | `0.7` | Max sensory gradient scale |
| `--gradient_warmup_steps` | int | `500` | Warmup steps for gradient ramp |

### Notes
- Authority layers: Learn stable representations (lower LR)
- Sensory layers: Learn input patterns (higher LR initially dampened)
- **alpha_sens_initial**: Start low to prevent S/A spikes

---

## Layerwise Alpha Dampening

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_layerwise_alpha` | flag | `True` | Enable per-layer scaling |
| `--disable_layerwise_alpha` | flag | `False` | Disable per-layer scaling |
| `--alpha_output_scale` | float | `0.5` | Scale for output layers 9-11 |
| `--alpha_reasoning_scale` | float | `1.0` | Scale for reasoning layers 6-8 |

### Notes
- Output layers get more stable (lower alpha)
- Reasoning layers get full expressiveness

---

## Dynamic Relaxation (9:3 → 6:6)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_dynamic_relaxation` | flag | `True` | Enable automatic transition |
| `--disable_dynamic_relaxation` | flag | `False` | Disable transition |
| `--relaxation_mode` | str | `sa_ratio` | Trigger mode |
| `--relaxation_stability_threshold` | float | `0.50` | S/A ratio threshold |
| `--relaxation_stability_window` | int | `500` | Rolling window size |
| `--relaxation_streak_target` | int | `5` | Consecutive stable evals |
| `--force_relaxation_step` | int | `None` | Force at specific step |

### Relaxation Mode Choices
| Value | Description |
|-------|-------------|
| `sa_ratio` | S/A ratio based (recommended) |
| `average` | SSI rolling mean |
| `consecutive` | SSI streak count |

### Target Configuration
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--relaxation_target_authority` | int | `6` | Target authority layers |
| `--relaxation_target_sensory` | int | `6` | Target sensory layers |
| `--relaxation_thaw_alpha` | float | `0.05` | Dampened Thaw starting α |
| `--relaxation_thaw_steps` | int | `500` | Thaw ramp steps |
| `--relaxation_ppl_spike_threshold` | float | `0.20` | PPL spike % for Viparyaya |
| `--relaxation_recovery_steps` | int | `100` | Viparyaya recovery steps |

---

## Saturation Gate

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_saturation_gate` | flag | `True` | Enable saturation detection |
| `--disable_saturation_gate` | flag | `False` | Disable saturation gate |
| `--saturation_coherence_threshold` | float | `0.74` | Coherence threshold |
| `--saturation_patience` | int | `50` | Flat derivative steps |
| `--saturation_thaw_start` | float | `0.3` | Thaw starting α |
| `--saturation_thaw_end` | float | `0.7` | Thaw ending α |
| `--saturation_thaw_steps` | int | `100` | Thaw ramp steps |

---

## Weight Transfer

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_weight_transfer` | flag | `True` | Enable weight transfer |
| `--disable_weight_transfer` | flag | `False` | Disable weight transfer |
| `--guna_lock_steps` | int | `50` | Steps to freeze W_q/W_k |

### Notes
- Transfers learned weights from Authority to new Sensory layers
- **guna_lock_steps**: Freeze Q/K projections briefly after transfer

---

## Toroidal Evolutionary Bridge

O12 → O1 recursive intelligence (state carryover across sequences).

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_toroidal_bridge` | flag | `False` | Enable O12→O1 carryover |
| `--toroidal_lambda` | float | `0.1` | Consistency loss weight |
| `--toroidal_dropout` | float | `0.1` | Seed projection dropout |
| `--toroidal_use_gating` | flag | `True` | Use gated projection |
| `--toroidal_truncated_bptt` | int | `0` | Gradient flow steps (0=detach) |
| `--toroidal_coherence_threshold` | float | `0.3` | Discontinuity alarm threshold |

### Notes
- Creates "memory" across sequence boundaries
- **toroidal_truncated_bptt**: 0 = no gradients across sequences

---

## Evolutionary Flow System

Full evolutionary flow across layer transitions.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_evolutionary_flow` | flag | `True` | Enable evolutionary flow |
| `--disable_evolutionary_flow` | flag | `False` | Disable evolutionary flow |
| `--evo_lambda` | float | `0.1` | Overall loss weight |
| `--evo_micro_weight` | float | `0.3` | Per-gate coherence weight |
| `--evo_meso_weight` | float | `0.3` | Cluster coherence weight |
| `--evo_macro_weight` | float | `0.4` | Toroidal coherence weight |
| `--evo_dropout` | float | `0.1` | Gate dropout |
| `--evo_use_rmatrix` | flag | `True` | Use R-Matrix |
| `--evo_coherence_window` | int | `100` | History tracking steps |
| `--evo_resonance_alpha` | float | `0.1` | O12→O1 resonance strength |

### LR Modulation
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--evo_lr_modulation` | flag | `True` | Enable metacognitive LR |
| `--evo_lr_slowdown` | float | `0.5` | LR multiplier for SLOW_DOWN |
| `--evo_lr_accelerate` | float | `1.2` | LR multiplier for ACCELERATE |

---

## CSR Phoneme-Ontological Grounding

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_csr` | flag | `True` | Enable CSR grounding |
| `--disable_csr` | flag | `False` | Disable CSR |
| `--csr_lambda` | float | `0.1` | CSR injection strength |
| `--csr_tau` | float | `0.07` | InfoNCE temperature |
| `--csr_use_phase_gating` | flag | `True` | Gate Phase with CSR confidence |
| `--csr_trainable` | flag | `True` | Allow CSR projection to train |
| `--untie_embeddings` | flag | `False` | Untie input/output embeddings |
| `--csr_use_entropy_sink` | flag | `True` | Layer 0 entropy floor |
| `--csr_use_synthesis_gate` | flag | `True` | Layer 11 synthesis |
| `--csr_alignment_layer` | int | `2` | Alignment layer (2=concept, avoid 11) |
| `--csr_projector_lr_scale` | float | `0.1` | CSR projector LR fraction |
| `--csr_gradient_warmup_steps` | int | `0` | Steps before enabling CSR gradients |

### Notes
- **untie_embeddings**: CRITICAL when using CSR to prevent vocabulary corruption
- **csr_tau**: Lower = sharper gradients (0.07 is good default)
- **csr_alignment_layer**: Use 2 for concept formation, avoid 11 (output)

### CSR Tuning Guide

#### What Each Parameter Does

| Parameter | Plain English | Effect of Increasing |
|-----------|---------------|---------------------|
| `csr_lambda` | How much CSR loss contributes to total loss | Stronger phoneme-ontology alignment, may slow PPL improvement |
| `csr_tau` | Temperature (sharpness of gradient signal) | Lower = sharper gradients, more decisive alignment |
| `csr_projector_lr_scale` | How fast CSR↔Hidden projection adapts | Faster adaptation, may be less stable |
| `csr_alignment_layer` | Which layer CSR aligns to | Layer 1 = fundamental, Layer 2 = concept, Layer 3+ = higher abstraction |
| `csr_gradient_warmup_steps` | Steps before CSR gradients flow to model | Lower = earlier ontological influence |

#### Strength Hierarchy

```bash
# Conservative (default) - Gentle ontological guidance
--csr_lambda 0.1 --csr_tau 0.07 --csr_projector_lr_scale 0.1

# Moderate - Balanced ontology vs perplexity
--csr_lambda 0.2 --csr_tau 0.05 --csr_projector_lr_scale 0.2

# Aggressive - Strong ontological shaping (may slow PPL)
--csr_lambda 0.5 --csr_tau 0.03 --csr_projector_lr_scale 0.5
```

#### Gradient Amplification Reference

| `csr_tau` | Amplification | Use Case |
|-----------|---------------|----------|
| `0.10` | 10x | Very gentle |
| `0.07` | 14x | Default, balanced |
| `0.05` | 20x | Moderate push |
| `0.03` | 33x | Aggressive shaping |
| `0.02` | 50x | Maximum (use with caution) |

#### When to Increase CSR Influence

| Symptom | Solution |
|---------|----------|
| Model learns grammar but no ontological structure | Increase `csr_lambda` to 0.2-0.3 |
| CSR alignment too slow | Lower `csr_tau` to 0.05 |
| Kosha steering not affecting embeddings | Increase `csr_projector_lr_scale` to 0.3 |
| Want ontological shaping from step 1 | Set `csr_gradient_warmup_steps 0` |
| PPL improving but Kosha phase stuck | Increase `csr_lambda` AND enable steering |

#### Example: Strong CSR with Kosha Steering

```bash
python train_unified_llm.py \
    --model_type ontological_hybrid \
    --enable_csr \
    --csr_lambda 0.3 \
    --csr_tau 0.05 \
    --csr_projector_lr_scale 0.3 \
    --csr_gradient_warmup_steps 25 \
    --enable_kosha_diagnostics --kosha_log_every 50 \
    --enable_kosha_steering --kosha_steering_force 0.35 \
    # ... other args
```

---

## SGP (Stochastic Gradient Persistence)

"Cement" for CSR structure stability.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_sgp` | flag | `True` | Enable SGP |
| `--disable_sgp` | flag | `False` | Disable SGP |
| `--sgp_base_rate` | int | `200` | Toroidal Refresh Rate (every N steps) |
| `--sgp_stagnation_rate` | int | `100` | Rate when stagnation detected (halved) |
| `--sgp_gamma` | float | `0.5` | Persistence coefficient |

### Notes
- SGP runs every `sgp_base_rate` steps (200 by default)
- When stagnation is detected, rate halves to `sgp_stagnation_rate` (100) for more frequent hammering
- Higher gamma = stronger "cement" (more gradient persistence)
- SGP state is saved to checkpoints and restored on resume

---

## Sattvic Controller

Dynamic λ_csr regulation based on training health.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--sattvic_initial_lambda` | float | `0.5` | Initial λ_csr during warmup |
| `--sattvic_floor_lambda` | float | `0.1` | Minimum λ_csr after decay |
| `--sattvic_warmup_steps` | int | `500` | Warmup phase steps |
| `--sattvic_variance_window` | int | `50` | Entropy variance window |
| `--sattvic_variance_threshold` | float | `0.001` | Stagnation threshold |

### Notes
- Controls CSR influence dynamically based on training state
- Decays from initial λ (0.5) to floor λ (0.1) over warmup
- Emergency boost: When stagnation/collapse detected, λ increases to break loops
- Sattvic state is saved to checkpoints and restored on resume

---

## Adaptive Training Controller

Automatic LR/Kp adjustment based on training dynamics.

### Core Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_adaptive_training` | flag | `True` | Enable adaptive training |
| `--disable_adaptive_training` | flag | `False` | Disable adaptive training |
| `--adaptive_lr_min` | float | `1e-5` | Minimum LR floor |
| `--adaptive_lr_max` | float | `1e-3` | Maximum LR ceiling |
| `--adaptive_lr_boost` | float | `1.5` | Boost multiplier for plateau |
| `--adaptive_lr_decay` | float | `0.7` | Decay multiplier for spike |

### Velocity & Plateau Detection

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--adaptive_velocity_slow` | float | `-2.0` | PPL velocity % for "too slow" |
| `--adaptive_velocity_spike` | float | `10.0` | PPL velocity % for "spike" |
| `--adaptive_plateau_window` | int | `5` | Evaluations to check plateau |
| `--adaptive_plateau_threshold` | float | `1.0` | Min improvement % |
| `--adaptive_min_interval` | int | `200` | Min steps between adjustments |

### Safety & Emergency Options (v9.8.2)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--adaptive_max_lr_relative` | float | `10.0` | Max LR = base_lr × this (prevents runaway) |
| `--adaptive_loss_spike_threshold` | float | `5.0` | % loss increase triggers emergency decay |
| `--adaptive_grad_norm_spike` | float | `100.0` | Gradient norm threshold for emergency |
| `--adaptive_emergency_decay` | float | `0.5` | Emergency decay factor (aggressive) |
| `--adaptive_consecutive_spike_limit` | int | `3` | Blocks boosts after N consecutive spikes |

### Notes
- Automatically boosts LR on plateaus, reduces on spikes
- **adaptive_min_interval**: Prevents thrashing between adjustments
- Emergency decay triggers on loss spikes or gradient explosions
- Consecutive spike limit prevents boost-spike-decay loops

---

## Auto Batch Sizing

VRAM-based automatic batch detection.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_auto_batch` | flag | `False` | Enable auto batch sizing |
| `--auto_batch_target_utilization` | float | `0.80` | Target VRAM % |
| `--auto_batch_safety_margin` | float | `0.05` | Extra headroom % |
| `--auto_batch_target_effective` | int | `0` | Target effective batch (0=just find max) |

### Notes
- Probes VRAM at startup to find optimal batch size
- Set `--auto_batch_target_effective` for specific effective batch with auto accumulation

---

## VRAM Governor (Dynamic Batch Scaling)

Runtime VRAM monitoring with automatic batch size adjustment.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--vram_threshold` | float | `0.92` | VRAM % to trigger batch reduction |
| `--vram_recovery_buffer` | float | `0.12` | Recovery buffer (batch increases when VRAM < threshold - buffer) |

### How It Works
- **Reduction**: When VRAM exceeds `vram_threshold` (92%), batch size is halved
- **Recovery**: When VRAM drops below `threshold - buffer` (80%), batch size increases
- **Gradient Accumulation**: Automatically increases to maintain effective batch size

### Example Configurations
| vram_threshold | vram_recovery_buffer | Reduce At | Recover At |
|----------------|---------------------|-----------|------------|
| `0.92` | `0.12` | 92% | 80% |
| `0.95` | `0.10` | 95% | 85% |
| `0.90` | `0.15` | 90% | 75% |

### Notes
- Recovery requires 200+ steps after reduction before attempting scale-up
- Use higher `vram_threshold` (e.g., 0.95) if you want more aggressive VRAM usage
- Use lower `vram_recovery_buffer` (e.g., 0.08) for faster batch recovery

---

## Friction Controller

Prevents extreme dominance ratios.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--disable_friction` | flag | `False` | Disable friction controller |
| `--friction_dom_high` | float | `3.0` | "Riot" threshold |
| `--friction_dom_low` | float | `0.3` | "Lock" threshold |
| `--friction_align_critical` | float | `-0.10` | Alignment critical threshold |

### Notes
- **friction_dom_high**: Set higher (e.g., 10.0) to allow Sanskrit dominance
- Prevents one signal from overwhelming others

---

## Stress Test Mode

Inject corruption to test model resilience.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--stress_test` | flag | `False` | Run stress test |
| `--stress_start` | int | `1000` | Step to start corruption |
| `--stress_duration` | int | `200` | Corruption duration |
| `--corruption_rate` | float | `0.10` | Batch corruption probability |
| `--corruption_mode` | str | `noise` | Corruption type |

### Corruption Mode Choices
| Value | Description |
|-------|-------------|
| `noise` | Add random noise |
| `label_flip` | Flip labels |
| `repeat` | Repeat tokens |

---

## Curriculum Learning (PPL-Gated)

Phased introduction of auxiliary losses based on validation perplexity.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_curriculum` | flag | `False` | Enable PPL-gated curriculum |
| `--curriculum_ppl_regularization` | float | `30.0` | PPL to enter REGULARIZATION |
| `--curriculum_ppl_grounding` | float | `15.0` | PPL to enter GROUNDING |
| `--curriculum_ppl_sovereign` | float | `10.0` | PPL to enter SOVEREIGN |
| `--curriculum_stability_window` | int | `5` | Consecutive evals below threshold |
| `--curriculum_hysteresis` | float | `1.5` | Prevent oscillation (must exceed threshold × this to regress) |

### Curriculum Phases

| Phase | PPL Range | Active Features |
|-------|-----------|-----------------|
| FOUNDATION | > 30 | Pure LM loss only |
| REGULARIZATION | 30-15 | + Light Bhava (0.01), Coherence (0.01) |
| GROUNDING | 15-10 | + CSR (0.05), Bridge (0.05), JEPA (0.1) |
| SOVEREIGN | < 10 | Full auxiliary stack |

### Notes
- Ensures LM loss remains dominant (≥50%) throughout training
- Stability window prevents premature phase transitions
- Hysteresis prevents oscillation at phase boundaries
- Once SOVEREIGN reached, phase is locked (no regression)

---

## Sequence Length Curriculum

Gradual sequence length ramping for efficient training.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_seq_curriculum` | flag | `False` | Enable sequence length ramping |
| `--seq_len_start` | int | `256` | Starting sequence length |
| `--seq_len_end` | int | `1024` | Target sequence length (0 = use max_seq_len) |
| `--seq_len_ramp_steps` | int | `5000` | Steps to ramp from start to end |
| `--seq_len_ramp_mode` | str | `linear` | Ramp mode: `linear` or `exponential` |
| `--seq_len_ppl_gate` | float | `0.0` | PPL gate (0 = step-based only) |

### Benefits
- Faster early training (more updates per second with short sequences)
- Lower VRAM initially (allows larger batch sizes)
- Syntax learned quickly before long-range dependencies

### Notes
- Data automatically reloaded when sequence length changes by ≥64 tokens
- PPL-gated mode ensures model masters current length before extending
- Exponential mode provides slower initial growth, faster final growth

---

## Sovereign Reasoning Kernel (SRK v9.8.0)

Centralized ontological intervention with layer-specific hooks.

### Core Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_srk` | flag | `False` | Enable SRK system |
| `--srk_hidden_dim` | int | `768` | Projection dimension |
| `--srk_total_steps` | int | `50000` | Total training steps for scheduling |
| `--srk_warmup_steps` | int | `5000` | System 1 warmup steps |

### Layer Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--srk_dna_bridge_layer` | int | `4` | DNA Bridge layer (foundational ontology) |
| `--srk_csr_alignment_layer` | int | `7` | CSR Hook layer (concept consolidation) |
| `--srk_witness_layer` | int | `9` | Witness layer (consciousness alignment) |
| `--srk_synthesis_layer` | int | `11` | Synthesis layer (output integration) |

### Component Toggles

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--srk_disable_dna_bridge` | flag | `False` | Disable DNA Bridge |
| `--srk_disable_witness` | flag | `False` | Disable Witness hook |
| `--srk_disable_synthesis` | flag | `False` | Disable Synthesis hook |
| `--srk_disable_imr` | flag | `False` | Disable Isomorphism Monitoring |
| `--srk_disable_mauna` | flag | `False` | Disable Mauna (silence) gating |

### Loss Weights

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--srk_lambda_f` | float | `1.0` | Forward prediction weight |
| `--srk_lambda_b` | float | `1.0` | Backward prediction weight |
| `--srk_lambda_c` | float | `0.5` | Consistency weight |
| `--srk_lambda_coherence` | float | `0.2` | Coherence weight |
| `--srk_lambda_entropy` | float | `0.1` | Entropy regularization |
| `--srk_lambda_task` | float | `1.0` | Task loss weight |

### Advanced Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--srk_isomorphism_threshold` | float | `0.75` | Isomorphism detection threshold |
| `--srk_karma_decay` | float | `0.9` | Karma momentum decay |
| `--srk_mauna_confidence_threshold` | float | `0.6` | Mauna confidence threshold |
| `--srk_mauna_consistency_threshold` | float | `0.5` | Mauna consistency threshold |
| `--srk_disable_nidra_penalty` | flag | `False` | Disable Nidra penalty |
| `--srk_nidra_penalty_weight` | float | `0.05` | Nidra penalty weight |

---

## Phase-JEPA (Joint Embedding Predictive Architecture)

Perceptual learning via k-step prediction.

### Core Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_jepa` | flag | `False` | Enable JEPA training |
| `--jepa_hidden_dim` | int | `256` | MLP hidden dimension |
| `--jepa_prediction_steps` | int | `4` | k-step lookahead |
| `--jepa_num_heads` | int | `4` | Number of attention heads |
| `--jepa_cosine_mode` | str | `complex` | Phase interaction: `standard`, `shifted`, `complex` |

### Loss Weights

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--jepa_vicreg_weight` | float | `1.0` | VICReg collapse prevention |
| `--jepa_alignment_weight` | float | `1.0` | Predictor-target alignment |
| `--jepa_prediction_weight` | float | `0.5` | Forward/backward consistency |
| `--jepa_orthogonality_weight` | float | `0.01` | Representation orthogonality |
| `--jepa_bhava_weight` | float | `10.0` | Bhava alignment weight |
| `--jepa_semantic_weight` | float | `1.0` | Semantic consistency |
| `--jepa_guna_weight` | float | `0.1` | Guna alignment |

### Target Network

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--jepa_target_momentum` | float | `0.996` | EMA momentum for target |
| `--jepa_momentum_schedule` | str | `cosine` | Momentum schedule: `constant`, `cosine`, `linear` |

### Training Phases (Body → Soul → Union)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--jepa_training_phase` | str | `body` | Current phase: `body`, `soul`, `union` |
| `--jepa_phase_body_steps` | int | `20000` | Duration of BODY phase |
| `--jepa_phase_soul_steps` | int | `30000` | Duration of SOUL phase |
| `--jepa_auto_phase_transition` | flag | `False` | Automatic phase transitions |

### Dynamic Graduation

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--jepa_enable_dynamic_graduation` | flag | `True` | Enable metric-based graduation |
| `--jepa_graduation_loss_threshold` | float | `20.0` | Graduate when loss < this |
| `--jepa_graduation_alignment_threshold` | float | `25.0` | Alignment threshold |

### Vritti Validation

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--jepa_enable_vritti_validation` | flag | `False` | Enable Vritti-based validation |
| `--jepa_viparyaya_threshold` | float | `0.4` | Viparyaya (error) threshold |
| `--jepa_vikalpa_threshold` | float | `0.6` | Vikalpa (conceptual) threshold |
| `--jepa_damping_factor` | float | `0.5` | Damping on Vritti detection |

### Karma Injection

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--jepa_enable_karma_injection` | flag | `False` | Enable karma gate injection |
| `--jepa_karma_gate_bias` | float | `0.5` | Initial karma gate bias |

---

## Ontological Bridge (Layer 4)

Projects to 12D ontology at foundational layer.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_onto_bridge` | flag | `False` | Enable ontological bridge |
| `--onto_bridge_lambda` | float | `0.1` | Bridge loss weight |
| `--onto_bridge_diversity` | float | `0.1` | Diversity penalty (prevents collapse) |
| `--onto_bridge_pramana` | float | `0.1` | Pramana (valid knowledge) weight |
| `--onto_bridge_layer` | int | `4` | Layer for bridge projection |

---

## RSS (Resurgent Start System)

PPL-gated feature activation for gradual system warm-up.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_rss` | flag | `False` | Enable RSS |
| `--rss_evoflow_ppl` | float | `100.0` | PPL to enable EvoFlow |
| `--rss_toroidal_ppl` | float | `60.0` | PPL to enable Toroidal Bridge |
| `--rss_csr_ppl` | float | `45.0` | PPL to enable CSR |
| `--rss_kosha_ppl` | float | `35.0` | PPL to enable Kosha Steering |
| `--rss_csr_warmup_steps` | int | `2500` | CSR warmup steps |
| `--rss_use_val_ppl` | flag | `True` | Use validation PPL (vs training) |

### Notes
- Prevents "14x gradient shock" from CSR activation
- Features activate as PPL drops below thresholds
- Use with caution - curriculum learning is generally preferred

---

## State Regularizer

Prevents activation saturation in Kosha states.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_state_regularizer` | flag | `False` | Enable state regularization |
| `--state_reg_anti_sat_weight` | float | `0.5` | Anti-saturation penalty weight |
| `--state_reg_variance_weight` | float | `0.2` | Variance penalty weight |
| `--state_reg_sat_thresh_high` | float | `0.95` | High saturation threshold |
| `--state_reg_sat_thresh_low` | float | `0.05` | Low saturation threshold |
| `--state_reg_target_std_kosha` | float | `0.15` | Target std for Kosha states |
| `--state_reg_vital_weight` | float | `1.5` | Extra weight for Vital Kosha |
| `--state_reg_bliss_weight` | float | `1.5` | Extra weight for Bliss Kosha |

---

## PIDv2 Batch Resize

Dynamic batch size adjustment based on training dynamics.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--pidv2_batch_resize` | flag | `False` | Enable batch resizing |
| `--pidv2_batch_min` | int | `4` | Minimum batch size |
| `--pidv2_batch_max` | int | `64` | Maximum batch size |
| `--pidv2_batch_velocity_threshold` | float | `5.0` | PPL velocity trigger |
| `--pidv2_batch_stable_streak` | int | `5` | Stable evals before resize |

---

## RIP Logger

Reality Rip event logging for debugging.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--enable_rip_logger` | flag | `False` | Enable RIP logging |
| `--rip_logger_dir` | str | `diagnostics/rips` | Directory for RIP logs |

---

## CSR Sparse Supervision

Word-boundary-only supervision for CSR.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--csr_sparse_supervision` | flag | `False` | Enable word-boundary-only supervision |
| `--csr_content_word_only` | flag | `False` | Only supervise content words |

### Notes
- Reduces computational overhead
- Focuses alignment on semantically meaningful boundaries
- Combine with `--csr_alignment_layer 7` for concept-level alignment

---

## Evolutionary Flow Fluency Gate

PPL-based gating for evolutionary flow.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--evo_fluency_gate` | flag | `False` | Enable fluency gating |
| `--evo_fluency_min_steps` | int | `2000` | Min steps before gating |
| `--evo_fluency_ppl_threshold` | float | `100.0` | PPL threshold for gating |

---

## Example Configurations

### Fast Development Run
```bash
python train_unified_llm.py \
  --model_size tiny \
  --max_steps 1000 \
  --batch_size 16 \
  --log_every 10 \
  --eval_every 50 \
  --sample_every 100
```

### Production Hybrid Training
```bash
python train_unified_llm.py \
  --model_type hybrid \
  --model_size medium \
  --cosine_mode shifted \
  --window_size 512 \
  --use_8bit_optimizer \
  --gradient_checkpointing \
  --mixed_precision bf16 \
  --max_steps 50000 \
  --learning_rate 1e-4
```

### Ontological with Sovereign Loss
```bash
python train_unified_llm.py \
  --model_type ontological_hybrid \
  --enable_sovereign_loss \
  --enable_csr \
  --untie_embeddings \
  --use_9_3_split \
  --controller pidv2 \
  --enable_stress_probe
```

### Resume Training
```bash
python train_unified_llm.py \
  --resume checkpoints_unified/step_10000.pt \
  --max_steps 20000
```

### Fine-tune with Fresh Optimizer
```bash
python train_unified_llm.py \
  --resume checkpoints_unified/best.pt \
  --resume_weights_only \
  --learning_rate 1e-5 \
  --max_steps 5000
```
