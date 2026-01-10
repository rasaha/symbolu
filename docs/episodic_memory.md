# Episodic Memory Module

## Overview

The Episodic Memory Module implements a **Sovereign-gated Retrieval-Augmented Generation (RAG)** system for Symbol-U. Unlike traditional RAG systems that always retrieve, this module uses the model's **32D Sovereign State** to decide *when* to consult external memory.

**Key Principle:** The Soul (32D State) controls whether the Brain (Memory) is consulted.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SOVEREIGN RAG ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌──────────┐    ┌──────────────────┐    ┌─────────────────────────┐  │
│   │  Prompt  │───▶│  Diagnostic Pass │───▶│  32D Sovereign State    │  │
│   └──────────┘    │  (model.forward)  │    │  [Bhava|Kosha|Vritti]   │  │
│                   └──────────────────┘    └───────────┬─────────────┘  │
│                                                       │                  │
│                                                       ▼                  │
│                                           ┌─────────────────────┐       │
│                                           │     GATE LOGIC      │       │
│                                           │  ─────────────────   │       │
│                                           │  Kosha==INTELLECTUAL │       │
│                                           │  Bhava∈[COG,RSN]     │       │
│                                           │  Vritti==MEMORY      │       │
│                                           │  Vritti==FACT+Hi-Ent │       │
│                                           └──────────┬──────────┘       │
│                                                      │                   │
│                              ┌───────────────────────┴───────────────┐  │
│                              │                                       │  │
│                         ┌────▼────┐                            ┌─────▼─┐│
│                         │RETRIEVE │                            │ SKIP  ││
│                         └────┬────┘                            └───┬───┘│
│                              │                                     │    │
│                   ┌──────────▼──────────┐                          │    │
│                   │  EpisodicMemoryStore │                         │    │
│                   │  (ChromaDB, 384D)    │                         │    │
│                   └──────────┬──────────┘                          │    │
│                              │                                     │    │
│                   ┌──────────▼──────────┐                          │    │
│                   │  Context Injection   │                         │    │
│                   │  [CONTEXT START]...  │                         │    │
│                   └──────────┬──────────┘                          │    │
│                              │                                     │    │
│                              └──────────────────┬──────────────────┘    │
│                                                 │                        │
│                                        ┌────────▼────────┐              │
│                                        │ model.generate() │              │
│                                        └────────┬────────┘              │
│                                                 │                        │
│                                        ┌────────▼────────┐              │
│                                        │    Response      │              │
│                                        └─────────────────┘              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Architecture

The module consists of three components:

| Component | File | Purpose |
|-----------|------|---------|
| **Memory Store** | `symbolu/rag/episodic_store.py` | Persistent vector database (ChromaDB + 384D embeddings) |
| **Offline Indexer** | `scripts/build_memory.py` | Populates memory from WikiText-103 |
| **Sovereign Interface** | `symbolu/inference_rag.py` | Gate logic + generation wrapper |

### Design Principles

1. **Separation of Storage and Reasoning**
   - Storage: 384D semantic embeddings (frozen `all-MiniLM-L6-v2`)
   - Reasoning: 32D Sovereign State (trainable model weights)
   - These are intentionally separate to avoid coupling

2. **Non-Differentiable Memory**
   - The episodic memory is read-only during inference
   - It does NOT participate in the training loop
   - Embeddings come from a frozen external model

3. **State-Gated Retrieval**
   - The model's ontological state determines retrieval
   - Prevents unnecessary database queries
   - Respects the model's "cognitive mode"

---

## Installation

### Dependencies

```bash
# Core dependencies (for EpisodicMemoryStore)
pip install chromadb sentence-transformers

# For offline indexing
pip install datasets tqdm
```

### Verify Installation

```python
# Check if episodic memory is available
from symbolu.rag import _HAS_EPISODIC
print(f"Episodic Memory available: {_HAS_EPISODIC}")
```

---

## Component 1: EpisodicMemoryStore

### Overview

`EpisodicMemoryStore` is a ChromaDB-backed persistent vector store that uses `sentence-transformers` for semantic embeddings.

### Location
```
symbolu/rag/episodic_store.py
```

### Class API

