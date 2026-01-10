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
) -> Dict[str, Any]:
    """
    Generate text with Sovereign-gated episodic memory retrieval.

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

    Returns:
        Dictionary with:
        - text: Generated text
        - retrieval_triggered: Whether retrieval was triggered
        - retrieval_reason: Reason for decision
        - retrieved_chunks: List of chunks (if any)
        - state_info: Sovereign state information
        - full_prompt: The actual prompt used
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

When retrieval is triggered, the prompt is augmented as:

```
[CONTEXT START]
Source: WikiText-103 (Chunk 1)
The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars
in Paris, France. It is named after the engineer Gustave Eiffel...

Source: WikiText-103 (Chunk 2)
Paris is the capital and most populous city of France, with an
estimated population of 2,165,423 residents...

Source: WikiText-103 (Chunk 3)
France is a country in Western Europe with several overseas regions
and territories...
[CONTEXT END]

Question: Where is the Eiffel Tower located?
Answer:
```

### Fallback Behavior

If retrieval is **not triggered** or **fails**:
- No context block is injected
- Pure generation proceeds with original prompt
- `retrieval_triggered` is set to `False` in the result

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

## Configuration

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
| 1.0.0 | 2024-01-10 | Initial implementation |

---

## References

- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Sentence-Transformers](https://www.sbert.net/)
- [WikiText-103 Dataset](https://huggingface.co/datasets/wikitext)
- Symbol-U Sovereign State: `symbolu/phase_transformer.py` (lines 74-151)
- SRK Architecture: `symbolu/sovereign/reasoning_kernel.py`
