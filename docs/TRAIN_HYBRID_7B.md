# train_hybrid_7b.py - CLI Reference

Training script for Hybrid 7B model with Phase Attention on FineWeb dataset. Optimized for A100 80GB GPUs with GQA, 8-bit optimizer, gradient checkpointing, and torch.compile.

## Quick Start

```bash
# Basic training (requires A100 80GB or better)
WANDB_MODE=disabled python train_hybrid_7b.py

# With custom window size for longer context
python train_hybrid_7b.py --window_size 512

# Without torch.compile (for debugging)
python train_hybrid_7b.py --no_compile

# Disable sample generation for faster training
python train_hybrid_7b.py --sample_interval 0
```

---

## Model Architecture

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--embed_dim` | int | `4096` | Embedding dimension |
| `--num_layers` | int | `32` | Number of transformer layers |
| `--num_heads` | int | `32` | Number of attention heads |
| `--n_kv_heads` | int | `8` | Number of KV heads (GQA) |
| `--ff_dim` | int | `11008` | Feed-forward dimension |
| `--max_seq_len` | int | `1024` | Maximum sequence length |

### Model Size (~6.66B parameters with GQA)

The default configuration creates a 7B-class model:

| Component | Dimensions | Notes |
|-----------|------------|-------|
| Embedding | 50257 × 4096 | GPT-2 tokenizer vocabulary |
| Attention | 32 heads, 8 KV heads | 4x KV memory savings via GQA |
| FFN | 4096 → 11008 → 4096 | LLaMA-style (2.7x embed_dim) |
| Layers | 32 total | 16 local + 16 hybrid |

### Grouped Query Attention (GQA)

| n_kv_heads | KV Heads per Q Head | Memory Savings | Use When |
|------------|---------------------|----------------|----------|
| `32` | 1:1 (full MHA) | None | Maximum quality, unlimited VRAM |
| `8` | 4:1 (Mistral-style) | **4x** | **Recommended** - good quality/memory tradeoff |
| `4` | 8:1 | 8x | Very memory constrained |
| `1` | 32:1 (MQA) | 32x | Extreme memory constraints |

**Note**: `n_kv_heads` must evenly divide `num_heads` (32).

---

## Hybrid Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--local_layers` | int | `16` | Number of local-only attention layers |
| `--window_size` | int | `256` | Local attention window size |
| `--cosine_mode` | str | `standard` | Phase attention cosine mode |
| `--decay_gamma` | float | `1.0` | State decay factor |

### Layer Split

With 32 layers and `local_layers=16`:
- **Layers 0-15**: Local attention only (fast, O(n×w) complexity)
- **Layers 16-31**: Hybrid attention (local + phase)

| local_layers | Split | Description |
|--------------|-------|-------------|
| `32` | All local | No phase attention (baseline) |
| `16` | 16:16 | **Balanced** - recommended |
| `8` | 8:24 | More phase attention |
| `0` | All hybrid | Maximum phase attention (slow) |

### Window Size

| Value | Context | Memory | Use When |
|-------|---------|--------|----------|
| `128` | 128 tokens | Low | Testing, small models |
| `256` | 256 tokens | Medium | **Default** - good balance |
| `512` | 512 tokens | Higher | Better fluency, more VRAM |
| `1024` | 1024 tokens | High | Long-range coherence, needs headroom |

**Note**: Window size affects local attention only. Phase attention sees all tokens regardless.

### Cosine Mode

| Value | Range | Description | Use When |
|-------|-------|-------------|----------|
| `standard` | [-1, 1] | Classic cosine similarity | Baseline |
| `shifted` | [0, 2] | `1 + cos` (no negatives) | Prevents token cancellation |
| `complex` | N/A | Uses both cos and sin | Directional asymmetry |

### State Decay (decay_gamma)

| Value | Effective Memory | Description |
|-------|-----------------|-------------|
| `1.0` | Infinite | Full context retention (**default**) |
| `0.99` | ~100 tokens | Slight recency bias |
| `0.95` | ~20 tokens | Strong local focus (Mamba/RWKV-like) |
| `0.9` | ~10 tokens | Very local |

---

## Training Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--batch_size` | int | `2` | Per-GPU batch size |
| `--gradient_accumulation` | int | `8` | Gradient accumulation steps |
| `--learning_rate` | float | `3e-4` | Peak learning rate |
| `--max_steps` | int | `100000` | Maximum training steps |
| `--warmup_steps` | int | `2000` | LR warmup steps |
| `--grad_clip` | float | `1.0` | Gradient clipping norm |