```python
class EpisodicMemoryStore:
    """
    Persistent Vector Database for Episodic Memory.

    Attributes:
        persistence_path: Path to ChromaDB storage directory
        collection_name: Name of the ChromaDB collection
        embedding_model_name: Sentence-transformers model name
    """

    def __init__(
        self,
        persistence_path: str = "./data/episodic_memory",
        collection_name: str = "episodic_memory",
        embedding_model_name: str = "all-MiniLM-L6-v2",
    ):
        """Initialize the memory store."""

    def add_memories(
        self,
        texts: List[str],
        sources: Optional[List[str]] = None,
        metadata: Optional[List[Dict[str, Any]]] = None,
        batch_size: int = 100,
    ) -> int:
        """Add text chunks to the memory store."""

    def query_memory(
        self,
        query_text: str,
        n_results: int = 3,
        min_score: float = 0.0,
    ) -> List[ScoredChunk]:
        """Query for relevant chunks."""

    def count(self) -> int:
        """Return number of chunks in store."""

    def clear(self) -> None:
        """Clear all entries."""

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the store."""
```

### Usage Examples

#### Basic Usage

```python
from symbolu.rag import EpisodicMemoryStore

# Create or load memory store
memory = EpisodicMemoryStore("./data/episodic_memory")

# Add memories
memory.add_memories(
    texts=[
        "The Eiffel Tower is located in Paris, France.",
        "Python was created by Guido van Rossum in 1991.",
        "The speed of light is approximately 299,792 km/s.",
    ],
    sources=["geography", "programming", "physics"],
)

# Query
results = memory.query_memory("Where is the Eiffel Tower?", n_results=3)
for chunk in results:
    print(f"Score: {chunk.score:.3f} | {chunk.text[:50]}...")
```

#### With Metadata

```python
memory.add_memories(
    texts=["Fact 1", "Fact 2"],
    sources=["WikiText-103"],
    metadata=[
        {"article_id": 1, "section": "intro"},
        {"article_id": 1, "section": "body"},
    ],
)
```

#### Persistence

```python
# Memory persists automatically to disk
memory = EpisodicMemoryStore("./data/my_memory")
memory.add_memories(["fact 1", "fact 2"])
print(f"Stored: {memory.count()} chunks")

# Later session - data is still there
memory2 = EpisodicMemoryStore("./data/my_memory")
print(f"Loaded: {memory2.count()} chunks")  # Same count
```

---

## Component 2: Offline Indexer

### Overview

The `build_memory.py` script populates the episodic memory from WikiText-103. It runs **separately from training** and does not touch the GPU training loop.

### Location
```
scripts/build_memory.py
```

### Command-Line Interface

```bash
# Quick test with validation split (~4k documents)
python scripts/build_memory.py --split validation

# Full build with train split (limited to 50k documents)
python scripts/build_memory.py --split train --limit 50000

# Custom settings
python scripts/build_memory.py \
    --output ./data/my_memory \
    --split train \
    --limit 100000 \
    --chunk-size 500 \
    --chunk-overlap 50 \
    --batch-size 200
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--output`, `-o` | `./data/episodic_memory` | ChromaDB persistence path |
| `--split`, `-s` | `validation` | WikiText-103 split: `train`, `validation`, `test` |
| `--limit`, `-l` | None (all) | Max source documents to process |
| `--chunk-size` | 500 | Chunk size in tokens |
| `--chunk-overlap` | 50 | Overlap between chunks |
| `--batch-size` | 100 | Batch size for embedding/insertion |

### Chunking Strategy

The indexer uses the **sentence-transformers tokenizer** for chunking:

```python
class TextChunker:
    """
    Chunks text to fit embedding model's window (~512 tokens).

    - Uses the same tokenizer as the embedding model
    - Prevents truncation artifacts
    - Overlapping chunks for context continuity
    """
```

### Example Output

```
$ python scripts/build_memory.py --split validation --limit 1000

2024-01-10 10:30:00 [INFO] Loading WikiText-103 (validation split)...
2024-01-10 10:30:02 [INFO] Limited to 1000 examples
2024-01-10 10:30:02 [INFO] Loading tokenizer from all-MiniLM-L6-v2...
Chunking: 100%|████████████████████| 1000/1000 [00:05<00:00]
2024-01-10 10:30:07 [INFO] Created 2847 chunks from 1000 documents
2024-01-10 10:30:07 [INFO] Initializing EpisodicMemoryStore...
Indexing: 100%|████████████████████| 29/29 [00:45<00:00]
2024-01-10 10:30:52 [INFO] Successfully indexed 2847 chunks
```

