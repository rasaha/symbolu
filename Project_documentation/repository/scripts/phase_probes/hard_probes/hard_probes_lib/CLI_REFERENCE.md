# Hard Probes CLI Reference

Per-module CLI usage documentation for `train_hard_probes.py`.

Each section documents the CLI arguments specific to one module, making it easy
to find the right flags for the feature you want to use.

---

## Table of Contents

1. [Core Training](#core-training) — `config.py`
2. [Dataset & Schemas](#dataset--schemas) — `dataset.py`, `schemas.py`, `vocabulary.py`
3. [Attention & Models](#attention--models) — `attention.py`, `models.py`
4. [Protected Phase](#protected-phase) — `protected.py`
5. [Phase Contracts](#phase-contracts) — `contracts.py`
6. [Evaluation & Ablation](#evaluation--ablation) — `evaluation.py`
7. [Real Language Mode](#real-language-mode) — `language.py`, `training.py`
8. [SRK Monitoring](#srk-monitoring) — `diagnostics.py` (SRK)
9. [Kosha/Witness Consciousness](#koshawitness-consciousness) — `diagnostics.py` (Kosha/Witness)
10. [Binding Cache](#binding-cache) — `language.py` (Binding Cache section)
11. [Entropy Control](#entropy-control) — via `imports.py`
12. [Benchmark: Interference](#benchmark-interference) — `benchmarks/interference.py`
13. [Benchmark: MoE FFN](#benchmark-moe-ffn) — `benchmarks/moe_ffn.py`
14. [Benchmark: HP-Quad](#benchmark-hp-quad) — `benchmarks/hp_quad.py`
15. [Benchmark: RLM-Phase-Quad](#benchmark-rlm-phase-quad) — `benchmarks/rlm_phase_quad.py`
16. [Benchmark: Reflective Phase-Quad](#benchmark-reflective-phase-quad) — `benchmarks/reflective_phase_quad.py`
17. [Benchmark: Causal World Model](#benchmark-causal-world-model) — `benchmarks/causal_world_model.py`
18. [Benchmark: Spatial-Causal](#benchmark-spatial-causal) — `benchmarks/spatial_causal.py`
19. [Benchmark: Adaptation (IA³ + LoRA)](#benchmark-adaptation-ia³--lora) — `benchmarks/adaptation.py`
20. [Benchmark: Chunking](#benchmark-chunking) — `benchmarks/chunking.py`

---

## Core Training

**Module:** `config.py`

Model architecture and training hyperparameters.

```bash
# Model architecture
python train_hard_probes.py \
    --d-model 128 \         # Model dimension (default: 128)
    --num-heads 8 \         # Attention heads (default: 8)
    --num-layers 4 \        # Transformer layers (default: 4)
    --d-ff 256              # FFN dimension (default: 256)

# Training hyperparameters
python train_hard_probes.py \
    --num-steps 15000 \     # Training steps (default: 15000)
    --batch-size 64 \       # Batch size (default: 64)
    --lr 1e-3 \             # Learning rate (default: 1e-3)
    --device cuda            # Device: cuda or cpu

# Checkpointing
python train_hard_probes.py \
    --checkpoint-dir ./checkpoints \  # Save best.pt and last.pt
    --save-every 5000                 # Also save periodic checkpoints
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--d-model` | 128 | Model dimension |
| `--num-heads` | 8 | Number of attention heads |
| `--num-layers` | 4 | Number of transformer layers |
| `--d-ff` | 256 | FFN dimension (2x d_model) |
| `--num-steps` | 15000 | Training steps |
| `--batch-size` | 64 | Batch size |
| `--lr` | 1e-3 | Learning rate |
| `--checkpoint-dir` | None | Directory for checkpoints |
| `--save-every` | 0 | Save periodic checkpoints every N steps |
| `--device` | auto | cuda if available, else cpu |

---

## Dataset & Schemas

**Modules:** `dataset.py`, `schemas.py`, `vocabulary.py`

Controls the synthetic relational reasoning dataset.

```bash
# Dataset size
python train_hard_probes.py \
    --train-samples 20000 \  # Training samples (default: 20000)
    --test-samples 1000      # Samples per test split (default: 1000)

# Schema composition
python train_hard_probes.py \
    --bind-ratio 0.7         # Ratio of BIND-dominant schemas (default: 0.6)

# Chain lengths (difficulty control)
python train_hard_probes.py \
    --train-chain-min 3 --train-chain-max 5 \    # Training chains
    --test-chain-min 6 --test-chain-max 8 \      # Test chains (harder)
    --persist-chain-min 8 --persist-chain-max 12  # Pure persistence test
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--train-samples` | 20000 | Training sample count |
| `--test-samples` | 1000 | Samples per test split |
| `--bind-ratio` | 0.6 | BIND-dominant schema ratio (0.0-1.0) |
| `--train-chain-min` | 3 | Min training chain length |
| `--train-chain-max` | 5 | Max training chain length |
| `--test-chain-min` | 6 | Min test chain length |
| `--test-chain-max` | 8 | Max test chain length |
| `--persist-chain-min` | 8 | Min persistence chain length |
| `--persist-chain-max` | 12 | Max persistence chain length |

---

## Attention & Models

**Modules:** `attention.py`, `models.py`

Phase attention configuration and hybrid curriculum models.

```bash
# Default: Quadratic vs Phase comparison
python train_hard_probes.py

# Enable bounded phase (constrains φ to [-π, π])
python train_hard_probes.py --bounded-phase

# Dual-channel attention (separates content from intent)
python train_hard_probes.py \
    --dual-channel-mode \
    --alignment-authority 0.1 \    # α weight (default: 0.1)
    --alignment-clamp-min 0.8 \    # Min modulator clamp
    --alignment-clamp-max 1.2      # Max modulator clamp

# Alignment reduction mode
python train_hard_probes.py \
    --alignment-reduction per_head  # per_head | global | per_batch_head

# Hybrid curriculum comparison
python train_hard_probes.py --compare-curricula

# Custom curriculum (Phase ratio per layer)
python train_hard_probes.py --run-hybrid --curriculum 0.9,0.7,0.3,0.1

# Parameter-matched comparison
python train_hard_probes.py --match-params
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--bounded-phase` | True | Constrain φ to [-π, π] via π*sin() |
| `--no-bounded-phase` | — | Disable bounded phase |
| `--dual-channel-mode` | False | Separate content from intent alignment |
| `--alignment-authority` | 0.1 | α: alignment term weight |
| `--alignment-clamp-min` | 0.8 | Min alignment modulator clamp |
| `--alignment-clamp-max` | 1.2 | Max alignment modulator clamp |
| `--alignment-reduction` | per_head | How to reduce alignment scores |
| `--run-hybrid` | False | Run hybrid model with inverted curriculum |
| `--curriculum` | 0.9,0.7,0.3,0.1 | Phase ratios per layer (comma-separated) |
| `--compare-curricula` | False | Compare inverted vs standard curriculum |
| `--match-params` | False | Match parameter counts for fairness |

---

## Protected Phase

**Module:** `protected.py`

Protected Phase architecture where Phase accumulates state and Quad queries it.
No gradient competition between the two mechanisms.

```bash
python train_hard_probes.py --protected-phase
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--protected-phase` | False | Run Protected Phase model |

---

## Phase Contracts

**Module:** `contracts.py`

No-write contract enforcement (V10.6.2) — prevents control signals from
injecting content into Phase.

```bash
# Enable enforcement (default)
python train_hard_probes.py --enforce-no-write-contracts

# Disable for performance
python train_hard_probes.py --no-enforce-no-write-contracts

# Warn instead of raise on violations
python train_hard_probes.py --no-strict-control-contract
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--enforce-no-write-contracts` | True | Enable no-write contract assertions |
| `--no-enforce-no-write-contracts` | — | Disable no-write contracts |
| `--strict-control-contract` | True | Raise on violations (strict mode) |
| `--no-strict-control-contract` | — | Warn mode (log and continue) |

---

## Evaluation & Ablation

**Module:** `evaluation.py`

Phase rotation tests and ablation modes for causal analysis.

```bash
# Phase rotation test
python train_hard_probes.py --rotation-test

# Custom rotation angles
python train_hard_probes.py --rotation-test --rotation-angles 0,30,60,90,120,150,180
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--rotation-test` | False | Run phase rotation test after training |
| `--rotation-angles` | 0,45,90,135,180,270 | Rotation angles in degrees |

---

## Real Language Mode

**Modules:** `language.py`, `training.py`

Switch from synthetic hard probes to real language modeling.

```bash
# WikiText language modeling
python train_hard_probes.py --real-language --dataset wikitext2

# Supported datasets
python train_hard_probes.py --real-language \
    --dataset wikitext103      # wikitext2 | wikitext103 | tinystories |
                               # writingprompts | imdb | openwebtext | c4

# Sequence length and vocab
python train_hard_probes.py --real-language \
    --seq-len 256 \            # Sequence length (default: 256)
    --lm-vocab-size 50257      # GPT-2 vocab size

# Phase-first curriculum
python train_hard_probes.py --real-language \
    --phase-first-curriculum \
    --alpha-phase-high 0.8 \   # Phase weight when PPL is high
    --alpha-phase-low 0.3      # Phase weight when PPL is low

# Layer probing
python train_hard_probes.py --real-language --probe-layers

# Quality sample monitoring
python train_hard_probes.py --real-language --sample-every 500

# Deep supervision
python train_hard_probes.py --real-language \
    --deep-supervision \
    --deep-supervision-lambda 0.5

# Soft routing warmup for quad
python train_hard_probes.py --real-language \
    --soft-routing-warmup 1000

# Proposal mode (quad proposes, phase integrates)
python train_hard_probes.py --real-language \
    --proposal-mode \
    --confidence-threshold 0.7
```

### Associative Recall Task

Forces quad to retrieve from phase memory across long delays.

```bash
python train_hard_probes.py --associative-recall \
    --ar-num-pairs 8 \          # Key-value pairs per sample
    --ar-delay-min 80 \         # Min filler tokens (> local window)
    --ar-delay-max 150 \        # Max filler tokens
    --ar-vocab-size 1000 \      # Vocabulary size
    --ar-train-samples 50000    # Training samples

# Dynamic delay curriculum
python train_hard_probes.py --associative-recall \
    --ar-dynamic-delay \
    --ar-target-delay-min 120 \
    --ar-target-delay-max 200 \
    --ar-curriculum-warmup 0.3
```

---

## SRK Monitoring

**Module:** `diagnostics.py` (SRK section)

Sovereign Reasoning Kernel monitoring for phase learning progression.

```bash
python train_hard_probes.py --real-language --enable-srk --probe-layers \
    --srk-dna-bridge-layer 0 \     # L4: DNA Bridge (default: 0)
    --srk-csr-layer 1 \            # L7: CSR Alignment (default: 1)
    --srk-witness-layer 2 \        # L9: Witness Arbitrator (default: 2)
    --srk-synthesis-layer 3 \      # L11: Synthesis Gate (default: 3)
    --srk-lambda-ontology 0.1 \    # Ontological alignment weight
    --srk-lambda-coherence 0.05    # Phase coherence weight

# Disable individual components
python train_hard_probes.py --real-language --enable-srk \
    --srk-disable-dna-bridge \
    --srk-disable-witness
```

---

## Kosha/Witness Consciousness

**Module:** `diagnostics.py` (Kosha/Witness section)

5-layer consciousness monitoring and Sakshi observer.

```bash
# Enable Kosha consciousness
python train_hard_probes.py --real-language \
    --enable-kosha \
    --kosha-target INTELLECTUAL \           # MATERIAL|VITAL|MENTAL|INTELLECTUAL|BLISSFUL
    --kosha-dampen-material 0.5 \          # Dampen material kosha
    --kosha-boost-target 0.4 \             # Boost target kosha
    --kosha-gyro-base-gain 0.15 \          # Gyroscopic loss base gain
    --kosha-gyro-max-gain 3.0              # Gyroscopic loss max gain

# Enable Witness observer
python train_hard_probes.py --real-language \
    --enable-witness \
    --witness-constraint-threshold 0.85 \  # Constraint detection threshold
    --witness-entropy-reg \                # Enable entropy regularization
    --witness-entropy-lambda 0.1           # Regularization weight

# Domain separation (SRK-aligned layers)
python train_hard_probes.py --real-language \
    --domain-separation \
    --csr-domain-layers 0,1 \
    --kosha-domain-layers 2 \
    --witness-domain-layers 2 \
    --synthesis-domain-layers 3
```

---

## Binding Cache

**Module:** `language.py` (Binding Cache section)

Three-path architecture: Local + Phase + Quad with no gradient competition.

```bash
python train_hard_probes.py --real-language --binding-cache \
    --binding-cache-top-k 64 \              # Top-K for quad query
    --local-window-size 64 \                # Local attention window
    --decay-gamma 0.9 \                     # Phase memory decay
    --binding-cache-phase-ratio 0.3,0.3,0.3,0.3 \  # Phase ratio per layer
    --binding-cache-local-ratio 0.4,0.4,0.4,0.4 \  # Local ratio per layer
    --binding-cache-quad-ratio 0.3,0.3,0.3,0.3     # Quad ratio per layer

# With explicit binding slots
python train_hard_probes.py --real-language --binding-cache \
    --binding-slots 32           # 0=disabled, 16-32 recommended
```

---

## Entropy Control

Entropy-based logit scale control for stable training and inference.

```bash
# Train-time entropy control
python train_hard_probes.py --real-language \
    --enable-entropy-control-train \
    --entropy-topk 50 \           # K for top-K entropy
    --entropy-h-min 0.15 \        # Lower bound of target band
    --entropy-h-max 0.35 \        # Upper bound of target band
    --entropy-control-lambda 0.01  # Band penalty weight

# Inference-time adaptive control
python train_hard_probes.py --real-language \
    --enable-entropy-control-infer \
    --infer-h-target 0.25 \       # Target entropy midpoint
    --infer-eta 0.02 \            # Adaptation rate
    --infer-delta-clip 0.05       # Error clipping bound

# Logit scale bounds
python train_hard_probes.py --real-language \
    --logit-scale-min -4.0 \
    --logit-scale-max 4.0
```

---

## Benchmark: Interference

**Module:** `benchmarks/interference.py`

Tests text interference scoring for proposal compatibility.

```bash
# Run interference benchmarks
python train_hard_probes.py --test-interference

# With custom lambda (0.01-0.03 for text)
python train_hard_probes.py --test-interference --interference-lambda 0.02

# With ablation (Base vs +Interference vs +BCVF vs +BCVF+Interference)
python train_hard_probes.py --test-interference --interference-ablation

# Full suite
python train_hard_probes.py --test-interference --interference-ablation \
    --interference-lambda 0.02 \
    --interference-min-step 8 \
    --interference-entropy-gate 1.2
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--test-interference` | False | Run interference benchmarks |
| `--interference-lambda` | 0.02 | Lambda for interference scoring |
| `--interference-min-step` | 8 | Min decoding step before interference |
| `--interference-entropy-gate` | 1.2 | Entropy threshold for gating |
| `--interference-ablation` | False | Run ablation comparison |

**Expected Results:** Task classifier >85% accuracy, multipliers in [0.9, 1.1], score change <20%.

---

## Benchmark: MoE FFN

**Module:** `benchmarks/moe_ffn.py`

Tests Mixtral-style Mixture of Experts FFN for compute efficiency.

```bash
# Run MoE benchmarks
python train_hard_probes.py --test-moe-ffn

# Custom expert configuration
python train_hard_probes.py --test-moe-ffn \
    --moe-num-experts 16 \
    --moe-top-k 2

# With ablation (Dense vs MoE-4E vs MoE-8E vs MoE-16E)
python train_hard_probes.py --test-moe-ffn --moe-ablation
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--test-moe-ffn` | False | Run MoE benchmarks |
| `--moe-num-experts` | 8 | Number of experts |
| `--moe-top-k` | 2 | Experts activated per token |
| `--moe-load-balance-weight` | 0.01 | Load balance loss weight |
| `--moe-router-z-weight` | 0.001 | Router z-loss weight |
| `--moe-ablation` | False | Run ablation comparison |

**Expected Results:** 1.5-2x speedup, <5% utilization imbalance, >70% router entropy.

---

## Benchmark: HP-Quad

**Module:** `benchmarks/hp_quad.py`

Tests Hierarchical Phase-Quad for multi-timescale processing.

```bash
python train_hard_probes.py --test-hp-quad

python train_hard_probes.py --test-hp-quad \
    --hp-num-levels 3 \
    --hp-d-phase-levels 128,256,512 \
    --hp-chunk-sizes 1,8,64 \
    --hp-boundary-threshold 0.5 \
    --hp-target-boundary-rate 0.15 \
    --hp-boundary-ablation
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--test-hp-quad` | False | Run HP-Quad benchmarks |
| `--hp-num-levels` | 3 | Hierarchy levels |
| `--hp-d-phase-levels` | 128,256,512 | Phase dimensions per level |
| `--hp-chunk-sizes` | 1,8,64 | Chunk sizes per level |
| `--hp-boundary-threshold` | 0.5 | Boundary detection threshold |
| `--hp-target-boundary-rate` | 0.15 | Target boundary rate |
| `--hp-boundary-ablation` | False | Run boundary detection ablation |

---

## Benchmark: RLM-Phase-Quad

**Module:** `benchmarks/rlm_phase_quad.py`

Tests RLM + Phase-Quad integration for unlimited context (10M+ tokens).

```bash
python train_hard_probes.py --test-rlm-phase-quad

python train_hard_probes.py --test-rlm-phase-quad \
    --rlm-pq-max-context 100000 \
    --rlm-pq-max-depth 3 \
    --rlm-pq-quality-threshold 0.7 \
    --rlm-pq-min-chunk 100 \
    --rlm-pq-max-chunk 4096

# Extended scalability test (up to 1M tokens)
python train_hard_probes.py --test-rlm-phase-quad --rlm-pq-scalability-test
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--test-rlm-phase-quad` | False | Run RLM-PQ benchmarks |
| `--rlm-pq-max-context` | 100000 | Maximum context size |
| `--rlm-pq-max-depth` | 3 | Maximum recursion depth |
| `--rlm-pq-quality-threshold` | 0.7 | Quality threshold for recursion |
| `--rlm-pq-min-chunk` | 100 | Minimum chunk size |
| `--rlm-pq-max-chunk` | 4096 | Maximum chunk size |
| `--rlm-pq-scalability-test` | False | Extended scalability tests |

---

## Benchmark: Reflective Phase-Quad

**Module:** `benchmarks/reflective_phase_quad.py`

Tests self-reflective latent-space revision with neural critic.
O(N) revision cost vs O(N²) for token-based approaches.

```bash
python train_hard_probes.py --test-reflective-phase-quad

python train_hard_probes.py --test-reflective-phase-quad \
    --rpq-max-revisions 3 \
    --rpq-threshold-high 0.85 \
    --rpq-threshold-low 0.50 \
    --rpq-batch-size 4 \
    --rpq-seq-len 64

# Ablation study
python train_hard_probes.py --test-reflective-phase-quad --rpq-ablation

# Adaptive thresholds (learned from input context)
python train_hard_probes.py --test-reflective-phase-quad --rpq-adaptive-threshold
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--test-reflective-phase-quad` | False | Run RPQ benchmarks |
| `--rpq-max-revisions` | 3 | Maximum revision attempts |
| `--rpq-threshold-high` | 0.85 | Quality for immediate acceptance |
| `--rpq-threshold-low` | 0.50 | Quality for major revision |
| `--rpq-batch-size` | 4 | Batch size for benchmarks |
| `--rpq-seq-len` | 64 | Sequence length for benchmarks |
| `--rpq-ablation` | False | Run ablation study |
| `--rpq-adaptive-threshold` | False | Use learned adaptive thresholds |

---

## Benchmark: Causal World Model

**Module:** `benchmarks/causal_world_model.py`

Tests explicit causal graphs, interventions, and world simulation.

```bash
python train_hard_probes.py --test-causal-world-model

# Extended benchmarks
python train_hard_probes.py --test-causal-world-model \
    --cwm-benchmark-discovery \
    --cwm-benchmark-intervention \
    --cwm-benchmark-counterfactual

# Causal datasets
python train_hard_probes.py --test-causal-world-model \
    --cwm-dataset copa          # copa | ecare | scm | all
    --cwm-dataset-samples 1000

# Synthetic SCM configuration
python train_hard_probes.py --test-causal-world-model \
    --cwm-dataset scm \
    --scm-num-variables 10 \
    --scm-edge-probability 0.3 \
    --scm-noise-std 0.1
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--test-causal-world-model` | False | Run CWM benchmarks |
| `--cwm-max-variables` | 128 | Max causal variables |
| `--cwm-dag-penalty` | 0.1 | DAG constraint weight |
| `--cwm-edge-threshold` | 0.5 | Edge existence threshold |
| `--cwm-dataset` | scm | Dataset: copa, ecare, scm, all |
| `--cwm-benchmark-discovery` | False | Extended discovery benchmarks |
| `--cwm-benchmark-intervention` | False | Extended intervention benchmarks |
| `--cwm-benchmark-counterfactual` | False | Extended counterfactual benchmarks |

---

## Benchmark: Spatial-Causal

**Module:** `benchmarks/spatial_causal.py`

Tests spatial reasoning with physics-grounded causal edges.

```bash
python train_hard_probes.py --test-spatial-causal

python train_hard_probes.py --test-spatial-causal \
    --scm-scenario all \              # falling_ball|collision|domino|stacking|all
    --scm-hidden-dim 256 \
    --scm-max-objects 64 \
    --scm-gravity 0.0 -9.81 0.0 \
    --scm-simulation-steps 100
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--test-spatial-causal` | False | Run spatial-causal benchmarks |
| `--scm-hidden-dim` | 256 | Hidden dimension |
| `--scm-max-objects` | 64 | Maximum spatial objects |
| `--scm-num-heads` | 8 | Attention heads |
| `--scm-gravity` | 0,-9.81,0 | Gravity vector [x,y,z] |
| `--scm-simulation-dt` | 0.01 | Simulation timestep |
| `--scm-simulation-steps` | 100 | Max simulation steps |
| `--scm-scenario` | falling_ball | Test scenario |

---

## Benchmark: Adaptation (IA³ + LoRA)

**Module:** `benchmarks/adaptation.py`

Tests controlled plasticity for Phase Quad fine-tuning.

```bash
python train_hard_probes.py --test-adaptation

# With LoRA enabled
python train_hard_probes.py --test-adaptation \
    --adapt-lora \
    --adapt-lora-rank 8 \
    --adapt-lora-alpha 16.0

# Ablation (IA3-only vs LoRA-only vs Combined)
python train_hard_probes.py --test-adaptation --adapt-ablation

# Custom model config
python train_hard_probes.py --test-adaptation \
    --adapt-embed-dim 256 \
    --adapt-num-heads 8 \
    --adapt-num-blocks 3 \
    --adapt-train-steps 100
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--test-adaptation` | False | Run adaptation benchmarks |
| `--adapt-ia3` | True | Enable IA³ gates |
| `--adapt-ia3-reg-lambda` | 0.01 | IA³ regularization lambda |
| `--adapt-lora` | False | Enable surgical LoRA |
| `--adapt-lora-rank` | 8 | LoRA rank |
| `--adapt-lora-alpha` | 16.0 | LoRA scaling alpha |
| `--adapt-embed-dim` | 256 | Embedding dimension |
| `--adapt-num-heads` | 8 | Attention heads |
| `--adapt-num-blocks` | 3 | DiT blocks |
| `--adapt-train-steps` | 100 | Training steps |
| `--adapt-ablation` | False | Run ablation comparison |

---

## Benchmark: Chunking

**Module:** `benchmarks/chunking.py`

Tests V10.2.1 chunking architecture: cross-attention, continuity, dependencies.

```bash
python train_hard_probes.py --test-chunking-v10

python train_hard_probes.py --test-chunking-v10 \
    --chunk-size 64 \
    --chunk-test-seq-len 256
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--test-chunking-v10` | False | Run chunking tests |
| `--chunk-size` | 64 | Chunk size for tests |
| `--chunk-test-seq-len` | 256 | Sequence length for continuity test |

---

## Common Recipes

### Full scientific comparison
```bash
python train_hard_probes.py \
    --compare-curricula --bind-ratio 0.7 --match-params \
    --rotation-test --num-steps 20000
```

### Real language with all monitoring
```bash
python train_hard_probes.py --real-language --dataset tinystories \
    --probe-layers --enable-srk --enable-kosha --enable-witness \
    --sample-every 500 --checkpoint-dir ./checkpoints
```

### Binding cache with associative recall
```bash
python train_hard_probes.py --binding-cache --associative-recall \
    --ar-num-pairs 16 --binding-slots 32 --ar-dynamic-delay
```

### All benchmarks suite
```bash
python train_hard_probes.py --test-interference --test-moe-ffn --test-hp-quad \
    --test-rlm-phase-quad --test-reflective-phase-quad --test-causal-world-model \
    --test-spatial-causal --test-adaptation --test-chunking-v10
```