### Effective Batch Size

```
Effective batch = batch_size × gradient_accumulation × num_gpus
Default: 2 × 8 × 1 = 16 sequences per update
Tokens per update: 16 × 1024 = 16,384 tokens
```

### Batch Size by GPU

| GPU | VRAM | batch_size | gradient_accumulation | Effective |
|-----|------|------------|----------------------|-----------|
| A100 40GB | 40GB | 1 | 16 | 16 |
| A100 80GB | 80GB | **2** | 8 | 16 |
| H100 80GB | 80GB | 2-4 | 4-8 | 16-32 |

### Learning Rate Schedule

The script uses cosine decay with warmup:
- **Warmup**: Linear ramp from 0 to `learning_rate` over `warmup_steps`
- **Decay**: Cosine decay from `learning_rate` to `min_learning_rate` (3e-5)

---

## Memory Optimization

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--no_mixed_precision` | flag | `False` | Disable BF16 mixed precision |
| `--no_gradient_checkpointing` | flag | `False` | Disable gradient checkpointing |
| `--no_8bit_optimizer` | flag | `False` | Disable 8-bit AdamW optimizer |
| `--no_compile` | flag | `False` | Disable torch.compile() |

### Memory Savings Breakdown

| Optimization | Memory Savings | Speed Impact | Default |
|--------------|---------------|--------------|---------|
| BF16 Mixed Precision | ~50% activations | +10-20% faster | **Enabled** |
| Gradient Checkpointing | ~30-40% activations | -15% slower | **Enabled** |
| 8-bit Optimizer | ~75% optimizer states | Minimal | **Enabled** |
| torch.compile | N/A | +15-30% faster | **Enabled** |

### VRAM Usage (A100 80GB)

| Configuration | Approx VRAM | Notes |
|---------------|-------------|-------|
| All optimizations ON | ~55-65 GB | **Default** - batch_size=2 |
| No 8-bit optimizer | ~70-75 GB | Requires batch_size=1 |
| No gradient checkpointing | OOM | Not recommended for 7B |
| No mixed precision | OOM | Not recommended |

### When to Disable

| Flag | Use When |
|------|----------|
| `--no_mixed_precision` | Numerical debugging, NaN issues |
| `--no_gradient_checkpointing` | Smaller models, more VRAM available |
| `--no_8bit_optimizer` | Precision-critical fine-tuning |
| `--no_compile` | Debugging, dynamic shapes, compile errors |

---

## Validation & Sampling

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--cache_val_batches` | int | `20` | Pre-cache N validation batches |
| `--sample_interval` | int | `50` | Generate samples every N steps |

### Validation Caching

The FineWeb streaming dataset causes a ~7 minute "Resolving data files" delay during validation. Pre-caching eliminates this:

| Value | Behavior |
|-------|----------|
| `0` | Disable caching (7-min delay each validation) |
| `20` | **Default** - cache 20 batches at startup |
| `50` | More cached batches for longer validation |

### Sample Generation

| Value | Behavior |
|-------|----------|
| `0` | Disable sample generation |
| `50` | **Default** - samples every 50 steps |
| `100` | Less frequent sampling |
| `200` | Minimal overhead |

**Note**: Sample generation uses `@torch._dynamo.disable` to avoid torch.compile issues with dynamic shapes.

---

## Dataset Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--dataset_name` | str | `HuggingFaceFW/fineweb` | HuggingFace dataset name |
| `--dataset_subset` | str | `sample-10BT` | Dataset subset/config |

### FineWeb Subsets

| Subset | Size | Tokens | Use When |
|--------|------|--------|----------|
| `sample-10BT` | ~10B tokens | ~10B | **Default** - good for initial training |
| `sample-100BT` | ~100B tokens | ~100B | Extended training |
| `CC-MAIN-*` | Varies | Varies | Specific Common Crawl snapshots |

### Using Other Datasets

```bash
# OpenWebText
python train_hybrid_7b.py --dataset_name openwebtext --dataset_subset ""

# The Pile (subset)
python train_hybrid_7b.py --dataset_name EleutherAI/pile --dataset_subset "pile-cc"
```

---