---

## Component 3: Sovereign Interface

### Overview

The `generate_with_memory()` function wraps the model and implements **state-gated retrieval**. It uses the 32D Sovereign State to decide when to consult memory.

### Location
```
symbolu/inference_rag.py
```

### The 32D Sovereign State

The model outputs a 32D state vector structured as:

```
Index Range    Component       Description
─────────────────────────────────────────────────────
[0:12]         Bhavas          12 ontological aspects (softmax)
[12:17]        Koshas          5 consciousness layers (softmax)
[17:22]        Vrittis         5 mental states (softmax)
[22:28]        Gunas           6 system dynamics (sigmoid)
[28:32]        Reserved        4 void/toroidal channels (tanh)
```

#### Relevant Indices for Gate Logic

| Component | Name | Index (in subspace) | Global Index |
|-----------|------|---------------------|--------------|
| Bhava | COG (Cognition) | 4 | 4 |
| Bhava | RSN (Reason) | 6 | 6 |
| Kosha | INTELLECTUAL | 3 | 15 |
| Vritti | FACT | 0 | 17 |
| Vritti | MEMORY | 4 | 21 |

### Gate Logic

Retrieval is triggered if **ANY** of these conditions are met:

```python
# Condition 1: Abstract reasoning mode
Kosha.argmax() == INTELLECTUAL

# Condition 2: Knowledge-seeking mode
Bhava.argmax() in [COG, RSN]

# Condition 3: Memory recall mode
Vritti.argmax() == MEMORY

# Condition 4: Uncertain fact mode
Vritti.argmax() == FACT AND Entropy > 4.5
```

#### Gate Logic Explanation

| Condition | Interpretation | Example Prompt |
|-----------|----------------|----------------|
| `Kosha=INTELLECTUAL` | Model is in abstract/logical reasoning | "What is the formula for..." |
| `Bhava=COG` | Model is seeking knowledge | "Tell me about..." |
| `Bhava=RSN` | Model is reasoning logically | "Why does X cause Y?" |
| `Vritti=MEMORY` | Model is in recall mode | "What did we discuss about..." |
| `Vritti=FACT + High Entropy` | Model knows it needs a fact but is uncertain | "The capital of Liechtenstein is..." |

### Function API

```python
def generate_with_memory(
    model: torch.nn.Module,
    tokenizer,
    memory_store: EpisodicMemoryStore,
    prompt: str,
    max_new_tokens: int = 100,
    temperature: float = 1.0,
    top_k: int = 50,
    n_retrieval_results: int = 3,
    min_retrieval_score: float = 0.0,
    force_retrieval: Optional[bool] = None,
    device: Optional[torch.device] = None,
    max_context_length: Optional[int] = None,  # NEW: Override model's max length
) -> Dict[str, Any]:
    """
    Generate text with Sovereign-gated episodic memory retrieval.

    Safety mechanisms:
    - Context truncation respects model's max_position_embeddings
    - Natural format for non-instruct models
    - Graceful fallback on any errors

    Args:
        model: OntologicalHybridTransformer model
        tokenizer: Tokenizer for encoding/decoding
        memory_store: EpisodicMemoryStore instance
        prompt: User's input prompt
        max_new_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        top_k: Top-k sampling parameter
        n_retrieval_results: Number of chunks to retrieve
        min_retrieval_score: Minimum similarity score for retrieval
        force_retrieval: Override gate logic (True=always, False=never)
        device: Device for computation
        max_context_length: Override model's max context length

    Returns:
        Dictionary with:
        - text: Generated text
        - retrieval_triggered: Whether retrieval was triggered
        - retrieval_reason: Reason for decision
        - retrieved_chunks: List of chunks (if any)
        - state_info: Sovereign state information (or None if failed)
        - full_prompt: The actual prompt used
        - truncated: Whether context was truncated
        - prompt_tokens: Final prompt token count
    """
```

