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

## Training

### Quick Start (Synthetic Data)

```bash
# 5 epochs (~2-3 minutes)
python scripts/train_contrastive.py --epochs 5 --synthetic --benchmark

# 10 epochs (better results)
python scripts/train_contrastive.py --epochs 10 --synthetic --benchmark
```

### With Real Datasets

```bash
# Install datasets library
pip install datasets

# Train with GSM8K (math) and WritingPrompts (stories)
python scripts/train_contrastive.py --epochs 10 --huggingface --benchmark
```

### Training Options

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

### Offline Training (No Internet)

```python
# First, save model on machine with internet:
from symbolu.ontological import save_model_for_offline
save_model_for_offline("./models/minilm")

# Then train offline:
python scripts/train_contrastive.py --epochs 10 --synthetic --model-path ./models/minilm
```

## Contrastive Training

The engine uses **triplet contrastive loss** to separate reasoning from creativity:

### Loss Functions

1. **Triplet Loss**: Anchor closer to positive (same domain) than negative (different domain)
   ```
   L = max(0, d(anchor, positive) - d(anchor, negative) + margin)
   ```

2. **Domain Separation Loss**: Maximize distance between domain centroids
   ```
   L = max(0, margin - distance(reasoning_centroid, creativity_centroid))
   ```

3. **Purity Loss**: Encourage sparse activations (one dominant layer)

4. **Orthogonality Loss**: Decorrelate the 10 dimensions

### Datasets

| Dataset | Domain | Description |
|---------|--------|-------------|
| GSM8K | Reasoning | Grade school math problems |
| ROCStories/WritingPrompts | Creativity | Story completion tasks |
| Synthetic | Both | Generated math/story samples |

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

### Basic Usage

```python
from symbolu.ontological import ContrastiveTrainer, ContrastiveConfig

# Create trainer
config = ContrastiveConfig(epochs=10, batch_size=16)
trainer = ContrastiveTrainer(config=config)

# Train
trainer.train(epochs=10, use_synthetic=True)

# Benchmark
results = trainer.benchmark()
print(f"Separation: {results['separation_score']:.2%}")
print(f"Accuracy: {results['overall_accuracy']:.2%}")

# Save model
trainer.save("model_contrastive.pt")
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

## File Structure

```
symbolu/ontological/
├── __init__.py              # Module exports
├── types.py                 # Type definitions (LAYER_NAMES, etc.)
├── encoder.py               # MiniLM/Hash encoders
├── pytorch_engine.py        # PyTorch engine implementation
├── contrastive_trainer.py   # Contrastive training pipeline
├── domain_datasets.py       # GSM8K, ROCStories loaders
└── benchmark_comparison.py  # Encoder benchmarking

scripts/
└── train_contrastive.py     # CLI training script
```

## Next Steps

1. **More epochs**: Try 20-50 epochs for potentially better separation
2. **Larger datasets**: Increase `--samples` to 1000-5000
3. **Hyperparameter tuning**: Adjust learning rate, margins, loss weights
4. **Additional domains**: Add more task types beyond reasoning/creativity
5. **Fine-tuning encoder**: Unfreeze MiniLM layers for end-to-end training

## References

- MiniLM: [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- GSM8K: [openai/gsm8k](https://huggingface.co/datasets/openai/gsm8k)
- WritingPrompts: [euclaise/writingprompts](https://huggingface.co/datasets/euclaise/writingprompts)