## Output & Logging

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output_dir` | str | `./checkpoints/hybrid_7b` | Checkpoint directory |
| `--wandb_project` | str | `hybrid-7b-fineweb` | Weights & Biases project |
| `--wandb_run_name` | str | `None` | W&B run name (auto-generated if None) |

### Disabling W&B

```bash
# Disable completely
WANDB_MODE=disabled python train_hybrid_7b.py

# Offline mode (sync later)
WANDB_MODE=offline python train_hybrid_7b.py
```

### Checkpoint Structure

```
./checkpoints/hybrid_7b/
├── step_1000.pt
├── step_2000.pt
├── ...
└── config.json
```

---

## Other Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--seed` | int | `42` | Random seed for reproducibility |

---

## Example Configurations

### Development/Testing (Smaller Model)

```bash
python train_hybrid_7b.py \
  --embed_dim 1024 \
  --num_layers 12 \
  --num_heads 16 \
  --n_kv_heads 4 \
  --ff_dim 2816 \
  --max_steps 1000 \
  --no_compile
```

### A100 80GB Production

```bash
python train_hybrid_7b.py \
  --batch_size 2 \
  --gradient_accumulation 8 \
  --window_size 512 \
  --cosine_mode shifted \
  --max_steps 100000
```

### A100 40GB (Memory Constrained)

```bash
python train_hybrid_7b.py \
  --batch_size 1 \
  --gradient_accumulation 16 \
  --window_size 256 \
  --max_seq_len 512
```

### H100 (Maximum Throughput)

```bash
python train_hybrid_7b.py \
  --batch_size 4 \
  --gradient_accumulation 4 \
  --window_size 1024 \
  --n_kv_heads 8
```

### Long Context Training

```bash
python train_hybrid_7b.py \
  --max_seq_len 2048 \
  --window_size 1024 \
  --batch_size 1 \
  --gradient_accumulation 16
```

### Fast Iteration (No Frills)

```bash
WANDB_MODE=disabled python train_hybrid_7b.py \
  --sample_interval 0 \
  --cache_val_batches 10 \
  --max_steps 10000
```

---

## Metrics Logged

The training script logs the following metrics:

| Metric | Description |
|--------|-------------|
| `Loss` | Cross-entropy loss (averaged over log_interval) |
| `PPL` | Perplexity (exp(loss)) |
| `LR` | Current learning rate |
| `Grad` | Gradient norm |
| `Tok/s` | Training throughput (tokens per second) |
| `VRAM` | Peak GPU memory usage (GB) |
| `VAL PPL` | Validation perplexity |
| `VAL Loss` | Validation loss |

### Log Format

```
[HH:MM:SS] Step   1000 | Loss: 4.2345 | PPL: 68.92 | LR: 2.85e-04 | Grad: 0.45 | Tok/s: 12500 | VRAM: 62.3GB
```

---

## Comparison with Mistral 7B

| Aspect | train_hybrid_7b.py | Mistral 7B |
|--------|-------------------|------------|
| Parameters | ~6.66B | 7.3B |
| Layers | 32 | 32 |
| Heads | 32 Q, 8 KV | 32 Q, 8 KV |
| FFN | 11008 | 14336 |
| Attention | Local + Phase (hybrid) | Sliding Window |
| Window Size | 256 (configurable) | 4096 |
| Context | 1024 (configurable) | 32768 |

### Key Differences

1. **Phase Attention**: Uses phase-based similarity instead of sliding window
2. **Smaller FFN**: 11008 vs 14336 (compensated by phase attention)
3. **Hybrid Layers**: First 16 layers are local-only for efficiency

---

## Troubleshooting

### Out of Memory (OOM)

1. Reduce `--batch_size` to 1
2. Increase `--gradient_accumulation` to maintain effective batch
3. Reduce `--window_size` to 128
4. Reduce `--max_seq_len` to 512

### torch.compile Errors

```bash
python train_hybrid_7b.py --no_compile
```

### Slow Validation (7-minute gaps)

Ensure validation caching is enabled:
```bash
python train_hybrid_7b.py --cache_val_batches 20
```

### NaN Loss

1. Reduce `--learning_rate` to 1e-4
2. Increase `--warmup_steps` to 4000
3. Try `--no_mixed_precision` (for debugging only)

### Sample Generation Hanging

This was fixed with `@torch._dynamo.disable` decorator. If still occurring:
```bash
python train_hybrid_7b.py --no_compile
```