### Usage Examples

#### Basic Generation

```python
from symbolu.inference_rag import generate_with_memory
from symbolu.rag import EpisodicMemoryStore

# Load your model and tokenizer
model = ...  # OntologicalHybridTransformer
tokenizer = ...

# Load memory
memory = EpisodicMemoryStore("./data/episodic_memory")

# Generate with memory-gated retrieval
result = generate_with_memory(
    model=model,
    tokenizer=tokenizer,
    memory_store=memory,
    prompt="What is the speed of light?",
)

print(f"Response: {result['text']}")
print(f"Retrieval: {result['retrieval_triggered']}")
print(f"Reason: {result['retrieval_reason']}")
```

#### Inspecting State

```python
from symbolu.inference_rag import get_state_description

result = generate_with_memory(model, tokenizer, memory, "Tell me about Python")

# Human-readable state
description = get_state_description(result['state_info'])
print(description)
# Output: "Bhava: COG | Kosha: INTELLECTUAL | Vritti: MEMORY | Entropy: 3.45"
```

#### Force Retrieval (for testing)

```python
# Always retrieve (bypass gate)
result = generate_with_memory(
    model, tokenizer, memory, prompt,
    force_retrieval=True,
)

# Never retrieve (bypass gate)
result = generate_with_memory(
    model, tokenizer, memory, prompt,
    force_retrieval=False,
)
```

#### Batch Generation

```python
from symbolu.inference_rag import generate_batch_with_memory

prompts = [
    "What is the capital of France?",
    "How does photosynthesis work?",
    "Write a poem about the ocean.",
]

results = generate_batch_with_memory(
    model, tokenizer, memory, prompts,
    max_new_tokens=50,
)

for prompt, result in zip(prompts, results):
    print(f"Q: {prompt}")
    print(f"A: {result['text']}")
    print(f"Retrieved: {result['retrieval_triggered']}")
    print()
```

### Context Injection Format

When retrieval is triggered, the prompt is augmented using a **natural instruction format** (better for non-instruct models):

```
Information:
The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars
in Paris, France. It is named after the engineer Gustave Eiffel...

Paris is the capital and most populous city of France, with an
estimated population of 2,165,423 residents...

France is a country in Western Europe with several overseas regions
and territories...

Based on the information above, answer the question.
Question: Where is the Eiffel Tower located?
Answer:
```

> **Note:** We use natural language format instead of special tokens like `[CONTEXT START]` because non-instruct models haven't seen these tokens during training and may get confused.

### Context Truncation (Safety Mechanism)

The system automatically truncates context to fit within the model's context window:

```python
# Available space calculation:
available_tokens = (
    model.config.max_position_embeddings  # e.g., 2048
    - prompt_template_tokens              # Template overhead
    - max_new_tokens                      # Reserved for generation
    - 50                                  # Safety buffer
)

# Chunks are added until space runs out
# Partial chunks are truncated with "..." if meaningful space remains
```

**Result includes truncation info:**
```python
result = generate_with_memory(...)
print(f"Truncated: {result['truncated']}")      # True if chunks were cut
print(f"Prompt tokens: {result['prompt_tokens']}")  # Final prompt size
```

### Fallback Behavior

If retrieval is **not triggered** or **fails**:
- No context block is injected
- Pure generation proceeds with original prompt
- `retrieval_triggered` is set to `False` in the result
- Errors are logged but don't crash the system

---

## Integration with Training

### Important: Do NOT Modify Training Loop

The Episodic Memory is **non-differentiable** and **read-only**:

```python
# ❌ WRONG - Do not do this
loss = model_loss + memory_retrieval_loss  # Memory has no gradients!

# ✅ CORRECT - Memory is inference-only
# Training: train_unified_llm.py (unchanged)
# Inference: generate_with_memory() (uses memory)
```

### Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                        TRAINING PHASE                            │
│  (train_unified_llm.py - NO memory involvement)                 │
│                                                                  │
│  WikiText-103 ──▶ Model ──▶ Loss ──▶ Backprop ──▶ Update       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ (Model saved)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MEMORY BUILD PHASE                           │
│  (scripts/build_memory.py - ONE TIME, offline)                  │
│                                                                  │
│  WikiText-103 ──▶ Chunker ──▶ MiniLM (384D) ──▶ ChromaDB       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ (Memory saved)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      INFERENCE PHASE                             │
│  (generate_with_memory - uses BOTH model and memory)            │
│                                                                  │
│  Prompt ──▶ Model(32D State) ──▶ Gate ──▶ Memory? ──▶ Generate │
└─────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Usage Guide

This section provides a complete walkthrough from training to inference with episodic memory.

### Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           COMPLETE PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌───────────┐ │
│  │   STEP 1    │     │   STEP 2    │     │   STEP 3    │     │  STEP 4   │ │
│  │   Train     │────▶│   Build     │────▶│   Load      │────▶│ Generate  │ │
│  │   Model     │     │   Memory    │     │   Both      │     │ with RAG  │ │
│  └─────────────┘     └─────────────┘     └─────────────┘     └───────────┘ │
│        │                   │                   │                   │        │
│        ▼                   ▼                   ▼                   ▼        │
│   GPU Training        CPU Indexing        Load Model         32D Gate      │
│   WikiText-103        WikiText-103        + Memory           Decision      │
│   32D Weights         384D Embeddings     to Device          + Retrieval   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Step 1: Train the 32D Ontological Hybrid Model

**Script:** `train_unified_llm.py`

```bash
# Train the Sovereign Model (32D state space)
python train_unified_llm.py \
    --model_type ontological_hybrid \
    --model_size small \
    --enable_srk \
    --state_dim 32 \
    --dataset wikitext \
    --epochs 10 \
    --batch_size 8 \
    --output_dir ./checkpoints/sovereign_v1
```

**Output:**
```
./checkpoints/sovereign_v1/
  ├── model.pt              # Model weights
  ├── tokenizer/            # Tokenizer files
  ├── config.json           # Model configuration
  └── training_log.json     # Training metrics
```

**What happens:**
- Model learns language patterns from WikiText-103
- 32D Sovereign State (Bhava/Kosha/Vritti/Guna) is trained
- **No episodic memory involved** - pure weight-based learning

---

### Step 2: Build the Episodic Memory (Offline, One-Time)

**Script:** `scripts/build_memory.py`

```bash
# AFTER training is complete, build the memory index
# This runs on CPU, separate from training

# Option A: Quick test with validation split (~5 min)
python scripts/build_memory.py \
    --split validation \
    --output ./data/episodic_memory

# Option B: Full corpus with train split (~30-60 min)
python scripts/build_memory.py \
    --split train \
    --limit 100000 \
    --output ./data/episodic_memory \
    --chunk-size 500 \
    --chunk-overlap 50
```

**Output:**
```
./data/episodic_memory/
  ├── chroma.sqlite3        # ChromaDB database
  └── [embedding files]     # 384D vectors
```

**What happens:**
- Loads WikiText-103 from HuggingFace
- Chunks text using sentence-transformers tokenizer
- Embeds chunks with `all-MiniLM-L6-v2` (384D)
- Stores in ChromaDB (persistent)
- **Completely separate from model weights**

> **Note:** You only run this ONCE. The memory persists to disk.

---

### Step 3: Load Model + Memory for Inference

Create an inference script or use interactively:

