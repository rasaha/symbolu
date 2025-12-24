# Ontological Engine Training Guide

A comprehensive guide to training and benchmarking the 100D Ontological Engine.

## Overview

The Ontological Engine maps text to a 100-dimensional vector space:
- **10D Ontological Layers** (O1-O10): Core semantic dimensions
- **90D Bhava Sub-layers**: Relational dynamics between layer pairs

### The 10 Ontological Layers

| Layer | Name | Description |
|-------|------|-------------|
| O1 | THINKING | Contemplation, philosophy, reflection |
| O2 | FORMING | Structure, creation, art, creativity |
| O3 | ACTING | Procedures, commands, action |
| O4 | TAGGING | Emotional tagging/classification |
| O5 | DIRECTING | Guidance, instruction, leadership |
| O6 | REASONING | Logic, analysis, problem-solving |
| O7 | PURPOSING | Goals, intention, purposefulness |
| O8 | META_OBSERVING | Meta-awareness, observation |
| O9 | UNIFYING | Integration, synthesis, unity |
| O10 | ABSOLVING | Resolution, completion, transcendence |

## Architecture

```
Text → MiniLM Encoder (384D) → MLP (256→128) → 10D Ontological
                                            ↓
                                    BhavaLayer → 90D Bhava
                                            ↓
                                    Full 100D Vector
                                            ↓
                              ┌─────────────┴─────────────┐
                              ↓                           ↓
                       ReasoningHead              CreativityHead
```

### Key Components

1. **MiniLM Encoder** (384D)
   - Model: `all-MiniLM-L6-v2`
   - 2.5x faster than DistilBERT
   - Semantic text embeddings

2. **OntologicalMLP**
   - Input: 384D encoder output
   - Hidden: 256D → 128D with skip connections
   - Output: 10D ontological vector

3. **BhavaLayer**
   - Derives 90D from 10D ontological
   - 9 pairs × 10 sub-layers each
   - Supervised via consistency loss

4. **Task Heads**
   - ReasoningHead: Focuses on O1, O6, O8
   - CreativityHead: Focuses on O2, O7, O9

## Installation

```bash
# Required
pip install torch sentence-transformers

# Optional (for HuggingFace datasets)
pip install datasets
```

## Training Modes

### 1. Contrastive Training (2 Domains)

Binary classification between reasoning and creativity domains.

```bash
# Quick test with synthetic data
python scripts/train_contrastive.py --epochs 5 --synthetic --benchmark

# Full training with HuggingFace
python scripts/train_contrastive.py --epochs 10 --huggingface --benchmark
```

### 2. Multi-Domain Training (10 Domains) ⭐ NEW

Train all 10 ontological layers with multi-label support.

```bash
# Quick test
python scripts/train_multi_domain.py --epochs 5 --samples 50 --benchmark

# Full training
python scripts/train_multi_domain.py --epochs 20 --samples 200 --benchmark
```

## Training Options

### Contrastive Trainer

| Flag | Description | Default |
|------|-------------|---------|
| `--epochs` | Number of training epochs | 10 |
| `--batch-size` | Batch size | 16 |
| `--lr` | Learning rate | 1e-4 |
| `--synthetic` | Use synthetic data | False |
| `--huggingface` | Use HuggingFace datasets | False |
| `--samples` | Samples per domain | 500 |
| `--device` | Device (auto/cuda/cpu) | auto |
| `--benchmark` | Run benchmark after training | False |
| `--output` | Output model path | model_contrastive.pt |
| `--seed` | Random seed | 42 |
| `--val-split` | Validation split ratio | 0.2 |
| `--patience` | Early stopping patience | 3 |

### Multi-Domain Trainer

| Flag | Description | Default |
|------|-------------|---------|
| `--epochs` | Number of training epochs | 10 |
| `--batch-size` | Batch size | 32 |
| `--lr` | Learning rate | 1e-4 |
| `--samples` | Samples per domain | 100 |
| `--device` | Device (auto/cuda/cpu) | auto |
| `--benchmark` | Run benchmark after training | False |
| `--output` | Output model path | model_multi_domain.pt |
| `--seed` | Random seed | 42 |
| `--val-split` | Validation split ratio | 0.2 |
| `--patience` | Early stopping patience | 5 |
| `--label-smoothing` | Label smoothing | 0.1 |

## Training Features

### Reproducibility

All training is reproducible with random seeds:

```python
from symbolu.ontological import ContrastiveConfig

config = ContrastiveConfig(seed=42)  # Fixed seed
```

### Validation and Early Stopping

- Automatic train/validation split (default 20%)
- Early stopping based on validation performance
- Best model checkpoint saved automatically

```python
config = ContrastiveConfig(
    validation_split=0.2,
    early_stopping_patience=3,
)
```

### Bhava Supervision

The 90D Bhava space is now actively trained via consistency loss:

```python
# Bhava target derived from ontological layer interactions
bhava_loss = MSE(bhava_output, compute_bhava_target(onto_output))
```

## Datasets

### Built-in Datasets

| Dataset | Domain | Description |
|---------|--------|-------------|
| **MathRAGDataset** | Reasoning | Arithmetic, algebra, geometry, logic |
| **CreativeMathDataset** | Creativity | Fractals, golden ratio, math art, stories |
| **MultiDomainDataset** | All 10 | Samples for each ontological layer |

### External Datasets

| Dataset | Domain | Description |
|---------|--------|-------------|
| GSM8K | Reasoning | Grade school math problems |
| ROCStories | Creativity | Story completion tasks |
| WritingPrompts | Creativity | Creative writing prompts |

### Generate Custom Datasets