```python
#!/usr/bin/env python3
"""
Inference script with Episodic Memory integration.
Run AFTER training (Step 1) and memory building (Step 2).
"""

import torch
import json
from pathlib import Path

# === Configuration ===
CHECKPOINT_DIR = "./checkpoints/sovereign_v1"
MEMORY_PATH = "./data/episodic_memory"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# === Step 3a: Load the trained Sovereign Model ===
from symbolu.phase_transformer import OntologicalHybridTransformer
from transformers import AutoTokenizer  # or your custom tokenizer

def load_model_and_tokenizer(checkpoint_dir: str, device: str):
    """Load the trained Sovereign Model."""

    # Load config
    with open(f"{checkpoint_dir}/config.json") as f:
        config = json.load(f)

    # Initialize model
    model = OntologicalHybridTransformer(
        vocab_size=config.get("vocab_size", 50257),
        embed_dim=config.get("embed_dim", 768),
        num_layers=config.get("num_layers", 12),
        num_heads=config.get("num_heads", 12),
        max_seq_len=config.get("max_seq_len", 2048),
        state_dim=32,  # 32D Sovereign State
    )

    # Load weights
    state_dict = torch.load(f"{checkpoint_dir}/model.pt", map_location=device)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(f"{checkpoint_dir}/tokenizer")

    print(f"✓ Model loaded: {sum(p.numel() for p in model.parameters()):,} parameters")
    return model, tokenizer

# === Step 3b: Load the Episodic Memory ===
from symbolu.rag import EpisodicMemoryStore

def load_memory(memory_path: str):
    """Load the pre-built episodic memory."""
    memory = EpisodicMemoryStore(persistence_path=memory_path)
    print(f"✓ Memory loaded: {memory.count():,} chunks")
    return memory

# === Initialize everything ===
model, tokenizer = load_model_and_tokenizer(CHECKPOINT_DIR, DEVICE)
memory = load_memory(MEMORY_PATH)

print(f"\n✓ Ready for inference with Episodic Memory on {DEVICE}!")
```

---

### Step 4: Generate with Sovereign-Gated RAG

```python
# Continue from Step 3...

from symbolu.inference_rag import generate_with_memory, get_state_description

def run_inference(prompt: str):
    """Run inference with automatic memory gating."""

    result = generate_with_memory(
        model=model,
        tokenizer=tokenizer,
        memory_store=memory,
        prompt=prompt,
        max_new_tokens=100,
        temperature=0.7,
        top_k=50,
        n_retrieval_results=3,
    )

    # Display results
    print(f"\n{'='*60}")
    print(f"PROMPT: {prompt}")
    print(f"{'='*60}")

    # Show Sovereign State
    if result['state_info']:
        print(f"STATE: {get_state_description(result['state_info'])}")

    # Show retrieval decision
    print(f"RETRIEVAL: {result['retrieval_triggered']} ({result['retrieval_reason']})")

    if result['retrieved_chunks']:
        print(f"CHUNKS: {len(result['retrieved_chunks'])} retrieved")
        for i, chunk in enumerate(result['retrieved_chunks'], 1):
            print(f"  [{i}] Score={chunk['score']:.3f}: {chunk['text'][:80]}...")

    if result['truncated']:
        print(f"TRUNCATED: Yes (prompt={result['prompt_tokens']} tokens)")

    print(f"\nRESPONSE: {result['text']}")
    print(f"{'='*60}\n")

    return result


# === Example Usage ===
if __name__ == "__main__":

    # This should trigger retrieval (Bhava=COG or Kosha=INTELLECTUAL)
    run_inference("What is the capital of France?")

    # This might NOT trigger retrieval (Kosha=VITAL, creative mode)
    run_inference("Write a poem about the ocean.")

    # This should trigger retrieval (factual question)
    run_inference("Who invented the telephone?")

    # Interactive mode
    print("\n--- Interactive Mode ---")
    while True:
        prompt = input("\nEnter prompt (or 'quit'): ").strip()
        if prompt.lower() == 'quit':
            break
        run_inference(prompt)
```

---

### What Happens at Inference Time (Detailed Flow)

```
User Prompt: "What year was the Eiffel Tower built?"
                           │
                           ▼
            ┌──────────────────────────────┐
            │  1. DIAGNOSTIC PASS          │
            │     model.forward(prompt)    │
            │     Extract 32D State        │
            └──────────────┬───────────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │  2. STATE EXTRACTION         │
            │  Bhava[0:12]  → argmax = COG │ ← Knowledge-seeking
            │  Kosha[12:17] → argmax = INT │ ← Intellectual mode
            │  Vritti[17:22]→ argmax = MEM │ ← Memory recall
            │  Entropy = 5.2               │ ← High uncertainty
            └──────────────┬───────────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │  3. GATE DECISION            │
            │  IF Kosha=INTELLECTUAL  ✓    │
            │  OR Bhava∈[COG,RSN]    ✓    │
            │  OR Vritti=MEMORY      ?    │
            │  OR (FACT+HighEntropy) ?    │
            │  ───────────────────────    │
            │  RESULT: RETRIEVE = TRUE    │
            └──────────────┬───────────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │  4. MEMORY RETRIEVAL         │
            │  Query: "Eiffel Tower built" │
            │  ───────────────────────     │
            │  Chunk 1 (0.89): "The Eiffel │
            │    Tower was completed in    │
            │    1889 for the World's..."  │
            │  Chunk 2 (0.76): "Gustave    │
            │    Eiffel designed..."       │
            └──────────────┬───────────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │  5. CONTEXT TRUNCATION       │
            │  Max context: 2048 tokens    │
            │  Available: 1500 tokens      │
            │  Chunk 1: 450 tokens ✓       │
            │  Chunk 2: 380 tokens ✓       │
            │  Total: 830 tokens (fits)    │
            └──────────────┬───────────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │  6. PROMPT AUGMENTATION      │
            │  ─────────────────────────   │
            │  Information:                │
            │  [Chunk 1 text]              │
            │  [Chunk 2 text]              │
            │                              │
            │  Based on the information... │
            │  Question: What year was...  │
            │  Answer:                     │
            └──────────────┬───────────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │  7. GENERATION               │
            │  model.generate(augmented)   │
            │  ─────────────────────────   │
            │  Output: "The Eiffel Tower   │
            │  was built in 1889."         │
            └──────────────────────────────┘
```

---

### When to Run Each Step

| Step | When to Run | Duration | Resource | Output |
|------|-------------|----------|----------|--------|
| **1. Train Model** | Once (or when retraining) | Hours to days | GPU intensive | Model weights (32D) |
| **2. Build Memory** | Once (after training) | 5-60 minutes | CPU only | ChromaDB (384D) |
| **3. Load Both** | Every inference session | 10-30 seconds | GPU + disk | Model + memory in RAM |
| **4. Generate** | Per prompt | 1-5 seconds | GPU | Generated text |

---

### Quick Reference Commands

```bash
# Step 1: Train (GPU, hours)
python train_unified_llm.py \
    --model_type ontological_hybrid \
    --model_size small \
    --enable_srk \
    --state_dim 32

# Step 2: Build Memory (CPU, minutes) - RUN ONCE
python scripts/build_memory.py \
    --split validation \
    --output ./data/episodic_memory

# Step 3 & 4: Inference (GPU, seconds per prompt)
python scripts/inference_with_memory.py
# Or use interactively in Python
```

---

### Complete Inference Script

Save this as `scripts/inference_with_memory.py`:

```python
#!/usr/bin/env python3
"""
Complete inference script with Episodic Memory.

Usage:
    python scripts/inference_with_memory.py --checkpoint ./checkpoints/sovereign_v1
    python scripts/inference_with_memory.py --interactive
"""

import argparse
import json
import torch
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Inference with Episodic Memory")
    parser.add_argument("--checkpoint", type=str, default="./checkpoints/sovereign_v1")
    parser.add_argument("--memory", type=str, default="./data/episodic_memory")
    parser.add_argument("--prompt", type=str, default=None)
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=100)
    parser.add_argument("--temperature", type=float, default=0.7)
    args = parser.parse_args()

    # Determine device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    # Load model
    from symbolu.phase_transformer import OntologicalHybridTransformer
    from transformers import AutoTokenizer

    with open(f"{args.checkpoint}/config.json") as f:
        config = json.load(f)

    model = OntologicalHybridTransformer(
        vocab_size=config.get("vocab_size", 50257),
        embed_dim=config.get("embed_dim", 768),
        num_layers=config.get("num_layers", 12),
        num_heads=config.get("num_heads", 12),
        max_seq_len=config.get("max_seq_len", 2048),
        state_dim=32,
    )
    model.load_state_dict(torch.load(f"{args.checkpoint}/model.pt", map_location=device))
    model.to(device)
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(f"{args.checkpoint}/tokenizer")
    print(f"✓ Model loaded")

    # Load memory
    from symbolu.rag import EpisodicMemoryStore
    memory = EpisodicMemoryStore(persistence_path=args.memory)
    print(f"✓ Memory loaded: {memory.count()} chunks")

    # Import generation function
    from symbolu.inference_rag import generate_with_memory, get_state_description

    def generate(prompt: str):
        result = generate_with_memory(
            model=model,
            tokenizer=tokenizer,
            memory_store=memory,
            prompt=prompt,
            max_new_tokens=args.max_tokens,
            temperature=args.temperature,
        )

        print(f"\n{'─'*50}")
        if result['state_info']:
            print(f"State: {get_state_description(result['state_info'])}")
        print(f"Retrieval: {result['retrieval_triggered']} ({result['retrieval_reason']})")
        if result['truncated']:
            print(f"Truncated: Yes ({result['prompt_tokens']} tokens)")
        print(f"{'─'*50}")
        print(f"Response: {result['text']}")
        return result

    # Run
    if args.prompt:
        generate(args.prompt)
    elif args.interactive:
        print("\n=== Interactive Mode (type 'quit' to exit) ===")
        while True:
            prompt = input("\nPrompt: ").strip()
            if prompt.lower() == 'quit':
                break
            if prompt:
                generate(prompt)
    else:
        # Demo prompts
        demos = [
            "What is the capital of France?",
            "Write a haiku about mountains.",
            "Who discovered penicillin?",
        ]
        for prompt in demos:
            print(f"\n>>> {prompt}")
            generate(prompt)

if __name__ == "__main__":
    main()
```