```python
from symbolu.ontological import (
    MathRAGDataset,
    CreativeMathDataset,
    MultiDomainDataset,
)

# Reasoning math
math = MathRAGDataset.generate(count=1000, seed=42)
math.save("data/math_rag.json")

# Creative math
creative = CreativeMathDataset.generate(count=500, seed=42)
creative.save("data/creative_math.json")

# All 10 domains
multi = MultiDomainDataset.generate(samples_per_domain=100, seed=42)
multi.save("data/multi_domain.json")
```

## Loss Functions

### Contrastive Training

1. **Triplet Loss**: Anchor closer to positive than negative
   ```
   L = max(0, d(anchor, positive) - d(anchor, negative) + margin)
   ```

2. **Domain Separation Loss**: Maximize centroid distance
   ```
   L = max(0, margin - distance(reasoning_centroid, creativity_centroid))
   ```

3. **Purity Loss**: Encourage sparse activations

4. **Orthogonality Loss**: Decorrelate dimensions

### Multi-Domain Training

1. **Soft Cross-Entropy**: Multi-label classification with label smoothing

2. **Bhava Consistency Loss**: Bhava reflects ontological interactions

3. **Purity Loss**: One dominant layer per sample

4. **Orthogonality Loss**: Independent dimensions

## Benchmark Results

### Encoder Comparison (No Training)

| Encoder | Domain Accuracy | Separation | Latency |
|---------|-----------------|------------|---------|
| Hash (384D) | 20% | 50% | 0.21ms |
| MiniLM (384D) | 76% | 67% | 12.70ms |

### Contrastive Training Results

| Configuration | Separation | Accuracy |
|---------------|------------|----------|
| Baseline (MiniLM, no training) | 67% | 76% |
| Synthetic (5 epochs) | 78.84% | 100% |
| Synthetic (10 epochs) | 75-86%* | 100% |
| HuggingFace (10 epochs) | 68.99% | 100% |

*Varies due to random synthetic data generation

### Key Findings

1. **MiniLM >> Hash**: Semantic encoder provides 280% improvement in domain accuracy
2. **Contrastive training works**: Separation improved from 67% to 86%
3. **100% domain accuracy**: Model reliably classifies reasoning vs creativity
4. **Synthetic vs Real**: Synthetic achieves higher separation but real data is more generalizable

## Python API

### Contrastive Training

```python
from symbolu.ontological import ContrastiveTrainer, ContrastiveConfig

config = ContrastiveConfig(
    epochs=10,
    batch_size=16,
    seed=42,
    validation_split=0.2,
    early_stopping_patience=3,
)
trainer = ContrastiveTrainer(config=config)

result = trainer.train(epochs=10, use_synthetic=True)
print(f"Best separation: {result['best_separation']:.2%}")
print(f"Best val separation: {result['best_val_separation']:.2%}")

trainer.save("model_contrastive.pt")
```

### Multi-Domain Training

```python
from symbolu.ontological import MultiDomainTrainer, MultiDomainConfig

config = MultiDomainConfig(
    epochs=10,
    samples_per_domain=100,
    seed=42,
    label_smoothing=0.1,
)
trainer = MultiDomainTrainer(config=config)

result = trainer.train(epochs=10)
print(f"Best accuracy: {result['best_accuracy']:.2%}")

trainer.benchmark()  # Per-domain breakdown
trainer.save("model_multi_domain.pt")
```

### Analyze Text

```python
from symbolu.ontological import PyTorchOntologicalEngine

engine = PyTorchOntologicalEngine()
result = engine.analyze("If A implies B and B implies C, then A implies C")

print(result["dominant_layer"])  # O6_REASONING
print(result["reasoning_score"])  # 0.85
print(result["creativity_score"])  # 0.23
```

### Load Trained Model

```python
import torch
from symbolu.ontological import PyTorchOntologicalEngine

engine = PyTorchOntologicalEngine()
checkpoint = torch.load("model_contrastive.pt")
engine.load_state_dict(checkpoint["engine_state"])
```

## Offline Training (No Internet)

```python
# First, save model on machine with internet:
from symbolu.ontological import save_model_for_offline
save_model_for_offline("./models/minilm")

# Then train offline:
python scripts/train_contrastive.py --epochs 10 --synthetic --model-path ./models/minilm
```

## File Structure

```
symbolu/ontological/
├── __init__.py               # Module exports
├── types.py                  # Type definitions (LAYER_NAMES, etc.)
├── encoder.py                # MiniLM/Hash encoders
├── pytorch_engine.py         # PyTorch engine implementation
├── contrastive_trainer.py    # 2-domain contrastive training
├── multi_domain_trainer.py   # 10-domain multi-label training
├── domain_datasets.py        # GSM8K, ROCStories loaders
├── multi_domain_dataset.py   # 10-domain dataset generator
├── math_rag_dataset.py       # Math reasoning dataset
├── creative_math_dataset.py  # Creative math dataset
└── benchmark_comparison.py   # Encoder benchmarking

scripts/
├── train_contrastive.py      # CLI: 2-domain training
└── train_multi_domain.py     # CLI: 10-domain training
```

## Recommended Training Path

1. **Start with contrastive training** (2 domains)
   ```bash
   python scripts/train_contrastive.py --epochs 10 --synthetic --benchmark
   ```

2. **Expand to multi-domain** (all 10 layers)
   ```bash
   python scripts/train_multi_domain.py --epochs 20 --samples 200 --benchmark
   ```

3. **Fine-tune with real data**
   ```bash
   python scripts/train_contrastive.py --epochs 10 --huggingface --benchmark
   ```

## References

- MiniLM: [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- GSM8K: [openai/gsm8k](https://huggingface.co/datasets/openai/gsm8k)
- WritingPrompts: [euclaise/writingprompts](https://huggingface.co/datasets/euclaise/writingprompts)