---

### Environment Variables

```bash
# ChromaDB settings (optional)
export CHROMA_PERSIST_DIRECTORY="./data/episodic_memory"

# Sentence-transformers cache (optional)
export SENTENCE_TRANSFORMERS_HOME="./models/sentence-transformers"
```

### Custom Embedding Model

```python
# Use a different embedding model
memory = EpisodicMemoryStore(
    persistence_path="./data/episodic_memory",
    embedding_model_name="all-mpnet-base-v2",  # 768D instead of 384D
)
```

### Tuning Gate Thresholds

The entropy threshold can be adjusted in `symbolu/inference_rag.py`:

```python
# Default: 4.5 (typical for vocab size ~50k)
ENTROPY_THRESHOLD = 4.5

# Lower = more sensitive (retrieve more often)
ENTROPY_THRESHOLD = 3.5

# Higher = less sensitive (retrieve less often)
ENTROPY_THRESHOLD = 5.5
```

---

## Troubleshooting

### Common Issues

#### 1. `ImportError: chromadb not found`

```bash
pip install chromadb
```

#### 2. `ImportError: sentence-transformers not found`

```bash
pip install sentence-transformers
```

#### 3. Memory returns no results

```python
# Check if memory is populated
memory = EpisodicMemoryStore("./data/episodic_memory")
print(f"Chunk count: {memory.count()}")

# If 0, run the indexer
# python scripts/build_memory.py --split validation
```

#### 4. Retrieval never triggers

```python
# Check state values
result = generate_with_memory(model, tokenizer, memory, prompt)
print(result['state_info'])

# Force retrieval to test
result = generate_with_memory(
    model, tokenizer, memory, prompt,
    force_retrieval=True,
)
```

#### 5. Slow embedding on first use

The sentence-transformers model is downloaded on first use (~90MB). Subsequent uses are cached.

```python
# Pre-download the model
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")
```

---

## API Reference Summary

### symbolu.rag

```python
from symbolu.rag import (
    # Episodic Memory
    EpisodicMemoryStore,
    create_episodic_memory,

    # Legacy RAG (hash-based)
    index_corpus,
    run_rag,

    # Types
    ScoredChunk,
    CandidateEntry,
)
```

### symbolu.inference_rag

```python
from symbolu.inference_rag import (
    # Main function
    generate_with_memory,
    generate_batch_with_memory,

    # State utilities
    extract_sovereign_state,
    should_retrieve,
    get_state_description,

    # Context formatting
    format_context,

    # Types
    SovereignStateInfo,
)
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1.0 | 2024-01-10 | Added safety mechanisms: context truncation, natural format, error handling |
| 1.0.0 | 2024-01-10 | Initial implementation |

---

## References

- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Sentence-Transformers](https://www.sbert.net/)
- [WikiText-103 Dataset](https://huggingface.co/datasets/wikitext)
- Symbol-U Sovereign State: `symbolu/phase_transformer.py` (lines 74-151)
- SRK Architecture: `symbolu/sovereign/reasoning_kernel.py`
